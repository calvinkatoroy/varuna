"""Report helpers shared by workflow, the audit routes and the PDF worker: filename slugs, the findings digest,
"is the PDF current", the per-task report row. Stdlib and db only (workflow imports this module)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
from typing import Optional
from urllib.parse import urlsplit

import db
import models

SLUG_MAX = 40
FILENAME_RE = re.compile(r"[A-Za-z0-9_]{1,200}\.pdf")   # used with fullmatch: `$` would accept a trailing newline
FALLBACK_FILENAME = "Pentest_Report.pdf"
_DIGEST_FIELDS = ("id", "verdict", "severity", "name", "host", "url", "description", "impact", "remediation",
                  "evidence", "cve", "cvss", "cwe", "owasp", "risk_rating", "tool")


def slug(text, fallback: str, limit: int = SLUG_MAX) -> str:
    ascii_text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    out = "_".join(re.findall(r"[A-Za-z0-9]+", ascii_text))[:limit].strip("_")
    return out or fallback


def target_host(target) -> str:
    t = (target or "").strip()
    try:
        return urlsplit(t if "://" in t else "http://" + t).hostname or ""
    except ValueError:
        return ""


def pdf_filename(org_name, target, n: int) -> str:
    return f"{slug(org_name, 'Client')}_{slug(target_host(target), 'Target')}_Pentest_Report_{int(n)}.pdf"


def safe_filename(name) -> str:
    """The only names that may reach a header are the ones the slugger can produce."""
    return name if isinstance(name, str) and FILENAME_RE.fullmatch(name) else FALLBACK_FILENAME


def content_disposition(name) -> str:
    n = safe_filename(name)
    return f"attachment; filename=\"{n}\"; filename*=UTF-8''{n}"


def ai_chat_enabled() -> bool:
    return os.environ.get("VARUNA_AI_CHAT", "1") != "0"


def findings_for(task: dict) -> list[dict]:
    """All findings of the task, in the one order the report uses (severity, then age, then id)."""
    rows = db.task_findings(task["id"])
    rows.sort(key=lambda f: (models.severity_rank(f.get("severity")), f.get("created_at") or "", f["id"]))
    return rows


def digest(findings: list[dict]) -> str:
    rows = sorted(({k: f.get(k) for k in _DIGEST_FIELDS} for f in findings), key=lambda r: r["id"])
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def _sev(f: dict) -> str:
    s = (f.get("severity") or "info").lower()
    return s if s in models.SEVERITY_ORDER else "info"


def counts(findings: list[dict]) -> dict:
    tp = [f for f in findings if (f.get("verdict") or "tp") != "fp"]
    sev = {s: 0 for s in models.SEVERITY_ORDER}
    for f in tp:
        sev[_sev(f)] += 1
    return {"total": len(findings), "tp": len(tp), "fp": len(findings) - len(tp),
            "manual": sum(1 for f in findings if f.get("tool") == "manual"), "severity": sev}


def pdf_gap(task: dict) -> Optional[str]:
    """Why this task cannot be submitted for review yet; None when a ready PDF matches the content and findings."""
    c = db.latest_content(task["id"])
    if not c:
        return "Open the audit page and generate the PDF before submitting."
    ready = db.latest_ready_pdf(task["id"])
    if not ready:
        return "Generate the PDF for this report before submitting it for review."
    if ready["content_version"] != c["version"] or ready["digest"] != digest(findings_for(task)):
        return "The report changed after the last PDF. Generate the PDF again before submitting."
    return None


def ensure_report(task: dict) -> dict:
    """The task's one row in `reports` (it carries the PDF password and the delivered file)."""
    r = db.report_for_task(task["id"])
    if r:
        return r
    try:
        rid = db.create_report(task.get("job_id") or "", task["org_id"], task["submitter"],
                               template="Pentest Report", task_id=task["id"])
    except sqlite3.IntegrityError:   # another request created it first
        return db.report_for_task(task["id"])
    return db.get_report(rid, org_id=None)
