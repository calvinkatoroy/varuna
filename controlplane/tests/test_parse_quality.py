"""Finding quality: evidence detail, CWE normalization/inference, host presentation."""
import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))

import correlate  # noqa: E402
import parse  # noqa: E402

NUCLEI = {
    "template-id": "sqli-error-based",
    "info": {"name": "Error based SQL Injection", "severity": "critical", "tags": ["sqli", "dast"],
             "classification": {"cwe-id": ["cwe-89"]}},
    "matcher-name": "sqlite", "extracted-results": ["SQLITE_ERROR"],
    "host": "127.0.0.1", "matched-at": "http://127.0.0.1:3000/rest/products/search?q=1'",
    "request": "GET /rest/products/search?q=1' HTTP/1.1\r\nHost: 127.0.0.1:3000\r\n\r\n",
    "response": "HTTP/1.1 500 Internal Server Error\r\nX: y\r\n\r\nbody",
    "curl-command": "curl -X 'GET' 'http://127.0.0.1:3000/rest/products/search?q=1'\\''",
}
NO_CLASS = {"info": {"name": "Public Swagger API - Detect", "severity": "info", "tags": ["exposure", "swagger"]},
            "host": "127.0.0.1", "matched-at": "http://127.0.0.1:3000/api-docs/swagger.json"}


def _parse(*objs, target="http://localhost:3000"):
    raw = {"nuclei": "\n".join(json.dumps(o) for o in objs)}
    return parse.parse_all(raw, {"target": target})


def test_nuclei_evidence_has_request_response_and_reproduction():
    f = _parse(NUCLEI)[0]
    for part in ("Matched at:", "Request: GET /rest/products/search", "Response: HTTP/1.1 500",
                 "Matcher: sqlite", "Extracted: SQLITE_ERROR", "Reproduce: curl"):
        assert part in f["evidence"], part


def test_cwe_is_normalized_and_inferred_when_missing():
    f1, f2 = _parse(NUCLEI, NO_CLASS)
    assert f1["cwe"] == "CWE-89"
    assert f2["cwe"] == "CWE-200"
    assert correlate.correlate([f2])[0]["owasp"] == "A05:2021-Security Misconfiguration"


def test_localhost_target_is_shown_as_localhost_not_loopback_ip():
    f = _parse(NUCLEI)[0]
    assert "127.0.0.1" not in f["url"] and "localhost:3000" in f["url"]
    other = _parse(NUCLEI, target="http://10.0.0.5")[0]
    assert "127.0.0.1" in other["url"], "only rewrite when the client's target was localhost"


def test_sqlmap_finding_uses_its_own_url_and_dbms():
    out = ("[09:00:00] [INFO] testing URL 'http://t/a?id=1'\n"
           "[09:00:01] [INFO] back-end DBMS: MySQL >= 5.0\n"
           "Parameter: id (GET)\n    Type: boolean-based blind\n    Payload: id=1 AND 1=1\n")
    f = parse.parse_sqlmap(out, host="http://t", url="http://t")[0]
    assert f["url"] == "http://t/a?id=1"
    assert "Back-end DBMS: MySQL" in f["evidence"] and "Payload: id=1 AND 1=1" in f["evidence"]
