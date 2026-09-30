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
import uuid

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # repo-root .env, for host-run dev (REDIS_URL, JWT_SECRET, ...)

from fastapi import Depends, FastAPI, Header, HTTPException, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field, StrictBool  # noqa: E402

import audit  # noqa: E402
import auth  # noqa: E402
import classifier  # noqa: E402
import cockpit  # noqa: E402
import db  # noqa: E402
import dispatch  # noqa: E402
import generator  # noqa: E402
import jwt_auth  # noqa: E402
import notify  # noqa: E402
import models  # noqa: E402
import redis_store  # noqa: E402
import scanopts  # noqa: E402
import store as report_store  # noqa: E402
import tenancy  # noqa: E402
import tokens  # noqa: E402
from deps import current_user, require_lead, require_pro  # noqa: E402

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

app = FastAPI(title="Varuna Browser API (public plane)")

# Explicit CORS: only the configured frontend origin(s) may call the API (C-6 security posture).
_CORS = os.environ.get("VARUNA_CORS_ORIGINS", "http://localhost:5173").split(",")
MAX_BODY = 1_000_000   # bytes; every JSON body here is small forms


@app.middleware("http")
async def clients_only(request, call_next):
    """NFR-24: the internet-facing plane serves clients. A valid team token is refused here (it
    works on the private plane), so stolen/phished team credentials gain nothing public."""
    if request.url.path.startswith("/api/") and os.environ.get("VARUNA_PUBLIC_TEAM_LOGIN") != "1":
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        try:
            role = jwt_auth.verify(token)["role"] if token else None
        except Exception:
            role = None   # invalid/expired: the endpoint's own auth returns the 401
        if role and models.is_team(role):
            return JSONResponse(status_code=403, content={"detail": "security team accounts use the private plane"})
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

FULL_STACK = ["katana", "nuclei", "sqlmap"]
SSE_POLL_INTERVAL = 1.5   # seconds between checks for a changed job record
SSE_MAX_SECONDS = 40 * 60  # generous cap so a stuck agent can't leave a connection open forever


# --- request models (Pydantic validation at the edge, C-6) ---
class LoginBody(BaseModel):
    username: str
    password: str


class RegisterBody(BaseModel):
    username: str
    password: str


class ScanBody(BaseModel):
    target: str
    tools: list[str] | None = None       # ignored for Standard (locked to full stack, REQ-5)
    division: str = ""
    opts: dict = {}


class RejectBody(BaseModel):
    reason: str = Field(default="", max_length=2000)


class ProposalBody(BaseModel):
    target: str = Field(max_length=2048)
    mode: str = Field(default="standard", pattern="^(standard|advanced)$")
    in_scope: str = Field(default="", max_length=4000)
    out_of_scope: str = Field(default="", max_length=4000)
    division: str = Field(default="", max_length=200)
    purpose: str = Field(default="", max_length=200)   # keperluan
    environment: str = Field(default="", max_length=200)
    test_window: str = Field(default="", max_length=200)
    roe: dict = {}
    authorization_attested: StrictBool = False
    emergency_contact: str = Field(default="", max_length=200)
    tools: list[str] = Field(default=[], max_length=10)
    opts: dict = {}


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
    if (models.is_team(jwt_auth.verify(token)["role"])
            and os.environ.get("VARUNA_PUBLIC_TEAM_LOGIN") != "1"):
        raise HTTPException(status_code=403,
                            detail="security team accounts sign in on the private plane")
    return {"token": token}


@app.post("/api/register")
def register(body: RegisterBody):
    """Self-service client registration (v2). Client-role only; grants nothing until a proposal
    is approved, so this being public is inert. Team accounts are seeded, never self-registered."""
    try:
        auth.register_client(body.username, body.password)
    except auth.UsernameTaken as e:
        raise HTTPException(status_code=409, detail=str(e))
    except auth.AuthError as e:   # bad username/password shape: a validation error, not a conflict
        raise HTTPException(status_code=422, detail=str(e))
    return {"token": jwt_auth.login(body.username, body.password, "api")}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


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
    return {"ok": True}


