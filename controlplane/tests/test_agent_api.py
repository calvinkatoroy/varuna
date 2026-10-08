"""Agent-API protocol + security tests (Phase C check).

Covers the enroll -> poll -> status/findings roundtrip, and the security invariants:
invalid token rejected, revoked token rejected (NFR-26), enrollment token one-time,
and cross-job ownership rejected (NFR-26). Runs offline with a FakeRedis, no server.

Standalone: `python controlplane/tests/test_agent_api.py`  (also pytest-compatible).
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)                                  # _fakeredis
sys.path.insert(0, os.path.join(HERE, "..", "common"))    # redis_store, tokens
sys.path.insert(0, os.path.join(HERE, "..", "api"))       # main

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()   # inject before any endpoint touches Redis

import db  # noqa: E402
import tokens  # noqa: E402
import main as api_main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(api_main.app)


def reset():
    redis_store._client = FakeRedis()
    db.reset_for_test(":memory:")   # pytest's autouse conftest fixture does this too; also
                                     # needed here for this file's standalone __main__ mode


def _enroll(username):
    import auth
    if not db.get_account(username):
        auth.create_account(username, "Passw0rd!x", "pentester")
    et = tokens.generate_enrollment_token(username)
    r = client.post("/agent/enroll", json={"enrollment_token": et})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_roundtrip():
    reset()
    H = _enroll("calvin")
    assert client.get("/agent/poll", headers=H).json()["job"] is None  # empty queue

    job = {"id": "job1", "target": "http://t.local", "target_class": "local",
           "submitter": "calvin", "role": "pentester", "status": "queued", "per_tool_status": {}}
    redis_store.set_job(job)
    redis_store.enqueue_job("calvin", "job1")

    got = client.get("/agent/poll", headers=H).json()["job"]
    assert got and got["id"] == "job1"

    r = client.post("/agent/jobs/job1/status", headers=H,
                    json={"status": "running", "per_tool_status": {"nuclei": "running"}})
    assert r.status_code == 200
    assert redis_store.get_job("job1")["status"] == "running"

    r = client.post("/agent/jobs/job1/findings", headers=H, json={"raw": {"nuclei": "x"}})
    assert r.status_code == 200


def test_invalid_token_rejected():
    reset()
    assert client.get("/agent/poll", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_revoked_token_rejected():
    reset()
    H = _enroll("bob")
    assert client.get("/agent/poll", headers=H).status_code == 200
    tokens.revoke_agent("bob")
    assert client.get("/agent/poll", headers=H).status_code == 401


def test_enrollment_token_is_one_time():
    reset()
    _client_acct("carol")
    et = tokens.generate_enrollment_token("carol")
    assert client.post("/agent/enroll", json={"enrollment_token": et}).status_code == 200
    assert client.post("/agent/enroll", json={"enrollment_token": et}).status_code == 401


def test_cross_job_ownership_rejected():
    reset()
    redis_store.set_job({"id": "ajob", "submitter": "alice", "status": "queued", "per_tool_status": {}})
    H = _enroll("bob")  # bob is not alice
    assert client.post("/agent/jobs/ajob/status", headers=H, json={"status": "done"}).status_code == 403
    assert client.post("/agent/jobs/ajob/findings", headers=H, json={"raw": {}}).status_code == 403
    assert client.get("/agent/jobs/ajob/suspended", headers=H).status_code == 403


def test_agent_of_another_org_cannot_touch_a_job_even_with_the_same_username():
    reset()
    oa, ob = db.create_org("A"), db.create_org("B")
    import auth
    auth.create_account("dup", "pw", "client", org_id=oa)   # the account now in org A, same name as B's old one
    redis_store.set_job({"id": "bjob", "submitter": "dup", "org_id": ob, "status": "queued", "per_tool_status": {}})
    H = _enroll("dup")
    assert client.post("/agent/jobs/bjob/status", headers=H, json={"status": "done"}).status_code == 403
    assert client.post("/agent/jobs/bjob/findings", headers=H, json={"raw": {}}).status_code == 403
    assert client.get("/agent/jobs/bjob/suspended", headers=H).status_code == 403
    redis_store.set_job({"id": "ajob2", "submitter": "dup", "org_id": oa, "status": "queued", "per_tool_status": {}})
    assert client.post("/agent/jobs/ajob2/status", headers=H, json={"status": "running"}).status_code == 200


def test_suspended_checkin():
    reset()
    redis_store.set_job({"id": "sjob", "submitter": "dina", "status": "running", "per_tool_status": {}})
    H = _enroll("dina")
    assert client.get("/agent/jobs/sjob/suspended", headers=H).json() == {"suspended": False}
    redis_store.set_suspended("sjob", True)
    assert client.get("/agent/jobs/sjob/suspended", headers=H).json() == {"suspended": True}


def test_ingest_pipeline_runs_on_upload():
    reset()
    import ollama  # pipeline module (on path via api -> ingest import)
    ollama.OLLAMA_URL = "http://127.0.0.1:1"   # no Ollama in tests -> graceful fallback (REQ-36)

    H = _enroll("calvin")
    job = {"id": "j9", "target": "http://t.local", "target_class": "local",
           "submitter": "calvin", "role": "pentester", "status": "running", "per_tool_status": {}}
    redis_store.set_job(job)

    nuclei = ('{"template-id":"CVE-2021-44228","info":{"name":"Log4j RCE","severity":"critical",'
              '"classification":{"cve-id":["CVE-2021-44228"],"cwe-id":["CWE-502"]}},'
              '"host":"http://t.local","matched-at":"http://t.local/api"}')
    r = client.post("/agent/jobs/j9/findings", headers=H, json={"raw": {"nuclei": nuclei}})
    assert r.status_code == 200

    # BackgroundTask ran: raw was parsed -> correlated -> stored as findings.
    findings = db.get_findings("j9")
    assert len(findings) == 1, "ingest did not store parsed findings"
    assert findings[0]["cve"] == "CVE-2021-44228"
    assert findings[0]["owasp"] == "A08:2021-Software and Data Integrity Failures"  # correlate tagged it
    assert findings[0].get("impact") is None   # enrichment fell back gracefully, finding kept un-enriched


def test_reenroll_revokes_old_binding():
    reset()
    t1 = tokens.issue_agent_token("dave")
    t2 = tokens.issue_agent_token("dave")   # re-enroll on a new machine
    r = redis_store.get_redis()
    assert r.get(redis_store.agent_token_key(tokens._hash(t1))) is None, "old reverse-index key orphaned"
    assert tokens.verify_agent_token(t1) is None, "old token still valid after re-enroll"
    assert tokens.verify_agent_token(t2) == "dave", "new token should be valid"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_agent_api: all green")


# --- disabled accounts / organizations lose their agents ---
def _client_acct(name, org="Org Z"):
    import auth
    oid = next((o["id"] for o in db.list_orgs() if o["name"] == org), None) or db.create_org(org)
    auth.create_account(name, "Passw0rd!x", "client", org_id=oid)
    return oid


def test_disabled_user_cannot_enroll_or_poll_and_can_after_reenable():
    reset()
    _client_acct("zed")
    H = _enroll("zed")
    assert client.get("/agent/poll", headers=H).status_code == 200
    db.set_account("zed", disabled=1)
    assert client.get("/agent/poll", headers=H).status_code == 401
    et = tokens.generate_enrollment_token("zed")
    assert client.post("/agent/enroll", json={"enrollment_token": et}).status_code == 401
    db.set_account("zed", disabled=0)
    H2 = _enroll("zed")
    assert client.get("/agent/poll", headers=H2).status_code == 200


def test_disabled_org_agent_refused_and_enrol_works_after_reenable():
    reset()
    oid = _client_acct("yan")
    H = _enroll("yan")
    db.set_org_status(oid, "disabled")
    assert client.get("/agent/poll", headers=H).status_code == 401
    et = tokens.generate_enrollment_token("yan")
    assert client.post("/agent/enroll", json={"enrollment_token": et}).status_code == 401
    db.set_org_status(oid, "active")
    assert client.get("/agent/poll", headers=H).status_code == 200


def test_cloud_agent_needs_no_account():
    reset()
    et = tokens.generate_enrollment_token("varuna-cloud")
    r = client.post("/agent/enroll", json={"enrollment_token": et})
    assert r.status_code == 200
    H = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/agent/poll", headers=H).status_code == 200


def test_org_disable_and_account_disable_via_sysadmin(priv):
    reset()
    import auth
    auth.create_account("root", "Passw0rd!x", "sysadmin")
    oid = _client_acct("xia")
    H = _enroll("xia")
    redis_store.set_job({"id": "qj", "submitter": "xia", "org_id": oid, "status": "queued", "per_tool_status": {}})
    redis_store.enqueue_job("xia", "qj")
    redis_store.add_org_job(oid, "qj")
    tok = priv.login("root", "Passw0rd!x")
    assert priv.post(f"/api/sysadmin/orgs/{oid}/disable", tok).status_code == 200
    assert redis_store.get_job("qj") is None and redis_store.list_org_jobs(oid) == []
    assert redis_store.dequeue_job("xia") is None
    assert client.get("/agent/poll", headers=H).status_code == 401
    priv.post(f"/api/sysadmin/orgs/{oid}/enable", tok)
    H2 = _enroll("xia")
    assert client.get("/agent/poll", headers=H2).status_code == 200
    assert priv.post("/api/sysadmin/accounts/xia/disable", tok).status_code == 200
    assert redis_store.get_agent("xia") is None   # agent binding revoked outright
    assert client.get("/agent/poll", headers=H2).status_code == 401


def test_job_done_completes_the_task_and_failed_suspends_it():
    import workflow
    from conftest import make_client, start_task, window
    reset()
    org = make_client("alice", "PT A")
    nb, na = window()
    tids = [db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8",
                                "scan_mode": "cloud", "not_before": nb, "not_after": na}) for _ in range(2)]
    jobs = [start_task(t) for t in tids]
    H = _enroll("varuna-cloud")
    assert client.post(f"/agent/jobs/{jobs[0]}/status", headers=H, json={"status": "done"}).status_code == 200
    assert db.get_proposal(tids[0], org_id=None)["stage"] == "completed"
    assert client.post(f"/agent/jobs/{jobs[0]}/status", headers=H, json={"status": "done"}).status_code == 200  # repeat: ignored
    client.post(f"/agent/jobs/{jobs[1]}/status", headers=H, json={"status": "failed", "error": "target refused connection"})
    t = db.get_proposal(tids[1], org_id=None)
    assert (t["scan_state"], t["suspend_reason"]) == ("suspended", "target refused connection")
    assert db.list_task_events(tids[1])[-1]["actor"] == workflow.SYSTEM
