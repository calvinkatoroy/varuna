"""Approval Gate + dispatch choke-point tests (SRS §4.3, REQ-19a, REQ-76).

The invariant that matters: a Standard cloud-target request never reaches an agent queue
without an explicit Approve, through ANY path. Pure logic over FakeRedis, offline.
Targets use IP literals so classification needs no DNS (deterministic).
"""
import datetime
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import dispatch  # noqa: E402
import tokens  # noqa: E402
import db  # noqa: E402
import classifier  # noqa: E402

LOCAL = "http://10.0.0.5"      # classifies local via ipaddress, no DNS
CLOUD = "http://8.8.8.8"       # classifies cloud via ipaddress, no DNS


def reset():
    redis_store._client = FakeRedis()


def _agent_online(user):
    tokens.issue_agent_token(user)   # sets last_seen = now -> online


def _agent_offline(user):
    tokens.issue_agent_token(user)
    a = redis_store.get_agent(user)
    a["last_seen"] = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=5)).isoformat()
    redis_store.set_agent(user, a)


def test_agent_record_without_org_is_a_mismatch_but_cloud_is_exempt():
    reset()
    redis_store.set_agent("legacy", {"status": "online", "token_hash": "x"})   # never recorded an org
    assert dispatch._org_mismatch({"submitter": "legacy", "org_id": None}) is True
    assert dispatch._org_mismatch({"submitter": "varuna-cloud", "org_id": "o1"}) is False


def _queued(user):
    return redis_store.dequeue_job(user)   # returns a job_id or None


def test_pro_cloud_never_gated():
    reset()
    _agent_online("pentester")
    res = dispatch.submit_scan("pentester", "pentester", None, CLOUD, ["katana", "nuclei"])
    assert res["state"] == "dispatched"
    assert _queued("pentester") == res["job_id"], "pro cloud scan should dispatch immediately"


def test_standard_local_dispatched_immediately():
    reset()
    _agent_online("staff")
    res = dispatch.submit_scan("staff", "client", None, LOCAL, ["katana", "nuclei", "sqlmap"])
    assert res["state"] == "dispatched"
    assert _queued("staff") == res["job_id"]


def test_standard_cloud_is_gated_not_queued():
    reset()
    _agent_online("staff")
    res = dispatch.submit_scan("staff", "client", None, CLOUD, ["katana"], division="Finance")
    assert res["state"] == "pending_approval"
    assert _queued("staff") is None, "gated request must NOT be enqueued before approval"
    pend = dispatch.pending_approvals()
    assert len(pend) == 1 and pend[0]["division"] == "Finance"


def test_approve_dispatches_through_choke_point():
    reset()
    _agent_online("staff")
    res = dispatch.submit_scan("staff", "client", None, CLOUD, ["katana"])
    dispatch.approve_request(res["job_id"], approver="ihsan")
    assert _queued("staff") == res["job_id"], "approved request should reach the agent queue"
    assert dispatch.pending_approvals() == [], "approved request should leave the queue"


def test_reject_discards_never_dispatched():
    reset()
    _agent_online("staff")
    res = dispatch.submit_scan("staff", "client", None, CLOUD, ["katana"])
    dispatch.reject_request(res["job_id"], approver="ihsan", reason="unauthorized target")
    assert _queued("staff") is None, "rejected request must never be enqueued"
    assert dispatch.pending_approvals() == []
    assert redis_store.get_approval(res["job_id"])["reason"] == "unauthorized target"


def test_choke_point_blocks_unapproved_cloud_directly():
    # Even calling dispatch_job directly (a hypothetical second code path) must refuse
    # an unapproved Standard cloud job. This is the REQ-19a defense-in-depth.
    reset()
    _agent_online("staff")
    job = {"id": "x", "role": "client", "target_class": classifier.CLASS_CLOUD,
           "submitter": "staff"}
    try:
        dispatch.dispatch_job(job)
    except dispatch.NotApproved:
        assert _queued("staff") is None
        return
    raise AssertionError("dispatch_job must reject an unapproved Standard cloud job")


