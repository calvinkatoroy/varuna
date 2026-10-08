"""Task API (step 2): client routes on the public plane, staff transitions on the private plane."""
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
import auth  # noqa: E402
import db  # noqa: E402
import workflow  # noqa: E402
from conftest import make_client, window  # noqa: E402

PW = "Passw0rd!x"


def _body(**over):
    nb, na = window()
    return {"target": "http://8.8.8.8", "path": "/app", "port": 8080, "notes": "login: demo/demo",
            "not_before": nb, "not_after": na, "scan_mode": "cloud", **over}


def test_client_creates_task_org_and_submitter_from_the_account(api):
    org = make_client("alice", "PT A")
    make_client("bob", "PT B")
    tok = api.login("alice", PW)
    r = api.post("/api/tasks", tok, _body(org_id=db.get_account("bob")["org_id"], submitter="bob", stage="delivered"))
    assert r.status_code == 200, r.text
    t = db.get_proposal(r.json()["id"], org_id=None)
    assert (t["org_id"], t["submitter"], t["stage"]) == (org, "alice", "task")
    assert r.json()["status"] == "waiting" and "assignee" not in r.json()


@pytest.mark.parametrize("over", [
    {"not_before": "2026-10-08T09:00:00"},                    # naive
    {"not_after": "2001-01-01T00:00:00+00:00", "not_before": "2000-01-01T00:00:00+00:00"},
    {"target": "javascript:alert(1)"}, {"path": "no-slash"}, {"port": 0}, {"port": "80; rm -rf"},
    {"scan_mode": "bogus"}, {"target": "http://10.0.0.5", "scan_mode": "cloud"},
])
def test_bad_task_fields_are_422(api, over):
    make_client("alice", "PT A")
    tok = api.login("alice", PW)
    assert api.post("/api/tasks", tok, _body(**over)).status_code == 422


def test_task_lists_and_reads_are_org_scoped(api):
    make_client("alice", "PT A")
    make_client("carol", "PT A")                               # colleague, same organization
    make_client("bob", "PT B")
    tid = api.post("/api/tasks", api.login("alice", PW), _body()).json()["id"]
    assert [t["id"] for t in api.get("/api/tasks", api.login("carol", PW)).json()] == [tid]
    bob = api.login("bob", PW)
    assert api.get("/api/tasks", bob).json() == []
    assert api.get(f"/api/tasks/{tid}", bob).status_code == 404
    assert api.get(f"/api/tasks/{tid}/events", bob).status_code == 404
    one = api.get(f"/api/tasks/{tid}", api.login("carol", PW)).json()
    assert one["timeline"] == [{"status": "waiting", "at": one["timeline"][0]["at"]}]


def test_client_sees_decline_cause_but_no_staff_detail(api):
    make_client("alice", "PT A")
    auth.create_account("rizky", PW, "pentester")
    tok = api.login("alice", PW)
    tid = api.post("/api/tasks", tok, _body()).json()["id"]
    workflow.transition(tid, "declined", "rizky", org_id=None, comment="Mohon kirim bukti kepemilikan")
    row = api.get("/api/tasks", tok).json()[0]
    assert row["status"] == "declined" and row["reason"] == "Mohon kirim bukti kepemilikan"
    assert "rizky" not in api.get(f"/api/tasks/{tid}", tok).text
    assert api.get(f"/api/tasks/{tid}/events", tok).json()[-1]["note"] == "Mohon kirim bukti kepemilikan"


def test_staff_cannot_create_tasks(api):
    auth.create_account("rizky", PW, "pentester")              # the api fixture enables dev team login
    assert api.post("/api/tasks", api.login("rizky", PW), _body()).status_code == 403


import io  # noqa: E402
import threading  # noqa: E402

import models  # noqa: E402
import redis_store  # noqa: E402
import tokens  # noqa: E402


def _staff(*pairs):
    for name, role in pairs:
        auth.create_account(name, PW, role)


def _new_task(stage="task", **extra):
    org = (db.get_account("alice") or {}).get("org_id") or make_client("alice", "PT A")
    nb, na = window()
    return db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8", "scan_mode": "cloud",
                               "not_before": nb, "not_after": na, "stage": stage, **extra})


def _move(priv, tok, tid, to, **body):
    version = db.get_proposal(tid, org_id=None)["version"]
    return priv.post(f"/api/tasks/{tid}/transition", tok, {"to": to, "version": version, **body})


def test_claim_start_and_stale_version_over_http(priv):
    _staff(("rizky", "pentester"))
    tid = _new_task()
    tok = priv.login("rizky", PW)
    r = _move(priv, tok, tid, "scan/pending")
    assert r.status_code == 200 and r.json()["version"] == 1, r.text
    stale = priv.post(f"/api/tasks/{tid}/transition", tok, {"to": "scan/scheduled", "version": 0, "scheduled_at": window()[1]})
    assert stale.status_code == 409
    tokens.issue_agent_token(models.CLOUD_AGENT)
    assert _move(priv, tok, tid, "scan/in_progress").json()["scan_state"] == "in_progress"
    assert priv.post("/api/tasks/nope/transition", tok, {"to": "declined", "version": 0}).status_code == 404


def test_transition_errors_map_to_status_codes(priv, api):
    _staff(("rizky", "pentester"), ("sari", "governance"))
    tid = _new_task()
    assert _move(priv, priv.login("sari", PW), tid, "scan/pending").status_code == 403
    assert _move(priv, priv.login("rizky", PW), tid, "declined", comment="   ").status_code == 422
    assert _move(priv, priv.login("rizky", PW), tid, "completed").status_code == 409
    client = api.login("alice", PW)                     # a client token on the private plane
    assert _move(priv, client, tid, "declined", comment="x").status_code == 403


