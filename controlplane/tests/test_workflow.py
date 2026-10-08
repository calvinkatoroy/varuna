"""Task workflow (step 2): transition table, roles from the DB, compare-and-set, one event per move."""
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
import tokens  # noqa: E402
import workflow  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402
from conftest import make_client, window  # noqa: E402

PW = "Passw0rd!x"
UTC = dt.UTC


@pytest.fixture(autouse=True)
def _env():
    redis_store._client = FakeRedis()
    for name, role in (("rizky", "pentester"), ("budi", "pentester"), ("dewi", "lead_pentester"),
                       ("agus", "lead_cyber"), ("sari", "governance"), ("hendra", "manager")):
        auth.create_account(name, PW, role)


def _task(stage="task", scan_state=None, target="http://8.8.8.8", scan_mode="cloud", start_min=-5, minutes=480, **extra):
    org = (db.get_account("alice") or {}).get("org_id") or make_client("alice", "PT A")
    nb, na = window(start_min, minutes)
    return db.create_proposal({"submitter": "alice", "org_id": org, "target": target, "scan_mode": scan_mode,
                               "stage": stage, "scan_state": scan_state, "not_before": nb, "not_after": na, **extra})


def _get(tid):
    return db.get_proposal(tid, org_id=None)


def _events(tid):
    return db.list_task_events(tid)


def test_claim_sets_assignee_and_writes_exactly_one_event():
    tid = _task()
    t = workflow.transition(tid, "scan/pending", "rizky", org_id=None)
    assert (t["stage"], t["scan_state"], t["assignee"], t["version"]) == ("scan", "pending", "rizky", 1)
    ev = _events(tid)
    assert len(ev) == 1 and (ev[0]["from_stage"], ev[0]["to_stage"], ev[0]["to_scan_state"], ev[0]["actor"]) == \
        ("task", "scan", "pending", "rizky")


def test_only_pentesters_claim_or_decline():
    tid = _task()
    for who in ("sari", "agus", "hendra", "alice", "nobody"):
        with pytest.raises(workflow.Forbidden):
            workflow.transition(tid, "scan/pending", who, org_id=None)
    assert _get(tid)["stage"] == "task" and _events(tid) == []


@pytest.mark.parametrize("cause", [None, "", "   ", "\t\n"])
def test_decline_needs_a_cause(cause):
    tid = _task()
    with pytest.raises(workflow.Invalid):
        workflow.transition(tid, "declined", "rizky", org_id=None, comment=cause)


def test_decline_stores_the_cause():
    tid = _task()
    t = workflow.transition(tid, "declined", "budi", org_id=None, comment="  Target is not yours  ")
    assert t["stage"] == "declined" and t["decline_cause"] == "Target is not yours"


def test_moves_not_in_the_table_are_conflict():
    tid = _task()
    for to in ("completed", "scan/in_progress", "delivered", "review_manager", "nonsense"):
        with pytest.raises(workflow.Conflict):
            workflow.transition(tid, to, "dewi", org_id=None)
    done = _task(stage="delivered")
    with pytest.raises(workflow.Conflict):
        workflow.transition(done, "review_manager", "hendra", org_id=None, comment="x")


def test_other_org_is_not_found():
    tid = _task()
    with pytest.raises(workflow.NotFound):
        workflow.transition(tid, "scan/pending", "rizky", org_id=db.create_org("PT Other"))


def test_start_rules_owner_agent_window():
    tid = _task(stage="scan", scan_state="pending", assignee="rizky")
    with pytest.raises(workflow.Forbidden):                      # another pentester is not the owner
        workflow.transition(tid, "scan/in_progress", "budi", org_id=None)
    with pytest.raises(workflow.Unavailable) as e:               # cloud scanner not online
        workflow.transition(tid, "scan/in_progress", "rizky", org_id=None)
    assert e.value.status == 409 and e.value.reason == "agent offline"
    tokens.issue_agent_token(models.CLOUD_AGENT)
    t = workflow.transition(tid, "scan/in_progress", "dewi", org_id=None)   # a lead pentester may start any task
    assert (t["stage"], t["scan_state"]) == ("scan", "in_progress") and t["job_id"]
    assert 1 <= t["max_minutes"] <= workflow.DEFAULT_MINUTES and t["scheduled_at"]
    assert redis_store.dequeue_job(models.CLOUD_AGENT) == t["job_id"]
    job = redis_store.get_job(t["job_id"])
    assert job["tools"] == workflow.FULL_STACK and job["org_id"] == t["org_id"] and job["executor"] == models.CLOUD_AGENT


