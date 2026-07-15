"""Finding pipeline tests: parse (Nuclei/SQLMap), correlate (dedup/tag/priority), enrich fallback.

Pure logic, offline. The Ollama success path needs a live model, so only its graceful-fallback
path (REQ-36) is checked here. Standalone runnable; also pytest-compatible.
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))

import parse  # noqa: E402
import correlate  # noqa: E402
import ollama  # noqa: E402

NUCLEI = "\n".join([
    '{"template-id":"CVE-2021-44228","info":{"name":"Apache Log4j RCE","severity":"critical",'
    '"classification":{"cve-id":["CVE-2021-44228"],"cwe-id":["CWE-502"],"cvss-score":10.0}},'
    '"host":"http://t.local","matched-at":"http://t.local/api","extracted-results":["jndi:ldap://x"]}',
    '{"template-id":"tls-version","info":{"name":"TLS 1.0 Detected","severity":"low",'
    '"classification":{"cwe-id":["CWE-327"]}},"host":"http://t.local","matched-at":"http://t.local"}',
    '{bad json here',   # malformed: must be skipped, not fatal
])

SQLMAP = """
sqlmap identified the following injection point(s):
Parameter: id (GET)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE clause
    Payload: id=1 AND 1234=1234
    Type: time-based blind
    Payload: id=1 AND SLEEP(5)
Parameter: name (POST)
    Type: error-based
    Payload: name=x' AND EXTRACTVALUE(1,CONCAT(0x7e,version()))
"""


def test_parse_nuclei():
    fs = parse.parse_nuclei(NUCLEI)
    assert len(fs) == 2, f"expected 2 findings (malformed skipped), got {len(fs)}"
    log4j = fs[0]
    assert log4j["cve"] == "CVE-2021-44228"
    assert log4j["cwe"] == "CWE-502"
    assert log4j["cvss"] == 10.0
    assert log4j["severity"] == "critical"
    assert log4j["tool"] == "nuclei"
    assert "jndi" in log4j["evidence"]


def test_parse_sqlmap():
    fs = parse.parse_sqlmap(SQLMAP, host="http://t.local", url="http://t.local/?id=1")
    assert len(fs) == 2, f"expected one finding per Parameter block, got {len(fs)}"
    assert fs[0]["tool"] == "sqlmap" and fs[0]["cwe"] == "CWE-89"
    assert "id" in fs[0]["name"] and "SLEEP(5)" in fs[0]["evidence"]
    assert "name" in fs[1]["name"]


def test_correlate_dedup_merges_sources():
    # Same CVE + url from nuclei and a manual entry -> one merged finding, both tools kept.
    a = {"name": "Log4j RCE", "severity": "critical", "host": "h", "url": "http://t/api",
         "cve": "CVE-2021-44228", "tool": "nuclei", "evidence": "auto"}
    b = {"name": "Log4j RCE", "severity": "critical", "host": "h", "url": "http://t/api",
         "cve": "CVE-2021-44228", "tool": "manual", "evidence": "human-confirmed"}
    out = correlate.correlate([a, b])
    assert len(out) == 1, "duplicate CVE on same url should merge"
    assert "nuclei" in out[0]["tool"] and "manual" in out[0]["tool"]
    assert "auto" in out[0]["evidence"] and "human-confirmed" in out[0]["evidence"]


def test_correlate_tags_owasp():
    f = {"name": "SQL Injection (id)", "severity": "critical", "host": "h", "url": "u",
         "cwe": "CWE-89", "tool": "sqlmap", "evidence": ""}
    out = correlate.correlate([f])
    assert out[0]["owasp"] == "A03:2021-Injection"


def test_correlate_priority_confirmed_first():
    unconf = {"name": "Some CVE", "severity": "critical", "host": "h", "url": "u1",
              "cve": "CVE-9", "tool": "nuclei", "evidence": ""}
    conf = {"name": "SQLi", "severity": "critical", "host": "h", "url": "u2",
            "tool": "sqlmap", "evidence": ""}
    out = correlate.correlate([unconf, conf])
    # same severity: confirmed exploitation (sqlmap) must sort ahead of an unconfirmed match
    assert out[0]["tool"] == "sqlmap", "confirmed exploit should rank first within a severity"


def test_enrich_fallback_never_crashes():
    # Point Ollama at a dead address: enrich must return the finding unchanged (REQ-36).
    ollama.OLLAMA_URL = "http://127.0.0.1:1"   # nothing listening
    f = {"name": "X", "severity": "high", "host": "h", "url": "u"}
    out = ollama.enrich(dict(f))
    assert "impact" not in out and out["name"] == "X", "fallback must keep finding un-enriched"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_pipeline: all green")
