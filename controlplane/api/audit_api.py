"""Audit page routes (step 4): everything a pentester does to a task's report while it is Completed, plus the
read-only views every team role gets. Task rows are loaded through the staff scope; `org_id` never comes from a request."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))

from fastapi import APIRouter, Depends, HTTPException, Response  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import audit  # noqa: E402
import db  # noqa: E402
import deps  # noqa: E402
import pdfjobs  # noqa: E402
import pdfpass  # noqa: E402
import ratelimit  # noqa: E402
import models  # noqa: E402
import reportcontent  # noqa: E402
import reportrender  # noqa: E402
import textsafe  # noqa: E402
import reportdoc  # noqa: E402
import store as report_store  # noqa: E402
import workflow  # noqa: E402
from deps import require_team  # noqa: E402
from tenancy import Scope  # noqa: E402

router = APIRouter(prefix="/api/tasks/{tid}")
AUDIT_STAGES = frozenset({"completed", "review_lead_pentester", "review_lead_cyber", "review_governance",
                          "review_manager", workflow.DELIVERING, "delivered"})


STAGE_MOVED = "The task moved on while you were editing. Send it back to change the report."


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
    try:
        pw = pdfpass.ensure(reportdoc.ensure_report(t)["id"])
    except pdfpass.Unavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    db.add_audit(t["id"], t["org_id"], user["username"], "password_view", "", {})
    audit.log("pdf_password_view", actor=user["username"], task=t["id"])
    return JSONResponse(content={"password": pw}, headers={"Cache-Control": "no-store"})


def _org_name(t: dict) -> str:
    return (db.get_org(t["org_id"]) or {}).get("name", "")


def _reportable(t: dict) -> None:
    if t["stage"] not in AUDIT_STAGES:
        raise HTTPException(status_code=409, detail="this task has no report yet")


@router.get("/audit")
def audit_summary(tid: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    t = _task(tid, scope)
    _reportable(t)
    c = reportcontent.ensure_v1(t)
    return {"task": {"id": t["id"], "target": t["target"], "stage": t["stage"], "version": t["version"],
                     "client": _org_name(t) or "Internal", "assignee": t.get("assignee")},
            "can_audit": workflow.can_audit(t, user["username"]), "ai_chat": reportdoc.ai_chat_enabled(),
            "content_version": c["version"], "counts": reportdoc.counts(reportdoc.findings_for(t)),
            "pdf": pdfjobs.summary(t)}


@router.get("/audit/trail")
def audit_trail(tid: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    t = _task(tid, scope)
    return [{k: r[k] for k in ("id", "actor", "action", "subject", "detail", "at")} for r in db.list_audit(t["id"])]


@router.get("/report/content")
def report_content(tid: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    t = _task(tid, scope)
    _reportable(t)
    c = reportcontent.ensure_v1(t)
    return {"version": c["version"], "created_by": c["created_by"], "created_at": c["created_at"], "note": c["note"],
            "preview": reportrender.preview(c["content"], t, _org_name(t), reportdoc.findings_for(t)),
            "versions": db.list_content_versions(t["id"])}


class RestoreBody(BaseModel):
    version: int
    base_version: int


@router.post("/report/restore")
def restore_version(tid: str, body: RestoreBody, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    """Undo is a new version holding an older one's content: history is never rewritten."""
    t = _task(tid, scope)
    require_owner(t, user)
    old = db.get_content(t["id"], body.version)
    if not old:
        raise HTTPException(status_code=404, detail="no such version")
    v = db.add_content(t["id"], t["org_id"], old["content"], user["username"], f"Restored version {body.version}",
                       base_version=body.base_version)
    if v is None:
        raise HTTPException(status_code=409, detail="The report changed. Refresh and try again.")
    db.add_audit(t["id"], t["org_id"], user["username"], "content_restore", str(body.version), {"new_version": v})
    return {"version": v}


def _finding_of(t: dict, fid: str, scope: Scope) -> dict:
    f = db.get_finding_with_task(fid, org_id=scope.org_id)
    if not f or f["task_id"] != t["id"]:
        raise HTTPException(status_code=404, detail="no such finding")
    return f


def _severity(raw: str) -> str:
    sev = (raw or "").strip().lower()
    if sev not in models.SEVERITY_ORDER:
        raise HTTPException(status_code=422, detail=f"severity must be one of {', '.join(models.SEVERITY_ORDER)}")
    return sev


class EditBody(BaseModel):
    severity: str | None = Field(default=None, max_length=20)
    impact: str | None = Field(default=None, max_length=4000)
    remediation: str | None = Field(default=None, max_length=4000)


@router.post("/findings/{fid}/edit")
def edit_finding(tid: str, fid: str, body: EditBody, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    t = _task(tid, scope)
    require_owner(t, user)
    f = _finding_of(t, fid, scope)
    changes: dict = {}
    if body.severity is not None:
        changes["severity"] = _severity(body.severity)
    for key in ("impact", "remediation"):
        value = getattr(body, key)
        if value is not None:
            changes[key] = textsafe.plain_lines(value).strip()
    if not changes:
        raise HTTPException(status_code=422, detail="nothing to change")
    if not db.set_finding_if_completed(fid, t["id"], **changes):
        raise HTTPException(status_code=409, detail=STAGE_MOVED)
    db.add_audit(t["id"], t["org_id"], user["username"], "finding_edit", fid,
                 {"before": {k: str(f.get(k) or "")[:200] for k in changes}, "after": {k: v[:200] for k, v in changes.items()}})
    return {"ok": True}


class ManualBody(BaseModel):
    name: str = Field(max_length=300)
    severity: str = Field(max_length=20)
    host: str = Field(default="", max_length=300)
    url: str = Field(default="", max_length=2048)
    description: str = Field(default="", max_length=4000)
    evidence: str = Field(default="", max_length=6000)
    remediation: str = Field(default="", max_length=4000)
    impact: str = Field(default="", max_length=4000)


@router.post("/findings/manual")
def add_manual(tid: str, body: ManualBody, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    t = _task(tid, scope)
    require_owner(t, user)
    if not t.get("job_id"):
        raise HTTPException(status_code=409, detail="this task has no scan to attach a finding to")
    name = textsafe.strip_controls(body.name).strip()
    if not name:
        raise HTTPException(status_code=422, detail="a finding needs a name")
    fields = {"name": name, "severity": _severity(body.severity),
              "host": textsafe.strip_controls(body.host).strip() or reportdoc.target_host(t["target"]) or t["target"],
              "url": textsafe.strip_controls(body.url).strip()}
    for key in ("description", "evidence", "remediation", "impact"):
        fields[key] = textsafe.plain_lines(getattr(body, key)).strip()
    fid = db.insert_manual_finding(t, fields)
    if fid is None:
        raise HTTPException(status_code=409, detail=STAGE_MOVED)
    db.add_audit(t["id"], t["org_id"], user["username"], "manual_add", fid, {"name": name[:120], "severity": fields["severity"]})
    return {"id": fid}
