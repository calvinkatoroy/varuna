"""Browser-facing JSON API, public plane (SRS C-6, §3.1, §4.11).

Replaces the Streamlit public UI: the React frontend calls these endpoints. Every request
is validated by Pydantic and (except login) gated by a JWT bearer token; role-restricted
endpoints add a require_pro dependency. All business logic and security controls are reused
unchanged from the framework-agnostic modules (auth, dispatch, classifier, redis_store).

This module covers the login + scan-submission + status pattern; approval, agent-install,
and report endpoints are added on the same pattern. The private-plane API (findings, manual
input, full reports) is a separate app bound to the Tailscale interface (NFR-24).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # repo-root .env, for host-run dev (REDIS_URL, JWT_SECRET, ...)

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field, StrictInt  # noqa: E402

import audit  # noqa: E402
import auth  # noqa: E402
import classifier  # noqa: E402
import cockpit  # noqa: E402
import db  # noqa: E402
import dispatch  # noqa: E402
import generator  # noqa: E402
import jwt_auth  # noqa: E402
import mailer  # noqa: E402
import models  # noqa: E402
import redis_store  # noqa: E402
import scanopts  # noqa: E402
import store as report_store  # noqa: E402
import tenancy  # noqa: E402
import tokens  # noqa: E402
import workflow  # noqa: E402
import deps  # noqa: E402
import profile_api  # noqa: E402
from deps import current_user, require_pro  # noqa: E402

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

app = FastAPI(title="Varuna Browser API (public plane)")
app.include_router(profile_api.router)

# Explicit CORS: only the configured frontend origin(s) may call the API (C-6 security posture).
_CORS = os.environ.get("VARUNA_CORS_ORIGINS", "http://localhost:5173").split(",")
MAX_BODY = 1_000_000   # bytes; every JSON body here is small forms


@app.middleware("http")
async def clients_only(request, call_next):
    """NFR-24: the internet-facing plane serves clients. A valid team token is refused here (it
    works on the private plane), so stolen/phished team credentials gain nothing public."""
    if request.url.path.startswith("/api/"):
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        try:
            role = jwt_auth.verify(token)["role"] if token else None
        except Exception:
            role = None   # invalid/expired: the endpoint's own auth returns the 401
        # Every non-client role is refused; the dev opt-in lets TEAM roles (never sysadmin) through.
        dev_team = os.environ.get("VARUNA_PUBLIC_TEAM_LOGIN") == "1" and role != models.ROLE_SYSADMIN
        if role and role != models.ROLE_CLIENT and not dev_team:
            return JSONResponse(status_code=403, content={"detail": "staff accounts use the private plane"})
    return await call_next(request)


@app.middleware("http")
async def limit_body(request, call_next):
    try:
        too_big = int(request.headers.get("content-length", 0)) > MAX_BODY
    except ValueError:
        too_big = True
    if too_big:
        return JSONResponse(status_code=413, content={"detail": "request body too large"})
    return await call_next(request)


# CORS goes on LAST so it is the outermost layer: the 403/413 answers from the middlewares above
# must carry CORS headers too, or the browser reports a network error instead of the status.
app.add_middleware(CORSMiddleware, allow_origins=_CORS, allow_methods=["*"], allow_headers=["*"])

FULL_STACK = workflow.FULL_STACK
SSE_POLL_INTERVAL = 1.5   # seconds between checks for a changed job record
SSE_MAX_SECONDS = 40 * 60  # generous cap so a stuck agent can't leave a connection open forever


# --- request models (Pydantic validation at the edge, C-6) ---
class LoginBody(BaseModel):
    username: str
    password: str


class ScanBody(BaseModel):
    target: str
    tools: list[str] | None = None       # ignored for Standard (locked to full stack, REQ-5)
    division: str = ""
    opts: dict = {}


class RejectBody(BaseModel):
    reason: str = Field(default="", max_length=2000)


@app.post("/api/login")
def login(body: LoginBody, x_forwarded_for: str = Header(default="api")):
    try:
        token = jwt_auth.login(body.username, body.password, x_forwarded_for)
    except auth.LockedOut:
        raise HTTPException(status_code=429, detail="too many failed attempts; try again later")
    except auth.MfaRequired:   # only team accounts can have two-factor, and they belong on the private plane
        raise HTTPException(status_code=403, detail="security team accounts sign in on the private plane")
    except auth.BadCredentials:
        raise HTTPException(status_code=401, detail="invalid username or password")
    # NFR-24: the public (internet-facing) plane is for clients. Security-team accounts sign in
    # on the private plane, so their credentials can't be brute-forced from the internet.
    # Local dev without a private plane can opt in with VARUNA_PUBLIC_TEAM_LOGIN=1.
    role = jwt_auth.verify(token)["role"]
    if models.is_sysadmin(role) or (role != models.ROLE_CLIENT and os.environ.get("VARUNA_PUBLIC_TEAM_LOGIN") != "1"):
        raise HTTPException(status_code=403,
                            detail="security team accounts sign in on the private plane")
    return {"token": token}


@app.post("/api/refresh")
def refresh(user: dict = Depends(current_user)):
    return {"token": jwt_auth.issue(user["username"])}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


class ResetRequestBody(BaseModel):
    email: str


class ResetConfirmBody(BaseModel):
    token: str
    new: str


@app.post("/api/password-reset/request")
def password_reset_request(body: ResetRequestBody, x_forwarded_for: str = Header(default="api")):
    """Always the same answer, so this cannot be used to discover who has an account."""
    for name, token in auth.start_reset(body.email, x_forwarded_for):
        link = f"{(os.environ.get('VARUNA_PUBLIC_URL') or 'http://localhost:5173').rstrip('/')}/reset?token={token}"
        text = (f"Hello {name},\n\nSomeone asked to reset the Varuna password for this account. "
                f"Open this link within 30 minutes to choose a new one:\n\n{link}\n\n"
                "If this wasn't you, ignore this email; your password has not changed.\n")
        threading.Thread(target=mailer.send, args=(body.email.strip(), "Reset your Varuna password", text), daemon=True).start()
        audit.log("password_reset_requested", actor=name)
    return {"ok": True}


@app.post("/api/password-reset/confirm")
def password_reset_confirm(body: ResetConfirmBody):
    try:
        auth.finish_reset(body.token, body.new)
    except auth.AuthError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"ok": True}


class PasswordBody(BaseModel):
    current: str
    new: str


@app.post("/api/password")
def change_password(body: PasswordBody, user: dict = Depends(current_user)):
    try:
        auth.change_password(user["username"], body.current, body.new)
    except auth.BadCredentials as e:
        raise HTTPException(status_code=403, detail=str(e))
    except auth.AuthError as e:
        raise HTTPException(status_code=422, detail=str(e))
    audit.log("password_changed", actor=user["username"])
    return {"ok": True, "token": jwt_auth.issue(user["username"])}


@app.get("/api/cockpit")
def get_cockpit(user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    """Client dashboard aggregate: the organization's engagements, posture, trend, latest delivered report."""
    if not models.is_client(user["role"]):
        raise HTTPException(status_code=403, detail="client role required")
    return cockpit.build_cockpit(user["username"], scope.org_id)


