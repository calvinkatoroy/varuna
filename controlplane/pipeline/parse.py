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


def _cwe(v):
    """Nuclei emits `cwe-200`; normalize to the CWE-200 form the rest of the pipeline keys on."""
    m = re.search(r"(\d+)", str(v or ""))
    return f"CWE-{m.group(1)}" if m else None


# Fallback when a template carries no classification: infer the weakness from its tags / name.
_TAG_CWE = (
    (("sqli", "sql-injection"), "CWE-89"), (("xss",), "CWE-79"), (("ssrf",), "CWE-918"),
    (("lfi", "traversal", "path-traversal"), "CWE-22"), (("redirect",), "CWE-601"),
    (("cors",), "CWE-942"), (("csrf",), "CWE-352"), (("xxe",), "CWE-611"),
    (("ssti",), "CWE-1336"), (("rce",), "CWE-94"), (("clickjacking", "x-frame"), "CWE-1021"),
    (("hsts",), "CWE-319"), (("cookie",), "CWE-614"), (("swagger", "openapi", "api-docs"), "CWE-200"),
    (("exposure", "exposed", "disclosure", "metrics", "backup", "config"), "CWE-200"),
    (("default-login", "default-credentials"), "CWE-798"), (("misconfig",), "CWE-16"),
)


def _infer_cwe(tags, name):
    hay = {t.lower() for t in (tags or [])} | set(re.findall(r"[a-z0-9-]+", (name or "").lower()))
    for keys, cwe in _TAG_CWE:
        if any(k in hay for k in keys):
            return cwe
    return None


def _nuclei_evidence(obj: dict) -> str:
    """Enough for a reader to see and reproduce the issue, not just a one-word extract."""
    lines = []
    if obj.get("matched-at"):
        lines.append(f"Matched at: {obj['matched-at']}")
    req = (obj.get("request") or "").splitlines()[0].strip() if obj.get("request") else ""
    if req:
        lines.append(f"Request: {req}")
    status = (obj.get("response") or "").splitlines()[0].strip() if obj.get("response") else ""
    if status:
        lines.append(f"Response: {status}")
    if obj.get("matcher-name"):
        lines.append(f"Matcher: {obj['matcher-name']}")
    ext = obj.get("extracted-results") or []
    if ext:
        lines.append("Extracted: " + (", ".join(map(str, ext)) if isinstance(ext, list) else str(ext)))
    if obj.get("curl-command"):
        lines.append(f"Reproduce: {obj['curl-command']}")
    return chr(10).join(lines)


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
        f = models.Finding(
            name=info.get("name") or obj.get("template-id") or "Nuclei finding",
            severity=(info.get("severity") or "info").lower(),
            host=obj.get("host") or matched,
            url=matched,
            description=info.get("description") or "",
            cve=_first(cls.get("cve-id")),
            cvss=cls.get("cvss-score"),
            cwe=_cwe(_first(cls.get("cwe-id"))) or _infer_cwe(info.get("tags"), info.get("name")),
            tool="nuclei",
            evidence=_nuclei_evidence(obj),
        )
        findings.append(f.to_dict())
    return findings


def parse_sqlmap(stdout: str, host: str = "", url: str = "") -> list[dict]:
    """SQLMap stdout: one finding per injectable Parameter block (REQ-30)."""
    findings = []
    current = None
    cur_url = url
    dbms = None
    for raw in (stdout or "").splitlines():
        line = raw.strip()
        mu = re.search(r"testing URL '([^']+)'", line)
        if mu:
            cur_url = mu.group(1)
        md = re.search(r"back-end DBMS:\s*(.+)", line)
        if md:
            dbms = md.group(1).strip()
        m = re.match(r"Parameter:\s*(.+)", line)
        if m:
            if current:
                findings.append(current)
            current = {"param": m.group(1), "evidence": [], "url": cur_url}
            continue
        if current and (line.startswith("Type:") or line.startswith("Title:") or line.startswith("Payload:")):
            current["evidence"].append(line)
    if current:
        findings.append(current)

    out = []
    for c in findings:
        if dbms:
            c["evidence"].append(f"Back-end DBMS: {dbms}")
        f = models.Finding(
            name=f"SQL Injection ({c['param']})",
            severity="critical",   # SQLMap confirms active exploitation (PT), always high-impact
            host=host or url,
            url=c.get("url") or url,
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
    return _present_host(findings, target)


def _present_host(findings: list[dict], target: str) -> list[dict]:
    """The agent scans localhost as 127.0.0.1 (tool resolvers); show the client the name they gave."""
    from urllib.parse import urlsplit
    t = urlsplit(target if "://" in target else "http://" + target)
    if (t.hostname or "").lower() != "localhost":
        return findings
    for f in findings:
        for k in ("host", "url", "evidence"):
            if f.get(k):
                f[k] = f[k].replace("127.0.0.1", "localhost")
    return findings
