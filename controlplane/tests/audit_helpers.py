"""Shared setup for the step 4 tests: one org, one completed task with two findings, five staff accounts, a fake
PDF converter and inline job runners."""
import io
import os
import sys
from types import SimpleNamespace

HERE = os.path.dirname(__file__)
for _sub in ("common", "api", "report", "pipeline"):
    sys.path.insert(0, os.path.join(HERE, "..", _sub))
sys.path.insert(0, HERE)

import auth  # noqa: E402
import db  # noqa: E402
import pdf_deliver  # noqa: E402
import redis_store  # noqa: E402
import store as report_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402
from conftest import make_client, window  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

PW = "Passw0rd!x"


def fake_pdf(_docx):
    b = io.BytesIO()
    c = canvas.Canvas(b)
    c.drawString(72, 720, "stub report")
    c.showPage()
    c.save()
    return b.getvalue()


def world(monkeypatch, tmp_path, stage="completed"):
    import pdfjobs
    redis_store._client = FakeRedis()
    monkeypatch.setattr(report_store, "REPORTS_DIR", str(tmp_path))
    monkeypatch.setattr(pdf_deliver, "CONVERT", fake_pdf)
    monkeypatch.setattr(pdfjobs, "_submit", pdfjobs.run_job)   # jobs run in the request thread
    org = make_client("alice", "PT A")
    for name, role in (("rizky", "pentester"), ("budi", "pentester"), ("dewi", "lead_pentester"),
                       ("agus", "lead_cyber"), ("sari", "governance")):
        auth.create_account(name, PW, role)
    nb, na = window()
    tid = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8", "stage": stage,
                              "assignee": "rizky", "job_id": "j1", "not_before": nb, "not_after": na,
                              "scan_mode": "cloud"})
    db.save_findings("j1", "alice", org, [
        {"name": "SQL injection", "severity": "critical", "host": "8.8.8.8", "url": "/a?id=1",
         "evidence": "SECRET-EVIDENCE-1", "impact": "Data theft.", "remediation": "Use bound parameters."},
        {"name": "Missing header", "severity": "low", "host": "8.8.8.8", "url": "/",
         "evidence": "SECRET-EVIDENCE-2", "impact": "Minor.", "remediation": "Add the header."}])
    fids = {f["name"]: f["id"] for f in db.get_findings("j1")}
    return SimpleNamespace(org=org, tid=tid, fids=fids)
