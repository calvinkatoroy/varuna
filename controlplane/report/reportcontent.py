"""Report content v1: the fixed sections and their starting text, built deterministically from the task (no LLM).
Findings are NOT copied in: counts, tables and finding pages are computed when the report is rendered."""
from __future__ import annotations

import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import db  # noqa: E402
import generator  # noqa: E402
import reportdoc  # noqa: E402

SCHEMA = 1
METHOD_INTRO = ("The assessment followed the steps below. Each step was automated and non-destructive, and the "
                "results were reviewed by the security team before this report was issued.")
METHOD_STEPS = (
    "Discovery: the application was crawled to enumerate pages, parameters and forms.",
    "Detection: known-vulnerability and misconfiguration checks, and injection testing, were run against what was found.",
    "Correlation: duplicate and related results were merged and each finding was classified against OWASP Top 10 (2021) and CWE.",
    "Triage: results were reviewed by the security team; false positives were removed before this report.",
    "Reporting: each finding is rated, described, evidenced, and paired with remediation guidance.",
)


def baseline(task: dict, org_name: str) -> dict:
    ids = itertools.count(1)
    nid = lambda: f"b{next(ids)}"   # noqa: E731
    para = lambda text, editable=True: {"id": nid(), "type": "paragraph", "text": text, "editable": editable}   # noqa: E731
    bullet = lambda text: {"id": nid(), "type": "bullet", "text": text, "editable": True}   # noqa: E731
    comp = lambda kind: {"id": nid(), "type": kind}   # noqa: E731
    host = reportdoc.target_host(task["target"]) or task["target"]
    client = org_name or "the client"
    return {"schema": SCHEMA, "sections": [
        {"id": "cover", "title": "Cover", "ai_insert": False, "blocks": [comp("cover")]},
        {"id": "executive_summary", "title": "Executive Summary", "ai_insert": True, "blocks": [
            para(f"Varuna performed an automated web application vulnerability assessment of {host} for {client}. "
                 "This report lists the findings the security team confirmed, how serious they are and how to fix them."),
            comp("severity_table"),
            para("Findings rated critical or high can lead to data exposure or system compromise and should be fixed "
                 "first; the remediation roadmap gives recommended timeframes."),
        ]},
        {"id": "scope", "title": "Scope and Coverage", "ai_insert": False,
         "blocks": [comp("scope_table"), *[para(p, editable=False) for p in generator.COVERAGE_PARAS]]},
        {"id": "methodology", "title": "Methodology", "ai_insert": True,
         "blocks": [para(METHOD_INTRO), *[bullet(s) for s in METHOD_STEPS], comp("tools_table")]},
        {"id": "findings_summary", "title": "Findings Summary", "ai_insert": False, "blocks": [comp("findings_table")]},
        {"id": "findings", "title": "Detailed Findings", "ai_insert": False,
         "blocks": [{"id": nid(), "type": "finding_overrides", "overrides": {}}]},
        {"id": "conclusion", "title": "Conclusion and Roadmap", "ai_insert": True, "blocks": [
            para("Prioritize remediation of critical and high findings, re-test after fixes, and schedule a follow-up "
                 "assessment to confirm closure."),
            comp("roadmap"),
        ]},
    ]}


def ensure_v1(task: dict, actor: str = "system") -> dict:
    """The task's latest content row, creating version 1 first when there is none (safe to call concurrently)."""
    c = db.latest_content(task["id"])
    if c:
        return c
    org = (db.get_org(task["org_id"]) or {}).get("name", "")
    db.add_content(task["id"], task["org_id"], baseline(task, org), actor, "Built from the scan", base_version=0)
    return db.latest_content(task["id"])
