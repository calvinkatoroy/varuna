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
import reportcontent  # noqa: E402
import notify  # noqa: E402
import reportdoc  # noqa: E402


def job_org(job: dict) -> str:
    """Organization that owns a job's rows: the originating task's (authoritative), else the
    job's own; "" for staff direct scans, which belong to no organization (staff-only)."""
    p = db.get_proposal_by_job(job["id"])
    return (p or {}).get("org_id") or job.get("org_id") or ""


def start_review(job: dict, editor: str = "system") -> str:
    """A task's report starts when its scan is ingested: the report row (the password and the delivered file live
    there) and content v1. No document is built here; the PDF is made later, on the audit page. Safe to repeat."""
    task = db.get_proposal_by_job(job["id"])
    if not task:
        raise ValueError("this scan belongs to no task")
    rid = reportdoc.ensure_report(task)["id"]
    reportcontent.ensure_v1(task, editor)
    audit.log("report_created", actor=editor, report=rid, job=job["id"])
    notify.notify(f"Report {rid[:8]} is ready for the assignee")
    return rid


def process_job(job_id: str, raw: dict) -> None:
    job = redis_store.get_job(job_id)
    if not job:
        return  # job expired between upload and processing (24h TTL)
    findings = parse.parse_all(raw, job)
    findings = correlate.correlate(findings)   # dedup + OWASP/CWE tag + priority
    # Findings are durable (SQLite), unlike the job record they came from - they must outlive
    # the job's 24h Redis TTL to survive the (possibly multi-day) review pipeline.
    db.save_findings(job_id, job["submitter"], job_org(job), findings, quick=bool(job.get("quick")))
    # A task's scan gets its report automatically (direct team scans have none; use /api/reports/generate).
    task = db.get_proposal_by_job(job_id)
    if task and not db.report_for_task(task["id"]):
        try:
            start_review(job)
        except Exception as e:   # a report-generation failure must not lose the findings
            print(f"WARNING: could not start review for job {job_id}: {e}", flush=True)
    # AI text comes last: the findings and the report are usable at once, enrichment fills in behind them
    # (ponytail: sequential, ~20 s a finding on a 7B; only empty fields are written, so a pentester's edit wins).
    for f in findings:
        e = ollama.enrich(dict(f))
        if e.get("impact") and e.get("remediation"):   # enrich() returns the finding unchanged on failure (REQ-36)
            db.fill_enrichment(db._finding_id(job_id, f), e["impact"], e["remediation"], e.get("risk_rating"))
    # ponytail: findings-ready is signalled by get_findings() being non-empty, not by job
    # status (the agent owns status). If the tiny status=done-before-findings race ever
    # matters to a UI, have ingest flip a findings_ready flag here.
