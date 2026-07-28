"""Browser JSON API: JWT auth + role gating + scan submission reusing the dispatch gate.

Proves the FastAPI replacement for the Streamlit public UI enforces the same security: no
token = rejected, bad creds = rejected, and submission still routes through the Approval
Gate (Standard cloud gated, Standard local dispatched). Offline, FakeRedis-backed.
"""
import datetime
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "api"))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import tokens  # noqa: E402
import browser  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(browser.app)
LOCAL, CLOUD = "http://10.0.0.5", "http://8.8.8.8"   # classify without DNS


def reset():
    redis_store._client = FakeRedis()


def _token(username, role):
    auth.create_account(username, "pw", role)
    tokens.issue_agent_token(username)   # register an online agent
    r = client.post("/api/login", json={"username": username, "password": "pw"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_login_bad_credentials_rejected():
    reset()
    auth.create_account("bob", "right", "pentester")
    assert client.post("/api/login", json={"username": "bob", "password": "wrong"}).status_code == 401


def test_register_then_login():
    reset()
    r = client.post("/api/register", json={"username": "carol", "password": "pw12345"})
    assert r.status_code == 200 and "token" in r.json(), r.text
    # duplicate username is rejected
    r2 = client.post("/api/register", json={"username": "carol", "password": "pw12345"})
    assert r2.status_code == 409


def test_report_tenant_isolation():
    reset()
    Ha = _token("alice", "client")
    Hb = _token("bob", "client")   # noqa: F841 (seeds bob's account for realism)
    Ht = _token("riyan", "pentester")
    fa = browser.report_store.save_report("alice", "job-a", "Executive Summary", b"A")["file"]
    fb = browser.report_store.save_report("bob", "job-b", "Executive Summary", b"B")["file"]
    # client alice: own-only list, cannot download bob's, can download own
    ra = client.get("/api/reports", headers=Ha).json()
    assert all(m["user"] == "alice" for m in ra) and any(m["file"] == fa for m in ra)
    assert client.get(f"/api/reports/{fb}/download", headers=Ha).status_code == 403
    assert client.get(f"/api/reports/{fa}/download", headers=Ha).status_code == 200
    # team riyan: sees all clients, can download any
    rt = client.get("/api/reports", headers=Ht).json()
    assert {m["file"] for m in rt} >= {fa, fb}
    assert client.get(f"/api/reports/{fa}/download", headers=Ht).status_code == 200


def test_client_proposal_requires_attestation():
    reset()
    H = _token("alice", "client")
    r = client.post("/api/proposals",
                    json={"target": "http://t.example", "authorization_attested": False}, headers=H)
    assert r.status_code == 422


def test_client_submits_and_proposals_are_scoped():
    reset()
    Ha = _token("alice", "client")
    Hb = _token("bob", "client")
    Ht = _token("riyan", "pentester")
    r = client.post("/api/proposals",
                    json={"target": "http://t.example", "authorization_attested": True,
                          "division": "IT", "purpose": "pre-release"}, headers=Ha)
    assert r.status_code == 200 and r.json()["status"] == "pending", r.text
    pid = r.json()["proposal_id"]
    assert all(p["submitter"] == "alice" for p in client.get("/api/proposals", headers=Ha).json())
    assert any(p["id"] == pid for p in client.get("/api/proposals", headers=Ha).json())
    assert not any(p["id"] == pid for p in client.get("/api/proposals", headers=Hb).json())
    assert any(p["id"] == pid for p in client.get("/api/proposals", headers=Ht).json())
    assert client.get(f"/api/proposals/{pid}", headers=Hb).status_code == 403
    assert client.get(f"/api/proposals/{pid}", headers=Ha).status_code == 200
    assert client.get(f"/api/proposals/{pid}", headers=Ht).status_code == 200


def test_lead_approves_proposal_and_dispatches():
    reset()
    Hc = _token("alice", "client")
    Hlead = _token("riyan", "lead_pentester")
    Hpen = _token("dodi", "pentester")
    pid = client.post("/api/proposals",
                      json={"target": CLOUD, "authorization_attested": True}, headers=Hc).json()["proposal_id"]
    # only the lead may approve
    assert client.post(f"/api/proposals/{pid}/approve", headers=Hpen).status_code == 403
    r = client.post(f"/api/proposals/{pid}/approve", headers=Hlead)
    assert r.status_code == 200, r.text
    jid = r.json()["job_id"]
    assert r.json()["status"] == "approved" and jid
    p = client.get(f"/api/proposals/{pid}", headers=Hlead).json()
    assert p["status"] == "approved" and p["job_id"] == jid
    assert redis_store.dequeue_job("alice") == jid   # queued for the client's agent


def test_lead_rejects_proposal():
    reset()
    Hc = _token("alice", "client")
    Hlead = _token("riyan", "lead_pentester")
    pid = client.post("/api/proposals",
                      json={"target": CLOUD, "authorization_attested": True}, headers=Hc).json()["proposal_id"]
    r = client.post(f"/api/proposals/{pid}/reject", json={"reason": "out of scope"}, headers=Hlead)
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    p = client.get(f"/api/proposals/{pid}", headers=Hlead).json()
    assert p["status"] == "rejected" and p["reject_reason"] == "out of scope"


def test_protected_endpoint_needs_token():
    reset()
    assert client.get("/api/scans/x").status_code == 401
    assert client.get("/api/scans/x", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_me_returns_identity():
    reset()
    H = _token("calvin", "pentester")
    body = client.get("/api/me", headers=H).json()
    assert body == {"username": "calvin", "role": "pentester"}


def test_client_cannot_direct_submit_scan():
    reset()
    H = _token("staff", "client")
    # v2: clients must file a proposal; direct /api/scans is team-only
    assert client.post("/api/scans", headers=H, json={"target": CLOUD}).status_code == 403
    assert client.post("/api/scans", headers=H, json={"target": LOCAL}).status_code == 403


def test_team_can_direct_submit_scan():
    reset()
    H = _token("staff", "pentester")
    res = client.post("/api/scans", headers=H, json={"target": LOCAL}).json()
    assert res["state"] == "dispatched"


def test_submit_without_agent_rejected():
    reset()
    auth.create_account("noagent", "pw", "pentester")
    token = client.post("/api/login", json={"username": "noagent", "password": "pw"}).json()["token"]
    H = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/scans", headers=H, json={"target": LOCAL}).status_code == 409


def test_evasion_target_rejected():
    reset()
    H = _token("staff", "pentester")
    assert client.post("/api/scans", headers=H, json={"target": "http://0x7f000001"}).status_code == 422


def test_agent_status_and_install_token():
    reset()
    H = _token("calvin", "pentester")   # _token registers an agent
    st = client.get("/api/agent", headers=H).json()
    assert st["registered"] and st["online"]
    tok = client.post("/api/agent/install-token", headers=H).json()
    assert tok["enrollment_token"]


def test_approvals_are_pro_only():
    reset()
    H_std = _token("staff", "client")
    assert client.get("/api/approvals", headers=H_std).status_code == 403   # require_pro


# (legacy /api/approvals flow removed: v2 replaces it with proposal approve/reject, tested above)


def test_report_generate_and_download():
    reset()
    H = _token("staff", "client")
    redis_store.set_job({"id": "jr", "target": "http://t.local", "submitter": "staff",
                         "status": "done", "per_tool_status": {}})
    redis_store.set_findings("jr", [{"name": "X", "severity": "high", "host": "h",
                                     "impact": "i", "remediation": "r"}])
    meta = client.post("/api/scans/jr/report", headers=H).json()
    assert meta["template"] == "Executive Summary"
    dl = client.get(f"/api/reports/{meta['file']}/download", headers=H)
    assert dl.status_code == 200 and dl.content[:2] == b"PK"
    assert any(r["file"] == meta["file"] for r in client.get("/api/reports", headers=H).json())


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_browser_api: all green")
