"""AI enrichment via local Ollama (SRS §4.6, REQ-34 to REQ-37).

Sends each finding to a locally hosted LLM (qwen2.5:7b) for impact, remediation, and
risk rating. temperature 0.2 for repeatable output (REQ-37). If Ollama is unavailable or
returns anything unparseable, the finding is kept WITHOUT enrichment fields and the scan
continues (REQ-36); enrichment is never allowed to crash a scan.
"""
from __future__ import annotations

import json
import os

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
TIMEOUT = 120
RISK_RATINGS = {"Critical", "High", "Medium", "Low", "Informational"}

_PROMPT = """You are a penetration testing report assistant. Given a vulnerability finding,
respond with ONLY a JSON object with exactly these keys:
  "impact": 2-4 sentences on business/technical impact,
  "remediation": 2-5 sentences on how to fix it,
  "risk_rating": one of Critical, High, Medium, Low, Informational.

Finding:
  name: {name}
  severity: {severity}
  host: {host}
  url: {url}
  description: {description}
  cve: {cve}
  cwe: {cwe}
  evidence: {evidence}
"""


def _build_prompt(f: dict) -> str:
    return _PROMPT.format(**{k: f.get(k, "") for k in
                             ("name", "severity", "host", "url", "description", "cve", "cwe", "evidence")})


def enrich(finding: dict) -> dict:
    """Return the finding with impact/remediation/risk_rating merged in, or unchanged on failure."""
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": _build_prompt(finding),
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = json.loads(resp.json()["response"])   # response is a JSON string (format=json)
        impact = data.get("impact")
        remediation = data.get("remediation")
        rating = data.get("risk_rating")
        if not (impact and remediation and rating in RISK_RATINGS):
            return finding  # incomplete/invalid enrichment: keep finding as-is (REQ-36)
        finding["impact"] = impact
        finding["remediation"] = remediation
        finding["risk_rating"] = rating
        return finding
    except Exception:
        # Ollama down, timeout, bad JSON, missing key: never crash the scan (REQ-36).
        return finding


def enrich_all(findings: list[dict]) -> list[dict]:
    return [enrich(f) for f in findings]   # sequential per §4.6.2


def enrich_missing(findings: list[dict]) -> list[dict]:
    """Enrich only findings that lack enrichment (e.g. a newly added manual finding)."""
    return [f if f.get("impact") else enrich(f) for f in findings]