@app.get("/api/cockpit")
def get_cockpit(user: dict = Depends(current_user)):
    """Client dashboard aggregate: own engagements, posture, trend, latest delivered report."""
    if not models.is_client(user["role"]):
        raise HTTPException(status_code=403, detail="client role required")
    return cockpit.build_cockpit(user["username"])


# --- scan proposals (v2): client submits, lead pentester approves ---
@app.post("/api/proposals")
def submit_proposal(body: ProposalBody, user: dict = Depends(current_user)):
    if not body.authorization_attested:
        raise HTTPException(status_code=422,
                            detail="authorization-to-test attestation is required")
    try:
        classifier.validate_syntax(body.target)
    except classifier.ClassifyRejected as e:
        raise HTTPException(status_code=422, detail=f"invalid target: {e}")
    p = {**body.model_dump(), "submitter": user["username"], "status": models.PROPOSAL_PENDING}
    if models.is_client(user["role"]):
        # Safe-profile lock (NFR-17/18/19): `mode` for a client only labels the scoping form.
        # Clients never choose tools or scan options; those are advanced-scan (team) inputs.
        p["tools"], p["opts"] = [], {}
    elif any(t not in FULL_STACK for t in p["tools"]):
        raise HTTPException(status_code=422, detail=f"tools must be a subset of {FULL_STACK}")
    pid = db.create_proposal(p)
    notify.notify(f"New scan proposal from {user['username']} awaiting lead approval ({pid[:8]})")
    return {"proposal_id": pid, "status": models.PROPOSAL_PENDING}


def _client_proposal_view(p: dict) -> dict:
    """Reshape a raw proposal row into what ClientProposals.tsx actually expects: status in
    the client vocabulary (not raw pending/approved/rejected - see cockpit.client_status), and
    `when`/`reason` field names instead of the DB's updated_at/reject_reason."""
    return {
        "id": p["id"], "target": p["target"], "purpose": p["purpose"], "division": p["division"],
        "status": cockpit.client_status(p), "when": p["updated_at"], "reason": p.get("reject_reason"),
        "job_id": p.get("job_id"),
    }


@app.get("/api/proposals")
def list_proposals(user: dict = Depends(current_user)):
    # team sees every client's proposals (raw shape - the team side reads /api/pipeline/board
    # instead, this is only kept broad in case something else needs the raw rows); a client
    # sees only their own, reshaped for what the client UI actually renders (v2 tenancy).
    if models.is_team(user["role"]):
        return db.list_proposals()
    return [_client_proposal_view(p) for p in db.list_proposals(submitter=user["username"])]


@app.get("/api/proposals/{pid}")
def get_proposal(pid: str, user: dict = Depends(current_user)):
    p = db.get_proposal(pid)
    if not p:
        raise HTTPException(status_code=404, detail="no such proposal")
    if not tenancy.visible_to(user["role"], user["username"], p["submitter"]):
        raise HTTPException(status_code=403, detail="not your proposal")
    return p


@app.post("/api/proposals/{pid}/approve")
def approve_proposal(pid: str, user: dict = Depends(require_lead)):
    p = db.get_proposal(pid)
    if not p:
        raise HTTPException(status_code=404, detail="no such proposal")
    if p["status"] != models.PROPOSAL_PENDING:
        raise HTTPException(status_code=409, detail="proposal is not pending")
    try:
        target_class = classifier.classify(p["target"])
    except classifier.ClassifyRejected as e:
        raise HTTPException(status_code=422, detail=f"target rejected: {e}")
    # Safe-profile lock, decided by the submitter's ROLE (never by the client-chosen `mode`):
    # client proposals always run the fixed full stack with no custom opts.
    submitter = db.get_account(p["submitter"])
    standard = not submitter or models.is_client(submitter["role"]) or p["mode"] == "standard"
    tools = FULL_STACK if standard else (p["tools"] or FULL_STACK)
    opts = {} if standard else p["opts"]
    job = models.Job(
        id=str(uuid.uuid4()), target=p["target"], target_class=target_class,
        submitter=p["submitter"], role=models.ROLE_CLIENT, tools=tools, opts=opts,
        status=models.STATUS_QUEUED, per_tool_status={},
    ).to_dict()
    # Atomic claim: of N concurrent approvals exactly one flips pending->approved and proceeds.
    if not db.claim_proposal(pid, models.PROPOSAL_PENDING,
                             status=models.PROPOSAL_APPROVED, job_id=job["id"]):
        raise HTTPException(status_code=409, detail="proposal is not pending")
    redis_store.set_job(job)
    redis_store.add_user_job(p["submitter"], job["id"])
    audit.log(audit.APPROVE, approver=user["username"], proposal=pid, job=job["id"])
    # Proposal is the gate; queue for the client's agent to pick up whenever it polls.
    dispatch.dispatch_job(job, pre_approved=True)
    return {"proposal_id": pid, "status": models.PROPOSAL_APPROVED, "job_id": job["id"]}