def test_start_outside_the_window_is_invalid():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    early = _task(stage="scan", scan_state="pending", assignee="rizky", start_min=60)
    with pytest.raises(workflow.Invalid):
        workflow.transition(early, "scan/in_progress", "rizky", org_id=None)
    late = _task(stage="scan", scan_state="pending", assignee="rizky", start_min=-120, minutes=60)
    with pytest.raises(workflow.Invalid):
        workflow.transition(late, "scan/in_progress", "rizky", org_id=None)


def test_explicit_duration_cannot_overflow_the_window():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _task(stage="scan", scan_state="pending", assignee="rizky", minutes=120)
    for bad in (0, -5, 10_000):
        with pytest.raises(workflow.Invalid):
            workflow.transition(tid, "scan/in_progress", "rizky", org_id=None, max_minutes=bad)
    assert workflow.transition(tid, "scan/in_progress", "rizky", org_id=None, max_minutes=30)["max_minutes"] == 30


def test_schedule_rules():
    tid = _task(stage="scan", scan_state="pending", assignee="rizky", start_min=60, minutes=240)
    nb = workflow.parse_utc(_get(tid)["not_before"])
    naive = (nb + dt.timedelta(minutes=10)).replace(tzinfo=None).isoformat()
    for at, minutes in ((None, None), (naive, None), ((nb - dt.timedelta(minutes=1)).isoformat(), 30),
                        ((nb + dt.timedelta(minutes=200)).isoformat(), 60)):
        with pytest.raises(workflow.Invalid):
            workflow.transition(tid, "scan/scheduled", "rizky", org_id=None, scheduled_at=at, max_minutes=minutes)
    at = (nb + dt.timedelta(minutes=10)).astimezone(dt.timezone(dt.timedelta(hours=7))).isoformat()   # WIB offset accepted
    t = workflow.transition(tid, "scan/scheduled", "rizky", org_id=None, scheduled_at=at, max_minutes=60)
    assert t["scan_state"] == "scheduled" and t["scheduled_at"].endswith("+00:00") and t["max_minutes"] == 60
    assert t["target_class"] == "cloud"
    assert workflow.transition(tid, "scan/pending", "rizky", org_id=None)["scan_state"] == "pending"   # cancel


@pytest.mark.parametrize("reason", [None, "", "  ", "\n\t "])
def test_suspend_needs_a_real_reason(reason):
    tid = _task(stage="scan", scan_state="in_progress", assignee="rizky", job_id="j1")
    with pytest.raises(workflow.Invalid):
        workflow.transition(tid, "scan/suspended", "rizky", org_id=None, comment=reason)


def test_suspend_flags_the_job_and_resume_continues_a_live_job():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _task(stage="scan", scan_state="in_progress", assignee="rizky", job_id="j1")
    redis_store.set_job({"id": "j1", "submitter": "alice", "status": "running", "org_id": _get(tid)["org_id"]})
    t = workflow.transition(tid, "scan/suspended", "rizky", org_id=None, comment="client asked to pause")
    assert t["suspend_reason"] == "client asked to pause" and redis_store.is_suspended("j1")
    t = workflow.transition(tid, "scan/in_progress", "rizky", org_id=None)
    assert t["job_id"] == "j1" and not redis_store.is_suspended("j1")


def test_resume_after_a_failed_job_dispatches_a_new_one():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _task(stage="scan", scan_state="suspended", assignee="rizky", job_id="j1")
    redis_store.set_job({"id": "j1", "submitter": "alice", "status": "failed"})
    t = workflow.transition(tid, "scan/in_progress", "rizky", org_id=None)
    assert t["job_id"] != "j1" and redis_store.dequeue_job(models.CLOUD_AGENT) == t["job_id"]


