"""Browser-facing JSON API, private plane (SRS §4.7, §4.6a, NFR-24).

Replaces the Streamlit private UI. Bound to the Tailscale interface only in production, no
public listener: full Findings Review, Manual Findings Input, and the full report archive
across all users and all four templates. Pro-only (require_pro on every endpoint).
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # repo-root .env, for host-run dev (REDIS_URL, JWT_SECRET, ...)

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402


import audit  # noqa: E402
import notify  # noqa: E402
import totp  # noqa: E402
import board  # noqa: E402
import db  # noqa: E402
import generator  # noqa: E402
import ingest  # noqa: E402
import models  # noqa: E402
import pdfpass  # noqa: E402
import redis_store  # noqa: E402
import reportdoc  # noqa: E402
import scheduler  # noqa: E402
import scanopts  # noqa: E402
import workflow  # noqa: E402
import store as report_store  # noqa: E402
import auth  # noqa: E402
import jwt_auth  # noqa: E402
import browser  # noqa: E402  (proposal/scan/finding logic is shared; only the auth plane differs)
import deps  # noqa: E402
import profile_api  # noqa: E402
import audit_api  # noqa: E402
import dispatch  # noqa: E402
from sysadmin import router as sysadmin_router  # noqa: E402
from tenancy import Scope  # noqa: E402
from deps import current_user, mfa_required, require_pro, require_staff_setup, require_team  # noqa: E402

app = FastAPI(title="Varuna Private API (Tailscale plane)")
_CORS = os.environ.get("VARUNA_CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=_CORS, allow_methods=["*"], allow_headers=["*"])
app.include_router(sysadmin_router)
app.include_router(profile_api.router)
app.include_router(audit_api.router)
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _mime(fname: str) -> str:
    return "application/pdf" if fname.endswith(".pdf") else DOCX_MIME


@app.on_event("startup")
def _warn_default_passwords() -> None:
    secret = jwt_auth.JWT_SECRET
    if secret == "dev-only-change-me" or len(secret) < 32:
        print("WARNING: JWT_SECRET is the built-in dev value or shorter than 32 characters. Anyone who knows it can forge "
              "logins. Set a long random value (openssl rand -hex 32).", flush=True)
    no_mfa = [a["username"] for a in db.list_accounts() if a["role"] != "client" and not a["totp_enabled"]]
    if no_mfa:
        print(f"NOTE: team accounts without two-factor: {', '.join(no_mfa)}. Enable it from the account menu.", flush=True)
    weak = auth.default_password_accounts()
    if weak:
        print(f"WARNING: team accounts still use the default password 'changeme': {', '.join(weak)}. "
              "Change them (POST /api/password or the admin reset) before any non-local use.", flush=True)


@app.on_event("startup")
def _check_password_keys() -> None:
    pdfpass.check_sealed()


@app.on_event("startup")
def _start_scheduler() -> None:
    """One scheduler loop per private-API process; the Redis lock lets only one of them work at a time."""
    if os.environ.get("VARUNA_SCHEDULER", "1") != "0":
        scheduler.start()


class LoginBody(BaseModel):
    username: str
    password: str
    code: str | None = None      # authenticator code, required once two-factor is enabled


@app.post("/api/login")
def login(body: LoginBody, x_forwarded_for: str = Header(default="api")):
    """Security-team sign-in (NFR-24): same credentials/throttle as the public plane, but only
    team roles get a token here, so a rejected client login never leaves a session behind."""
    try:
        token = jwt_auth.login(body.username, body.password, x_forwarded_for, body.code)
    except auth.LockedOut:
        raise HTTPException(status_code=429, detail="too many failed attempts; try again later")
    except auth.MfaRequired:
        raise HTTPException(status_code=401, detail="mfa_required")   # the UI then asks for the code
    except auth.BadCredentials as e:
        raise HTTPException(status_code=401, detail=str(e))
    if not (models.is_team(jwt_auth.verify(token)["role"]) or models.is_sysadmin(jwt_auth.verify(token)["role"])):
        raise HTTPException(status_code=403, detail="that account doesn't have security-team access")
    return {"token": token}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


class PasswordBody(BaseModel):
    current: str
    new: str


@app.post("/api/password")
def change_password(body: PasswordBody, user: dict = Depends(require_staff_setup)):
    try:
        auth.change_password(user["username"], body.current, body.new)
    except auth.BadCredentials as e:
        raise HTTPException(status_code=403, detail=str(e))
    except auth.AuthError as e:
        raise HTTPException(status_code=422, detail=str(e))
    audit.log("password_changed", actor=user["username"])
    return {"ok": True, "token": jwt_auth.issue(user["username"])}


@app.post("/api/refresh")
def refresh(user: dict = Depends(current_user)):
    return {"token": jwt_auth.issue(user["username"])}


# --- two-factor (TOTP) for team accounts: enrol with an authenticator app, then logins need a code ---
class CodeBody(BaseModel):
    code: str


class MfaDisableBody(BaseModel):
    password: str
    code: str = ""


@app.get("/api/mfa")
def mfa_status(user: dict = Depends(require_staff_setup)):
    acct = db.get_account(user["username"]) or {}
    return {"enabled": bool(acct.get("totp_enabled")), "required": mfa_required()}


@app.post("/api/mfa/setup")
def mfa_setup(user: dict = Depends(require_staff_setup)):
    """New secret (not enforced until confirmed). Shown once here; the app also gets the otpauth URI."""
    secret = auth.mfa_begin(user["username"])
    return {"secret": secret, "uri": totp.otpauth_uri(user["username"], secret)}


@app.post("/api/mfa/enable")
def mfa_enable(body: CodeBody, user: dict = Depends(require_staff_setup)):
    try:
        auth.mfa_confirm(user["username"], body.code)
    except auth.BadCredentials as e:
        raise HTTPException(status_code=422, detail=str(e))
    except auth.AuthError as e:
        raise HTTPException(status_code=409, detail=str(e))
    audit.log("mfa_enabled", actor=user["username"])
    return {"enabled": True, "token": jwt_auth.issue(user["username"])}


@app.post("/api/mfa/disable")
def mfa_disable(body: MfaDisableBody, user: dict = Depends(require_staff_setup)):
    try:
        auth.mfa_disable(user["username"], body.password, body.code)
    except auth.BadCredentials as e:
        raise HTTPException(status_code=403, detail=str(e))
    audit.log("mfa_disabled", actor=user["username"])
    return {"enabled": False, "token": jwt_auth.issue(user["username"])}


# --- team actions that used to live on the public plane (NFR-24): same logic as browser.py,
# served here so team tokens are not needed on the internet-facing API at all. ---
@app.post("/api/scans")
def submit_scan(body: browser.ScanBody, user: dict = Depends(require_team)):
    return browser.submit_scan(body, user)


@app.get("/api/scans/{job_id}/events")
async def scan_events(job_id: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    """Live scan progress for the team (the public plane refuses team tokens, NFR-24)."""
    return await browser.scan_events(job_id, user, scope)


@app.get("/api/findings")
def list_findings(task_id: str | None = None, limit: int = Query(100, ge=1, le=200), cursor: str | None = None,
                  upto: str | None = None, severity: str | None = None,
                  user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    return browser.findings_list(task_id, limit, cursor, upto, severity, user, scope)


# Declared before `/api/findings/{job_id}` below, or "targets" would be taken for a job id.
@app.get("/api/findings/targets")
def findings_targets(user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    return browser.targets_view(user, scope)


@app.get("/api/findings/id/{fid}")
def finding_one(fid: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    return browser.one_view(fid, user, scope)


@app.post("/api/findings/{fid}/status")
def set_finding_status(fid: str, body: browser.FindingStatusBody, user: dict = Depends(require_team),
                       scope: Scope = Depends(deps.scope)):
    return browser.set_finding_status(fid, body, user, scope)


@app.get("/api/findings/{job_id}")
def findings(job_id: str, user: dict = Depends(require_pro)):
    return db.get_findings(job_id)


class VerdictBody(BaseModel):
    verdict: str   # "tp" | "fp"




# --- team board (step 2): role-scoped kanban columns built from task stages ---
@app.get("/api/board")
def get_board(column: str | None = None, user: dict = Depends(require_team)):
    """Role-scoped columns (step 2). Staff scope only; the scheduler runs the stall reaper, not this read."""
    try:
        return board.build_board(user, column)
    except PermissionError:
        raise HTTPException(status_code=403, detail="this column is not visible to your role")


@app.get("/api/reports/all")
def all_reports(user: dict = Depends(require_pro)):
    return report_store.list_all_reports()


class GenerateBody(BaseModel):
    job_id: str
    template: str


@app.post("/api/reports/generate")
def generate_report(body: GenerateBody, user: dict = Depends(require_pro), scope: Scope = Depends(deps.scope)):
    job = dispatch.get_job(scope, body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    try:
        data = generator.generate(job, db.get_findings(body.job_id), body.template)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return report_store.save_report(user["username"], body.job_id, body.template, data, org_id=ingest.job_org(job))


@app.get("/api/reports/{fname}/download")
def download_report(fname: str, user: dict = Depends(require_pro)):
    try:
        data = report_store.read_report(fname)
    except OSError:
        raise HTTPException(status_code=404, detail="no such report")
    return Response(content=data, media_type=_mime(fname),
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# --- task workflow (step 2): every staff move goes through one route; workflow.py decides who may ---
class TransitionBody(BaseModel):
    to: str = Field(max_length=40)
    version: int
    comment: str | None = Field(default=None, max_length=2000)
    scheduled_at: str | None = Field(default=None, max_length=64)
    max_minutes: int | None = None
    opts: dict | None = None


def _staff_task(tid: str, scope: Scope) -> dict:
    t = db.get_proposal(tid, org_id=scope.org_id)
    if not t:
        raise HTTPException(status_code=404, detail="no such task")
    return t


@app.post("/api/tasks/{tid}/transition")
def task_transition(tid: str, body: TransitionBody, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    opts = None
    if body.opts is not None:   # advanced options: allow-list + clamp, destructive ones lead-only (safe-profile lock)
        try:
            opts = scanopts.sanitize(body.opts, user["role"])
        except scanopts.BadOpts as e:
            raise HTTPException(status_code=422, detail=str(e))
    t = deps.run_workflow(workflow.transition, tid, body.to, user["username"], org_id=scope.org_id,
                          version=body.version, comment=body.comment, scheduled_at=body.scheduled_at,
                          max_minutes=body.max_minutes, opts=opts, on_deliver=_deliver_task)
    return {"id": t["id"], "stage": t["stage"], "scan_state": t["scan_state"], "version": t["version"]}


@app.get("/api/tasks/{tid}/events")
def task_events(tid: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    _staff_task(tid, scope)
    return db.list_task_events(tid)


_DETAIL_KEYS = ("id", "target", "path", "port", "notes", "scan_mode", "not_before", "not_after", "max_minutes",
                "scheduled_at", "assignee", "suspend_reason", "decline_cause", "stage", "scan_state", "version", "job_id")


def _deliver_task(task: dict) -> None:
    """workflow's on_deliver hook. The PDF was built and protected at audit time; delivery only publishes the latest
    one, after checking it still matches the report (a send-back to Completed can leave it stale)."""
    pdf = db.latest_ready_pdf(task["id"])
    if not pdf:
        raise HTTPException(status_code=409, detail="this task has no PDF to deliver")
    gap = reportdoc.pdf_gap(task)
    if gap:
        raise HTTPException(status_code=409, detail=gap)
    db.set_report(reportdoc.ensure_report(task)["id"], stage=models.REPORT_DELIVERED, delivered_pdf=pdf["stored_name"])


@app.get("/api/tasks/{tid}/detail")
def task_detail(tid: str, user: dict = Depends(require_team), scope: Scope = Depends(deps.scope)):
    t = _staff_task(tid, scope)
    return {"task": {k: t.get(k) for k in _DETAIL_KEYS}, "can_audit": workflow.can_audit(t, user["username"]),
            "has_report": t["stage"] in audit_api.AUDIT_STAGES}


@app.post("/api/findings/{fid}/verdict")
def set_finding_verdict(fid: str, body: VerdictBody, user: dict = Depends(require_team),
                        scope: Scope = Depends(deps.scope)):
    if body.verdict not in ("tp", "fp"):
        raise HTTPException(status_code=422, detail="verdict must be tp or fp")
    f = db.get_finding_with_task(fid, org_id=scope.org_id)
    if not f:
        raise HTTPException(status_code=404, detail="no such finding")
    task = db.get_proposal(f["task_id"], org_id=None) if f.get("task_id") else None   # None for a direct staff scan
    if task:
        audit_api.require_owner(task, user)             # a task's report changes on its audit page, at Completed
    db.set_finding(fid, verdict=body.verdict)
    if task:
        db.add_audit(task["id"], task["org_id"], user["username"], "verdict", fid,
                     {"verdict": body.verdict, "name": f["name"][:120]})
    return {"ok": True}
