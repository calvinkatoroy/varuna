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


def _queued(user):
    return redis_store.dequeue_job(user)   # returns a job_id or None


def test_pro_cloud_never_gated():
    reset()
    _agent_online("pentester")
    res = dispatch.submit_scan("pentester", "pro", CLOUD, ["katana", "nuclei"])
    assert res["state"] == "dispatched"
    assert _queued("pentester") == res["job_id"], "pro cloud scan should dispatch immediately"


def test_standard_local_dispatched_immediately():
    reset()
    _agent_online("staff")
    res = dispatch.submit_scan("staff", "standard", LOCAL, ["katana", "nuclei", "sqlmap"])
    assert res["state"] == "dispatched"
    assert _queued("staff") == res["job_id"]


def test_standard_cloud_is_gated_not_queued():
    reset()
    _agent_online("staff")
    res = dispatch.submit_scan("staff", "standard", CLOUD, ["katana"], division="Finance")
    assert res["state"] == "pending_approval"
    assert _queued("staff") is None, "gated request must NOT be enqueued before approval"
    pend = dispatch.pending_approvals()
    assert len(pend) == 1 and pend[0]["division"] == "Finance"


def test_approve_dispatches_through_choke_point():
    reset()
    _agent_online("staff")
    res = dispatch.submit_scan("staff", "standard", CLOUD, ["katana"])
    dispatch.approve_request(res["job_id"], approver="ihsan")
    assert _queued("staff") == res["job_id"], "approved request should reach the agent queue"
    assert dispatch.pending_approvals() == [], "approved request should leave the queue"


def test_reject_discards_never_dispatched():
    reset()
    _agent_online("staff")
    res = dispatch.submit_scan("staff", "standard", CLOUD, ["katana"])
    dispatch.reject_request(res["job_id"], approver="ihsan", reason="unauthorized target")
    assert _queued("staff") is None, "rejected request must never be enqueued"
    assert dispatch.pending_approvals() == []
    assert redis_store.get_approval(res["job_id"])["reason"] == "unauthorized target"


def test_choke_point_blocks_unapproved_cloud_directly():
    # Even calling dispatch_job directly (a hypothetical second code path) must refuse
    # an unapproved Standard cloud job. This is the REQ-19a defense-in-depth.
    reset()
    _agent_online("staff")
    job = {"id": "x", "role": "standard", "target_class": classifier.CLASS_CLOUD,
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
        dispatch.submit_scan("staff", "standard", LOCAL, ["katana"])
    except dispatch.OfflineAgent:
        assert _queued("staff") is None, "offline dispatch must not silently queue (REQ-76)"
        return
    raise AssertionError("offline agent should raise OfflineAgent")


def test_list_jobs_newest_first():
    reset()
    _agent_online("pentester")
    r1 = dispatch.submit_scan("pentester", "pro", CLOUD, ["katana"])
    r2 = dispatch.submit_scan("pentester", "pro", CLOUD, ["nuclei"])
    jobs = dispatch.list_jobs("pentester")
    assert [j["id"] for j in jobs] == [r2["job_id"], r1["job_id"]]


def test_classify_rejected_propagates():
    reset()
    _agent_online("staff")
    try:
        dispatch.submit_scan("staff", "standard", "http://0x7f000001", ["katana"])
    except classifier.ClassifyRejected:
        return   # fail closed: evasion target rejected before any dispatch
    raise AssertionError("an evasion target must be rejected, not classified")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_dispatch: all green")