@app.post("/api/proposals/{pid}/reject")
def reject_proposal(pid: str, body: RejectBody, user: dict = Depends(require_lead)):
    p = db.get_proposal(pid)
    if not p:
        raise HTTPException(status_code=404, detail="no such proposal")
    if not db.claim_proposal(pid, models.PROPOSAL_PENDING,
                             status=models.PROPOSAL_REJECTED, reject_reason=body.reason):
        raise HTTPException(status_code=409, detail="proposal is not pending")
    audit.log(audit.REJECT, approver=user["username"], proposal=pid, reason=body.reason)
    return {"proposal_id": pid, "status": models.PROPOSAL_REJECTED}


@app.post("/api/scans")
def submit_scan(body: ScanBody, user: dict = Depends(current_user)):
    # v2: clients never direct-submit; they file a proposal that the lead pentester approves.
    # Direct submit is the security team's advanced path only.
    if models.is_client(user["role"]):
        raise HTTPException(status_code=403, detail="clients submit a scan proposal for approval")
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
        return dispatch.submit_scan(user["username"], user["role"], body.target,
                                    tools, opts=opts, division=body.division)
    except classifier.ClassifyRejected as e:
        raise HTTPException(status_code=422, detail=f"target rejected: {e}")
    except dispatch.OfflineAgent as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/api/scans")
def list_scans(user: dict = Depends(current_user)):
    return dispatch.list_jobs(user["username"])


@app.get("/api/scans/{job_id}")
def scan_status(job_id: str, user: dict = Depends(current_user)):
    job = redis_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    if not tenancy.visible_to(user["role"], user["username"], job["submitter"]):
        raise HTTPException(status_code=403, detail="not your scan")
    return {
        "id": job["id"],
        "status": job["status"],
        "target_class": job.get("target_class"),
        "per_tool_status": job.get("per_tool_status", {}),
        "agent_online": tokens.is_online(job["submitter"]),
    }


@app.get("/api/scans/{job_id}/events")
async def scan_events(job_id: str, user: dict = Depends(current_user)):
    """Live scan progress (v2): a phase-by-phase installer-style feed, not a smooth percentage
    - the agent only reports at tool-phase boundaries (scan.py's checkpoint), it doesn't have
    fractional progress within a single Katana/Nuclei/SQLMap run. Polls the same job record the
    agent writes to server-side and pushes a frame only when something actually changed, so a
    client watching doesn't need to poll itself. Closes once the job reaches done/failed, or
    after SSE_MAX_SECONDS regardless (a stuck agent shouldn't leave a connection open forever).

    Native EventSource can't send an Authorization header, so the frontend uses a fetch-based
    reader instead (see api.ts's streamEvents) - this is a plain authenticated GET either way.
    """
    job = redis_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    if not tenancy.visible_to(user["role"], user["username"], job["submitter"]):
        raise HTTPException(status_code=403, detail="not your scan")

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
@app.get("/api/agent")
def agent_status(user: dict = Depends(current_user)):
    return {"registered": bool(redis_store.get_agent(user["username"])),
            "online": tokens.is_online(user["username"])}


@app.post("/api/agent/install-token")
def install_token(user: dict = Depends(current_user)):
    # Agents are installed AFTER approval (v2): a client with nothing approved gets no token.
    if models.is_client(user["role"]) and not any(
            p["status"] == models.PROPOSAL_APPROVED
            for p in db.list_proposals(submitter=user["username"])):
        raise HTTPException(status_code=403, detail="agent install unlocks once a proposal is approved")
    return {"enrollment_token": tokens.generate_enrollment_token(user["username"])}


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
def list_reports(user: dict = Depends(current_user)):
    # team sees every client's delivered reports; a client sees only their own (v2 tenancy)
    owner = None if models.is_team(user["role"]) else user["username"]
    rows = db.list_reports(owner=owner, stage=models.REPORT_DELIVERED)
    return [_delivered_report_view(r) for r in rows]


