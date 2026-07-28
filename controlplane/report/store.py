"""Generated-report store: save .docx to a volume, index metadata in Redis (DAT-2, REQ-50).

Public-plane scope: a Standard user's own Executive Summaries (REQ-50a). The Pro full
archive lives on the private plane (private API). Files persist on a volume; the Redis index
lets the Reports page list them without scanning the filesystem.
"""
from __future__ import annotations

import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import redis_store  # noqa: E402

REPORTS_DIR = os.environ.get("REPORTS_DIR", "report_output")
RETENTION_DAYS = int(os.environ.get("REPORT_RETENTION_DAYS", "7"))   # NFR-28


GLOBAL_KEY = "reports:_all"   # Pro full archive across all users (REQ-50a)


def _index_key(user: str) -> str:
    return f"reports:{user}"


def save_report(user: str, job_id: str, template: str, data: bytes) -> dict:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    fname = f"{job_id}_{template.replace(' ', '_')}.docx"
    with open(os.path.join(REPORTS_DIR, fname), "wb") as f:
        f.write(data)
    meta = {"user": user, "job_id": job_id, "template": template, "file": fname,
            "ts": datetime.datetime.now(datetime.UTC).isoformat()}
    r = redis_store.get_redis()
    r.rpush(_index_key(user), json.dumps(meta))
    r.rpush(GLOBAL_KEY, json.dumps(meta))
    purge_old_reports()   # opportunistic retention enforcement (NFR-28)
    return meta


def list_reports(user: str) -> list[dict]:
    r = redis_store.get_redis()
    return [json.loads(x) for x in r.lrange(_index_key(user), 0, -1)]


def list_all_reports() -> list[dict]:
    r = redis_store.get_redis()
    return [json.loads(x) for x in r.lrange(GLOBAL_KEY, 0, -1)]


def save_report_file(fname: str, data: bytes) -> None:
    """Write raw report bytes (a review version or delivered PDF) to the reports volume."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(os.path.join(REPORTS_DIR, fname), "wb") as f:
        f.write(data)


def owner_of(fname: str) -> str | None:
    """Owner (username) of a report file, from the global index; None if unknown (v2 tenancy)."""
    for m in list_all_reports():
        if m.get("file") == fname:
            return m.get("user")
    return None


def read_report(fname: str) -> bytes:
    with open(os.path.join(REPORTS_DIR, fname), "rb") as f:
        return f.read()


def purge_old_reports(max_age_days: int | None = None) -> int:
    """Delete reports past the retention window; rebuild the indexes from what remains (NFR-28).

    Called opportunistically on save; also runnable on a schedule for strict enforcement.
    ponytail: O(n) index rebuild per call, fine at PoC scale; index by day-bucket if it grows.
    """
    max_age_days = RETENTION_DAYS if max_age_days is None else max_age_days
    cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=max_age_days)
    r = redis_store.get_redis()
    kept, purged = [], 0
    for m in list_all_reports():
        try:
            ts = datetime.datetime.fromisoformat(m["ts"])
        except (ValueError, KeyError, TypeError):
            kept.append(m)   # unparseable timestamp: keep, don't silently delete
            continue
        if ts >= cutoff:
            kept.append(m)
        else:
            try:
                os.remove(os.path.join(REPORTS_DIR, m["file"]))
            except OSError:
                pass
            purged += 1
    for key in list(r.scan_iter(match="reports:*")):
        r.delete(key)
    for m in kept:
        r.rpush(GLOBAL_KEY, json.dumps(m))
        r.rpush(_index_key(m["user"]), json.dumps(m))
    return purged


def wipe_all() -> dict:
    """Offboarding data-destruction (NFR-28): all findings, reports, scan data, and the audit
    log. Accounts and agent bindings are intentionally NOT touched (remove separately)."""
    counts = redis_store.wipe_scan_data()
    redis_store.wipe_audit()
    r = redis_store.get_redis()
    for key in list(r.scan_iter(match="reports:*")):
        r.delete(key)
    files = 0
    if os.path.isdir(REPORTS_DIR):
        for fn in os.listdir(REPORTS_DIR):
            try:
                os.remove(os.path.join(REPORTS_DIR, fn))
                files += 1
            except OSError:
                pass
    counts["report_files"] = files
    return counts
