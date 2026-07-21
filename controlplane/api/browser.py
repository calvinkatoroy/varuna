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

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # repo-root .env, for host-run dev (REDIS_URL, JWT_SECRET, ...)

from fastapi import Depends, FastAPI, Header, HTTPException, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import auth  # noqa: E402
import classifier  # noqa: E402
import dispatch  # noqa: E402
import generator  # noqa: E402
import jwt_auth  # noqa: E402
import models  # noqa: E402
import redis_store  # noqa: E402
import store as report_store  # noqa: E402
import tokens  # noqa: E402
from deps import current_user, require_pro  # noqa: E402

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


class ScanBody(BaseModel):
    target: str
    tools: list[str] | None = None       # ignored for Standard (locked to full stack, REQ-5)
    division: str = ""
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


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


@app.post("/api/scans")
def submit_scan(body: ScanBody, user: dict = Depends(current_user)):
    if not redis_store.get_agent(user["username"]):
        raise HTTPException(status_code=409, detail="no agent registered; install your agent first")
    # Standard is locked to the full safe-profile stack; Pro chooses (defaults to full).
    tools = FULL_STACK if user["role"] == models.ROLE_STANDARD else (body.tools or FULL_STACK)
    opts = {} if user["role"] == models.ROLE_STANDARD else body.opts
    try:
        return dispatch.submit_scan(user["username"], user["role"], body.target,
                                    tools, opts=opts, division=body.division)
    except classifier.ClassifyRejected as e:
        raise HTTPException(status_code=422, detail=f"target rejected: {e}")
    except dispatch.OfflineAgent as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/api/scans/{job_id}")
def scan_status(job_id: str, user: dict = Depends(current_user)):
    job = redis_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
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


# --- approval queue (Pro only; §4.3) ---
class RejectBody(BaseModel):
    reason: str = ""


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
    try:
        data = report_store.read_report(fname)
    except OSError:
        raise HTTPException(status_code=404, detail="no such report")
    return Response(content=data, media_type=DOCX_MIME,
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
