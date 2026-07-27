"""Submission, Approval Gate, and the single dispatch choke point (SRS §4.3, §4.12).

Every path that can start a scan (Standard local auto-run, Pro launch, post-approval
release) routes through dispatch_job(), which re-asserts the Approval Gate invariant and
the submitter's agent liveness before it ever enqueues. No other code enqueues to an agent.
This is the choke point REQ-19a mandates: the gate cannot be bypassed by a second code path.

Lives in common/ as control-plane business logic imported by the UI (Phase F).
"""
from __future__ import annotations

import datetime
import uuid

import audit
import classifier
import models
import redis_store
import tokens

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"


class OfflineAgent(Exception):
    """Submitter's agent is not online; reject the dispatch, never silently queue (REQ-76)."""


class NotApproved(Exception):
    """A cloud-target Standard request reached dispatch without an Approve action (REQ-19a)."""


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def _is_gated(role: str, target_class: str) -> bool:
    # Only a Standard request against a cloud target is gated (§4.3, C-9).
    return role == models.ROLE_STANDARD and target_class == classifier.CLASS_CLOUD


def submit_scan(submitter: str, role: str, target: str, tools: list,
                opts: dict | None = None, division: str = "") -> dict:
    """Create + route a scan. Raises ClassifyRejected (fail closed) or OfflineAgent.

    Returns {"job_id", "state": "pending_approval" | "dispatched"}.
    """
    target_class = classifier.classify(target)   # raises ClassifyRejected -> caller shows error
    job = models.Job(
        id=str(uuid.uuid4()), target=target, target_class=target_class,
        submitter=submitter, role=role, tools=tools, opts=opts or {},
        status=models.STATUS_QUEUED, per_tool_status={},
    ).to_dict()
    redis_store.set_job(job)
    redis_store.add_user_job(submitter, job["id"])
    audit.log(audit.SUBMIT, submitter=submitter, target=target,
              target_class=target_class, role=role, job=job["id"])

    if _is_gated(role, target_class):
        redis_store.set_approval(job["id"], {
            "submitter": submitter, "division": division, "target": target,
            "target_class": target_class, "timestamp": _now(), "status": PENDING,
        })
        redis_store.add_pending_approval(job["id"])
        return {"job_id": job["id"], "state": "pending_approval"}

    dispatch_job(job)   # Standard local, or any Pro: dispatch now (REQ-15a, REQ-15b)
    return {"job_id": job["id"], "state": "dispatched"}


def dispatch_job(job: dict) -> None:
    """THE choke point. Re-check the gate + agent liveness, then enqueue. REQ-19a, REQ-76."""
    if _is_gated(job["role"], job["target_class"]):
        appr = redis_store.get_approval(job["id"])
        if not appr or appr.get("status") != APPROVED:
            raise NotApproved("cloud-target Standard request is not approved (REQ-19a)")
    if not tokens.is_online(job["submitter"]):
        raise OfflineAgent("Your agent is offline. Start it and try again.")
    redis_store.enqueue_job(job["submitter"], job["id"])


def approve_request(job_id: str, approver: str) -> None:
    """Approve a queued Standard cloud request and dispatch it through the choke point."""
    appr = redis_store.get_approval(job_id)
    if not appr or appr.get("status") != PENDING:
        raise ValueError("no pending request for this job")
    appr["status"] = APPROVED
    redis_store.set_approval(job_id, appr)
    redis_store.remove_pending_approval(job_id)
    audit.log(audit.APPROVE, approver=approver, job=job_id)
    dispatch_job(redis_store.get_job(job_id))   # may raise OfflineAgent (REQ-18)


def reject_request(job_id: str, approver: str, reason: str) -> None:
    """Reject a queued request: discard, notify, never dispatch (REQ-19)."""
    appr = redis_store.get_approval(job_id)
    if not appr or appr.get("status") != PENDING:
        raise ValueError("no pending request for this job")
    appr["status"] = REJECTED
    appr["reason"] = reason
    redis_store.set_approval(job_id, appr)
    redis_store.remove_pending_approval(job_id)
    audit.log(audit.REJECT, approver=approver, job=job_id, reason=reason)


def list_jobs(username: str, limit: int = 20) -> list[dict]:
    """Recent jobs submitted by this user, newest first (for a jobs table, REQ-24 context).

    Skips job ids whose 24h TTL has already expired (redis_store.get_job returns None).
    """
    out = []
    for jid in redis_store.list_user_jobs(username, limit):
        job = redis_store.get_job(jid)
        if job:
            out.append(job)
    return out


def pending_approvals() -> list[dict]:
    """The Approval Queue: pending Standard cloud requests for a Pro user to act on (REQ-16)."""
    out = []
    for jid in redis_store.list_pending_approvals():
        appr = redis_store.get_approval(jid)
        if appr and appr.get("status") == PENDING:
            out.append({**appr, "job_id": jid})
    return out