def test_role_is_read_from_the_db_at_call_time():
    tid = _task()
    db.set_account("rizky", role="governance")
    with pytest.raises(workflow.Forbidden):
        workflow.transition(tid, "scan/pending", "rizky", org_id=None)
    db.set_account("budi", disabled=1)
    with pytest.raises(workflow.Forbidden):
        workflow.transition(tid, "scan/pending", "budi", org_id=None)


def test_demoted_assignee_loses_ownership():
    tid = _task(stage="scan", scan_state="pending", assignee="rizky")
    db.set_account("rizky", role="manager")
    with pytest.raises(workflow.Forbidden):
        workflow.transition(tid, "scan/scheduled", "rizky", org_id=None, scheduled_at=window()[1])


def test_stale_version_is_conflict():
    tid = _task()
    with pytest.raises(workflow.Conflict):
        workflow.transition(tid, "scan/pending", "rizky", org_id=None, version=7)
    assert workflow.transition(tid, "scan/pending", "rizky", org_id=None, version=0)["version"] == 1


def test_system_and_scheduler_rows_are_theirs_only():
    tid = _task(stage="scan", scan_state="in_progress", assignee="rizky")
    with pytest.raises(workflow.Forbidden):
        workflow.transition(tid, "completed", "dewi", org_id=None)
    assert workflow.transition(tid, "completed", workflow.SYSTEM, org_id=None)["stage"] == "completed"
    tid2 = _task()
    with pytest.raises(workflow.Forbidden):
        workflow.transition(tid2, "expired", "dewi", org_id=None)
    assert workflow.transition(tid2, "expired", workflow.SCHEDULER, org_id=None)["stage"] == "expired"


def test_review_chain_approve_path_and_wrong_role():
    """Converted from test_report_pipeline.py (advance path, wrong role denied, past delivered invalid)."""
    tid = _task(stage="completed", assignee="rizky")
    with pytest.raises(workflow.Forbidden):
        workflow.transition(tid, "review_lead_pentester", "budi", org_id=None)      # not the assignee
    workflow.transition(tid, "review_lead_pentester", "rizky", org_id=None)
    with pytest.raises(workflow.Forbidden):
        workflow.transition(tid, "review_lead_cyber", "sari", org_id=None)        # governance does not own this stage
    for who, to in (("dewi", "review_lead_cyber"), ("agus", "review_governance"), ("sari", "review_manager")):
        assert workflow.transition(tid, to, who, org_id=None)["stage"] == to
    with pytest.raises(workflow.Conflict):                                          # delivery needs the deliver hook
        workflow.transition(tid, "delivered", "hendra", org_id=None)
    calls = []
    t = workflow.transition(tid, "delivered", "hendra", org_id=None, on_deliver=calls.append)
    assert t["stage"] == "delivered" and len(calls) == 1 and calls[0]["stage"] == "review_manager"
    assert [e["to_stage"] for e in _events(tid)] == ["review_lead_pentester", "review_lead_cyber", "review_governance",
                                                       "review_manager", "delivered"]
    with pytest.raises(workflow.Conflict):
        workflow.transition(tid, "review_manager", "hendra", org_id=None, comment="x")


def test_review_chain_send_back_one_stage_with_comment():
    """Converted from test_report_pipeline.py (send back one stage; the first review stage returns to completed)."""
    tid = _task(stage="review_governance", assignee="rizky")
    with pytest.raises(workflow.Invalid):
        workflow.transition(tid, "review_lead_cyber", "sari", org_id=None, comment=" ")
    assert workflow.transition(tid, "review_lead_cyber", "sari", org_id=None, comment="fix the summary")["stage"] == "review_lead_cyber"
    first = _task(stage="review_lead_pentester", assignee="rizky")
    assert workflow.transition(first, "completed", "dewi", org_id=None, comment="add evidence")["stage"] == "completed"


def test_failed_delivery_restores_the_manager_stage():
    tid = _task(stage="review_manager", assignee="rizky")

    def boom(_task):
        raise RuntimeError("soffice died")
    with pytest.raises(RuntimeError):
        workflow.transition(tid, "delivered", "hendra", org_id=None, on_deliver=boom)
    t = _get(tid)
    assert t["stage"] == "review_manager" and _events(tid) == []


