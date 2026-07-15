"""Executive Summary sanitizer: the one private -> public data crossing (SRS REQ-49).

A Standard user's Executive Summary is built on the private plane and the finished file
crosses back to the public plane (REQ-50a). The security of the "findings never touch the
public internet" guarantee rests entirely on this function, so it is an ALLOW-LIST, not a
deny-list: only the named business-safe fields cross. Any field not listed here (evidence,
CVE, CVSS, tool names, payloads, and any field added to the schema in future) is dropped by
default and can never leak.
"""
from __future__ import annotations

# Business-facing fields safe for a management audience. Everything else is excluded by
# omission (REQ-49 excludes raw evidence, CVE, CVSS, tool names, technical payloads).
SAFE_FIELDS = ("name", "severity", "risk_rating", "impact", "remediation", "owasp")


def sanitize_finding(f: dict) -> dict:
    return {k: f[k] for k in SAFE_FIELDS if f.get(k) not in (None, "")}


def sanitize_findings(findings: list[dict]) -> list[dict]:
    return [sanitize_finding(f) for f in findings]
