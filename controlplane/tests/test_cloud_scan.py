"""Cloud scan (run by Varuna on the host) vs local scan (run by the client's own agent)."""
import os
import sys

os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"
HERE = os.path.dirname(__file__)
for p in ("", "../common", "../api", "../pipeline", "..", "../../agent", "../../agent/tools"):
    sys.path.insert(0, os.path.join(HERE, p))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import browser  # noqa: E402
import db  # noqa: E402
import jwt_auth  # noqa: E402
import main as agent_api  # noqa: E402
import models  # noqa: E402
import scan  # noqa: E402
import tokens  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

pub, agent = TestClient(browser.app), TestClient(agent_api.app)
PUBLIC_IP = "http://8.8.8.8"


def _h(name, role="client"):
    auth.create_account(name, "password1", role, org_id=db.create_org("org-" + name) if role == "client" else None)
    return {"Authorization": f"Bearer {jwt_auth.login(name, 'password1', 'ip')}"}


def _agent_headers(username):
    et = tokens.generate_enrollment_token(username)
    return {"Authorization": f"Bearer {agent.post('/agent/enroll', json={'enrollment_token': et}).json()['token']}"}


def _propose(H, target, scan_mode):
    return pub.post("/api/proposals", headers=H, json={"target": target, "scan_mode": scan_mode, "division": "x", "purpose": "periodic", "authorization_attested": True})


def test_cloud_proposal_must_be_public_but_local_may_be_anything():
    H = _h("cl1")
    for private in ("http://localhost:3000", "http://127.0.0.1", "http://10.1.2.3", "http://192.168.0.5", "http://169.254.169.254",
                    "http://intranet.corp", "http://printer.local", "http://singlelabel"):
        r = _propose(H, private, "cloud")
        assert r.status_code == 422 and "On my computer" in r.json()["detail"], (private, r.text)
        assert _propose(H, private, "local").status_code == 200, private          # same address is fine for a local scan
    assert _propose(H, PUBLIC_IP, "cloud").status_code == 200
    assert _propose(H, "https://example.com", "cloud").status_code == 200
    assert pub.post("/api/proposals", headers=H, json={"target": PUBLIC_IP, "scan_mode": "bogus", "authorization_attested": True}).status_code == 422


def test_approved_cloud_job_goes_to_the_cloud_scanner_not_the_clients_queue():
    H, lead = _h("cl2"), _h("cl2_lead", "lead_pentester")
    pid = _propose(H, PUBLIC_IP, "cloud").json()["proposal_id"]
    r = pub.post(f"/api/proposals/{pid}/approve", headers=lead); assert r.status_code == 200, r.text
    job = redis_store.get_job(r.json()["job_id"])
    assert job["scan_mode"] == "cloud" and job["executor"] == models.CLOUD_AGENT and job["submitter"] == "cl2"
    assert redis_store.dequeue_job("cl2") is None                       # the client's own agent never sees it
    assert redis_store.dequeue_job(models.CLOUD_AGENT) == job["id"]
    # and a local proposal still goes to the client's agent
    pid2 = _propose(H, PUBLIC_IP, "local").json()["proposal_id"]
    job2 = redis_store.get_job(pub.post(f"/api/proposals/{pid2}/approve", headers=lead).json()["job_id"])
    assert job2["scan_mode"] == "local" and not job2["executor"] and redis_store.dequeue_job("cl2") == job2["id"]


def test_cloud_approval_refuses_a_target_that_resolves_private():
    H, lead = _h("cl3"), _h("cl3_lead", "lead_pentester")
    pid = db.create_proposal({"submitter": "cl3", "target": "http://127.0.0.1:3000", "scan_mode": "cloud", "authorization_attested": True,
                              "org_id": db.get_account("cl3")["org_id"]})   # slipped past submit
    r = pub.post(f"/api/proposals/{pid}/approve", headers=lead)
    assert r.status_code == 422 and "public target" in r.json()["detail"]
    assert db.get_proposal(pid, org_id=None)["status"] == "pending"     # nothing was claimed


def test_only_the_cloud_scanner_may_run_a_cloud_job():
    H, lead = _h("cl4"), _h("cl4_lead", "lead_pentester")
    jid = pub.post(f"/api/proposals/{_propose(H, PUBLIC_IP, 'cloud').json()['proposal_id']}/approve", headers=lead).json()["job_id"]
    cloud, other = _agent_headers(models.CLOUD_AGENT), _agent_headers("somebody_else")
    polled = agent.get("/agent/poll", headers=cloud).json()["job"]
    assert polled["id"] == jid
    assert agent.post(f"/agent/jobs/{jid}/status", headers=cloud, json={"status": "running"}).status_code == 200
    assert agent.post(f"/agent/jobs/{jid}/status", headers=other, json={"status": "done"}).status_code == 403   # another agent cannot
    assert agent.post(f"/agent/jobs/{jid}/findings", headers=other, json={"raw": {}}).status_code == 403


