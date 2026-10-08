"""Private-plane API: Pro-only findings review, manual input, full report generation.

Proves the FastAPI replacement for the Streamlit private UI keeps Pro-only gating and reuses
the manual-finding + report pipeline. Offline, FakeRedis-backed, Ollama falls back.
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import db  # noqa: E402
import jwt_auth  # noqa: E402
import ollama  # noqa: E402
import private_api  # noqa: E402
import store as report_store  # noqa: E402
import tempfile  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

report_store.REPORTS_DIR = tempfile.mkdtemp()
ollama.OLLAMA_URL = "http://127.0.0.1:1"   # graceful fallback
client = TestClient(private_api.app)


def reset():
    redis_store._client = FakeRedis()


def docx_bytes(text="x"):
    """A real minimal .docx: uploads are validated (empty/non-docx bytes are rejected)."""
    import io
    import docx
    d = docx.Document(); d.add_paragraph(text)
    b = io.BytesIO(); d.save(b)
    return b.getvalue()


EDITED, LEAD_V, FINAL = docx_bytes("edited"), docx_bytes("lead"), docx_bytes("final")


def _pro_header(username="ihsan"):
    auth.create_account(username, "pw", "pentester")
    return {"Authorization": f"Bearer {jwt_auth.login(username, 'pw', 'ip')}"}


def _std_header(username="staff"):
    auth.create_account(username, "pw", "client", org_id=db.create_org("org-" + username))
    return {"Authorization": f"Bearer {jwt_auth.login(username, 'pw', 'ip')}"}


def test_findings_pro_only():
    reset()
    assert client.get("/api/findings/j1", headers=_std_header()).status_code == 403


def test_manual_finding_then_review():
    reset()
    H = _pro_header()
    redis_store.set_job({"id": "j1", "target": "http://t", "submitter": "ihsan",
                         "status": "done", "per_tool_status": {}})
    r = client.post("/api/findings/j1/manual", headers=H, json={
        "name": "IDOR", "severity": "high", "host": "http://t",
        "url": "http://t/x", "description": "d", "evidence": "e"})
    assert r.status_code == 200 and r.json()[0]["tool"] == "manual"
    review = client.get("/api/findings/j1", headers=H).json()
    assert review[0]["name"] == "IDOR"


def test_full_report_templates_and_archive():
    reset()
    H = _pro_header()
    redis_store.set_job({"id": "j2", "target": "http://t", "submitter": "ihsan",
                         "status": "done", "per_tool_status": {}})
    _db.save_findings("j2", "ihsan", "", [{"name": "SQLi", "severity": "critical", "host": "h",
                                       "cve": "CVE-1", "evidence": "x", "owasp": "A03:2021-Injection"}])
    for template in ("Full Technical", "OWASP Web App", "ILCS Internal"):
        r = client.post("/api/reports/generate", headers=H, json={"job_id": "j2", "template": template})
        assert r.status_code == 200, f"{template}: {r.text}"
    archive = client.get("/api/reports/all", headers=H).json()
    assert len(archive) == 3


def test_manual_missing_job_404():
    reset()
    H = _pro_header()
    r = client.post("/api/findings/none/manual", headers=H,
                    json={"name": "x", "severity": "low", "host": "h"})
    assert r.status_code == 404


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_private_api: all green")


# --- v2 report review pipeline ---
import db as _db  # noqa: E402
import models  # noqa: E402

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _hdr(username, role):
    auth.create_account(username, "pw", role, org_id=db.create_org("org-" + username) if role == "client" else None)
    return {"Authorization": f"Bearer {jwt_auth.login(username, 'pw', 'ip')}"}


def _review_task(stage, job_id, assignee="aisah"):
    org = _db.create_org("PT " + job_id)
    tid = _db.create_proposal({"submitter": "alice", "target": "http://t", "org_id": org, "stage": stage,
                               "job_id": job_id, "assignee": assignee})
    rid = _db.create_report(job_id, org, "alice", template="Full Technical")
    return tid, rid


def _move(H, tid, to, **body):
    return client.post(f"/api/tasks/{tid}/transition", headers=H,
                       json={"to": to, "version": _db.get_proposal(tid, org_id=None)["version"], **body})


def test_review_pipeline_versions_follow_the_task_stage():
    reset()
    Hpen = _hdr("aisah", "pentester")
    Hlead = _hdr("riyan", "lead_pentester")
    Hgov = _hdr("dodi", "governance")
    tid, rid = _review_task("completed", "j1")
    up = lambda H, data: client.post(f"/api/pipeline/reports/{rid}/version", files={"file": ("e.docx", data, DOCX_MIME)}, headers=H)
    r = up(Hpen, EDITED)                                       # the assignee edits at `completed`
    assert r.status_code == 200 and r.json()["version_no"] == 1, r.text
    assert up(Hgov, EDITED).status_code == 403                 # governance does not own this stage
    assert _move(Hpen, tid, "review_lead_pentester").status_code == 200
    assert up(Hlead, LEAD_V).status_code == 200                # the lead pentester owns the first review
    assert _move(Hlead, tid, "review_lead_cyber").json()["stage"] == "review_lead_cyber"
    versions = client.get(f"/api/pipeline/reports/{rid}/versions", headers=Hlead).json()
    assert [v["version_no"] for v in versions] == [1, 2]
    assert client.get(f"/api/pipeline/reports/{rid}/versions/1/download", headers=Hlead).content == EDITED


def test_review_pipeline_sendback_needs_a_comment():
    reset()
    Hgov = _hdr("hani", "governance")
    tid, _ = _review_task("review_governance", "j2")
    assert _move(Hgov, tid, "review_lead_cyber").status_code == 422
    r = _move(Hgov, tid, "review_lead_cyber", comment="severity of XSS looks too high")
    assert r.status_code == 200 and r.json()["stage"] == "review_lead_cyber"


# --- v2 protected-PDF delivery (fake the docx->pdf converter; keep real pypdf encryption) ---
import io as _io  # noqa: E402
import pdf_deliver  # noqa: E402
from reportlab.pdfgen import canvas as _canvas  # noqa: E402
from pypdf import PdfReader as _PdfReader  # noqa: E402


def _fake_convert(_docx):
    b = _io.BytesIO(); c = _canvas.Canvas(b); c.drawString(72, 720, "stub"); c.showPage(); c.save()
    return b.getvalue()


pdf_deliver.CONVERT = _fake_convert


def test_manager_approval_delivers_protected_pdf():
    reset()
    Hgov, Hman = _hdr("hani", "governance"), _hdr("bayu", "manager")
    tid, rid = _review_task("review_manager", "j3")
    _db.add_report_version(rid, filename=f"{rid}_v1.docx", editor="hani")
    report_store.save_report_file(f"{rid}_v1.docx", FINAL)
    assert _move(Hgov, tid, "delivered").status_code == 403
    r = _move(Hman, tid, "delivered")
    assert r.status_code == 200 and r.json()["stage"] == "delivered", r.text
    rep = _db.get_report(rid, org_id=None)
    assert rep["stage"] == models.REPORT_DELIVERED and rep["delivered_pdf"] and rep["pdf_password"]
    assert rep["password_viewed"] is False
    assert _PdfReader(_io.BytesIO(report_store.read_report(rep["delivered_pdf"]))).is_encrypted


def test_governance_reissue_password():
    reset()
    Hgov, Hman, Hrep = _hdr("hani", "governance"), _hdr("bayu", "manager"), _hdr("aisah", "pentester")
    tid, rid = _review_task("review_manager", "j4")
    _db.add_report_version(rid, filename=f"{rid}_v1.docx", editor="hani")
    report_store.save_report_file(f"{rid}_v1.docx", FINAL)
    _move(Hman, tid, "delivered")
    _db.set_report(rid, password_viewed=1)                     # client already viewed
    assert client.post(f"/api/pipeline/reports/{rid}/reissue-password", headers=Hrep).status_code == 403
    r = client.post(f"/api/pipeline/reports/{rid}/reissue-password", headers=Hgov)
    assert r.status_code == 200 and r.json()["password"]
    assert _db.get_report(rid, org_id=None)["password_viewed"] is False


def test_finished_task_scan_generates_v1_owned_by_client():
    reset()
    import ingest
    org = _db.create_org("PT Alice")
    job = {"id": "jc", "target": "http://t", "submitter": "alice", "status": "done", "per_tool_status": {}, "org_id": org}
    redis_store.set_job(job)
    _db.create_proposal({"submitter": "alice", "target": "http://t", "org_id": org, "stage": "completed", "job_id": "jc"})
    _db.save_findings("jc", "alice", org, [{"name": "X", "severity": "high", "host": "h"}])
    rid = ingest.start_review(job)
    rep = _db.get_report(rid, org_id=org)
    assert rep["owner"] == "alice" and rep["org_id"] == org and rep["stage"] == models.REPORT_DRAFT
    assert len(_db.list_report_versions(rid)) == 1


# --- v2 board/detail/verdict views ---
def test_board_requires_team():
    reset()
    Hc = _hdr("alice", "client")
    assert client.get("/api/board", headers=Hc).status_code == 403


def test_board_shape_and_stages():
    reset()
    H = _hdr("riyan", "lead_pentester")
    org = _db.create_org("PT Alice")
    from conftest import window
    nb, na = window()
    pid = _db.create_proposal({"submitter": "alice", "target": "http://t", "org_id": org, "not_before": nb, "not_after": na})
    r = client.get("/api/board", headers=H).json()
    assert [c["id"] for c in r] == ["task", "scan", "completed", "review_lead_pentester", "review_lead_cyber",
                                    "review_governance", "review_manager", "delivered", "closed"]
    card = next(c for c in r if c["id"] == "task")["cards"][0]
    assert card["id"] == pid and card["client"] == "PT Alice" and card["version"] == 0   # the org, not the submitter
    assert {a["kind"] for a in card["actions"]} == {"claim", "decline"}

    running = _db.create_proposal({"submitter": "alice", "target": "http://t", "org_id": org, "stage": "scan",
                                   "scan_state": "in_progress", "job_id": "j-scan", "not_before": nb, "not_after": na})
    redis_store.set_job({"id": "j-scan", "submitter": "alice", "status": "running", "per_tool_status": {}})
    scan = next(c for c in client.get("/api/board", headers=H).json() if c["id"] == "scan")["cards"]
    assert next(c for c in scan if c["id"] == running)["jobId"] == "j-scan"


def test_detail_for_a_task_with_its_report():
    reset()
    H = _hdr("riyan", "lead_pentester")
    org = _db.create_org("PT Alice")
    pid = _db.create_proposal({"submitter": "alice", "target": "http://t", "org_id": org, "notes": "Compliance",
                               "stage": "completed", "job_id": "jd", "assignee": "riyan"})
    rid = _db.create_report("jd", org, "alice")
    _db.add_report_version(rid, filename="f.docx", editor="aisah", note="v1")
    d = client.get(f"/api/tasks/{pid}/detail", headers=H).json()
    assert d["task"]["notes"] == "Compliance" and d["report_id"] == rid
    assert len(d["versions"]) == 1 and d["versions"][0]["editor"] == "aisah"
    assert client.get("/api/tasks/nope/detail", headers=H).status_code == 404


def test_suspend_resume_requires_team_owner_and_reason_and_flags_job():
    reset()
    from conftest import window
    import tokens
    Ht = _hdr("riyan", "lead_pentester")
    Hc = _hdr("alice", "client")
    nb, na = window()
    pid = _db.create_proposal({"submitter": "alice", "target": "http://8.8.8.8", "scan_mode": "cloud",
                               "org_id": _db.get_account("alice")["org_id"], "stage": "scan", "scan_state": "in_progress",
                               "job_id": "js", "assignee": "riyan", "not_before": nb, "not_after": na})
    redis_store.set_job({"id": "js", "target": "http://t", "submitter": "alice", "status": "running", "per_tool_status": {}})
    move = lambda H, to, **b: client.post(f"/api/tasks/{pid}/transition", headers=H,
                                          json={"to": to, "version": _db.get_proposal(pid, org_id=None)["version"], **b})
    assert move(Hc, "scan/suspended", comment="x").status_code == 403
    assert move(Ht, "scan/suspended", comment="  ").status_code == 422
    assert move(Ht, "scan/suspended", comment="client maintenance").status_code == 200
    assert redis_store.is_suspended("js") is True
    tokens.issue_agent_token("varuna-cloud")
    assert move(Ht, "scan/in_progress").status_code == 200 and redis_store.is_suspended("js") is False


def test_finding_verdict_requires_team_and_updates():
    reset()
    Ht = _hdr("aisah", "pentester")
    Hc = _hdr("alice", "client")
    _db.save_findings("jf", "alice", _db.get_account("alice")["org_id"], [{"name": "X", "severity": "low", "host": "h"}])
    fid = _db.get_findings("jf")[0]["id"]
    assert client.post(f"/api/findings/{fid}/verdict", json={"verdict": "fp"},
                       headers=Hc).status_code == 403
    r = client.post(f"/api/findings/{fid}/verdict", json={"verdict": "fp"}, headers=Ht)
    assert r.status_code == 200 and _db.get_findings("jf")[0]["verdict"] == "fp"
