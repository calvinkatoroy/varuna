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
    auth.create_account(username, "pw", "client")
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
    _db.save_findings("j2", "ihsan", [{"name": "SQLi", "severity": "critical", "host": "h",
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
    auth.create_account(username, "pw", role)
    return {"Authorization": f"Bearer {jwt_auth.login(username, 'pw', 'ip')}"}


def test_review_pipeline_forward_and_versions():
    reset()
    Hrep = _hdr("aisah", "reporter")
    Hlead = _hdr("riyan", "lead_pentester")
    Hpen = _hdr("dodi", "pentester")
    rid = _db.create_report(job_id="j1", owner="alice", template="Full Technical")
    # reporter uploads a new version
    r = client.post(f"/api/pipeline/reports/{rid}/version",
                    files={"file": ("edit.docx", EDITED, DOCX_MIME)}, headers=Hrep)
    assert r.status_code == 200 and r.json()["version_no"] == 1, r.text
    # a pentester does not own the reporter stage -> cannot forward
    assert client.post(f"/api/pipeline/reports/{rid}/forward", headers=Hpen).status_code == 403
    # reporter forwards -> lead
    assert client.post(f"/api/pipeline/reports/{rid}/forward", headers=Hrep).json()["stage"] \
        == models.REPORT_LEAD
    # lead uploads a version and forwards -> governance
    client.post(f"/api/pipeline/reports/{rid}/version",
                files={"file": ("lead.docx", LEAD_V, DOCX_MIME)}, headers=Hlead)
    assert client.post(f"/api/pipeline/reports/{rid}/forward", headers=Hlead).json()["stage"] \
        == models.REPORT_GOVERNANCE
    # lead sees all versions (history kept)
    versions = client.get(f"/api/pipeline/reports/{rid}/versions", headers=Hlead).json()
    assert [v["version_no"] for v in versions] == [1, 2]
    assert client.get(f"/api/pipeline/reports/{rid}/versions/1/download", headers=Hlead).content == EDITED


def test_review_pipeline_sendback():
    reset()
    Hgov = _hdr("hani", "governance")
    rid = _db.create_report(job_id="j2", owner="bob", stage=models.REPORT_GOVERNANCE)
    r = client.post(f"/api/pipeline/reports/{rid}/sendback", headers=Hgov)
    assert r.status_code == 200 and r.json()["stage"] == models.REPORT_LEAD


# --- v2 protected-PDF delivery (fake the docx->pdf converter; keep real pypdf encryption) ---
import io as _io  # noqa: E402
import pdf_deliver  # noqa: E402
from reportlab.pdfgen import canvas as _canvas  # noqa: E402
from pypdf import PdfReader as _PdfReader  # noqa: E402


def _fake_convert(_docx):
    b = _io.BytesIO(); c = _canvas.Canvas(b); c.drawString(72, 720, "stub"); c.showPage(); c.save()
    return b.getvalue()


pdf_deliver.CONVERT = _fake_convert


def test_governance_forward_delivers_protected_pdf():
    reset()
    Hgov = _hdr("hani", "governance")
    rid = _db.create_report(job_id="j3", owner="carol", stage=models.REPORT_GOVERNANCE)
    client.post(f"/api/pipeline/reports/{rid}/version",
                files={"file": ("final.docx", FINAL, DOCX_MIME)}, headers=Hgov)
    r = client.post(f"/api/pipeline/reports/{rid}/forward", headers=Hgov)
    assert r.status_code == 200 and r.json()["stage"] == models.REPORT_DELIVERED, r.text
    rep = _db.get_report(rid)
    assert rep["delivered_pdf"] and rep["pdf_password"] and rep["password_viewed"] is False
    data = report_store.read_report(rep["delivered_pdf"])
    assert _PdfReader(_io.BytesIO(data)).is_encrypted


def test_governance_reissue_password():
    reset()
    Hgov = _hdr("hani", "governance")
    Hrep = _hdr("aisah", "reporter")
    rid = _db.create_report(job_id="j4", owner="dan", stage=models.REPORT_GOVERNANCE)
    client.post(f"/api/pipeline/reports/{rid}/version",
                files={"file": ("f.docx", FINAL, DOCX_MIME)}, headers=Hgov)
    client.post(f"/api/pipeline/reports/{rid}/forward", headers=Hgov)   # -> delivered
    _db.set_report(rid, password_viewed=1)                              # client already viewed
    assert client.post(f"/api/pipeline/reports/{rid}/reissue-password", headers=Hrep).status_code == 403
    r = client.post(f"/api/pipeline/reports/{rid}/reissue-password", headers=Hgov)
    assert r.status_code == 200 and r.json()["password"]
    assert _db.get_report(rid)["password_viewed"] is False


def test_pipeline_create_generates_v1_owned_by_client():
    reset()
    H = _hdr("dodi", "pentester")
    redis_store.set_job({"id": "jc", "target": "http://t", "submitter": "alice",
                         "status": "done", "per_tool_status": {}})
    _db.save_findings("jc", "alice", [{"name": "X", "severity": "high", "host": "h"}])
    r = client.post("/api/pipeline/reports", json={"job_id": "jc", "template": "Full Technical"}, headers=H)
    assert r.status_code == 200 and r.json()["stage"] == models.REPORT_REPORTER, r.text
    rid = r.json()["report_id"]
    assert len(client.get(f"/api/pipeline/reports/{rid}/versions", headers=H).json()) == 1
    assert _db.get_report(rid)["owner"] == "alice"


# --- v2 board/detail/verdict views ---
def test_board_requires_team():
    reset()
    Hc = _hdr("alice", "client")
    assert client.get("/api/pipeline/board", headers=Hc).status_code == 403


def test_board_shape_and_stages():
    reset()
    H = _hdr("riyan", "lead_pentester")
    pid = _db.create_proposal({"submitter": "alice", "target": "http://t", "mode": "standard"})
    r = client.get("/api/pipeline/board", headers=H).json()
    ids = [c["id"] for c in r]
    assert ids == ["pending", "scanning", "in_review_reporter", "in_review_lead",
                   "in_review_governance", "delivered", "rejected"]
    pending = next(c for c in r if c["id"] == "pending")["cards"]
    assert pending[0]["id"] == pid and pending[0]["client"] == "alice"

    _db.update_proposal(pid, status="approved", job_id="j-scan")
    redis_store.set_job({"id": "j-scan", "submitter": "alice", "status": "running", "per_tool_status": {}})
    scanning = next(c for c in client.get("/api/pipeline/board", headers=H).json()
                    if c["id"] == "scanning")["cards"]
    assert scanning[0]["jobId"] == "j-scan" and scanning[0]["suspended"] is False


def test_detail_for_proposal_and_report():
    reset()
    H = _hdr("riyan", "lead_pentester")
    pid = _db.create_proposal({"submitter": "alice", "target": "http://t", "mode": "standard",
                               "purpose": "Compliance", "division": "IT",
                               "authorization_attested": True})
    d = client.get(f"/api/pipeline/detail/{pid}", headers=H).json()
    assert d["proposal"]["purpose"] == "Compliance" and d["proposal"]["authorized"] is True
    assert "versions" not in d

    rid = _db.create_report(job_id="jd", owner="alice")
    _db.add_report_version(rid, filename="f.docx", editor="aisah", note="v1")
    _db.update_proposal(pid, job_id="jd")
    d2 = client.get(f"/api/pipeline/detail/{rid}", headers=H).json()
    assert d2["proposal"]["purpose"] == "Compliance"
    assert len(d2["versions"]) == 1 and d2["versions"][0]["editor"] == "aisah"

    assert client.get("/api/pipeline/detail/nope", headers=H).status_code == 404


def test_suspend_resume_requires_team_and_flags_job():
    reset()
    Ht = _hdr("riyan", "lead_pentester")
    Hc = _hdr("alice", "client")
    redis_store.set_job({"id": "js", "target": "http://t", "submitter": "alice",
                         "status": "running", "per_tool_status": {}})

    assert client.post("/api/pipeline/scans/js/suspend", headers=Hc).status_code == 403
    assert client.post("/api/pipeline/scans/nope/suspend", headers=Ht).status_code == 404

    r = client.post("/api/pipeline/scans/js/suspend", headers=Ht)
    assert r.status_code == 200 and redis_store.is_suspended("js") is True

    r = client.post("/api/pipeline/scans/js/resume", headers=Ht)
    assert r.status_code == 200 and redis_store.is_suspended("js") is False


def test_finding_verdict_requires_team_and_updates():
    reset()
    Ht = _hdr("aisah", "reporter")
    Hc = _hdr("alice", "client")
    _db.save_findings("jf", "alice", [{"name": "X", "severity": "low", "host": "h"}])
    fid = _db.get_findings("jf")[0]["id"]
    assert client.post(f"/api/findings/{fid}/verdict", json={"verdict": "fp"},
                       headers=Hc).status_code == 403
    r = client.post(f"/api/findings/{fid}/verdict", json={"verdict": "fp"}, headers=Ht)
    assert r.status_code == 200 and _db.get_findings("jf")[0]["verdict"] == "fp"