# --- tasks (step 2): a client asks for a scan inside a time window; a pentester claims it ---
class TaskBody(BaseModel):
    target: str = Field(max_length=2048)
    path: str = Field(default="", max_length=512)
    port: StrictInt | None = None
    notes: str = Field(default="", max_length=4000)
    not_before: str = Field(max_length=64)
    not_after: str = Field(max_length=64)
    scan_mode: str = Field(default="local", pattern="^(local|cloud)$")


def _client_task_view(t: dict) -> dict:
    """What a client may see of a task: status words and the decline cause, never staff names or comments."""
    return {
        "id": t["id"], "target": t["target"], "path": t["path"] or "", "port": t["port"], "notes": t["notes"] or "",
        "scan_mode": t["scan_mode"], "status": workflow.client_status(t), "when": t["updated_at"],
        "reason": t["decline_cause"] if t["stage"] == "declined" else None, "job_id": t["job_id"],
        "not_before": t["not_before"], "not_after": t["not_after"],
        "scheduled_at": t["scheduled_at"] if t["stage"] == "scan" else None,
    }


def _client_only(user: dict) -> None:
    if not models.is_client(user["role"]):
        raise HTTPException(status_code=403, detail="client role required")


def _scoped_task(tid: str, scope: tenancy.Scope) -> dict:
    t = db.get_proposal(tid, org_id=scope.org_id)
    if not t:   # out of scope answers exactly like missing
        raise HTTPException(status_code=404, detail="no such task")
    return t


