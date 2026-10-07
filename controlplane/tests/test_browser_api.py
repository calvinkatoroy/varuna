"""Browser JSON API: JWT auth + role gating + scan submission reusing the dispatch gate.

Proves the FastAPI replacement for the Streamlit public UI enforces the same security: no
token = rejected, bad creds = rejected, and submission still routes through the Approval
Gate (Standard cloud gated, Standard local dispatched). Offline, FakeRedis-backed.
"""
import datetime
import os
import sys

os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"   # tests log team roles in via the public app
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "api"))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import db  # noqa: E402
import models  # noqa: E402
import tokens  # noqa: E402
import browser  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(browser.app)
LOCAL, CLOUD = "http://10.0.0.5", "http://8.8.8.8"   # classify without DNS


def reset():
    redis_store._client = FakeRedis()


def _token(username, role):
    auth.create_account(username, "pw", role, org_id=db.create_org("org-" + username) if role == "client" else None)
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
    r = client.post("/api/register", json={"username": "carol", "password": "pw123456"})
    assert r.status_code == 200 and "token" in r.json(), r.text
    # duplicate username is rejected
    r2 = client.post("/api/register", json={"username": "carol", "password": "pw123456"})
    assert r2.status_code == 409


def test_legacy_report_download_tenancy():
    """/api/reports/{fname}/download (the older, filename-addressed download used by the
    legacy Executive-Summary generator) still enforces tenancy independent of /api/reports'
    listing, which now sources from the v2 delivered-report pipeline (see the next test)."""
    reset()
    Ha = _token("alice", "client")
    _token("bob", "client")
    Ht = _token("riyan", "pentester")
    fa = browser.report_store.save_report("alice", "job-a", "Executive Summary", b"A")["file"]
    fb = browser.report_store.save_report("bob", "job-b", "Executive Summary", b"B")["file"]
    assert client.get(f"/api/reports/{fb}/download", headers=Ha).status_code == 403
    assert client.get(f"/api/reports/{fa}/download", headers=Ha).status_code == 200
    assert client.get(f"/api/reports/{fa}/download", headers=Ht).status_code == 200


def test_reports_list_is_v2_delivered_and_tenant_scoped():
    reset()
    Ha = _token("alice", "client")
    _token("bob", "client")
    Ht = _token("riyan", "pentester")
    ra_id = db.create_report(job_id="job-a", owner="alice")
    db.set_report(ra_id, stage=models.REPORT_DELIVERED, delivered_pdf="a.pdf")
    rb_id = db.create_report(job_id="job-b", owner="bob")
    db.set_report(rb_id, stage=models.REPORT_DELIVERED, delivered_pdf="b.pdf")
    # a report still in review (not delivered yet) must not show up for anyone via this list
    db.set_report(db.create_report(job_id="job-c", owner="alice"), stage=models.REPORT_LEAD)

    ra = client.get("/api/reports", headers=Ha).json()
    assert {r["id"] for r in ra} == {ra_id}
    rt = client.get("/api/reports", headers=Ht).json()
    assert {r["id"] for r in rt} == {ra_id, rb_id}


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
    # /api/proposals reshapes for the client UI (see _client_proposal_view) and doesn't carry
    # `submitter` - a fresh DB (reset() above) means alice's own list is just this one proposal,
    # so id-scoping alone proves tenancy without needing that field.
    assert [p["id"] for p in client.get("/api/proposals", headers=Ha).json()] == [pid]
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


