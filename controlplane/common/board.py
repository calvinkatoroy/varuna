"""Compose the team review-pipeline board (v2): pending -> scanning -> reporter -> lead ->
governance -> delivered, plus a terminal rejected column (see proposals.reject_reason).

Pure aggregation over the existing durable stores (proposals + findings in SQLite, jobs in
Redis) - no new persistence, this just shapes what already exists into the Kanban view the
frontend expects. Same "pure, unit-testable without HTTP" pattern as report_pipeline.py: no
FastAPI here, the private API endpoint is a thin wrapper around build_board().
"""
from __future__ import annotations

import db
import models
import redis_store
import tokens
import workflow

COLUMNS = [
    ("pending", "Pending approval", "accent"),
    ("scanning", "Scanning", "info"),
    ("in_review_reporter", "Reporter", "high"),
    ("in_review_lead", "Lead", "crit"),
    ("in_review_governance", "Governance", "med"),
    ("delivered", "Delivered", "low"),
    ("rejected", "Rejected", "crit"),
]

SEV_KEYS = {"critical": "c", "high": "h", "medium": "m", "low": "l"}
META_TRUNC = 60


def _sev_counts(job_id: str | None) -> dict:
    counts = {"c": 0, "h": 0, "m": 0, "l": 0}
    if not job_id:
        return counts
    for f in db.get_findings(job_id):
        if f.get("verdict") != "tp":
            continue
        k = SEV_KEYS.get(f.get("severity"))
        if k:
            counts[k] += 1
    return counts


def _client(org_id: str | None) -> str:
    """Cards name the client organization; the submitter stays on the row for audit."""
    org = db.get_org(org_id) if org_id else None
    return org["name"] if org else "Internal"


def _proposal_card(p: dict) -> dict:
    return {
        "id": p["id"], "client": _client(p["org_id"]), "target": p["target"], "mode": p["mode"],
        "scanMode": p.get("scan_mode", "local"),
        "sev": {"c": 0, "h": 0, "m": 0, "l": 0}, "meta": f"Submitted {p['created_at']}",
    }


def _scanning_card(p: dict) -> dict:
    job = redis_store.get_job(p["job_id"]) if p.get("job_id") else None
    per_tool = (job or {}).get("per_tool_status", {})
    if (job or {}).get("status") == "failed":
        return {
            "id": p["id"], "client": _client(p["org_id"]), "target": p["target"], "mode": p["mode"],
            "sev": _sev_counts(p.get("job_id")), "meta": f"Failed: {job.get('error') or 'scan failed'}",
            "jobId": p.get("job_id"), "suspended": False,
        }
    cloud = p.get("scan_mode") == "cloud"
    online = tokens.is_online(models.CLOUD_AGENT if cloud else p["submitter"])
    meta = ", ".join(f"{t} {s}" for t, s in per_tool.items()) or (
        "Queued" if online else ("Waiting for the cloud scanner" if cloud else "Waiting for client agent"))
    if (job or {}).get("status") == "running" and not online:
        meta += " - scanner offline, scan stalled" if cloud else " - agent offline, scan stalled"   # team should chase it
    return {
        "id": p["id"], "client": _client(p["org_id"]), "target": p["target"], "mode": p["mode"], "scanMode": p.get("scan_mode", "local"),
        "sev": _sev_counts(p.get("job_id")), "meta": meta,
        "jobId": p.get("job_id"),   # needed by the frontend to call suspend/resume by job id
        "suspended": redis_store.is_suspended(p["job_id"]) if p.get("job_id") else False,
    }


