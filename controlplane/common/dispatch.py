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
import db
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


def submit_scan(submitter: str, role: str, org_id: str | None, target: str, tools: list,
                opts: dict | None = None, division: str = "") -> dict:
    """Create + route a scan. Raises ClassifyRejected (fail closed) or OfflineAgent.
    org_id comes from the submitting account (None for staff), never from request input.

    Returns {"job_id", "state": "pending_approval" | "dispatched"}.
    """
    target_class = classifier.classify(target)   # raises ClassifyRejected -> caller shows error
    job = models.Job(
        id=str(uuid.uuid4()), target=target, target_class=target_class,
        submitter=submitter, role=role, tools=tools, opts=opts or {},
        status=models.STATUS_QUEUED, per_tool_status={}, org_id=org_id,
    ).to_dict()
    redis_store.set_job(job)
    redis_store.add_org_job(org_id, job["id"])
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


def dispatch_job(job: dict, pre_approved: bool = False) -> None:
    """THE choke point. Re-check the gate + agent liveness, then enqueue. REQ-19a, REQ-76.

    pre_approved (v2): a lead-pentester-approved proposal already gated this job. Skip the
    legacy standard+cloud redis-approval check AND the online refusal, and queue it for the
    client's agent to pick up whenever it next polls (the client installs the agent AFTER
    approval, so it is normally offline at approve-time).
    A job whose organization differs from the receiving agent's is never enqueued: it is failed.
    """
    if _org_mismatch(job):
        job.update(status=models.STATUS_FAILED, error="scan refused: agent belongs to another organization")
        redis_store.set_job(job)
        audit.log("dispatch_refused_org", job=job["id"], agent=job.get("executor") or job["submitter"])
        print(f"WARNING: refused job {job['id']}: organization differs from the agent's", flush=True)
        return
    if pre_approved:
        redis_store.enqueue_job(job.get("executor") or job["submitter"], job["id"])   # cloud jobs go to the cloud scanner
        return
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


def _org_mismatch(job: dict) -> bool:
    """True when the agent that would run this job belongs to another organization. Agents are
    per user: the org is the account's (DB) and, once enrolled, the one recorded at enrolment.
    Varuna's own cloud scanner serves every organization."""
    owner = job.get("executor") or job["submitter"]
    if owner == models.CLOUD_AGENT:
        return False
    orgs = {(db.get_account(owner) or {}).get("org_id") or None}
    agent = redis_store.get_agent(owner)
    if agent and "org_id" in agent:
        orgs.add(agent["org_id"] or None)
    return orgs != {job.get("org_id") or None}


def get_job(scope, job_id: str) -> dict | None:
    """A Redis job as seen through a tenancy Scope: None when missing or outside the scope."""
    job = redis_store.get_job(job_id)
    if not job or (scope.org_id is not None and job.get("org_id") != scope.org_id):
        return None
    return job


def list_jobs(org_id: str | None, limit: int = 20) -> list[dict]:
    """Recent jobs of this organization, newest first (for a jobs table, REQ-24 context).
    org_id None lists staff direct scans (they belong to no organization).

    Skips job ids whose 24h TTL has already expired (redis_store.get_job returns None).
    """
    out = []
    for jid in redis_store.list_org_jobs(org_id, limit):
        job = redis_store.get_job(jid)
        if job and (job.get("org_id") or None) == (org_id or None):
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
