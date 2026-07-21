"""FastAPI agent-API, the only interface any agent talks to (SRS §3.3, §4.12).

Endpoints (all agent-initiated, outbound-only from the agent's side):
  POST /agent/enroll              consume an enrollment token, issue a bearer token
  GET  /agent/poll                fetch the next job for this agent's account
  POST /agent/jobs/{id}/status    update overall/per-tool status (ownership-checked)
  POST /agent/jobs/{id}/findings  upload raw tool output (ownership-checked)
  POST /agent/heartbeat           liveness ping

Every endpoint except enroll requires a valid bearer token (NFR-23); the status and
findings endpoints additionally require that the caller owns the job (NFR-26).
Fronted by Caddy on :443 in production (§3.4); runs on an internal port otherwise.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # repo-root .env, for host-run dev (REDIS_URL, JWT_SECRET, ...)

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import redis_store  # noqa: E402
import tokens  # noqa: E402
import ingest  # noqa: E402

app = FastAPI(title="Varuna Agent API")


def current_agent(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    username = tokens.verify_agent_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="invalid or revoked agent token")
    return username


def _owned_job_or_403(job_id: str, username: str) -> dict:
    job = redis_store.get_job(job_id)
    if not tokens.owns_job(username, job):
        # 404-shaped as 403: don't distinguish "not yours" from "gone" to a caller.
        raise HTTPException(status_code=403, detail="job not owned by this agent")
    return job


class EnrollBody(BaseModel):
    enrollment_token: str


class StatusBody(BaseModel):
    status: str | None = None
    per_tool_status: dict | None = None
    error: str | None = None


class FindingsBody(BaseModel):
    raw: dict   # e.g. {"nuclei": "<jsonl>", "sqlmap": "<stdout>", "katana": "<jsonl>"}


@app.post("/agent/enroll")
def enroll(body: EnrollBody):
    username = tokens.consume_enrollment_token(body.enrollment_token)
    if not username:
        raise HTTPException(status_code=401, detail="invalid or expired enrollment token")
    token = tokens.issue_agent_token(username)
    return {"token": token, "username": username}


@app.get("/agent/poll")
def poll(username: str = Depends(current_agent)):
    tokens.touch_agent(username)
    job_id = redis_store.dequeue_job(username)
    if not job_id:
        return {"job": None}
    job = redis_store.get_job(job_id)   # may be None if it expired between dispatch and poll
    return {"job": job}


@app.post("/agent/jobs/{job_id}/status")
def update_status(job_id: str, body: StatusBody, username: str = Depends(current_agent)):
    job = _owned_job_or_403(job_id, username)
    if body.status is not None:
        job["status"] = body.status
    if body.per_tool_status:
        job.setdefault("per_tool_status", {}).update(body.per_tool_status)
    if body.error is not None:
        job["error"] = body.error
    redis_store.set_job(job)
    return {"ok": True}


@app.post("/agent/jobs/{job_id}/findings")
def upload_findings(job_id: str, body: FindingsBody, background: BackgroundTasks,
                    username: str = Depends(current_agent)):
    _owned_job_or_403(job_id, username)
    redis_store.set_raw(job_id, body.raw)
    background.add_task(ingest.process_job, job_id, body.raw)   # parse -> correlate -> enrich -> store
    return {"ok": True}


@app.post("/agent/heartbeat")
def heartbeat(username: str = Depends(current_agent)):
    tokens.touch_agent(username)
    return {"ok": True}
