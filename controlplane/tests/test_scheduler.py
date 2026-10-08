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