@app.post("/api/tasks")
def create_task(body: TaskBody, user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    _client_only(user)
    t = deps.run_workflow(workflow.create_task, user["username"], scope.org_id, **body.model_dump())
    return _client_task_view(t)


@app.get("/api/tasks")
def list_tasks(user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    _client_only(user)
    return [_client_task_view(t) for t in db.list_proposals(org_id=scope.org_id)]


@app.get("/api/tasks/{tid}")
def get_task(tid: str, user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    _client_only(user)
    return {**_client_task_view(_scoped_task(tid, scope)), "timeline": workflow.client_timeline(tid)}


@app.get("/api/tasks/{tid}/events")
def task_timeline(tid: str, user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    _client_only(user)
    _scoped_task(tid, scope)
    return workflow.client_timeline(tid)


@app.post("/api/scans")
def submit_scan(body: ScanBody, user: dict = Depends(current_user)):
    # v2: clients never direct-submit; they file a proposal that the lead pentester approves.
    # Direct submit is the security team's advanced path only.
    if models.is_client(user["role"]):
        raise HTTPException(status_code=403, detail="clients submit a scan proposal for approval")
    if not models.is_team(user["role"]):   # sysadmin and any other non-team role: no scanning at all
        raise HTTPException(status_code=403, detail="your role cannot start scans")
    # Standard is locked to the full safe-profile stack; Pro chooses (defaults to full).
    tools = FULL_STACK if models.is_client(user["role"]) else (body.tools or FULL_STACK)
    if any(t not in FULL_STACK for t in tools):
        raise HTTPException(status_code=422, detail=f"tools must be a subset of {FULL_STACK}")
    try:   # allow-list + clamp; destructive options are lead-pentester-only (safe-profile lock)
        opts = {} if models.is_client(user["role"]) else scanopts.sanitize(body.opts, user["role"])
    except scanopts.BadOpts as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not redis_store.get_agent(user["username"]):   # after validation: bad input gets its own error first
        raise HTTPException(status_code=409, detail="no agent registered; install your agent first")
    try:
        # Direct scans are staff-only and have no proposal: the job belongs to no organization
        # (staff-only visibility), never to whatever a request names.
        return dispatch.submit_scan(user["username"], user["role"], None, body.target,
                                    tools, opts=opts, division=body.division)
    except classifier.ClassifyRejected as e:
        raise HTTPException(status_code=422, detail=f"target rejected: {e}")
    except dispatch.OfflineAgent as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/api/scans")
def list_scans(user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    return dispatch.list_jobs(scope.org_id)


@app.get("/api/scans/{job_id}")
def scan_status(job_id: str, user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    job = dispatch.get_job(scope, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    return {
        "id": job["id"],
        "status": job["status"],
        "target_class": job.get("target_class"),
        "per_tool_status": job.get("per_tool_status", {}),
        "agent_online": tokens.is_online(job["submitter"]),
    }


@app.get("/api/scans/{job_id}/events")
async def scan_events(job_id: str, user: dict = Depends(current_user),
                      scope: tenancy.Scope = Depends(deps.scope)):
    """Live scan progress (v2): a phase-by-phase installer-style feed, not a smooth percentage
    - the agent only reports at tool-phase boundaries (scan.py's checkpoint), it doesn't have
    fractional progress within a single Katana/Nuclei/SQLMap run. Polls the same job record the
    agent writes to server-side and pushes a frame only when something actually changed, so a
    client watching doesn't need to poll itself. Closes once the job reaches done/failed, or
    after SSE_MAX_SECONDS regardless (a stuck agent shouldn't leave a connection open forever).

    Native EventSource can't send an Authorization header, so the frontend uses a fetch-based
    reader instead (see api.ts's streamEvents) - this is a plain authenticated GET either way.
    """
    if not dispatch.get_job(scope, job_id):
        raise HTTPException(status_code=404, detail="no such job")

    async def gen():
        last = None
        elapsed = 0.0
        while elapsed < SSE_MAX_SECONDS:
            j = redis_store.get_job(job_id)
            if not j:
                yield f"data: {json.dumps({'status': 'gone'})}\n\n"
                return
            snapshot = {
                "status": j.get("status"),
                "per_tool_status": j.get("per_tool_status", {}),
                "suspended": redis_store.is_suspended(job_id),
            }
            if snapshot != last:
                yield f"data: {json.dumps(snapshot)}\n\n"
                last = snapshot
            if j.get("status") in (models.STATUS_DONE, models.STATUS_FAILED):
                return
            await asyncio.sleep(SSE_POLL_INTERVAL)
            elapsed += SSE_POLL_INTERVAL

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- agent enrollment (REQ-71 to REQ-73) ---
_CLOSED = ("declined", "expired")


def _own_tasks(user: dict, scope: tenancy.Scope) -> list[dict]:
    """Agents are per user (a job goes to its submitter's agent), so agent questions look at this
    user's own tasks within their organization."""
    return [t for t in db.list_proposals(org_id=scope.org_id) if t["submitter"] == user["username"]]


@app.get("/api/agent")
def agent_status(user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    mine = [t for t in _own_tasks(user, scope) if t["stage"] not in _CLOSED]
    return {"registered": bool(redis_store.get_agent(user["username"])),
            "online": tokens.is_online(user["username"]),
            # a client whose scans are all run by Varuna has no agent of their own to show
            "cloud_only": bool(mine) and all(t.get("scan_mode") == models.SCAN_CLOUD for t in mine),
            "cloud_online": tokens.is_online(models.CLOUD_AGENT)}


@app.post("/api/agent/install-token")
def install_token(user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    # A client gets an agent once a pentester has taken one of their tasks; nothing claimed, no token.
    if models.is_client(user["role"]) and not any(
            t["stage"] not in ("task", *_CLOSED) for t in _own_tasks(user, scope)):
        raise HTTPException(status_code=403, detail="agent install unlocks once a pentester accepts a task")
    return {"enrollment_token": tokens.generate_enrollment_token(user["username"])}


def _installer_cmd(base: str, token: str) -> str:
    """A double-clickable Windows installer for non-technical clients: it runs the same one-liner, shows plain
    progress, and never closes on its own so a failure can be read. The token inside is one-time and expires in an hour."""
    lines = [
        "@echo off",
        "title Varuna agent installer",
        "echo Installing the Varuna agent. This takes a few minutes. Please keep this window open.",
        "echo.",
        f'powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:VARUNA_URL=\'{base}\'; $env:VARUNA_TOKEN=\'{token}\'; irm {base}/dist/install.ps1 | iex"',
        "if errorlevel 1 (",
        "  echo.",
        "  echo Something went wrong. Please send a screenshot of this window to your Varuna contact.",
        ") else (",
        "  echo.",
        "  echo Done. You can close this window and go back to Varuna.",
        ")",
        "pause",
    ]
    return "\r\n".join(lines) + "\r\n"


@app.get("/api/agent/installer")
def agent_installer(request: Request, user: dict = Depends(current_user),
                    scope: tenancy.Scope = Depends(deps.scope)):
    """Same gate as /api/agent/install-token (a claimed task); returns Install-Varuna.cmd with a fresh token."""
    tok = install_token(user, scope)["enrollment_token"]
    base = (os.environ.get("VARUNA_PUBLIC_URL") or
            f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{request.headers.get('x-forwarded-host') or request.headers.get('host')}").rstrip("/")
    audit.log("agent_installer_downloaded", actor=user["username"])
    return Response(content=_installer_cmd(base, tok), media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="Install-Varuna.cmd"', "Cache-Control": "no-store"})


# --- legacy v1 approval queue (team only; RejectBody defined above) ---
@app.get("/api/approvals")
def list_approvals(user: dict = Depends(require_pro)):
    return dispatch.pending_approvals()


@app.post("/api/approvals/{job_id}/approve")
def approve(job_id: str, user: dict = Depends(require_pro)):
    try:
        dispatch.approve_request(job_id, user["username"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except dispatch.OfflineAgent as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


@app.post("/api/approvals/{job_id}/reject")
def reject(job_id: str, body: RejectBody, user: dict = Depends(require_pro)):
    try:
        dispatch.reject_request(job_id, user["username"], body.reason or "no reason given")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


# --- reports (v2): a client's own DELIVERED, signed-off, protected-PDF reports from the
# review pipeline (db.reports) - not the legacy Redis Executive-Summary generator below,
# which is a separate, older concept (REQ-50a) still used by /api/scans/{id}/report. ---
def _delivered_report_view(r: dict) -> dict:
    p = db.get_proposal_by_job(r["job_id"])
    return {
        "id": r["id"], "engagement": (p or {}).get("target", r["job_id"]),
        "delivered": r["updated_at"], "findings": len(db.get_findings(r["job_id"])),
        "templates": [r["template"]], "signed": True,
    }


@app.get("/api/reports")
def list_reports(user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    # team sees every organization's delivered reports; a client sees only their organization's
    rows = db.list_reports(stage=models.REPORT_DELIVERED, org_id=scope.org_id)
    return [_delivered_report_view(r) for r in rows]


# --- client findings (v2): flat, tenancy-filtered, confirmed (tp) findings across all of a
# client's own engagements - what ClientFindings.tsx shows. ---
@app.get("/api/findings")
def list_findings(user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    is_team = models.is_team(user["role"])
    rows = db.list_findings(org_id=scope.org_id)
    # Clients only ever see confirmed (tp) findings; the team also triages false positives
    # via FindingsReview, so they see everything.
    return rows if is_team else [f for f in rows if f["verdict"] == "tp"]


class FindingStatusBody(BaseModel):
    status: str   # "open" | "fixed"


@app.post("/api/findings/{fid}/status")
def set_finding_status(fid: str, body: FindingStatusBody, user: dict = Depends(current_user),
                       scope: tenancy.Scope = Depends(deps.scope)):
    if body.status not in ("open", "fixed"):
        raise HTTPException(status_code=422, detail="status must be open or fixed")
    if not db.get_finding(fid, org_id=scope.org_id):
        raise HTTPException(status_code=404, detail="no such finding")
    db.set_finding(fid, status=body.status)
    return {"ok": True}


@app.post("/api/scans/{job_id}/report")
def generate_report(job_id: str, user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    job = dispatch.get_job(scope, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    # Public plane only serves the sanitized Executive Summary (REQ-49/50a). Pro full
    # templates are on the private plane.
    data = generator.generate(job, db.get_findings(job_id), "Executive Summary")
    return report_store.save_report(user["username"], job_id, "Executive Summary", data, org_id=job.get("org_id"))


@app.get("/api/reports/{rid}/delivered")
def download_delivered(rid: str, user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    """Client downloads their organization's DELIVERED report as a password-protected PDF (read-only)."""
    r = db.get_report(rid, org_id=scope.org_id)
    if not r:
        raise HTTPException(status_code=404, detail="no such report")
    if r["stage"] != models.REPORT_DELIVERED or not r["delivered_pdf"]:
        raise HTTPException(status_code=409, detail="report not delivered yet")
    try:
        data = report_store.read_report(r["delivered_pdf"])
    except OSError:
        raise HTTPException(status_code=404, detail="delivered file missing")
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{r["delivered_pdf"]}"'})


@app.get("/api/reports/{rid}/password")
def view_password(rid: str, user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    """View-once PDF password for the owning organization. After one view, the client must ask
    governance to re-issue it."""
    r = db.get_report(rid, org_id=scope.org_id)
    if not r:
        raise HTTPException(status_code=404, detail="no such report")
    if r["stage"] != models.REPORT_DELIVERED or not r["pdf_password"]:
        raise HTTPException(status_code=409, detail="report not delivered yet")
    if not db.claim_password_view(rid):   # atomic: two simultaneous requests cannot both see it
        raise HTTPException(status_code=403,
                            detail="password already viewed; request re-issue from governance")
    return {"password": r["pdf_password"]}


@app.get("/api/reports/{fname}/download")
def download_report(fname: str, user: dict = Depends(current_user), scope: tenancy.Scope = Depends(deps.scope)):
    if scope.org_id is not None and report_store.org_of(fname) != scope.org_id:
        raise HTTPException(status_code=404, detail="no such report")
    try:
        data = report_store.read_report(fname)
    except OSError:
        raise HTTPException(status_code=404, detail="no such report")
    return Response(content=data, media_type=DOCX_MIME,
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
