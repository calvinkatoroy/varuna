"""Parse raw tool output into the standard finding schema (SRS §4.5, REQ-27/28/30/33).

Parsing is centralized on the control plane (agents ship raw output, §4.5.1) so a parser
fix ships once, not to every installed agent. Malformed lines are skipped, never fatal
(error resilience, §4.10). Katana output is discovery metadata, not findings (REQ-27),
so it is not parsed here.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import models  # noqa: E402


def _first(seq):
    return seq[0] if isinstance(seq, list) and seq else None


def parse_nuclei(jsonl_text: str) -> list[dict]:
    """Nuclei -jsonl: one JSON object per line (REQ-28)."""
    findings = []
    for line in (jsonl_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue  # skip malformed line, keep going (§4.10)
        info = obj.get("info") or {}
        cls = info.get("classification") or {}
        matched = obj.get("matched-at") or obj.get("host") or ""
        evidence = obj.get("extracted-results") or []
        f = models.Finding(
            name=info.get("name") or obj.get("template-id") or "Nuclei finding",
            severity=(info.get("severity") or "info").lower(),
            host=obj.get("host") or matched,
            url=matched,
            description=info.get("description") or "",
            cve=_first(cls.get("cve-id")),
            cvss=cls.get("cvss-score"),
            cwe=_first(cls.get("cwe-id")),
            tool="nuclei",
            evidence="\n".join(evidence) if isinstance(evidence, list) else str(evidence),
        )
        findings.append(f.to_dict())
    return findings


def parse_sqlmap(stdout: str, host: str = "", url: str = "") -> list[dict]:
    """SQLMap stdout: one finding per injectable Parameter block (REQ-30)."""
    findings = []
    current = None
    for raw in (stdout or "").splitlines():
        line = raw.strip()
        m = re.match(r"Parameter:\s*(.+)", line)
        if m:
            if current:
                findings.append(current)
            current = {"param": m.group(1), "evidence": []}
            continue
        if current and (line.startswith("Type:") or line.startswith("Title:") or line.startswith("Payload:")):
            current["evidence"].append(line)
    if current:
        findings.append(current)

    out = []
    for c in findings:
        f = models.Finding(
            name=f"SQL Injection ({c['param']})",
            severity="critical",   # SQLMap confirms active exploitation (PT), always high-impact
            host=host or url,
            url=url,
            description="SQL injection confirmed by SQLMap.",
            cwe="CWE-89",
            tool="sqlmap",
            evidence="\n".join(c["evidence"]),
        )
        out.append(f.to_dict())
    return out


def parse_all(raw: dict, job: dict) -> list[dict]:
    """Dispatch each tool's raw output to its parser. `raw` = {tool: output}."""
    target = (job or {}).get("target", "")
    findings = []
    if raw.get("nuclei"):
        findings += parse_nuclei(raw["nuclei"])
    if raw.get("sqlmap"):
        findings += parse_sqlmap(raw["sqlmap"], host=target, url=target)
    return findings
