"""Reporting Intelligence: correlate/dedup, OWASP/CWE tagging, priority order (SRS §4.6b).

This is where a pile of raw hits becomes a validated, prioritized finding set, the
difference between a scanner and a report generator. Runs over the whole finding set for
a job (automated + manual) before Findings Review and Report Generation (REQ-61 to REQ-64).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import models  # noqa: E402

# CWE -> OWASP Top 10:2021 category (modest, defensible subset; REQ-62).
CWE_OWASP = {
    "CWE-89": "A03:2021-Injection",
    "CWE-79": "A03:2021-Injection",
    "CWE-78": "A03:2021-Injection",
    "CWE-94": "A03:2021-Injection",
    "CWE-22": "A01:2021-Broken Access Control",
    "CWE-284": "A01:2021-Broken Access Control",
    "CWE-639": "A01:2021-Broken Access Control",
    "CWE-200": "A05:2021-Security Misconfiguration",
    "CWE-16": "A05:2021-Security Misconfiguration",
    "CWE-1104": "A06:2021-Vulnerable and Outdated Components",
    "CWE-937": "A06:2021-Vulnerable and Outdated Components",
    "CWE-287": "A07:2021-Identification and Authentication Failures",
    "CWE-384": "A07:2021-Identification and Authentication Failures",
    "CWE-502": "A08:2021-Software and Data Integrity Failures",
    "CWE-918": "A10:2021-Server-Side Request Forgery",
    "CWE-693": "A05:2021-Security Misconfiguration",
    "CWE-1021": "A05:2021-Security Misconfiguration",
    "CWE-942": "A05:2021-Security Misconfiguration",
    "CWE-614": "A05:2021-Security Misconfiguration",
    "CWE-538": "A05:2021-Security Misconfiguration",
    "CWE-611": "A05:2021-Security Misconfiguration",
    "CWE-319": "A02:2021-Cryptographic Failures",
    "CWE-522": "A02:2021-Cryptographic Failures",
    "CWE-601": "A01:2021-Broken Access Control",
    "CWE-352": "A01:2021-Broken Access Control",
    "CWE-798": "A07:2021-Identification and Authentication Failures",
    "CWE-1336": "A03:2021-Injection",
}


def _dedup_key(f: dict):
    # Same underlying issue on the same location: prefer CVE identity, else name.
    ident = (f.get("cve") or f.get("name", "")).strip().lower()
    return ident, (f.get("url") or f.get("host") or "")


def _merge(a: dict, b: dict) -> dict:
    """Merge b into a, preserving all contributing tool names and evidence (REQ-61, REQ-64)."""
    tools = {t for t in (a.get("tool", ""), b.get("tool", "")) if t}
    a["tool"] = "; ".join(sorted(tools))
    ev = [e for e in (a.get("evidence", ""), b.get("evidence", "")) if e]
    a["evidence"] = "\n---\n".join(ev)
    # keep the more severe rating and fill any missing scalar fields from b
    if models.severity_rank(b.get("severity", "")) < models.severity_rank(a.get("severity", "")):
        a["severity"] = b["severity"]
    for k in ("cve", "cvss", "cwe", "description", "owasp"):
        if not a.get(k) and b.get(k):
            a[k] = b[k]
    return a


def _tag_owasp(f: dict) -> None:
    if f.get("owasp"):
        return
    cwe = (f.get("cwe") or "").upper()
    if cwe in CWE_OWASP:
        f["owasp"] = CWE_OWASP[cwe]
        return
    name = (f.get("name") or "").lower()
    if "sql" in name:
        f["owasp"] = "A03:2021-Injection"
    elif "xss" in name or "cross-site scripting" in name:
        f["owasp"] = "A03:2021-Injection"
    elif "ssrf" in name:
        f["owasp"] = "A10:2021-Server-Side Request Forgery"


def _confirmed(f: dict) -> bool:
    # SQLMap = active exploitation; manual = human-verified. Both outrank an unconfirmed match.
    tool = (f.get("tool") or "").lower()
    return "sqlmap" in tool or "manual" in tool


def _priority(f: dict):
    # Lower sorts first: by severity, then confirmed-exploit before unconfirmed, then name.
    return (models.severity_rank(f.get("severity", "")), 0 if _confirmed(f) else 1, f.get("name", ""))


def correlate(findings: list[dict]) -> list[dict]:
    merged: dict = {}
    order = []
    for f in findings:
        key = _dedup_key(f)
        if key in merged:
            _merge(merged[key], dict(f))
        else:
            merged[key] = dict(f)
            order.append(key)
    result = [merged[k] for k in order]
    for f in result:
        _tag_owasp(f)
    result.sort(key=_priority)
    return result