def _race(fn, n=2):
    barrier, results = threading.Barrier(n), []

    def run(i):
        barrier.wait()
        try:
            fn(i)
            results.append("ok")
        except workflow.Conflict:
            results.append("conflict")
    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return sorted(results)


def test_two_approvers_exactly_one_wins():
    auth.create_account("sari2", PW, "governance")
    tid = _task(stage="review_governance", assignee="rizky")
    who = ["sari", "sari2"]
    assert _race(lambda i: workflow.transition(tid, "review_manager", who[i], org_id=None)) == ["conflict", "ok"]
    assert len(_events(tid)) == 1


def test_two_claims_one_winner():
    tid = _task()
    who = ["rizky", "budi"]
    assert _race(lambda i: workflow.transition(tid, "scan/pending", who[i], org_id=None)) == ["conflict", "ok"]
    assert _get(tid)["assignee"] in who and len(_events(tid)) == 1


def test_actions_list_allowed_moves_and_why():
    tid = _task(stage="scan", scan_state="pending", assignee="rizky")
    acts = {a["to"]: a for a in workflow.actions(_get(tid), "budi")}
    assert set(acts) == {"scan/in_progress", "scan/scheduled"}                 # system-only rows are not offered
    assert not acts["scan/in_progress"]["allowed"] and "assignee" in acts["scan/in_progress"]["why"]
    assert all(a["allowed"] for a in workflow.actions(_get(tid), "rizky"))


def test_create_task_validates_and_records_the_first_event():
    org = make_client("alice", "PT A")
    nb, na = window()
    t = workflow.create_task("alice", org, target="http://8.8.8.8", path="/app", port=8443, notes="login at /app",
                             not_before=nb, not_after=na, scan_mode="cloud")
    assert (t["stage"], t["scan_state"], t["version"]) == ("task", None, 0)
    assert workflow.scan_url(t) == "http://8.8.8.8:8443/app"
    ev = _events(t["id"])
    assert len(ev) == 1 and ev[0]["from_stage"] is None and ev[0]["to_stage"] == "task" and ev[0]["actor"] == "alice"
    past = (dt.datetime.now(UTC) - dt.timedelta(hours=1)).isoformat()
    bad = [dict(not_before=nb.replace("+00:00", ""), not_after=na),          # naive
           dict(not_before=na, not_after=nb),                                 # ends before it starts
           dict(not_before=past, not_after=past),                             # already over
           dict(not_before=nb, not_after=na, path="app"),                     # path must start with /
           dict(not_before=nb, not_after=na, port=70000),
           dict(not_before=nb, not_after=na, target="javascript:alert(1)"),
           dict(not_before=nb, not_after=na, target="http://10.0.0.5", scan_mode="cloud")]
    for b in bad:
        args = {"target": "http://8.8.8.8", "scan_mode": "local", **b}
        with pytest.raises(workflow.Invalid):
            workflow.create_task("alice", org, **args)


def test_client_timeline_hides_internal_detail():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _task()
    workflow.transition(tid, "scan/pending", "rizky", org_id=None)
    workflow.transition(tid, "scan/in_progress", "rizky", org_id=None)
    workflow.transition(tid, "scan/suspended", "rizky", org_id=None, comment="internal: client server melted")
    tl = workflow.client_timeline(tid)
    assert [i["status"] for i in tl] == ["accepted", "scanning", "paused"]
    assert "rizky" not in str(tl) and "melted" not in str(tl)
    other = _task()
    workflow.transition(other, "declined", "rizky", org_id=None, comment="Bukti kepemilikan belum ada")
    assert workflow.client_timeline(other) == [{"status": "declined", "at": _events(other)[0]["at"],
                                                "note": "Bukti kepemilikan belum ada"}]


def test_update_proposal_refuses_stage_changes():
    tid = _task()
    with pytest.raises(ValueError):
        db.update_proposal(tid, stage="delivered")


def test_update_and_claim_proposal_refuse_workflow_columns():
    tid = _task()
    for col in ("stage", "scan_state", "version"):
        with pytest.raises(ValueError):
            db.update_proposal(tid, **{col: 5})
        with pytest.raises(ValueError):
            db.claim_proposal(tid, "pending", **{col: 5})
    assert _get(tid)["version"] == 0


