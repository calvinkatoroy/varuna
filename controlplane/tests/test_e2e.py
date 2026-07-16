"""Backend end-to-end pipe test across all three real APIs + the full pipeline.

login (browser) -> install-token (browser) -> enroll (agent) -> submit (browser) ->
poll (agent) -> upload raw (agent) -> ingest parse/correlate/enrich -> status (browser) ->
findings review (private) -> report generate (private). One shared FakeRedis; Ollama falls
back. This is the closest offline proof that the whole system is wired correctly.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))
sys.path.insert(0, os.path.join(HERE, "..", "report"))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import ollama  # noqa: E402
import store as report_store  # noqa: E402
import browser  # noqa: E402
import main as agent_api  # noqa: E402
import private_api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

report_store.REPORTS_DIR = tempfile.mkdtemp()
ollama.OLLAMA_URL = "http://127.0.0.1:1"   # enrichment falls back gracefully

BC = TestClient(browser.app)       # public plane
AC = TestClient(agent_api.app)     # agent plane
PC = TestClient(private_api.app)   # private plane

NUCLEI = ('{"template-id":"CVE-2021-44228","info":{"name":"Log4j RCE","severity":"critical",'
          '"classification":{"cve-id":["CVE-2021-44228"],"cwe-id":["CWE-502"]}},'
          '"host":"http://10.0.0.5","matched-at":"http://10.0.0.5/api"}')


def test_full_system_pipe():
    redis_store._client = FakeRedis()
    auth.create_account("ihsan", "pw", "pro")

    # 1. login (browser API) -> JWT
    jwt = BC.post("/api/login", json={"username": "ihsan", "password": "pw"}).json()["token"]
    BH = {"Authorization": f"Bearer {jwt}"}

    # 2. install-token (browser) -> 3. enroll agent (agent API) -> agent bearer
    et = BC.post("/api/agent/install-token", headers=BH).json()["enrollment_token"]
    agent_token = AC.post("/agent/enroll", json={"enrollment_token": et}).json()["token"]
    AH = {"Authorization": f"Bearer {agent_token}"}

    # 4. submit a local scan (browser) -> dispatched (agent is online after enroll)
    res = BC.post("/api/scans", headers=BH, json={"target": "http://10.0.0.5"}).json()
    assert res["state"] == "dispatched", res
    jid = res["job_id"]

    # 5. agent polls (agent API) -> gets its job
    job = AC.get("/agent/poll", headers=AH).json()["job"]
    assert job and job["id"] == jid

    # 6. agent uploads raw output -> ingest parses/correlates/enriches (BackgroundTask)
    assert AC.post(f"/agent/jobs/{jid}/findings", headers=AH, json={"raw": {"nuclei": NUCLEI}}).status_code == 200
    AC.post(f"/agent/jobs/{jid}/status", headers=AH, json={"status": "done"})

    # 7. status via browser API reflects done
    assert BC.get(f"/api/scans/{jid}", headers=BH).json()["status"] == "done"

    # 8. findings review via private API (same JWT; ihsan is pro)
    findings = PC.get(f"/api/findings/{jid}", headers=BH).json()
    assert len(findings) == 1
    assert findings[0]["cve"] == "CVE-2021-44228"
    assert findings[0]["owasp"] == "A08:2021-Software and Data Integrity Failures"  # correlate tagged it

    # 9. full report via private API
    rep = PC.post("/api/reports/generate", headers=BH, json={"job_id": jid, "template": "Full Technical"})
    assert rep.status_code == 200 and rep.json()["template"] == "Full Technical"
    fname = rep.json()["file"]
    dl = PC.get(f"/api/reports/{fname}/download", headers=BH)
    assert dl.status_code == 200 and dl.content[:2] == b"PK"


if __name__ == "__main__":
    test_full_system_pipe()
    print("test_e2e: full system pipe OK")
