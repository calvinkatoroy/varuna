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


def test_protected_endpoint_needs_token():
    reset()
    assert client.get("/api/scans/x").status_code == 401
    assert client.get("/api/scans/x", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_me_returns_identity():
    reset()
    H = _token("calvin", "pentester")
    body = client.get("/api/me", headers=H).json()
    assert body == {"username": "calvin", "role": "pentester"}


def test_standard_cloud_is_gated():
    reset()
    H = _token("staff", "client")
    res = client.post("/api/scans", headers=H, json={"target": CLOUD}).json()
    assert res["state"] == "pending_approval", "Standard cloud target must hit the Approval Gate"


def test_standard_local_dispatched():
    reset()
    H = _token("staff", "client")
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


def test_approval_flow_via_api():
    reset()
    H_std = _token("staff", "client")
    H_pro = _token("ihsan", "pentester")
    job_id = client.post("/api/scans", headers=H_std, json={"target": CLOUD}).json()["job_id"]
    pending = client.get("/api/approvals", headers=H_pro).json()
    assert any(p["job_id"] == job_id for p in pending)
    assert client.post(f"/api/approvals/{job_id}/approve", headers=H_pro).status_code == 200
    assert client.get("/api/approvals", headers=H_pro).json() == []   # left the queue


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