def test_pre_workflow_rows_are_closed_by_the_migration(tmp_path):
    import sqlite3
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE proposals (id TEXT PRIMARY KEY, submitter TEXT NOT NULL, status TEXT NOT NULL "
                "DEFAULT 'pending', mode TEXT DEFAULT 'standard', target TEXT NOT NULL, in_scope TEXT, out_of_scope TEXT, "
                "division TEXT, purpose TEXT, environment TEXT, test_window TEXT, roe_json TEXT DEFAULT '{}', "
                "authorization_attested INTEGER NOT NULL DEFAULT 0, emergency_contact TEXT, "
                "tools_json TEXT DEFAULT '[]', opts_json TEXT DEFAULT '{}', job_id TEXT, reject_reason TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), "
                "updated_at TEXT NOT NULL DEFAULT (datetime('now')))")
    old.execute("INSERT INTO proposals (id, submitter, status, target) VALUES ('old1', 'alice', 'rejected', 'x.com')")
    old.commit()
    old.close()
    db.close()
    db._path = path
    def stages():
        return dict(tuple(r) for r in db.get_conn().execute("SELECT id, stage FROM proposals"))
    assert stages() == {"old1": "expired"}
    tid = _task()
    assert stages()[tid] == "task"
    db.close()
    assert stages() == {"old1": "expired", tid: "task"}   # second start: no re-backfill


def _fut(minutes):
    return (dt.datetime.now(UTC) + dt.timedelta(minutes=minutes)).isoformat()


_ALLOWED = [
    # (id, from stage, from scan_state, to, actor, comment)
    ("sched-start", "scan", "scheduled", "scan/in_progress", workflow.SCHEDULER, None),
    ("sched-suspend", "scan", "scheduled", "scan/suspended", workflow.SCHEDULER, "agent offline"),
    ("sched-expire", "scan", "scheduled", "expired", workflow.SCHEDULER, None),
    ("pending-expire", "scan", "pending", "expired", workflow.SCHEDULER, None),
    ("task-expire", "task", None, "expired", workflow.SCHEDULER, None),
    ("susp-schedule", "scan", "suspended", "scan/scheduled", "rizky", None),
    ("susp-complete", "scan", "suspended", "completed", workflow.SYSTEM, None),
    ("susp-expire", "scan", "suspended", "expired", "rizky", "client went away"),
    ("cyber-sendback", "review_lead_cyber", None, "review_lead_pentester", "agus", "more evidence"),
    ("manager-sendback", "review_manager", None, "review_governance", "hendra", "wording"),
    ("prog-suspend-sched", "scan", "in_progress", "scan/suspended", workflow.SCHEDULER, "window closing"),
    ("prog-suspend-agent", "scan", "in_progress", "scan/suspended", workflow.SYSTEM, "agent lost"),
]


@pytest.mark.parametrize("frm_stage,frm_state,to,actor,comment", [c[1:] for c in _ALLOWED], ids=[c[0] for c in _ALLOWED])
def test_every_remaining_table_row_is_allowed(frm_stage, frm_state, to, actor, comment):
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _task(stage=frm_stage, scan_state=frm_state, assignee="rizky")
    extra = {"scheduled_at": _fut(30), "max_minutes": 30} if to == "scan/scheduled" else {}
    t = workflow.transition(tid, to, actor, org_id=None, comment=comment, **extra)
    assert workflow.state_key(t) == to
    ev = _events(tid)
    assert len(ev) == 1 and ev[0]["actor"] == actor and t["version"] == 1


def test_suspended_close_needs_a_reason_and_sendbacks_need_a_comment():
    tid = _task(stage="scan", scan_state="suspended", assignee="rizky")
    with pytest.raises(workflow.Invalid):
        workflow.transition(tid, "expired", "rizky", org_id=None, comment="  ")
    for stage, to, who in (("review_lead_cyber", "review_lead_pentester", "agus"),
                           ("review_manager", "review_governance", "hendra")):
        t2 = _task(stage=stage, assignee="rizky")
        with pytest.raises(workflow.Invalid):
            workflow.transition(t2, to, who, org_id=None, comment=" ")
        with pytest.raises(workflow.Forbidden):
            workflow.transition(t2, to, "rizky", org_id=None, comment="x")


