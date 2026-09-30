"""Advanced-scan options: allow-list, clamping, and the destructive-option lock."""
import os
import sys

HERE = os.path.dirname(__file__)
os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"
for sub in ("common", "api", "pipeline", "report"):
    sys.path.insert(0, os.path.join(HERE, "..", sub))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent", "tools"))

import pytest  # noqa: E402

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import browser  # noqa: E402
import jwt_auth  # noqa: E402
import nuclei  # noqa: E402
import scanopts  # noqa: E402
import sqlmap  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

LEAD, PEN = "lead_pentester", "pentester"
client = TestClient(browser.app)


def test_normal_options_are_normalized_and_unknown_keys_dropped():
    out = scanopts.sanitize({
        "depth": "3", "crawl_duration": 300, "rate": 150, "headless": 1, "severity": ["high", "bogus", "critical"],
        "tags": ["cves", "exposures", "nope"], "technique": "beu", "level": 2, "evil": "rm -rf", "cookie": "a=b",
    }, PEN)
    assert out == {"depth": 3, "crawl_duration": "300s", "rate": 150, "headless": True,
                   "severity": ["high", "critical"], "tags": ["cve", "exposure"], "technique": "BEU",
                   "level": 2, "cookie": "a=b"}
    assert "evil" not in out


@pytest.mark.parametrize("bad", [{"depth": 99}, {"rate": 0}, {"crawl_duration": 5}, {"severity": ["nope"]},
                                 {"cookie": "x\ny"}, {"auth": {"login_url": "/l"}}])
def test_out_of_range_or_malformed_options_are_rejected(bad):
    with pytest.raises(scanopts.BadOpts):
        scanopts.sanitize(bad, LEAD)


def test_aggressive_and_destructive_switches_are_lead_only_and_need_opt_in():
    for opts in ({"aggressive": True}, {"level": 4}, {"risk": 2}):
        with pytest.raises(scanopts.BadOpts):
            scanopts.sanitize(opts, PEN)                      # a plain pentester cannot
        assert scanopts.sanitize(opts, LEAD)["aggressive"] is True
    with pytest.raises(scanopts.BadOpts):
        scanopts.sanitize({"dump": True}, LEAD)               # destructive needs aggressive first
    assert scanopts.sanitize({"aggressive": True, "os_shell": True}, LEAD)["os_shell"] is True
    with pytest.raises(scanopts.BadOpts):
        scanopts.sanitize({"aggressive": True, "dump": True}, PEN)


def test_api_enforces_it_and_clients_still_cannot_scan():
    def hdr(u, role):
        auth.create_account(u, "password1", role)
        return {"Authorization": "Bearer " + jwt_auth.login(u, "password1", "ip")}
    body = lambda **o: {"target": "http://10.0.0.5", "tools": ["nuclei"], "opts": o}
    Hp = hdr("pen1", PEN)
    assert client.post("/api/scans", json=body(os_shell=True), headers=Hp).status_code == 422
    assert client.post("/api/scans", json={**body(), "tools": ["nmap"]}, headers=Hp).status_code == 422
    assert client.post("/api/scans", json=body(depth=99), headers=Hp).status_code == 422
    assert client.post("/api/scans", json=body(), headers=hdr("kid", "client")).status_code == 403


def test_tools_honour_the_validated_options():
    safe = sqlmap.build("u", "o", level=5, risk=3, technique="BE")
    assert safe[safe.index("--level") + 1] == "2" and safe[safe.index("--risk") + 1] == "1", "safe profile is capped"
    assert safe[safe.index("--technique") + 1] == "BE"
    agg = sqlmap.build("u", "o", aggressive=True, level=4, risk=2)
    assert agg[agg.index("--level") + 1] == "4" and agg[agg.index("--risk") + 1] == "2"
    n = nuclei.build("u", "o", surface=True, tags=["xss", "exposure"], severity="high,critical")
    assert n[n.index("-tags") + 1] == "xss,exposure" and n[n.index("-severity") + 1] == "high,critical"
