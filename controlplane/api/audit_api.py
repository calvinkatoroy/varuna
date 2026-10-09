"""Audit page routes (step 4): everything a pentester does to a task's report while it is Completed, plus the
read-only views every team role gets. Task rows are loaded through the staff scope; `org_id` never comes from a request."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))

from fastapi import APIRouter, Depends, HTTPException, Response  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

import audit  # noqa: E402
import db  # noqa: E402
import deps  # noqa: E402
import pdfjobs  # noqa: E402
import pdfpass  # noqa: E402
import ratelimit  # noqa: E402
import reportdoc  # noqa: E402
import store as report_store  # noqa: E402
import workflow  # noqa: E402
from deps import require_team  # noqa: E402
from tenancy import Scope  # noqa: E402

router = APIRouter(prefix="/api/tasks/{tid}")
AUDIT_STAGES = frozenset({"completed", "review_lead_pentester", "review_lead_cyber", "review_governance",
                          "review_manager", workflow.DELIVERING, "delivered"})


def _task(tid: str, scope: Scope) -> dict:
    t = db.get_proposal(tid, org_id=scope.org_id)
    if not t:
        raise HTTPException(status_code=404, detail="no such task")
    return t


def require_owner(task: dict, user: dict) -> None:
    """Writes: Completed stage (409 otherwise) and the assignee or a lead pentester (403 otherwise)."""
    if task["stage"] != "completed":
        raise HTTPException(status_code=409, detail="The report can only be changed while the task is Completed. "
                                                    "Send it back to change it.")
    if not workflow.can_audit(task, user["username"]):
        raise HTTPException(status_code=403, detail="only the assignee or a lead pentester can change this report")


def _rate(fn, *a):
    try:
        return fn(*a)
    except ratelimit.RateLimited as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.post("/report/generate")
def generate(tid: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    t = _task(tid, scope)
    require_owner(t, user)
    job, code = _rate(pdfjobs.request_pdf, t, user["username"])
    return JSONResponse(status_code=code, content={"job": pdfjobs.view(job)})


@router.get("/report/jobs/{jid}")
def job_status(tid: str, jid: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    t = _task(tid, scope)
    job = db.get_pdf(jid, task_id=t["id"])
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    return pdfjobs.view(job)


@router.get("/report/pdfs/{jid}/download")
def download_pdf(tid: str, jid: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    t = _task(tid, scope)
    p = db.get_pdf(jid, task_id=t["id"])
    if not p or p["status"] != "ready":
        raise HTTPException(status_code=404, detail="no such PDF")
    try:
        data = report_store.read_report(p["stored_name"])
    except OSError:
        raise HTTPException(status_code=404, detail="the PDF file is missing")
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": reportdoc.content_disposition(p["filename"]), "Cache-Control": "no-store"})


@router.get("/report/password")
def pdf_password(tid: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    t = _task(tid, scope)
    if not db.latest_ready_pdf(t["id"]):
        raise HTTPException(status_code=409, detail="No PDF has been generated yet.")
    pw = pdfpass.ensure(reportdoc.ensure_report(t)["id"])
    db.add_audit(t["id"], t["org_id"], user["username"], "password_view", "", {})
    audit.log("pdf_password_view", actor=user["username"], task=t["id"])
    return JSONResponse(content={"password": pw}, headers={"Cache-Control": "no-store"})