def test_failed_dispatch_after_start_suspends_the_task(monkeypatch):
    import dispatch
    tokens.issue_agent_token(models.CLOUD_AGENT)

    def refuse(job, pre_approved=False):
        job.update(status=models.STATUS_FAILED, error="scan refused: agent belongs to another organization")
        redis_store.set_job(job)
    monkeypatch.setattr(dispatch, "dispatch_job", refuse)
    tid = _task(stage="scan", scan_state="pending", assignee="rizky")
    t = workflow.transition(tid, "scan/in_progress", "rizky", org_id=None)
    assert (t["stage"], t["scan_state"]) == ("scan", "suspended")
    assert "another organization" in t["suspend_reason"]
    ev = _events(tid)
    assert [(e["to_scan_state"], e["actor"]) for e in ev] == [("in_progress", "rizky"), ("suspended", workflow.SYSTEM)]


def test_event_insert_failure_rolls_the_stage_change_back(monkeypatch):
    tid = _task()

    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(db, "_insert_event", boom)
    with pytest.raises(RuntimeError):
        workflow.transition(tid, "scan/pending", "rizky", org_id=None)
    monkeypatch.undo()
    t = _get(tid)
    assert (t["stage"], t["version"], t["assignee"]) == ("task", 0, None)
    assert _events(tid) == []


def test_delivery_never_leaves_the_task_in_delivering():
    tid = _task(stage="review_manager", assignee="rizky")

    def meddle(t):
        assert db.cas_task(tid, 1, {"assignee": "budi"})   # someone else moves it mid-delivery
    with pytest.raises(workflow.Conflict):                  # final CAS lost
        workflow.transition(tid, "delivered", "hendra", org_id=None, on_deliver=meddle)

    tid2 = _task(stage="review_manager", assignee="rizky")

    def meddle_then_fail(t):
        assert db.cas_task(tid2, 1, {"assignee": "budi"})
        raise RuntimeError("soffice died")
    with pytest.raises(workflow.Conflict):                  # restore CAS lost
        workflow.transition(tid2, "delivered", "hendra", org_id=None, on_deliver=meddle_then_fail)


def test_system_actor_names_cannot_be_registered():
    for name in ("sys:agent", "a:b", "sys:scheduler"):
        with pytest.raises(ValueError):
            auth.create_account(name, PW, "pentester")
    assert db.get_account("sys:agent") is None


@pytest.mark.parametrize("bad", ["abc", True, "1e3x", float("inf"), None])
def test_bad_max_minutes_is_422_not_500(bad):
    with pytest.raises(workflow.Invalid):
        workflow._minutes(bad, 60)
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _task(stage="scan", scan_state="pending", assignee="rizky")
    if bad is not None:
        with pytest.raises(workflow.Invalid):
            workflow.transition(tid, "scan/in_progress", "rizky", org_id=None, max_minutes=bad)
        with pytest.raises(workflow.Invalid):
            workflow.transition(tid, "scan/scheduled", "rizky", org_id=None, scheduled_at=_fut(30), max_minutes=bad)


def test_less_than_a_minute_left_is_422():
    tokens.issue_agent_token(models.CLOUD_AGENT)
    tid = _task(stage="scan", scan_state="pending", assignee="rizky")
    db.update_proposal(tid, not_after=(dt.datetime.now(UTC) + dt.timedelta(seconds=30)).isoformat())
    for mm in (None, 5):
        with pytest.raises(workflow.Invalid, match="not enough time left"):
            workflow.transition(tid, "scan/in_progress", "rizky", org_id=None, max_minutes=mm)
    assert (_get(tid)["stage"], _get(tid)["scan_state"]) == ("scan", "pending")


@pytest.mark.parametrize("value", ["0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-05:00", "garbage", None])
def test_extreme_or_garbage_times_are_422(value):
    with pytest.raises(workflow.Invalid):
        workflow.parse_utc(value, "scheduled_at")