def test_advanced_opts_on_start_are_sanitized_by_role(priv):
    _staff(("rizky", "pentester"), ("dewi", "lead_pentester"))
    tid = _new_task(stage="scan", scan_state="pending", assignee="rizky")
    tokens.issue_agent_token(models.CLOUD_AGENT)
    assert _move(priv, priv.login("rizky", PW), tid, "scan/in_progress", opts={"level": 5}).status_code == 422
    r = _move(priv, priv.login("dewi", PW), tid, "scan/in_progress", opts={"level": 5, "depth": 2})
    assert r.status_code == 200, r.text
    job = redis_store.get_job(db.get_proposal(tid, org_id=None)["job_id"])
    assert job["opts"]["aggressive"] is True and job["opts"]["depth"] == 2


def test_two_approvers_over_http_one_200_one_409(priv):
    _staff(("sari", "governance"), ("sari2", "governance"))
    tid = _new_task(stage="review_governance", assignee="rizky")
    toks = [priv.login("sari", PW), priv.login("sari2", PW)]
    barrier, codes = threading.Barrier(2), []

    def go(i):
        barrier.wait()
        codes.append(priv.post(f"/api/tasks/{tid}/transition", toks[i], {"to": "review_manager", "version": 0}).status_code)
    threads = [threading.Thread(target=go, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200, 409] and len(db.list_task_events(tid)) == 1


def _report_for(tid, tmp_path):
    import docx
    import store
    store.REPORTS_DIR = str(tmp_path)
    t = db.get_proposal(tid, org_id=None)
    rid = db.create_report(t["job_id"], t["org_id"], "alice")
    d = docx.Document(); d.add_paragraph("final"); b = io.BytesIO(); d.save(b)
    store.save_report_file(f"{rid}_v1.docx", b.getvalue())
    db.add_report_version(rid, filename=f"{rid}_v1.docx", editor="rizky")
    return rid


def test_manager_approval_delivers_the_protected_pdf(priv, tmp_path, monkeypatch):
    import pdf_deliver
    from reportlab.pdfgen import canvas

    def fake(_docx):
        b = io.BytesIO(); c = canvas.Canvas(b); c.drawString(72, 720, "x"); c.showPage(); c.save()
        return b.getvalue()
    monkeypatch.setattr(pdf_deliver, "CONVERT", fake)
    _staff(("hendra", "manager"))
    tid = _new_task(stage="review_manager", assignee="rizky", job_id="jdel")
    rid = _report_for(tid, tmp_path)
    r = _move(priv, priv.login("hendra", PW), tid, "delivered")
    assert r.status_code == 200 and r.json()["stage"] == "delivered", r.text
    rep = db.get_report(rid, org_id=None)
    assert rep["stage"] == "delivered" and rep["delivered_pdf"] and rep["pdf_password"]


def test_delivery_without_a_report_is_409_and_stage_restored(priv):
    _staff(("hendra", "manager"))
    tid = _new_task(stage="review_manager", assignee="rizky", job_id="jnone")
    assert _move(priv, priv.login("hendra", PW), tid, "delivered").status_code == 409
    assert db.get_proposal(tid, org_id=None)["stage"] == "review_manager"


def test_staff_events_and_detail(priv):
    _staff(("rizky", "pentester"))
    tid = _new_task()
    tok = priv.login("rizky", PW)
    _move(priv, tok, tid, "declined", comment="internal note")
    ev = priv.get(f"/api/tasks/{tid}/events", tok).json()
    assert ev[-1]["actor"] == "rizky" and ev[-1]["comment"] == "internal note"
    d = priv.get(f"/api/tasks/{tid}/detail", tok).json()
    assert d["task"]["decline_cause"] == "internal note" and d["report_id"] is None and d["versions"] == []
    assert priv.get("/api/tasks/nope/detail", tok).status_code == 404


def test_legacy_proposal_routes_are_gone(api, priv):
    make_client("alice", "PT A")
    tok = api.login("alice", PW)
    for path, method in (("/api/proposals", "POST"), ("/api/proposals", "GET"), ("/api/proposals/x", "GET"),
                         ("/api/proposals/x/approve", "POST"), ("/api/proposals/x/reject", "POST")):
        assert api.request(method, path, tok, json={}).status_code in (404, 405), path
    auth.create_account("dewi", PW, "lead_pentester")
    lead = priv.login("dewi", PW)
    for path, method in (("/api/proposals/x/approve", "POST"), ("/api/pipeline/scans/x/suspend", "POST"),
                         ("/api/pipeline/scans/x/resume", "POST"), ("/api/pipeline/detail/x", "GET")):
        assert priv.request(method, path, lead, json={}).status_code in (404, 405), path
    import models
    assert not hasattr(models, "PROPOSAL_PENDING") and not hasattr(models, "can_approve")


def test_install_token_unlocks_once_a_task_is_claimed(api):
    make_client("alice", "PT A")
    auth.create_account("rizky", PW, "pentester")
    tok = api.login("alice", PW)
    tid = api.post("/api/tasks", tok, _body(scan_mode="local")).json()["id"]
    assert api.post("/api/agent/install-token", tok).status_code == 403
    workflow.transition(tid, "scan/pending", "rizky", org_id=None)
    assert api.post("/api/agent/install-token", tok).status_code == 200
