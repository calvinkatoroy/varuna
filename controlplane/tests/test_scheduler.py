"""Scheduler (step 2): starts due scans, waits for an offline agent, suspends after 15 min, expires, locks."""
import datetime as dt
import os
import sys
import threading

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
import auth  # noqa: E402
import db  # noqa: E402
import models  # noqa: E402
import redis_store  # noqa: E402
import scheduler  # noqa: E402
import tokens  # noqa: E402
import workflow  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402
from conftest import make_client, start_task, window  # noqa: E402

UTC = dt.UTC


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    redis_store._client = FakeRedis()
    auth.create_account("rizky", "Passw0rd!x", "pentester")
    sent = []
    monkeypatch.setattr(scheduler.notify, "notify", sent.append)
    return sent


def _scheduled(at_min=-1, start_min=-10, minutes=480):
    org = (db.get_account("alice") or {}).get("org_id") or make_client("alice", "PT A")
    nb, na = window(start_min, minutes)
    at = (dt.datetime.now(UTC) + dt.timedelta(minutes=at_min)).replace(microsecond=0).isoformat()
    return db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8", "scan_mode": "cloud",
                               "not_before": nb, "not_after": na, "stage": "scan", "scan_state": "scheduled",
                               "assignee": "rizky", "scheduled_at": at, "max_minutes": 60, "target_class": "cloud"})


def _get(tid):
    return db.get_proposal(tid, org_id=None)


def test_due_scan_starts_when_the_scanner_is_online():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _scheduled()
    assert scheduler.tick(dt.datetime.now(UTC))["started"] == 1
    t = _get(tid)
    assert t["scan_state"] == "in_progress" and redis_store.dequeue_job(models.CLOUD_AGENT) == t["job_id"]
    assert db.list_task_events(tid)[-1]["actor"] == workflow.SCHEDULER


def test_not_yet_due_is_left_alone():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _scheduled(at_min=30)
    assert scheduler.tick(dt.datetime.now(UTC))["started"] == 0 and _get(tid)["scan_state"] == "scheduled"


def test_offline_waits_then_suspends_after_15_minutes(_env):
    tid = _scheduled()
    now = dt.datetime.now(UTC)
    assert scheduler.tick(now)["waiting"] == 1
    first = _get(tid)["due_since"]
    assert first and _get(tid)["scan_state"] == "scheduled"
    scheduler.tick(now + dt.timedelta(minutes=14))
    assert _get(tid)["due_since"] == first and _get(tid)["scan_state"] == "scheduled"   # first miss is kept
    assert scheduler.tick(now + dt.timedelta(minutes=15))["suspended"] == 1
    t = _get(tid)
    assert t["scan_state"] == "suspended" and t["suspend_reason"] == "agent offline"
    assert any("rizky" in m and "agent offline" in m for m in _env)
    assert scheduler.tick(now + dt.timedelta(minutes=30))["started"] == 0           # never retried silently


def test_unresolvable_target_suspends_with_its_own_reason(monkeypatch):
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _scheduled()
    monkeypatch.setattr(workflow.classifier, "classify", lambda t, **k: (_ for _ in ()).throw(
        workflow.classifier.ClassifyRejected("cannot resolve")))
    now = dt.datetime.now(UTC)
    scheduler.tick(now)
    scheduler.tick(now + dt.timedelta(minutes=16))
    assert _get(tid)["suspend_reason"] == "target unreachable"


def test_window_passed_expires_waiting_work():
    org = make_client("alice", "PT A")
    nb, na = window(-120, 60)
    waiting = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8",
                                  "not_before": nb, "not_after": na})
    pending = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8", "stage": "scan",
                                  "scan_state": "pending", "assignee": "rizky", "not_before": nb, "not_after": na})
    late = _scheduled(at_min=-30, start_min=-120, minutes=60)
    assert scheduler.tick(dt.datetime.now(UTC))["expired"] == 3
    assert {_get(t)["stage"] for t in (waiting, pending, late)} == {"expired"}


def test_running_scan_past_the_window_or_duration_is_suspended_not_killed():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _scheduled()
    now = dt.datetime.now(UTC)
    scheduler.tick(now)
    job_id = _get(tid)["job_id"]
    scheduler.tick(now + dt.timedelta(minutes=61))                       # max_minutes = 60
    t = _get(tid)
    assert t["scan_state"] == "suspended" and t["suspend_reason"] == "maximum scan duration reached"
    assert redis_store.is_suspended(job_id) and redis_store.get_job(job_id)["status"] == "queued"
    tid2 = _scheduled(start_min=-10, minutes=20)
    scheduler.tick(now)
    scheduler.tick(now + dt.timedelta(minutes=11))
    assert _get(tid2)["suspend_reason"] == "client window ended"


def test_double_tick_starts_the_scan_once():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _scheduled()
    now = dt.datetime.now(UTC)
    barrier, results = threading.Barrier(2), []

    def go():
        barrier.wait()
        results.append(scheduler.tick(now)["started"])
    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [0, 1]
    assert len(redis_store.list_org_jobs(_get(tid)["org_id"])) == 1


def test_lock_keeps_a_second_runner_out(monkeypatch):
    r = redis_store.get_redis()
    assert scheduler._acquire(r, "a") and not scheduler._acquire(r, "b") and scheduler._acquire(r, "a")
    calls = []
    monkeypatch.setattr(scheduler, "tick", lambda now: calls.append(now))
    stop = threading.Event()
    stop.set()                                    # run() always does one pass, then sees the stop flag
    scheduler.run(stop, interval=0)               # its own random token: lock held by "a"
    assert calls == []
    r.delete(scheduler.LOCK_KEY)
    scheduler.run(stop, interval=0)
    assert len(calls) == 1