def test_offline_agent_rejected_not_queued():
    reset()
    _agent_offline("staff")
    try:
        dispatch.submit_scan("staff", "client", None, LOCAL, ["katana"])
    except dispatch.OfflineAgent:
        assert _queued("staff") is None, "offline dispatch must not silently queue (REQ-76)"
        return
    raise AssertionError("offline agent should raise OfflineAgent")


def test_list_jobs_newest_first():
    reset()
    _agent_online("pentester")
    r1 = dispatch.submit_scan("pentester", "pentester", None, CLOUD, ["katana"])
    r2 = dispatch.submit_scan("pentester", "pentester", None, CLOUD, ["nuclei"])
    jobs = dispatch.list_jobs(None)   # staff direct scans belong to no organization
    assert [j["id"] for j in jobs] == [r2["job_id"], r1["job_id"]]


def test_classify_rejected_propagates():
    reset()
    _agent_online("staff")
    try:
        dispatch.submit_scan("staff", "client", None, "http://0x7f000001", ["katana"])
    except classifier.ClassifyRejected:
        return   # fail closed: evasion target rejected before any dispatch
    raise AssertionError("an evasion target must be rejected, not classified")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_dispatch: all green")


def test_pre_approved_enqueues_skipping_gate_and_online():
    # v2: a lead-approved proposal queues the client's job even with no redis approval and an
    # offline agent (client installs the agent after approval; the job waits in the queue).
    reset()
    _agent_offline("alice")
    job = {"id": "pa1", "role": "client", "target_class": classifier.CLASS_CLOUD,
           "submitter": "alice"}
    dispatch.dispatch_job(job, pre_approved=True)
    assert _queued("alice") == "pa1"


def test_staff_scope_lists_every_org_and_client_scope_only_its_own():
    reset()
    oa, ob = db.create_org("A"), db.create_org("B")
    for jid, org in (("ja", oa), ("jb", ob), ("js", None)):
        redis_store.set_job({"id": jid, "submitter": "u", "org_id": org, "status": "queued"})
        redis_store.add_org_job(org, jid)
    assert {j["id"] for j in dispatch.list_jobs(None)} == {"ja", "jb", "js"}
    assert [j["id"] for j in dispatch.list_jobs(oa)] == ["ja"]


def test_jobs_carry_org_and_are_listed_and_read_per_org():
    reset()
    import tenancy
    oa = db.create_org("A")
    _agent_online("pentester")
    staff =dispatch.submit_scan("pentester", "pentester", None, CLOUD, ["katana"])
    redis_store.set_job({"id": "ja", "submitter": "alice", "org_id": oa, "status": "queued"})
    redis_store.add_org_job(oa, "ja")
    assert [j["id"] for j in dispatch.list_jobs(oa)] == ["ja"]
    assert {j["id"] for j in dispatch.list_jobs(None)} == {"ja", staff["job_id"]}   # staff scope: every org
    assert dispatch.list_jobs("org-b") == []
    assert dispatch.get_job(tenancy.Scope(oa), "ja")["id"] == "ja"
    assert dispatch.get_job(tenancy.Scope("org-b"), "ja") is None          # other org: as if missing
    assert dispatch.get_job(tenancy.Scope(None), "ja")["id"] == "ja"       # staff see every org
    assert dispatch.get_job(tenancy.Scope(oa), staff["job_id"]) is None


def test_dispatch_refuses_a_job_of_another_org_and_fails_it():
    reset()
    import auth
    import db
    oa, ob = db.create_org("PT A"), db.create_org("PT B")
    auth.create_account("alice", "Passw0rd!x", "client", org_id=oa)
    _agent_online("alice")
    assert redis_store.get_agent("alice")["org_id"] == oa      # enrolment records the org
    job = {"id": "jx", "role": "client", "target_class": classifier.CLASS_LOCAL,
           "submitter": "alice", "org_id": ob, "status": "queued"}
    redis_store.set_job(job)
    dispatch.dispatch_job(job, pre_approved=True)
    assert _queued("alice") is None, "a job of another org must never reach the agent"
    assert redis_store.get_job("jx")["status"] == "failed"
    ok = {**job, "id": "jy", "org_id": oa}
    dispatch.dispatch_job(ok, pre_approved=True)
    assert _queued("alice") == "jy"
