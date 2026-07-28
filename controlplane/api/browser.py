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
from pydantic import BaseModel  # noqa: E402

import audit  # noqa: E402
import auth  # noqa: E402
import classifier  # noqa: E402
import db  # noqa: E402
import dispatch  # noqa: E402
import generator  # noqa: E402
import jwt_auth  # noqa: E402
import models  # noqa: E402
import redis_store  # noqa: E402
import store as report_store  # noqa: E402
import tenancy  # noqa: E402
import tokens  # noqa: E402
from deps import current_user, require_lead, require_pro  # noqa: E402

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

app = FastAPI(title="Varuna Browser API (public plane)")

# Explicit CORS: only the configured frontend origin(s) may call the API (C-6 security posture).
_CORS = os.environ.get("VARUNA_CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=_CORS, allow_methods=["*"], allow_headers=["*"])

FULL_STACK = ["katana", "nuclei", "sqlmap"]


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
    reason: str = ""


class ProposalBody(BaseModel):
    target: str
    mode: str = "standard"
    in_scope: str = ""
    out_of_scope: str = ""
    division: str = ""
    purpose: str = ""                    # keperluan
    environment: str = ""
    test_window: str = ""
    roe: dict = {}
    authorization_attested: bool = False
    emergency_contact: str = ""
    tools: list[str] = []
    opts: dict = {}


@app.post("/api/login")
def login(body: LoginBody, x_forwarded_for: str = Header(default="api")):
    try:
        token = jwt_auth.login(body.username, body.password, x_forwarded_for)
    except auth.LockedOut:
        raise HTTPException(status_code=429, detail="too many failed attempts; try again later")
    except auth.BadCredentials:
        raise HTTPException(status_code=401, detail="invalid username or password")
    return {"token": token}


@app.post("/api/register")
def register(body: RegisterBody):
    """Self-service client registration (v2). Client-role only; grants nothing until a proposal
    is approved, so this being public is inert. Team accounts are seeded, never self-registered."""
    try:
        auth.register_client(body.username, body.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"token": jwt_auth.login(body.username, body.password, "api")}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


# --- scan proposals (v2): client submits, lead pentester approves ---
@app.post("/api/proposals")
def submit_proposal(body: ProposalBody, user: dict = Depends(current_user)):
    if not body.authorization_attested:
        raise HTTPException(status_code=422,
                            detail="authorization-to-test attestation is required")
    p = {**body.model_dump(), "submitter": user["username"], "status": models.PROPOSAL_PENDING}
    pid = db.create_proposal(p)
    return {"proposal_id": pid, "status": models.PROPOSAL_PENDING}


@app.get("/api/proposals")
def list_proposals(user: dict = Depends(current_user)):
    # team sees every client's proposals; a client sees only their own (v2 tenancy)
    if models.is_team(user["role"]):
        return db.list_proposals()
    return db.list_proposals(submitter=user["username"])


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
    # Safe-profile lock: standard (client) proposals run the fixed full stack, no custom opts.
    standard = p["mode"] == "standard"
    tools = FULL_STACK if standard else (p["tools"] or FULL_STACK)
    opts = {} if standard else p["opts"]
    job = models.Job(
        id=str(uuid.uuid4()), target=p["target"], target_class=target_class,
        submitter=p["submitter"], role=models.ROLE_CLIENT, tools=tools, opts=opts,
        status=models.STATUS_QUEUED, per_tool_status={},
    ).to_dict()
    redis_store.set_job(job)
    redis_store.add_user_job(p["submitter"], job["id"])
    db.update_proposal(pid, status=models.PROPOSAL_APPROVED, job_id=job["id"])
    audit.log(audit.APPROVE, approver=user["username"], proposal=pid, job=job["id"])
    # Proposal is the gate; queue for the client's agent to pick up whenever it polls.
    dispatch.dispatch_job(job, pre_approved=True)
    return {"proposal_id": pid, "status": models.PROPOSAL_APPROVED, "job_id": job["id"]}


@app.post("/api/proposals/{pid}/reject")
def reject_proposal(pid: str, body: RejectBody, user: dict = Depends(require_lead)):
    p = db.get_proposal(pid)
    if not p:
        raise HTTPException(status_code=404, detail="no such proposal")
    if p["status"] != models.PROPOSAL_PENDING:
        raise HTTPException(status_code=409, detail="proposal is not pending")
    db.update_proposal(pid, status=models.PROPOSAL_REJECTED, reject_reason=body.reason)
    audit.log(audit.REJECT, approver=user["username"], proposal=pid, reason=body.reason)
    return {"proposal_id": pid, "status": models.PROPOSAL_REJECTED}


@app.post("/api/scans")
def submit_scan(body: ScanBody, user: dict = Depends(current_user)):
    if not redis_store.get_agent(user["username"]):
        raise HTTPException(status_code=409, detail="no agent registered; install your agent first")
    # Standard is locked to the full safe-profile stack; Pro chooses (defaults to full).
    tools = FULL_STACK if models.is_client(user["role"]) else (body.tools or FULL_STACK)
    opts = {} if models.is_client(user["role"]) else body.opts
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


# --- agent enrollment (REQ-71 to REQ-73) ---
@app.get("/api/agent")
def agent_status(user: dict = Depends(current_user)):
    return {"registered": bool(redis_store.get_agent(user["username"])),
            "online": tokens.is_online(user["username"])}


@app.post("/api/agent/install-token")
def install_token(user: dict = Depends(current_user)):
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


# --- reports (public plane: Standard's own sanitized Executive Summaries, REQ-50a) ---
@app.get("/api/reports")
def list_reports(user: dict = Depends(current_user)):
    # team sees every client's reports; a client sees only their own (v2 tenancy)
    if models.is_team(user["role"]):
        return report_store.list_all_reports()
    return report_store.list_reports(user["username"])


@app.post("/api/scans/{job_id}/report")
def generate_report(job_id: str, user: dict = Depends(current_user)):
    job = redis_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    # Public plane only serves the sanitized Executive Summary (REQ-49/50a). Pro full
    # templates are on the private plane.
    data = generator.generate(job, redis_store.get_findings(job_id), "Executive Summary")
    return report_store.save_report(user["username"], job_id, "Executive Summary", data)


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