# --- client findings (v2): flat, tenancy-filtered, confirmed (tp) findings across all of a
# client's own engagements - what ClientFindings.tsx shows. ---
@app.get("/api/findings")
def list_findings(user: dict = Depends(current_user)):
    is_team = models.is_team(user["role"])
    rows = db.list_findings(owner=None if is_team else user["username"])
    # Clients only ever see confirmed (tp) findings; the team also triages false positives
    # via FindingsReview, so they see everything.
    return rows if is_team else [f for f in rows if f["verdict"] == "tp"]


class FindingStatusBody(BaseModel):
    status: str   # "open" | "fixed"


@app.post("/api/findings/{fid}/status")
def set_finding_status(fid: str, body: FindingStatusBody, user: dict = Depends(current_user)):
    if body.status not in ("open", "fixed"):
        raise HTTPException(status_code=422, detail="status must be open or fixed")
    f = db.get_finding(fid)
    if not f:
        raise HTTPException(status_code=404, detail="no such finding")
    if not tenancy.visible_to(user["role"], user["username"], f["owner"]):
        raise HTTPException(status_code=403, detail="not your finding")
    db.set_finding(fid, status=body.status)
    return {"ok": True}


@app.post("/api/scans/{job_id}/report")
def generate_report(job_id: str, user: dict = Depends(current_user)):
    job = redis_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    if not tenancy.visible_to(user["role"], user["username"], job["submitter"]):
        raise HTTPException(status_code=403, detail="not your scan")
    # Public plane only serves the sanitized Executive Summary (REQ-49/50a). Pro full
    # templates are on the private plane.
    data = generator.generate(job, db.get_findings(job_id), "Executive Summary")
    return report_store.save_report(user["username"], job_id, "Executive Summary", data)


@app.get("/api/reports/{rid}/delivered")
def download_delivered(rid: str, user: dict = Depends(current_user)):
    """Client downloads their own DELIVERED report as a password-protected PDF (read-only)."""
    r = db.get_report(rid)
    if not r:
        raise HTTPException(status_code=404, detail="no such report")
    if not tenancy.visible_to(user["role"], user["username"], r["owner"]):
        raise HTTPException(status_code=403, detail="not your report")
    if r["stage"] != models.REPORT_DELIVERED or not r["delivered_pdf"]:
        raise HTTPException(status_code=409, detail="report not delivered yet")
    try:
        data = report_store.read_report(r["delivered_pdf"])
    except OSError:
        raise HTTPException(status_code=404, detail="delivered file missing")
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{r["delivered_pdf"]}"'})


@app.get("/api/reports/{rid}/password")
def view_password(rid: str, user: dict = Depends(current_user)):
    """View-once PDF password for the owning client. After one view, the client must ask
    governance to re-issue it."""
    r = db.get_report(rid)
    if not r:
        raise HTTPException(status_code=404, detail="no such report")
    if not tenancy.visible_to(user["role"], user["username"], r["owner"]):
        raise HTTPException(status_code=403, detail="not your report")
    if r["stage"] != models.REPORT_DELIVERED or not r["pdf_password"]:
        raise HTTPException(status_code=409, detail="report not delivered yet")
    if not db.claim_password_view(rid):   # atomic: two simultaneous requests cannot both see it
        raise HTTPException(status_code=403,
                            detail="password already viewed; request re-issue from governance")
    return {"password": r["pdf_password"]}


@app.get("/api/reports/{fname}/download")
def download_report(fname: str, user: dict = Depends(current_user)):
    owner = report_store.owner_of(fname)
    if not (models.is_team(user["role"]) or owner == user["username"]):
        raise HTTPException(status_code=403, detail="not your report")
    try:
        data = report_store.read_report(fname)
    except OSError:
        raise HTTPException(status_code=404, detail="no such report")
    return Response(content=data, media_type=DOCX_MIME,
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
