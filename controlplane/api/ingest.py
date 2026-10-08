"""Ingest: turn an agent's raw upload into stored, enriched, correlated findings.

Runs as a FastAPI BackgroundTask off the findings-upload endpoint so the upload returns
fast while enrichment (slow, per-finding) happens after. Parsing, enrichment, and
correlation all happen centrally on the control plane (§4.5.1, §4.6, §4.6b).

Order is dedup-BEFORE-enrich: correlate merges duplicates first, so enrichment runs once
per real finding instead of once per raw hit (fewer LLM calls). Correlation's priority sort
uses tool/severity, which are known pre-enrichment, so the ordering stays valid.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))

import db  # noqa: E402
import redis_store  # noqa: E402
import models  # noqa: E402
import parse  # noqa: E402
import correlate  # noqa: E402
import ollama  # noqa: E402
import audit  # noqa: E402
import generator  # noqa: E402
import notify  # noqa: E402
import store as report_store  # noqa: E402


def job_org(job: dict) -> str:
    """Organization that owns a job's rows: the originating task's (authoritative), else the
    job's own; "" for staff direct scans, which belong to no organization (staff-only)."""
    p = db.get_proposal_by_job(job["id"])
    return (p or {}).get("org_id") or job.get("org_id") or ""


def add_manual_finding(job_id: str, fields: dict) -> list[dict]:
    """Append a Pro-entered finding to a job, then re-correlate + enrich (§4.6a, REQ-57 to 60).

    Uses the same schema and pipeline as automated findings; tagged tool="manual" (REQ-58).
    Correlation may dedup it against an existing automated finding on the same host/url.
    """
    job = redis_store.get_job(job_id)
    if not job:
        raise ValueError("no such job (it may have expired)")
    manual = models.Finding(tool="manual", **fields).to_dict()
    combined = db.get_findings(job_id) + [manual]
    combined = correlate.correlate(combined)          # dedup + tag + priority over the whole set
    combined = ollama.enrich_missing(combined)         # enrich only the not-yet-enriched (REQ-59)
    db.save_findings(job_id, job["submitter"], job_org(job), combined)
    return combined


def start_review(job: dict, template: str = "Full Technical", editor: str = "system") -> str:
    """Generate v1 of the task's report (a draft until delivery). The owner is the client who owns the job."""
    data = generator.generate(job, db.get_findings(job["id"]), template)
    rid = db.create_report(job["id"], job_org(job), job["submitter"], template=template)
    fname = f"{rid}_v1.docx"
    report_store.save_report_file(fname, data)
    db.add_report_version(rid, filename=fname, editor=editor, note="auto-generated v1")
    audit.log("report_created", actor=editor, report=rid, job=job["id"])
    notify.notify(f"Report {rid[:8]} is ready for the assignee")
    return rid


def process_job(job_id: str, raw: dict) -> None:
    job = redis_store.get_job(job_id)
    if not job:
        return  # job expired between upload and processing (24h TTL)
    findings = parse.parse_all(raw, job)
    findings = correlate.correlate(findings)   # dedup + OWASP/CWE tag + priority
    findings = ollama.enrich_all(findings)     # graceful fallback per finding (REQ-36)
    # Findings are durable (SQLite), unlike the job record they came from - they must outlive
    # the job's 24h Redis TTL to survive the (possibly multi-day) review pipeline.
    db.save_findings(job_id, job["submitter"], job_org(job), findings)
    # A task's scan gets its report automatically (direct team scans have none; use /api/reports/generate).
    if db.get_proposal_by_job(job_id) and not db.get_report_by_job(job_id):
        try:
            start_review(job)
        except Exception as e:   # a report-generation failure must not lose the findings
            print(f"WARNING: could not start review for job {job_id}: {e}", flush=True)
    # ponytail: findings-ready is signalled by get_findings() being non-empty, not by job
    # status (the agent owns status). If the tiny status=done-before-findings race ever
    # matters to a UI, have ingest flip a findings_ready flag here.
