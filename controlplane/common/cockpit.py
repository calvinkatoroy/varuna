"""Compose the client dashboard aggregate (v2): one client's own engagements, portfolio
posture, findings trend, and latest delivered report - shaped for ClientCockpit.tsx.

Pure aggregation over durable stores (proposals + findings in SQLite, jobs in Redis), same
"pure, unit-testable without HTTP" pattern as board.py/report_pipeline.py.

Trend is bucketed from findings' own created_at month, not a padded fixed 6-month window -
there's no time-series store here, so this only ever shows as much real history as actually
exists (often 1 point for a fresh account). Honest over impressive.
"""
from __future__ import annotations

import db
import redis_store

GRADE_BANDS = (  # (min_critical, min_high) -> grade, checked in order
    (2, 0, "D"), (1, 0, "C"), (0, 1, "B"), (0, 0, "A"),
)


def _grade(sev: dict) -> str:
    for min_c, min_h, g in GRADE_BANDS:
        if sev["c"] >= min_c and sev["h"] >= min_h:
            return g
    return "A"


def _sev_counts(job_id: str | None) -> tuple[dict, int, int]:
    counts = {"c": 0, "h": 0, "m": 0, "l": 0}
    if not job_id:
        return counts, 0, 0
    fixed = 0
    key_of = {"critical": "c", "high": "h", "medium": "m", "low": "l"}
    for f in db.get_findings(job_id):
        if f.get("verdict") != "tp":
            continue
        k = key_of.get(f.get("severity"))
        if k:
            counts[k] += 1
        if f.get("status") == "fixed":
            fixed += 1
    open_n = sum(counts.values()) - fixed
    return counts, max(open_n, 0), fixed


def client_status(p: dict) -> str:
    """Map a raw proposal row (status: pending/approved/rejected) to the client-facing
    vocabulary (pending/scanning/in_review/delivered/rejected) the frontend actually uses -
    shared here so /api/cockpit and /api/proposals can't drift apart on what "scanning" means."""
    if p["status"] in ("pending", "rejected"):
        return p["status"]
    # approved: derive from report stage. No direct proposal->report FK; look it up by job.
    reports = [r for r in db.list_reports(org_id=p["org_id"]) if r["job_id"] == p.get("job_id")]
    report = reports[0] if reports else None
    if report and report["stage"] == "delivered":
        return "delivered"
    return "in_review" if report else "scanning"


def _engagement(p: dict) -> dict | None:
    status = client_status(p)
    if status == "rejected":
        return None
    sev, open_n, fixed = _sev_counts(p.get("job_id"))
    return {
        "id": p["id"], "target": p["target"], "mode": p["mode"], "status": status,
        "grade": _grade(sev), "sev": sev, "open": open_n, "fixed": fixed,
        "when": p["updated_at"],
    }


def _trend(findings: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = {}
    key_of = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
    for f in findings:
        if f.get("status") == "fixed":
            continue   # trend tracks OPEN findings by month, matching the cockpit's "open now"
        month = (f.get("created_at") or "")[:7]   # "YYYY-MM"
        if not month:
            continue
        row = buckets.setdefault(month, {"month": month, "critical": 0, "high": 0, "medium": 0, "low": 0})
        k = key_of.get(f.get("severity"))
        if k:
            row[k] += 1
    return [buckets[m] for m in sorted(buckets)]


def build_cockpit(username: str, org_id: str) -> dict:
    """One organization's dashboard (every member of the org sees the same data)."""
    proposals = db.list_proposals(org_id=org_id)
    engagements = [e for e in (_engagement(p) for p in proposals) if e]

    findings = [f for f in db.list_findings(org_id=org_id) if f.get("verdict") == "tp"]
    sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    fixed = 0
    for f in findings:
        if f.get("severity") in sev:
            sev[f["severity"]] += 1
        if f.get("status") == "fixed":
            fixed += 1
    total = sum(sev.values())
    posture = {
        **sev, "total": total, "fixed": fixed, "open": max(total - fixed, 0),
        "resolved": round(100 * fixed / total) if total else 0,
    }

    delivered = [r for r in db.list_reports(org_id=org_id) if r["stage"] == "delivered"]
    latest = delivered[0] if delivered else None
    if latest:
        rp = db.get_proposal_by_job(latest["job_id"])
        latest_report = {
            "engagement": (rp or {}).get("target", latest["job_id"]),
            "delivered": latest["updated_at"],
            "templates": 1,
            "findings": len(db.get_findings(latest["job_id"])),
            "signed": True,
        }
    else:
        latest_report = None

    return {
        # Real accounts have no separate display name today; username stands in for it.
        "me": {"username": username, "name": username, "role": "client"},
        "engagements": engagements,
        "posture": posture,
        "trend": _trend(findings),
        "latestReport": latest_report,
    }


if __name__ == "__main__":
    class FakeRedis:
        def __init__(self): self.d = {}
        def get(self, k): return self.d.get(k)
        def set(self, k, v, ex=None): self.d[k] = v

    redis_store._client = FakeRedis()
    db.reset_for_test(":memory:")

    org = db.create_org("PT Alice")
    pid = db.create_proposal({"submitter": "alice", "target": "http://t", "mode": "standard", "org_id": org})
    assert build_cockpit("bob", db.create_org("PT Bob"))["engagements"] == []
    c = build_cockpit("alice", org)
    assert c["engagements"][0]["status"] == "pending" and c["posture"]["total"] == 0

    db.update_proposal(pid, status="approved", job_id="j1")
    db.save_findings("j1", "alice", org, [
        {"name": "SQLi", "severity": "critical", "host": "h"},
        {"name": "XSS", "severity": "low", "host": "h"},
    ])
    c = build_cockpit("alice", org)
    eng = c["engagements"][0]
    assert eng["status"] == "scanning" and eng["sev"]["c"] == 1 and eng["grade"] == "C"
    assert c["posture"]["total"] == 2 and c["posture"]["open"] == 2
    assert len(c["trend"]) >= 1

    rid = db.create_report("j1", org, "alice")
    db.set_report(rid, stage="delivered", delivered_pdf="x.pdf")
    c = build_cockpit("alice", org)
    assert c["engagements"][0]["status"] == "delivered"
    assert c["latestReport"]["engagement"] == "http://t"

    print("cockpit.py self-check OK")
