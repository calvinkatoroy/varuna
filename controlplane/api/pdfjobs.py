"""PDF report jobs: claim -> worker thread -> ready/failed. The request thread only enqueues; LibreOffice
conversion (up to 180 s) runs on a one-thread pool, serialised by pdf_deliver's lock anyway."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))

import audit  # noqa: E402
import db  # noqa: E402
import pdf_deliver  # noqa: E402
import pdfpass  # noqa: E402
import ratelimit  # noqa: E402
import reportcontent  # noqa: E402
import reportdoc  # noqa: E402
import reportrender  # noqa: E402
import store as report_store  # noqa: E402

log = logging.getLogger("varuna.pdfjobs")
GEN_LIMIT = int(os.environ.get("VARUNA_PDF_PER_10MIN") or "5")
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="varuna-pdf")
_VIEW = ("id", "n", "status", "filename", "content_version", "error", "requested_by", "created_at", "updated_at")


def _submit(jid: str) -> None:
    POOL.submit(run_job, jid)


def view(row):
    """What the browser may see of a job: never the stored file name or the digest."""
    return {k: row.get(k) for k in _VIEW} if row else None


def summary(task: dict) -> dict:
    return {"current": reportdoc.pdf_gap(task) is None, "latest": view(db.latest_ready_pdf(task["id"])),
            "active": view(db.active_pdf(task["id"])), "history": [view(r) for r in db.list_pdfs(task["id"], 10)]}


def request_pdf(task: dict, actor: str, inline: bool = False):
    """-> (job row, http status). 202: a job is queued or running (the same one for every caller). 200: the latest
    ready PDF already matches the report, nothing was created."""
    db.reap_pdfs(db.PDF_STALE_S)
    for _ in range(3):
        active = db.active_pdf(task["id"])
        if active:
            return active, 202
        content = reportcontent.ensure_v1(task)
        if db.latest_ready_pdf(task["id"]) and reportdoc.pdf_gap(task) is None:
            return db.latest_ready_pdf(task["id"]), 200
        ratelimit.hit(f"pdfgen:{actor}", GEN_LIMIT, 600)
        job, created = db.claim_pdf(task["id"], task["org_id"], content["version"], actor)
        if job is None:   # the active job finished between the failed insert and the read: look again
            continue
        if created:
            db.add_audit(task["id"], task["org_id"], actor, "pdf_requested", job["id"], {"content_version": content["version"]})
            if inline:
                run_job(job["id"])
            else:
                _submit(job["id"])
            job = db.get_pdf(job["id"])
        return job, 202
    raise RuntimeError("could not claim a PDF job")


def _public_error(e: Exception) -> str:
    """A fixed sentence per failure kind. The exception text (paths, tool output) never reaches the page."""
    if isinstance(e, pdfpass.Unavailable):
        return str(e)
    if isinstance(e, subprocess.TimeoutExpired):
        return "PDF conversion timed out. Try again."
    if isinstance(e, FileNotFoundError):
        return "The PDF converter is not installed on the server."
    if isinstance(e, subprocess.CalledProcessError):
        return "PDF conversion failed. Try again."
    return "PDF generation failed. Try again."


def run_job(jid: str) -> None:
    job = db.get_pdf(jid)
    if not job or not db.set_pdf_state(jid, "rendering"):
        return
    stored = None
    try:
        task = db.get_proposal(job["task_id"], org_id=None)
        findings = reportdoc.findings_for(task)          # ONE snapshot: rendered AND digested
        dg = reportdoc.digest(findings)
        content = db.get_content(task["id"], job["content_version"])["content"]
        org_name = (db.get_org(task["org_id"]) or {}).get("name", "")
        docx = reportrender.render_docx(content, task, org_name, findings)
        if not db.set_pdf_state(jid, "converting"):
            return
        password = pdfpass.ensure(reportdoc.ensure_report(task)["id"])
        pdf = pdf_deliver.deliver(docx, password)
        stored = f"pdf-{uuid.uuid4().hex}.pdf"
        report_store.save_report_file(stored, pdf)
        row = db.finish_pdf(jid, task["id"], dg, stored,
                            lambda n: reportdoc.pdf_filename(org_name, task["target"], n))
        if row is None:   # reaped while converting: the file is an orphan
            _discard(stored)
        else:
            audit.log("pdf_generated", actor=job["requested_by"], task=task["id"], n=row["n"])
    except Exception as e:   # never raises into the pool; the previous PDF is untouched
        log.exception("PDF job %s for task %s failed", jid, job["task_id"])   # full traceback stays on the server
        if stored:
            _discard(stored)
        db.set_pdf_state(jid, "failed", _public_error(e))
        audit.log("pdf_failed", actor=job["requested_by"], task=job["task_id"], kind=type(e).__name__)


def _discard(stored: str) -> None:
    try:
        os.remove(os.path.join(report_store.REPORTS_DIR, stored))
    except OSError:
        pass
