"""Team board (step 2): columns by role, built from proposals.stage/scan_state (filtered in the query).
Pentesters and lead pentesters see every column; each other reviewer role sees only its own approval
list plus Delivered. The private API endpoint is a thin wrapper around build_board()."""
from __future__ import annotations

import db
import models
import redis_store
import tokens
import workflow

COLUMNS = [
    ("task", "Tasks", "accent"),
    ("scan", "Scans", "info"),
    ("completed", "Completed", "high"),
    ("review_lead_pentester", "Lead Pentester review", "crit"),
    ("review_lead_cyber", "Lead Cyber review", "med"),
    ("review_governance", "Governance review", "med"),
    ("review_manager", "Manager review", "high"),
    ("delivered", "Delivered", "low"),
    ("closed", "Declined / Expired", "crit"),
]
_STAGES = {"closed": ("declined", "expired"), "review_manager": ("review_manager", workflow.DELIVERING)}

CAP = 50
_CAPPED = ("delivered", "closed")

SEV_KEYS = {"critical": "c", "high": "h", "medium": "m", "low": "l"}


def visible_columns(role: str) -> list[str]:
    if role in workflow.PENTESTERS:
        return [c[0] for c in COLUMNS]
    own = next((s for s, r in workflow.STAGE_ROLE.items() if r == role), None)
    return [own, "delivered"] if own else []


def _sev_counts(job_id: str | None) -> dict:
    counts = {"c": 0, "h": 0, "m": 0, "l": 0}
    for f in db.get_findings(job_id) if job_id else []:
        k = SEV_KEYS.get(f.get("severity"))
        if f.get("verdict") == "tp" and k:
            counts[k] += 1
    return counts


def _client(org_id: str | None) -> str:
    """Cards name the client organization; the submitter stays on the row for audit."""
    org = db.get_org(org_id) if org_id else None
    return org["name"] if org else "Internal"


def _scan_meta(t: dict) -> str:
    state = t.get("scan_state")
    if state == "pending":
        return f"Claimed by {t.get('assignee') or 'nobody'}"
    if state == "scheduled":
        return f"Starts {t.get('scheduled_at')}"
    if state == "suspended":
        return t.get("suspend_reason") or "Suspended"
    job = redis_store.get_job(t["job_id"]) if t.get("job_id") else None
    cloud = t.get("scan_mode") == models.SCAN_CLOUD
    online = tokens.is_online(models.CLOUD_AGENT if cloud else t["submitter"])
    meta = ", ".join(f"{k} {v}" for k, v in (job or {}).get("per_tool_status", {}).items()) or (
        "Queued" if online else ("Waiting for the cloud scanner" if cloud else "Waiting for client agent"))
    if (job or {}).get("status") == "running" and not online:
        meta += " - scanner offline, scan stalled" if cloud else " - agent offline, scan stalled"
    return meta


def _meta(t: dict) -> str:
    stage = t["stage"]
    if stage == "task":
        return f"Submitted {t['created_at']}"
    if stage == "scan":
        return _scan_meta(t)
    if stage == "completed":
        return "Scan finished, ready to submit"
    if stage == workflow.DELIVERING:
        return "Delivering the protected PDF"
    if stage == "delivered":
        return f"{t['updated_at']} · PDF sent"
    if stage == "declined":
        return t.get("decline_cause") or "Declined"
    if stage == "expired":
        return "Client window ended"
    r = db.get_report_by_job(t["job_id"]) if t.get("job_id") else None
    v = db.latest_version(r["id"]) if r else None
    return f"v{v['version_no']} · {v['editor']}" if v else "No report yet"


def _card(t: dict, viewer: dict) -> dict:
    return {
        "id": t["id"], "version": t["version"], "stage": t["stage"], "scanState": t.get("scan_state"),
        "client": _client(t["org_id"]), "target": workflow.scan_url(t), "scanMode": t.get("scan_mode", "local"),
        "sev": _sev_counts(t.get("job_id")), "meta": _meta(t), "assignee": t.get("assignee"),
        "jobId": t.get("job_id"), "suspended": t.get("scan_state") == "suspended",
        "reason": t.get("decline_cause") or t.get("suspend_reason"),
        "actions": workflow.actions(t, viewer["username"]),
    }


STALL_SECONDS = 15 * 60   # a running scan whose agent has been silent this long is failed, not "scanning"


def reap_stalled(now=None) -> int:
    """A running scan whose agent has been silent 15+ min: fail the job and suspend the task with the reason,
    so it never sits in 'in progress' forever. Returns how many were reaped."""
    n = 0
    for t in db.list_proposals(stage="scan", scan_state="in_progress", org_id=None):   # background: every org
        job = redis_store.get_job(t["job_id"]) if t.get("job_id") else None
        if not job or job.get("status") != "running":
            continue
        agent = models.CLOUD_AGENT if t.get("scan_mode") == models.SCAN_CLOUD else t["submitter"]
        gap = tokens.offline_seconds(agent, now)
        if gap is not None and gap > STALL_SECONDS:
            reason = f"agent offline for {int(gap // 60)} min during the scan"
            job.update(status="failed", error=reason)
            redis_store.set_job(job)
            try:
                workflow.transition(t["id"], "scan/suspended", workflow.SYSTEM, org_id=None, comment=reason, now=now)
            except workflow.WorkflowError:
                pass
            n += 1
    return n


def build_board(viewer: dict, column: str | None = None) -> list[dict]:
    """viewer = the signed-in staff member ({username, role}). Raises PermissionError for a hidden column."""
    cols = visible_columns(viewer["role"])
    if column is not None:
        if column not in cols:
            raise PermissionError(column)
        cols = [column]
    out = []
    for cid, title, accent in COLUMNS:
        if cid not in cols:
            continue
        tasks = [t for s in _STAGES.get(cid, (cid,)) for t in db.list_proposals(stage=s, org_id=None)]
        col = {"id": cid, "title": title, "accent": accent}
        if cid in _CAPPED:   # long-lived columns show the newest cards only
            tasks.sort(key=lambda t: t["updated_at"], reverse=True)
            col["more"] = max(0, len(tasks) - CAP)
            tasks = tasks[:CAP]
        out.append({**col, "cards": [_card(t, viewer) for t in tasks]})
    return out
