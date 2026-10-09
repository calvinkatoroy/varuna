"""Client quick scan: self-service scan of a PRIVATE target, no task, no report, hidden from the team's findings."""
import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
for d in ("common", "api", "report"):
    sys.path.insert(0, os.path.join(HERE, "..", d))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

redis_store._client = FakeRedis()
import audit  # noqa: E402
import auth  # noqa: E402
import browser  # noqa: E402
import db  # noqa: E402
import ingest  # noqa: E402
import main as agent_api  # noqa: E402
import models  # noqa: E402
import private_api  # noqa: E402
import tokens  # noqa: E402
import test_browser_api as tb  # noqa: E402

pub = TestClient(browser.app)
prv = TestClient(private_api.app)
LOCAL, PUBLIC = "http://10.0.0.5", "http://8.8.8.8"
OK = {"consent": True}


def _client(name, org=None):
    return tb._token(name, "client", org)


def _staff(name, role="pentester"):
    auth.create_account(name, "pw", role)
    r = prv.post("/api/login", json={"username": name, "password": "pw"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _post(H, target=LOCAL, **kw):
    return pub.post("/api/quick-scans", headers=H, json={"target": target, **(OK | kw)})


def test_client_starts_a_quick_scan_on_a_private_target():
    tb.reset()
    H = _client("qa")
    r = _post(H)
    assert r.status_code == 200 and r.json()["state"] == "dispatched"
    job = redis_store.get_job(r.json()["job_id"])
    assert job["quick"] is True and job["org_id"] == tb._org("qa") and job["opts"] == {}
    assert job["tools"] == list(browser.FULL_STACK)                       # the locked safe profile
    assert redis_store.dequeue_job("qa") == job["id"]                     # the client's own agent gets it
    assert [e for e in audit.read_all() if e["type"] == audit.QUICK_SCAN][-1]["org"] == tb._org("qa")


def test_refusals():
    tb.reset()
    H = _client("qb")
    assert _post(H, target=PUBLIC).status_code == 422                     # public targets need a pentester
    assert _post(H, consent=False).status_code == 422                    # consent is required every time
    assert pub.post("/api/quick-scans", headers=H, json={"target": LOCAL}).status_code == 422
    auth.create_account("noagent", "pw", "client", org_id=tb._org("qb"))
    t = pub.post("/api/login", json={"username": "noagent", "password": "pw"}).json()["token"]
    assert _post({"Authorization": f"Bearer {t}"}).status_code == 409    # no agent installed
    assert pub.post("/api/quick-scans", headers=tb._token("pen", "pentester"),
                    json={"target": LOCAL, "consent": True}).status_code == 403   # staff use the board
    assert pub.post("/api/quick-scans", json={"target": LOCAL, "consent": True}).status_code == 401


def test_kill_switch_one_active_scan_and_daily_limit(monkeypatch):
    tb.reset()
    H = _client("qc")
    monkeypatch.setenv("VARUNA_QUICK_SCAN", "0")
    assert _post(H).status_code == 503
    monkeypatch.delenv("VARUNA_QUICK_SCAN")
    jid = _post(H).json()["job_id"]
    assert _post(H).status_code == 409                                    # one at a time per organization
    job = redis_store.get_job(jid); job["status"] = models.STATUS_DONE; redis_store.set_job(job)
    agent_api._job_finished(job)                                          # finishing frees the organization
    monkeypatch.setattr(browser, "QUICK_PER_DAY", 2)
    assert _post(H).status_code == 200
    agent_api._job_finished({**job, "quick": True})
    assert _post(H).status_code == 429                                    # third in a day
    assert _post(H).status_code == 429 and not redis_store.get_redis().get(browser.quick_lock_key(tb._org("qc")))


def _ingest_quick(H, owner):
    jid = _post(H).json()["job_id"]
    nuclei = {"info": {"name": "Exposed metrics", "severity": "medium", "tags": ["exposure"]},
              "host": "10.0.0.5", "matched-at": "http://10.0.0.5/metrics"}
    import ollama
    real, ollama.enrich = ollama.enrich, lambda f: f
    try:
        ingest.process_job(jid, {"nuclei": json.dumps(nuclei)})
    finally:
        ollama.enrich = real
    return jid


def test_findings_belong_to_the_client_only():
    tb.reset()
    Ha, Hb = _client("qd"), _client("qe")
    jid = _ingest_quick(Ha, "qd")
    assert not [r for r in db.list_reports(org_id=None) if r["job_id"] == jid]      # no report is ever built
    own = pub.get("/api/findings/targets", headers=Ha).json()
    assert len(own) == 1 and own[0]["quick"] is True and own[0]["total"] == 1
    assert own[0]["target"] == "http://10.0.0.5"                                   # named by what was scanned, port kept
    fid = db.get_findings(jid)[0]["id"]
    assert pub.get(f"/api/findings/id/{fid}", headers=Ha).status_code == 200
    assert pub.get("/api/findings/targets", headers=Hb).json() == []               # another organization: nothing
    assert pub.get(f"/api/findings/id/{fid}", headers=Hb).status_code == 404
    assert pub.get(f"/api/scans/{jid}", headers=Hb).status_code == 404
    assert [j["id"] for j in pub.get("/api/scans", headers=Ha).json() if j["quick"]] == [jid]


def test_the_team_sees_the_log_but_never_the_findings():
    tb.reset()
    Ha = _client("qf")
    jid = _ingest_quick(Ha, "qf")
    fid = db.get_findings(jid)[0]["id"]
    for role in ("pentester", "lead_pentester", "governance", "manager"):
        Hs = _staff(f"s-{role}", role)
        assert prv.get("/api/findings/targets", headers=Hs).json() == []
        assert prv.get("/api/findings", headers=Hs).json() == []
        assert prv.get(f"/api/findings/id/{fid}", headers=Hs).status_code == 404
        assert prv.get(f"/api/findings/{jid}", headers=Hs).json() == []
        assert prv.post(f"/api/findings/{fid}/verdict", headers=Hs, json={"verdict": "fp"}).status_code in (403, 404)
    assert db.get_findings(jid)[0]["verdict"] == "tp"
    log = prv.get("/api/quick-scans", headers=_staff("s-log")).json()
    assert log[0]["user"] == "qf" and log[0]["target"] == LOCAL and "findings" not in json.dumps(log).lower()
    assert pub.get("/api/quick-scans", headers=Ha).status_code in (404, 405)       # the log is not on the client plane


def test_staff_direct_scan_findings_stay_visible_to_staff():
    tb.reset()
    jid = "direct-1"
    db.save_findings(jid, "pen", "", [{"name": "X", "severity": "low", "host": "h", "url": "/", "tool": "nuclei"}])
    assert not db.quick_job(jid) and len(db.list_findings(org_id=None)) == 1