def test_client_proposals_list_uses_client_status_vocabulary():
    """Regression: the list endpoint used to return the raw DB status (pending/approved/
    rejected) straight through, which crashed the frontend the moment a proposal was approved
    (it only knows pending/scanning/in_review/delivered/rejected). Every field the client UI
    actually reads (status/when/reason/job_id) must be present with the right name/vocabulary."""
    reset()
    Hc = _token("alice", "client")
    Hlead = _token("riyan", "lead_pentester")

    pending_id = client.post("/api/proposals", json={"target": "http://a.example",
                             "authorization_attested": True}, headers=Hc).json()["proposal_id"]
    approved_id = client.post("/api/proposals", json={"target": CLOUD,
                              "authorization_attested": True}, headers=Hc).json()["proposal_id"]
    client.post(f"/api/proposals/{approved_id}/approve", headers=Hlead)
    rejected_id = client.post("/api/proposals", json={"target": "http://b.example",
                              "authorization_attested": True}, headers=Hc).json()["proposal_id"]
    client.post(f"/api/proposals/{rejected_id}/reject", json={"reason": "not authorized"}, headers=Hlead)

    rows = {p["id"]: p for p in client.get("/api/proposals", headers=Hc).json()}
    assert rows[pending_id]["status"] == "pending"
    assert rows[approved_id]["status"] == "scanning"   # approved, no report yet
    assert rows[approved_id]["job_id"]
    assert rows[rejected_id]["status"] == "rejected"
    assert rows[rejected_id]["reason"] == "not authorized"
    for p in rows.values():
        assert "when" in p and "submitter" not in p


def test_protected_endpoint_needs_token():
    reset()
    assert client.get("/api/scans/x").status_code == 401
    assert client.get("/api/scans/x", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_me_returns_identity():
    reset()
    H = _token("calvin", "pentester")
    body = client.get("/api/me", headers=H).json()
    assert body == {"username": "calvin", "role": "pentester", "org_id": None, "must_change_password": False}


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
    db.save_findings("jr", "staff", [{"name": "X", "severity": "high", "host": "h",
                                      "impact": "i", "remediation": "r"}])
    meta = client.post("/api/scans/jr/report", headers=H).json()
    assert meta["template"] == "Executive Summary"
    dl = client.get(f"/api/reports/{meta['file']}/download", headers=H)
    assert dl.status_code == 200 and dl.content[:2] == b"PK"
    # /api/reports itself is a separate, v2-delivered-only listing now (see
    # test_reports_list_is_v2_delivered_and_tenant_scoped) - this legacy generate/download
    # path doesn't feed it, by design.


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_browser_api: all green")


def test_client_delivered_pdf_and_view_once_password():
    reset()
    Ha = _token("alice", "client")
    Hb = _token("bob", "client")
    rid = db.create_report(job_id="j1", owner="alice")
    db.set_report(rid, stage=models.REPORT_DELIVERED, delivered_pdf=f"{rid}.pdf",
                  pdf_password="pw123", password_viewed=0)
    browser.report_store.save_report_file(f"{rid}.pdf", b"%PDF-1.4 fake")
    assert client.get(f"/api/reports/{rid}/delivered", headers=Hb).status_code == 403  # not owner
    r = client.get(f"/api/reports/{rid}/delivered", headers=Ha)
    assert r.status_code == 200 and r.content == b"%PDF-1.4 fake"
    p = client.get(f"/api/reports/{rid}/password", headers=Ha)
    assert p.status_code == 200 and p.json()["password"] == "pw123"
    assert client.get(f"/api/reports/{rid}/password", headers=Ha).status_code == 403  # view-once


def test_client_cannot_access_undelivered_report():
    reset()
    Ha = _token("alice", "client")
    rid = db.create_report(job_id="j2", owner="alice")   # still at reporter stage
    assert client.get(f"/api/reports/{rid}/delivered", headers=Ha).status_code == 409


def test_cockpit_is_client_only_and_scoped():
    reset()
    Ha = _token("alice", "client")
    Ht = _token("riyan", "pentester")
    assert client.get("/api/cockpit", headers=Ht).status_code == 403   # team has no cockpit
    r = client.post("/api/proposals", headers=Ha,
                    json={"target": "http://t.example", "authorization_attested": True})
    assert r.status_code == 200
    c = client.get("/api/cockpit", headers=Ha).json()
    assert c["me"]["username"] == "alice"
    assert c["engagements"][0]["target"] == "http://t.example"
    assert c["posture"]["total"] == 0 and c["latestReport"] is None


def test_client_findings_are_own_confirmed_only():
    reset()
    Ha = _token("alice", "client")
    Hb = _token("bob", "client")
    Ht = _token("riyan", "pentester")
    db.save_findings("ja", "alice", [
        {"name": "SQLi", "severity": "critical", "host": "h"},
        {"name": "FalsePos", "severity": "low", "host": "h2"},
    ])
    db.save_findings("jb", "bob", [{"name": "XSS", "severity": "high", "host": "h3"}])
    fp_id = next(f["id"] for f in db.get_findings("ja") if f["name"] == "FalsePos")
    db.set_finding(fp_id, verdict="fp")

    ra = client.get("/api/findings", headers=Ha).json()
    assert {f["name"] for f in ra} == {"SQLi"}   # bob's finding hidden, fp hidden

    rt = client.get("/api/findings", headers=Ht).json()
    assert {f["name"] for f in rt} == {"SQLi", "FalsePos", "XSS"}   # team sees everything

    sqli_id = ra[0]["id"]
    assert client.post(f"/api/findings/{sqli_id}/status", headers=Hb,
                       json={"status": "fixed"}).status_code == 403   # bob doesn't own alice's finding
    assert client.post(f"/api/findings/{sqli_id}/status", headers=Ha,
                       json={"status": "fixed"}).status_code == 200
    assert db.get_findings("ja")[0]["status"] == "fixed"


# --- v2 live scan progress (SSE) ---
import json  # noqa: E402
import threading  # noqa: E402
import time as _time  # noqa: E402


def _sse_frames(resp) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in resp.iter_lines() if line.startswith("data: ")]