def test_nobody_can_register_the_cloud_scanners_name():
    for name in ("varuna-cloud", "Varuna-Cloud", "varuna-anything"):
        r = pub.post("/api/register", json={"username": name, "password": "password1"})
        assert r.status_code == 409, (name, r.text)


def test_agent_status_tells_a_cloud_only_client_not_to_install_anything():
    H, lead = _h("cl5"), _h("cl5_lead", "lead_pentester")
    assert pub.get("/api/agent", headers=H).json()["cloud_only"] is False                       # nothing yet
    pub.post(f"/api/proposals/{_propose(H, PUBLIC_IP, 'cloud').json()['proposal_id']}/approve", headers=lead)
    s = pub.get("/api/agent", headers=H).json()
    assert s["cloud_only"] is True and isinstance(s["cloud_online"], bool)
    _agent_headers(models.CLOUD_AGENT)                                                           # scanner enrols and checks in
    tokens.touch_agent(models.CLOUD_AGENT)
    assert pub.get("/api/agent", headers=H).json()["cloud_online"] is True
    assert pub.get("/api/proposals", headers=H).json()[0]["scan_mode"] == "cloud"


def test_scanner_refuses_private_targets_even_if_the_server_is_fooled(monkeypatch):
    import pytest
    monkeypatch.delenv("VARUNA_CLOUD_ALLOW_HOSTS", raising=False)
    cloud = lambda t: {"scan_mode": "cloud", "target": t}
    ok = lambda h: {"93.184.216.34"}
    scan.assert_cloud_safe(cloud("https://example.com"), resolve=ok)                             # public: fine
    scan.assert_cloud_safe({"scan_mode": "local", "target": "http://127.0.0.1"})                 # local jobs are not this guard's business
    for evil in ({"127.0.0.1"}, {"10.0.0.7"}, {"100.70.151.71"}, {"169.254.169.254"}, {"93.184.216.34", "192.168.1.1"}, set()):
        with pytest.raises(RuntimeError, match="open on the internet"):
            scan.assert_cloud_safe(cloud("https://site.example"), resolve=lambda h, e=evil: e)    # incl. one bad address among good ones
    monkeypatch.setenv("VARUNA_CLOUD_ALLOW_HOSTS", "mine.example, other.example")
    scan.assert_cloud_safe(cloud("https://mine.example/x"), resolve=lambda h: {"100.70.151.71"})  # the owner's explicit exception
    with pytest.raises(RuntimeError):
        scan.assert_cloud_safe(cloud("https://not-listed.example"), resolve=lambda h: {"100.70.151.71"})


def test_owner_allow_list_lets_a_privately_resolving_own_site_be_approved(monkeypatch):
    H, lead = _h("cl6"), _h("cl6_lead", "lead_pentester")
    monkeypatch.setattr(browser.classifier, "classify", lambda t, **k: browser.classifier.CLASS_LOCAL)      # resolves to a tailnet address
    pid = _propose(H, "https://mine.example.org", "cloud").json()["proposal_id"]
    monkeypatch.delenv("VARUNA_CLOUD_ALLOW_HOSTS", raising=False)
    assert pub.post(f"/api/proposals/{pid}/approve", headers=lead).status_code == 422                       # not listed: refused
    monkeypatch.setenv("VARUNA_CLOUD_ALLOW_HOSTS", "mine.example.org")
    assert pub.post(f"/api/proposals/{pid}/approve", headers=lead).status_code == 200                       # the owner's own site: allowed


def test_agent_survives_connection_errors_instead_of_dying(monkeypatch):
    """A control-plane restart or network blip used to raise out of run() and kill the agent for good."""
    import httpx
    import agent as agent_module
    calls = {"n": 0}

    class Resp:
        status_code = 401
        def json(self): return {"job": None}

    def flaky(url, headers=None, **kw):
        calls["n"] += 1
        if calls["n"] <= 3:
            raise httpx.ConnectError("control plane restarting")
        return Resp()                                   # then a 401 ends the loop so the test terminates

    monkeypatch.setattr(agent_module.httpx, "get", flaky)
    monkeypatch.setattr(agent_module.time, "sleep", lambda s: None)
    agent_module.run("token")
    assert calls["n"] == 4                              # three blips survived, then it carried on polling


def test_cloud_badge_survives_after_the_scan_into_review_and_delivery_cards():
    import board
    H, lead = _h("cl7"), _h("cl7_lead", "lead_pentester")
    jid = pub.post(f"/api/proposals/{_propose(H, PUBLIC_IP, 'cloud').json()['proposal_id']}/approve", headers=lead).json()["job_id"]
    rid = db.create_report(jid, db.get_account("cl7")["org_id"], "cl7", template="Full Technical")
    card = board._report_card(db.get_report(rid, org_id=None))
    assert card["scanMode"] == "cloud"