def test_running_scan_failure_is_suspended_with_the_reason():
    org = make_client("alice", "PT A")
    nb, na = window()
    tid = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8", "scan_mode": "cloud",
                              "not_before": nb, "not_after": na})
    job_id = start_task(tid)
    workflow.transition(tid, "scan/suspended", workflow.SYSTEM, org_id=None, comment="nuclei crashed")
    assert _get(tid)["suspend_reason"] == "nuclei crashed" and redis_store.is_suspended(job_id)


def test_malformed_row_does_not_starve_the_others():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    bad = _scheduled()
    db.update_proposal(bad, not_after="garbage")
    good = _scheduled()
    assert scheduler.tick(dt.datetime.now(UTC))["started"] == 1
    assert _get(good)["scan_state"] == "in_progress" and _get(bad)["scan_state"] == "scheduled"
    org = _get(good)["org_id"]
    waiting = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8",
                                  "not_before": "x", "not_after": "2020-01-01T00:00:00"})
    old = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8",
                              "not_before": window(-120, 60)[0], "not_after": window(-120, 60)[1]})
    assert scheduler.tick(dt.datetime.now(UTC))["expired"] == 1
    assert _get(old)["stage"] == "expired" and _get(waiting)["stage"] == "task"


def test_malformed_running_row_does_not_stop_the_duration_check():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    a, b = _scheduled(), _scheduled()
    now = dt.datetime.now(UTC)
    scheduler.tick(now)
    db.update_proposal(a, scheduled_at="garbage")
    db.update_proposal(b, not_after="garbage")
    c = _scheduled()
    scheduler.tick(now)
    out = scheduler.tick(now + dt.timedelta(minutes=61))
    assert out["suspended"] == 1 and _get(c)["scan_state"] == "suspended"


def test_start_side_effect_failure_is_contained(monkeypatch):
    tokens.issue_agent_token(models.CLOUD_AGENT)
    a, b = _scheduled(), _scheduled()
    real = workflow.dispatch.dispatch_job
    calls = []

    def boom(job, **k):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("redis down")
        return real(job, **k)
    monkeypatch.setattr(workflow.dispatch, "dispatch_job", boom)
    out = scheduler.tick(dt.datetime.now(UTC))
    assert out["started"] == 1 and out["suspended"] == 1
    states = {_get(a)["scan_state"], _get(b)["scan_state"]}
    assert states == {"in_progress", "suspended"}
    sus = next(t for t in (_get(a), _get(b)) if t["scan_state"] == "suspended")
    assert sus["suspend_reason"] == "could not dispatch the scan"


def test_reasons_are_accurate():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _scheduled(at_min=-1, start_min=-10)
    nb = (dt.datetime.now(UTC) + dt.timedelta(minutes=30)).isoformat()
    db.update_proposal(tid, not_before=nb)
    now = dt.datetime.now(UTC)
    scheduler.tick(now)
    scheduler.tick(now + dt.timedelta(minutes=16))
    assert "has not started" in _get(tid)["suspend_reason"]


def test_expiry_is_checked_before_the_scheduled_time():
    tid = _scheduled(at_min=600, start_min=-10, minutes=60)   # scheduled_at after not_after
    assert scheduler.tick(dt.datetime.now(UTC) + dt.timedelta(minutes=70))["expired"] == 1
    assert _get(tid)["stage"] == "expired"


# --- a crash during delivery must not strand the task in `delivering` ---
def _delivering(with_report=None):
    tid = _scheduled()
    db.get_conn().execute("UPDATE proposals SET stage='delivering', scan_state=NULL, job_id='jd', assignee='rizky' WHERE id=?", (tid,))
    db.get_conn().commit()
    if with_report:
        rid = db.create_report("jd", db.get_proposal(tid, org_id=None)["org_id"], "alice", task_id=tid)
        db.set_report(rid, stage=with_report)
    return tid


def test_stuck_delivering_with_a_delivered_report_is_finished():
    tid = _delivering(with_report="delivered")
    out = scheduler.tick(dt.datetime.now(UTC) + dt.timedelta(minutes=11))
    assert _get(tid)["stage"] == "delivered" and out["recovered"] == 1
    assert db.list_task_events(tid)[-1]["actor"] == workflow.SCHEDULER


def test_stuck_delivering_without_a_delivered_report_returns_to_the_manager():
    tid = _delivering(with_report="draft")
    scheduler.tick(dt.datetime.now(UTC) + dt.timedelta(minutes=11))
    assert _get(tid)["stage"] == "review_manager"
    ev = db.list_task_events(tid)[-1]
    assert ev["actor"] == workflow.SCHEDULER and "delivery did not finish, returned to manager review" in ev["comment"]


def test_delivering_under_ten_minutes_is_untouched():
    tid = _delivering()
    scheduler.tick(dt.datetime.now(UTC) + dt.timedelta(minutes=5))
    assert _get(tid)["stage"] == "delivering"


def test_recovery_moves_are_scheduler_only():
    tid = _delivering()
    for to in ("delivered", "review_manager"):
        with pytest.raises(workflow.Forbidden):
            workflow.transition(tid, to, "rizky", org_id=None)