def test_scan_events_tenancy():
    reset()
    Ha = _token("alice", "client")
    Hb = _token("bob", "client")
    redis_store.set_job({"id": "je1", "target": "http://t", "submitter": "alice",
                         "status": "done", "per_tool_status": {}})
    assert client.get("/api/scans/je1/events", headers=Hb).status_code == 403
    assert client.get("/api/scans/nope/events", headers=Ha).status_code == 404
    with client.stream("GET", "/api/scans/je1/events", headers=Ha) as r:
        assert r.status_code == 200


def test_scan_events_closes_immediately_when_already_done():
    reset()
    H = _token("alice", "client")
    redis_store.set_job({"id": "je2", "target": "http://t", "submitter": "alice",
                         "status": "done", "per_tool_status": {"katana": "done", "nuclei": "done"}})
    with client.stream("GET", "/api/scans/je2/events", headers=H) as r:
        frames = _sse_frames(r)
    assert len(frames) == 1
    assert frames[0]["status"] == "done"
    assert frames[0]["per_tool_status"] == {"katana": "done", "nuclei": "done"}


def test_scan_events_streams_progress_until_done():
    reset()
    browser.SSE_POLL_INTERVAL = 0.05
    try:
        H = _token("alice", "client")
        redis_store.set_job({"id": "je3", "target": "http://t", "submitter": "alice",
                             "status": "running", "per_tool_status": {"katana": "running"}})

        def flip():
            _time.sleep(0.15)
            redis_store.set_job({"id": "je3", "target": "http://t", "submitter": "alice",
                                 "status": "running", "per_tool_status": {"katana": "done", "nuclei": "running"}})
            _time.sleep(0.15)
            redis_store.set_job({"id": "je3", "target": "http://t", "submitter": "alice",
                                 "status": "done", "per_tool_status": {"katana": "done", "nuclei": "done"}})

        threading.Thread(target=flip, daemon=True).start()
        with client.stream("GET", "/api/scans/je3/events", headers=H) as r:
            frames = _sse_frames(r)
    finally:
        browser.SSE_POLL_INTERVAL = 1.5

    assert frames[0]["per_tool_status"] == {"katana": "running"}
    assert frames[-1]["status"] == "done"
    assert frames[-1]["per_tool_status"] == {"katana": "done", "nuclei": "done"}
    assert len(frames) >= 3   # at least: initial, mid-transition, final
