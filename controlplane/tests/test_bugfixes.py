"""Regression tests for the 2026-09-30 end-to-end bug hunt (docs/test-report-2026-09-30.md)."""
import concurrent.futures as cf
import io
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import browser  # noqa: E402
import db  # noqa: E402
import jwt_auth  # noqa: E402
import models  # noqa: E402
import private_api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

pub, priv = TestClient(browser.app), TestClient(private_api.app)
CLOUD = "http://8.8.8.8"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _h(username, role, pw="password1"):
    auth.create_account(username, pw, role)
    return {"Authorization": f"Bearer {jwt_auth.login(username, pw, 'ip')}"}


def _prop(H, **over):
    body = {"target": CLOUD, "authorization_attested": True, **over}
    return pub.post("/api/proposals", json=body, headers=H)


def _docx(text="x"):
    import docx
    d = docx.Document(); d.add_paragraph(text)
    b = io.BytesIO(); d.save(b)
    return b.getvalue()


def test_client_cannot_smuggle_advanced_opts():                       # H1
    redis_store._client = FakeRedis()
    Hc, Hl = _h("alice", "client"), _h("riyan", "lead_pentester")
    r = _prop(Hc, mode="advanced", tools=["sqlmap", "; calc"],
              opts={"aggressive": True, "os_shell": True, "dump": True})
    pid = r.json()["proposal_id"]
    p = pub.get(f"/api/proposals/{pid}", headers=Hl).json()
    assert p["opts"] == {} and p["tools"] == []                       # stripped at submit
    # even if a stale/hostile row carries them, approval keys off the submitter's role
    db.update_proposal(pid, opts_json='{"os_shell": true}', tools_json='["sqlmap"]')
    jid = pub.post(f"/api/proposals/{pid}/approve", headers=Hl).json()["job_id"]
    job = redis_store.get_job(jid)
    assert job["opts"] == {} and job["tools"] == browser.FULL_STACK
    assert _prop(Hc, mode="root").status_code == 422


def test_team_advanced_tools_must_be_known():
    Ht = _h("dimas", "pentester")
    assert _prop(Ht, mode="advanced", tools=["nmap"]).status_code == 422


def test_generate_report_is_tenant_scoped():                          # H2
    redis_store._client = FakeRedis()
    Ha, Hb = _h("acme", "client"), _h("globex", "client")
    pid = _prop(Ha).json()["proposal_id"]
    jid = pub.post(f"/api/proposals/{pid}/approve", headers=_h("lead1", "lead_pentester")).json()["job_id"]
    assert pub.post(f"/api/scans/{jid}/report", headers=Hb).status_code == 403
    assert pub.post(f"/api/scans/{jid}/report", headers=Ha).status_code == 200


def test_concurrent_approvals_create_one_job():                       # H3
    redis_store._client = FakeRedis()
    Hc, Hl = _h("bob", "client"), _h("lead2", "lead_pentester")
    pid = _prop(Hc).json()["proposal_id"]
    with cf.ThreadPoolExecutor(8) as ex:
        codes = list(ex.map(lambda _: pub.post(f"/api/proposals/{pid}/approve", headers=Hl).status_code, range(8)))
    assert codes.count(200) == 1 and codes.count(409) == 7, codes
    assert len(redis_store.list_user_jobs("bob")) == 1


def test_concurrent_submits_all_succeed():                            # H4
    Hc = _h("carl", "client")
    with cf.ThreadPoolExecutor(30) as ex:
        codes = list(ex.map(lambda i: _prop(Hc, target=f"http://10.0.0.{i + 1}").status_code, range(30)))
    assert set(codes) == {200}, codes
    assert len(db.list_proposals(submitter="carl")) == 30


def test_bad_docx_is_rejected_and_password_not_listed():              # H5, H6
    Hrep, Hgov = _h("aisah", "reporter"), _h("hani", "governance")
    rid = db.create_report(job_id="j9", owner="dan")
    up = lambda data: priv.post(f"/api/pipeline/reports/{rid}/version",
                                files={"file": ("f.docx", data, DOCX)}, headers=Hrep)
    assert up(b"").status_code == 422 and up(b"NOT A DOCX").status_code == 422
    assert db.list_report_versions(rid) == []
    assert up(_docx()).status_code == 200
    db.set_report(rid, stage=models.REPORT_DELIVERED, pdf_password="s3cret", delivered_pdf="x.pdf")
    rows = priv.get("/api/pipeline/reports", headers=Hrep).json()
    assert rows and all("pdf_password" not in r for r in rows)


def test_target_validated_at_submit():                                # M2
    Hc = _h("erin", "client")
    for bad in ("", "file:///etc/passwd", "not a url <b>x</b>", "x" * 3000, "ftp://a.com"):
        assert _prop(Hc, target=bad).status_code == 422, bad
    assert _prop(Hc, target="example.com").status_code == 200


def test_attestation_must_be_a_real_boolean():
    assert _prop(_h("finn", "client"), authorization_attested="yes").status_code == 422


def test_register_rules_and_case_collision():                         # M3
    for u, p in (("ab", "password1"), ("a b c", "password1"), ("<script>", "password1"),
                 ("gina", "short"), ("gina", "p" * 100)):
        assert pub.post("/api/register", json={"username": u, "password": p}).status_code == 409, (u, p)
    assert pub.post("/api/register", json={"username": "gina", "password": "password1"}).status_code == 200
    assert pub.post("/api/register", json={"username": "GINA", "password": "password1"}).status_code == 409


def test_lockout_is_per_source_not_account_wide():                    # M7
    redis_store._client = FakeRedis()
    auth.create_account("victim", "password1", "client")
    for _ in range(auth.FAIL_LIMIT + 2):
        pub.post("/api/login", json={"username": "victim", "password": "bad"},
                 headers={"X-Forwarded-For": "6.6.6.6"})
    assert pub.post("/api/login", json={"username": "victim", "password": "password1"},
                    headers={"X-Forwarded-For": "6.6.6.6"}).status_code == 429   # attacker locked
    assert pub.post("/api/login", json={"username": "victim", "password": "password1"},
                    headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200   # owner fine


def test_install_token_needs_approved_proposal():                     # M4
    redis_store._client = FakeRedis()
    Hc, Hl = _h("hank", "client"), _h("lead3", "lead_pentester")
    assert pub.post("/api/agent/install-token", headers=Hc).status_code == 403
    pid = _prop(Hc).json()["proposal_id"]
    pub.post(f"/api/proposals/{pid}/approve", headers=Hl)
    assert pub.post("/api/agent/install-token", headers=Hc).status_code == 200


def test_verdict_on_missing_finding_404_and_body_limit():
    Ht = _h("tim", "pentester")
    assert priv.post("/api/findings/nope/verdict", json={"verdict": "fp"}, headers=Ht).status_code == 404
    r = pub.post("/api/proposals", content=b"x" * 2_000_000, headers=_h("ivy", "client"))
    assert r.status_code == 413


def test_team_login_only_on_private_plane():                          # M5
    os.environ.pop("VARUNA_PUBLIC_TEAM_LOGIN", None)
    try:
        auth.create_account("riyan9", "password1", "lead_pentester")
        auth.create_account("acme9", "password1", "client")
        creds = lambda u: {"username": u, "password": "password1"}
        assert pub.post("/api/login", json=creds("riyan9")).status_code == 403
        assert pub.post("/api/login", json=creds("acme9")).status_code == 200
        assert priv.post("/api/login", json=creds("riyan9")).status_code == 200
        assert priv.post("/api/login", json=creds("acme9")).status_code == 403
    finally:
        os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"