def _report_card(r: dict) -> dict:
    # The job that produced this report may have already fallen out of Redis's 24h TTL by the
    # time a multi-day review reaches this stage - fall back to the durable proposal row
    # (matched by job_id) for target/mode rather than a possibly-expired job record.
    p = db.get_proposal_by_job(r["job_id"])
    target = p["target"] if p else r["job_id"]
    mode = p["mode"] if p else "standard"
    v = db.latest_version(r["id"])
    stage_word = "delivered" if r["stage"] == "delivered" else "editing"
    meta = f"v{v['version_no']} · {stage_word}" if v else "v1"
    return {
        "id": r["id"], "client": _client(r["org_id"]), "target": target, "mode": mode, "scanMode": p.get("scan_mode", "local") if p else "local",
        "sev": _sev_counts(r["job_id"]), "meta": meta, "owner": (v or {}).get("editor"),
    }


def _delivered_card(r: dict) -> dict:
    card = _report_card(r)
    if r.get("delivered_pdf"):
        card["meta"] = f"{r['updated_at']} · PDF sent"
    return card


def _rejected_card(p: dict) -> dict:
    card = _proposal_card(p)
    reason = p.get("reject_reason") or "No reason recorded."
    card["meta"] = reason[:META_TRUNC] + ("…" if len(reason) > META_TRUNC else "")
    card["rejectReason"] = reason
    return card


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


def build_board(org_id: str | None = None) -> list[dict]:
    """org_id None = every organization (staff scope)."""
    proposals = db.list_proposals(org_id=org_id)
    reports = db.list_reports(org_id=org_id)
    reported_job_ids = {r["job_id"] for r in reports}

    cols: dict[str, list[dict]] = {cid: [] for cid, _, _ in COLUMNS}
    for p in proposals:
        if p["status"] == "pending":
            cols["pending"].append(_proposal_card(p))
        elif p["status"] == "rejected":
            cols["rejected"].append(_rejected_card(p))
        elif p["status"] == "approved" and p.get("job_id") not in reported_job_ids:
            # Approved with no report yet: still counts as "scanning" whether the agent is
            # actively running or the scan finished and just hasn't been turned into a report.
            cols["scanning"].append(_scanning_card(p))
    for r in reports:
        if r["stage"] == "delivered":
            cols["delivered"].append(_delivered_card(r))
        elif r["stage"] in ("in_review_reporter", "in_review_lead", "in_review_governance"):
            cols[r["stage"]].append(_report_card(r))

    return [{"id": cid, "title": title, "accent": accent, "cards": cols[cid]}
            for cid, title, accent in COLUMNS]


if __name__ == "__main__":
    import redis_store as _rs

    class FakeRedis:
        def __init__(self): self.d = {}
        def get(self, k): return self.d.get(k)
        def set(self, k, v, ex=None): self.d[k] = v

    _rs._client = FakeRedis()
    db.reset_for_test(":memory:")

    org = db.create_org("PT Alice")
    pid = db.create_proposal({"submitter": "alice", "target": "http://t", "mode": "standard", "org_id": org})
    board = build_board()
    assert next(c for c in board if c["id"] == "pending")["cards"][0]["client"] == "PT Alice"

    db.update_proposal(pid, status="approved", job_id="j1")
    _rs.set_job({"id": "j1", "submitter": "alice", "status": "running", "per_tool_status": {"katana": "done"}})
    board = build_board()
    scanning = next(c for c in board if c["id"] == "scanning")["cards"]
    assert len(scanning) == 1 and "katana done" in scanning[0]["meta"]

    rid = db.create_report("j1", org, "alice")
    db.add_report_version(rid, filename="f.docx", editor="aisah", note="v1")
    board = build_board()
    assert next(c for c in board if c["id"] == "scanning")["cards"] == []
    reporter = next(c for c in board if c["id"] == "in_review_reporter")["cards"]
    assert len(reporter) == 1 and reporter[0]["target"] == "http://t" and reporter[0]["owner"] == "aisah"

    pid2 = db.create_proposal({"submitter": "bob", "target": "http://t2", "mode": "standard", "org_id": org})
    db.update_proposal(pid2, status="rejected", reject_reason="not authorized")
    board = build_board()
    rejected = next(c for c in board if c["id"] == "rejected")["cards"]
    assert rejected[0]["rejectReason"] == "not authorized"

    print("board.py self-check OK")
