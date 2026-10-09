"""Regression tests for the 2026-09-30 end-to-end bug hunt (docs/test-report-2026-09-30.md)."""
import concurrent.futures as cf
import io
import os
import sys

os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"   # most tests act as team users through the public app
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))
sys.path.insert(0, os.path.join(HERE, ".."))

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
    auth.create_account(username, pw, role, org_id=db.create_org("org-" + username) if role == "client" else None)
    return {"Authorization": f"Bearer {jwt_auth.login(username, pw, 'ip')}"}


def _org(username):
    return db.get_account(username)["org_id"]


def _prop(H, **over):
    from conftest import window
    nb, na = window()
    return pub.post("/api/tasks", json={"target": CLOUD, "not_before": nb, "not_after": na, **over}, headers=H)


def _docx(text="x"):
    import docx
    d = docx.Document(); d.add_paragraph(text)
    b = io.BytesIO(); d.save(b)
    return b.getvalue()


def test_client_cannot_smuggle_advanced_opts():                       # H1
    from conftest import start_task
    redis_store._client = FakeRedis()
    Hc = _h("alice", "client")
    r = _prop(Hc, mode="advanced", tools=["sqlmap", "; calc"], opts={"aggressive": True, "os_shell": True, "dump": True})
    pid = r.json()["id"]
    t = db.get_proposal(pid, org_id=None)
    assert t["opts"] == {} and t["tools"] == []                       # extra body keys are ignored at create
    job = redis_store.get_job(start_task(pid, "riyan"))
    assert job["opts"] == {} and job["tools"] == browser.FULL_STACK
    assert _prop(Hc, scan_mode="root").status_code == 422


def test_pentester_cannot_set_aggressive_opts_lead_can():
    import tokens
    _h("al2", "client")
    Hp, Hl = _h("dimas", "pentester"), _h("lead9", "lead_pentester")
    pid = _prop(_h("al3", "client")).json()["id"]
    tokens.issue_agent_token("al3")
    priv.post(f"/api/tasks/{pid}/transition", headers=Hp, json={"to": "scan/pending", "version": 0})
    body = {"to": "scan/in_progress", "version": 1, "opts": {"level": 5}}
    assert priv.post(f"/api/tasks/{pid}/transition", headers=Hp, json=body).status_code == 422
    assert priv.post(f"/api/tasks/{pid}/transition", headers=Hl, json=body).status_code == 200


def test_public_plane_builds_no_report_from_a_scan():                 # H2: nothing unreviewed reaches a client
    from conftest import start_task
    redis_store._client = FakeRedis()
    Ha, Hb = _h("acme", "client"), _h("globex", "client")
    jid = start_task(_prop(Ha).json()["id"], "pen1")
    for H in (Ha, Hb):
        assert pub.post(f"/api/scans/{jid}/report", headers=H).status_code in (404, 405)


def test_concurrent_claims_have_one_winner_and_one_job():             # H3
    import tokens
    redis_store._client = FakeRedis()
    Hc = _h("bob", "client")
    pens = [_h(f"pen{i}", "pentester") for i in range(8)]
    pid = _prop(Hc).json()["id"]
    claim = lambda H: priv.post(f"/api/tasks/{pid}/transition", headers=H, json={"to": "scan/pending", "version": 0}).status_code
    with cf.ThreadPoolExecutor(8) as ex:
        codes = list(ex.map(claim, pens))
    assert codes.count(200) == 1 and codes.count(409) == 7, codes
    owner = pens[codes.index(200)]
    tokens.issue_agent_token("bob")
    start = lambda _: priv.post(f"/api/tasks/{pid}/transition", headers=owner,
                                json={"to": "scan/in_progress", "version": 1}).status_code
    with cf.ThreadPoolExecutor(8) as ex:
        codes = list(ex.map(start, range(8)))
    assert codes.count(200) == 1, codes
    assert len(redis_store.list_org_jobs(_org("bob"))) == 1


def test_concurrent_submits_all_succeed():                            # H4
    Hc = _h("carl", "client")
    with cf.ThreadPoolExecutor(30) as ex:
        codes = list(ex.map(lambda i: _prop(Hc, target=f"http://10.0.0.{i + 1}").status_code, range(30)))
    assert set(codes) == {200}, codes
    assert len(db.list_proposals(org_id=_org("carl"))) == 30


def test_port_and_path_are_validated():
    Hc = _h("finn", "client")
    assert _prop(Hc, port="80; rm -rf /").status_code == 422
    assert _prop(Hc, path="../../etc").status_code == 422




def test_target_validated_at_submit():                                # M2
    Hc = _h("erin", "client")
    for bad in ("", "file:///etc/passwd", "not a url <b>x</b>", "x" * 3000, "ftp://a.com", "javascript:alert(1)", "host:notaport"):
        assert _prop(Hc, target=bad).status_code == 422, bad
    assert _prop(Hc, target="example.com", scan_mode="local").status_code == 200


def test_lockout_is_per_source_not_account_wide():                    # M7
    redis_store._client = FakeRedis()
    auth.create_account("victim", "password1", "client", org_id=db.create_org("org-victim"))
    for _ in range(auth.FAIL_LIMIT + 2):
        pub.post("/api/login", json={"username": "victim", "password": "bad"},
                 headers={"X-Forwarded-For": "6.6.6.6"})
    assert pub.post("/api/login", json={"username": "victim", "password": "password1"},
                    headers={"X-Forwarded-For": "6.6.6.6"}).status_code == 429   # attacker locked
    assert pub.post("/api/login", json={"username": "victim", "password": "password1"},
                    headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200   # owner fine


def test_install_token_needs_a_claimed_task():                         # M4
    import workflow
    redis_store._client = FakeRedis()
    Hc = _h("hank", "client")
    _h("pen3", "pentester")
    assert pub.post("/api/agent/install-token", headers=Hc).status_code == 403
    workflow.transition(_prop(Hc).json()["id"], "scan/pending", "pen3", org_id=None)
    assert pub.post("/api/agent/install-token", headers=Hc).status_code == 200


def test_verdict_on_missing_finding_404_and_body_limit():
    Ht = _h("tim", "pentester")
    assert priv.post("/api/findings/nope/verdict", json={"verdict": "fp"}, headers=Ht).status_code == 404
    r = pub.post("/api/tasks", content=b"x" * 2_000_000, headers=_h("ivy", "client"))
    assert r.status_code == 413


def test_team_login_only_on_private_plane():                          # M5
    os.environ.pop("VARUNA_PUBLIC_TEAM_LOGIN", None)
    try:
        auth.create_account("riyan9", "password1", "lead_pentester")
        auth.create_account("acme9", "password1", "client", org_id=db.create_org("org-acme9"))
        creds = lambda u: {"username": u, "password": "password1"}
        assert pub.post("/api/login", json=creds("riyan9")).status_code == 403
        assert pub.post("/api/login", json=creds("acme9")).status_code == 200
        assert priv.post("/api/login", json=creds("riyan9")).status_code == 200
        assert priv.post("/api/login", json=creds("acme9")).status_code == 403
    finally:
        os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"


def test_public_plane_refuses_team_tokens_and_private_serves_team_actions():
    os.environ.pop("VARUNA_PUBLIC_TEAM_LOGIN", None)
    try:
        redis_store._client = FakeRedis()
        Hl = _h("riyan8", "lead_pentester")             # a valid team token
        Hc = _h("kim", "client")
        assert pub.get("/api/me", headers=Hl).status_code == 403          # refused on the public plane
        assert pub.get("/api/me", headers=Hc).status_code == 200
        assert pub.get("/api/me", headers={"Authorization": "Bearer junk"}).status_code == 401
        pid = _prop(Hc).json()["id"]
        r = priv.post(f"/api/tasks/{pid}/transition", headers=Hl, json={"to": "scan/pending", "version": 0})
        assert r.status_code == 200 and r.json()["scan_state"] == "pending", r.text
        assert priv.post(f"/api/tasks/{pid}/transition", headers=Hl, json={"to": "declined", "version": 0,
                                                                          "comment": "x"}).status_code == 409
        assert priv.get("/api/findings", headers=Hl).status_code == 200
        assert priv.post(f"/api/tasks/{pid}/transition", headers=Hc, json={"to": "declined", "version": 1}).status_code == 403
    finally:
        os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"


def test_change_password_and_disable_and_admin_reset():
    redis_store._client = FakeRedis()
    Hc = _h("lena", "client", pw="firstpass1")
    assert pub.post("/api/password", json={"current": "WRONG", "new": "secondpass1"}, headers=Hc).status_code == 403
    assert pub.post("/api/password", json={"current": "firstpass1", "new": "short"}, headers=Hc).status_code == 422
    assert pub.post("/api/password", json={"current": "firstpass1", "new": "secondpass1"}, headers=Hc).status_code == 200
    assert pub.post("/api/login", json={"username": "lena", "password": "firstpass1"}).status_code == 401
    assert pub.post("/api/login", json={"username": "lena", "password": "secondpass1"}).status_code == 200

    Hl = _h("root", "sysadmin")
    Hp = _h("pen9", "pentester")
    assert priv.get("/api/sysadmin/accounts", headers=Hp).status_code == 403            # sysadmin only
    rows = priv.get("/api/sysadmin/accounts", headers=Hl).json()
    assert rows and all("password_hash" not in r for r in rows)
    r = priv.post("/api/sysadmin/accounts", json={"username": "newrep", "role": "pentester"}, headers=Hl)
    assert r.status_code == 200
    assert priv.post("/api/sysadmin/accounts", json={"username": "NEWREP", "role": "pentester"}, headers=Hl).status_code == 409
    assert priv.post("/api/sysadmin/accounts", json={"username": "x1", "role": "pentester"}, headers=Hl).status_code == 422
    temp = priv.post("/api/sysadmin/accounts/lena/reset-password", headers=Hl)
    assert temp.status_code == 200
    temp = temp.json()["temp_password"]
    assert pub.post("/api/login", json={"username": "lena", "password": temp}).status_code == 200
    tok = pub.post("/api/login", json={"username": "lena", "password": temp}).json()["token"]
    assert priv.post("/api/sysadmin/accounts/lena/disable", headers=Hl).status_code == 200
    assert pub.post("/api/login", json={"username": "lena", "password": temp}).status_code == 401      # cannot log in
    assert pub.get("/api/me", headers={"Authorization": "Bearer " + tok}).status_code == 401                   # live token dies too
    assert priv.post("/api/sysadmin/accounts/root/disable", headers=Hl).status_code == 409                        # not yourself
    assert priv.post("/api/sysadmin/accounts/lena/enable", headers=Hl).status_code == 200
    assert pub.post("/api/login", json={"username": "lena", "password": temp}).status_code == 200


def test_default_password_detection_and_backup(tmp_path):
    auth.create_account("seeded", "changeme", "pentester")
    auth.create_account("fine", "notdefault1", "pentester")
    assert auth.default_password_accounts() == ["seeded"]
    import backup_db
    backup_db.DB = db._db_path()
    out = backup_db.backup(str(tmp_path / "b"), keep=2)
    import sqlite3
    conn = sqlite3.connect(out)
    assert conn.execute("select count(*) from accounts").fetchone()[0] >= 2
    conn.close()   # Windows cannot delete an open file (retention below removes old backups)
    for _ in range(3):
        backup_db.backup(str(tmp_path / "b"), keep=2)
    assert len(list((tmp_path / "b").glob("varuna-*.db"))) == 2, "retention keeps the newest N"


def test_finished_scan_starts_review_automatically(tmp_path):
    import json
    import ingest
    import ollama
    import store as report_store
    report_store.REPORTS_DIR = str(tmp_path)
    ollama.OLLAMA_URL = "http://127.0.0.1:1"          # enrichment falls back gracefully
    redis_store._client = FakeRedis()
    from conftest import start_task
    Hc = _h("zed", "client")
    jid = start_task(_prop(Hc).json()["id"], "pen7")
    nuclei = {"info": {"name": "Exposed metrics", "severity": "medium", "tags": ["exposure"]},
              "host": "8.8.8.8", "matched-at": "http://8.8.8.8/metrics"}
    ingest.process_job(jid, {"nuclei": json.dumps(nuclei)})
    reports = [r for r in db.list_reports(org_id=None) if r["job_id"] == jid]
    assert len(reports) == 1 and reports[0]["stage"] == models.REPORT_DRAFT and reports[0]["owner"] == "zed"
    assert reports[0]["org_id"] == _org("zed")                         # copied from the proposal
    assert {f["org_id"] for f in db.get_findings(jid)} == {_org("zed")}
    assert db.latest_content(db.get_proposal_by_job(jid)["id"])["version"] == 1
    ingest.process_job(jid, {"nuclei": json.dumps(nuclei)})       # re-ingest must not duplicate
    assert len([r for r in db.list_reports(org_id=None) if r["job_id"] == jid]) == 1


def test_findings_are_saved_before_ai_enrichment_and_edits_win(tmp_path):
    import json
    import ingest
    import ollama
    import store as report_store
    report_store.REPORTS_DIR = str(tmp_path)
    redis_store._client = FakeRedis()
    from conftest import start_task
    jid = start_task(_prop(_h("yan", "client")).json()["id"], "pen8")
    nuclei = {"info": {"name": "Exposed metrics", "severity": "medium", "tags": ["exposure"]},
              "host": "8.8.8.8", "matched-at": "http://8.8.8.8/metrics"}
    seen = []

    def fake(f):
        seen.append(len(db.get_findings(jid)))             # already visible while the AI works
        return {**f, "impact": "AI impact", "remediation": "AI fix", "risk_rating": "Medium"}
    real, ollama.enrich = ollama.enrich, fake
    try:
        ingest.process_job(jid, {"nuclei": json.dumps(nuclei)})
        assert seen == [1] and db.get_findings(jid)[0]["impact"] == "AI impact"
        fid = db.get_findings(jid)[0]["id"]
        db.set_finding(fid, impact="Edited by pentester")
        assert db.fill_enrichment(fid, "AI again", "AI fix", "Low") is False   # an edit is never overwritten
        assert db.get_findings(jid)[0]["impact"] == "Edited by pentester"
    finally:
        ollama.enrich = real




def test_refusals_from_middleware_still_carry_cors_headers():
    """A browser hides a response without CORS headers behind a network error, so the SPA could
    not tell 403 (team token on the public plane) from a dead server and logged the user out."""
    os.environ.pop("VARUNA_PUBLIC_TEAM_LOGIN", None)
    try:
        origin = browser._CORS[0]   # whichever origin this environment allows
        Hl = {**_h("riyan99", "lead_pentester"), "Origin": origin}
        r = pub.get("/api/me", headers=Hl)
        assert r.status_code == 403 and r.headers.get("access-control-allow-origin") == origin
        big = pub.post("/api/tasks", content=b"x" * 2_000_000, headers={**_h("cors1", "client"), "Origin": origin})
        assert big.status_code == 413 and big.headers.get("access-control-allow-origin") == origin
    finally:
        os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"


def test_board_flags_a_scan_whose_agent_died():
    import board
    from conftest import start_task, window
    redis_store._client = FakeRedis()
    _h("mona", "client")
    nb, na = window()
    tid = db.create_proposal({"submitter": "mona", "org_id": _org("mona"), "target": CLOUD,
                              "not_before": nb, "not_after": na})
    jid = start_task(tid, "pen55")
    job = redis_store.get_job(jid)
    job.update(status="running", per_tool_status={"katana": "done", "nuclei": "running"})
    redis_store.set_job(job)
    agent = redis_store.get_agent("mona"); agent["last_seen"] = "2000-01-01T00:00:00+00:00"; redis_store.set_agent("mona", agent)
    cards = next(c for c in board.build_board({"username": "pen55", "role": "pentester"}) if c["id"] == "scan")["cards"]
    meta = next(c["meta"] for c in cards if c["jobId"] == jid)
    assert "katana done" in meta and "stalled" in meta


def test_stalled_scans_are_failed_after_the_agent_is_silent_too_long():
    import datetime
    import board
    import tokens
    from conftest import start_task, window
    redis_store._client = FakeRedis()
    _h("nora", "client")
    nb, na = window()
    tid = db.create_proposal({"submitter": "nora", "org_id": _org("nora"), "target": CLOUD,
                              "not_before": nb, "not_after": na})
    jid = start_task(tid, "pen56")                                     # local scan: nora's own agent, seen now
    job = redis_store.get_job(jid); job["status"] = "running"; redis_store.set_job(job)
    assert board.reap_stalled() == 0                                   # recently seen: leave it
    later = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=board.STALL_SECONDS // 60 + 1)
    assert board.reap_stalled(now=later) == 1
    assert redis_store.get_job(jid)["status"] == "failed"
    t = db.get_proposal(tid, org_id=None)
    assert t["scan_state"] == "suspended" and "offline" in t["suspend_reason"]
    assert board.reap_stalled(now=later) == 0                          # idempotent








def test_team_gets_live_scan_progress_on_the_private_plane():
    """Regression: with team tokens refused on the public plane, the review drawer's live progress
    (which streamed from the public API) silently 403'd. The team has its own stream now."""
    os.environ.pop("VARUNA_PUBLIC_TEAM_LOGIN", None)
    try:
        redis_store._client = FakeRedis()
        from conftest import start_task
        Hc, Hl = _h("sse1", "client"), _h("lead_sse", "lead_pentester")
        jid = start_task(_prop(Hc).json()["id"], "lead_sse")
        job = redis_store.get_job(jid); job["status"] = "done"; redis_store.set_job(job)
        assert pub.get(f"/api/scans/{jid}/events", headers=Hl).status_code == 403          # public: refused
        with priv.stream("GET", f"/api/scans/{jid}/events", headers=Hl) as r:              # private: streams
            body = "".join(r.iter_text())
        assert r.status_code == 200 and '"status": "done"' in body
        assert priv.get(f"/api/scans/{jid}/events", headers=Hc).status_code == 403          # client: not the team route
    finally:
        os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"


def test_login_ignores_username_case_and_throttle_counts_all_spellings():
    import pytest
    auth.create_account("MixedCase", "password1", "client", org_id=db.create_org("org-mixed"))
    assert auth.authenticate("mixedcase", "password1", "ip1").username == "MixedCase"
    assert auth.authenticate("MIXEDCASE", "password1", "ip1").username == "MixedCase"
    for spelling in ("mixedcase", "MIXEDCASE", "MixedCase", "mIxEdCaSe", "MiXeDcAsE"):      # 5 wrong tries, 5 spellings
        with pytest.raises(auth.BadCredentials):
            auth.authenticate(spelling, "wrong-password", "ip2")
    with pytest.raises(auth.LockedOut):                                                      # still ONE account's counter
        auth.authenticate("MixedCase", "password1", "ip2")


def test_installer_cmd_download_is_gated_and_carries_a_working_one_time_token(monkeypatch):
    import tokens
    monkeypatch.delenv("VARUNA_PUBLIC_URL", raising=False)
    H = _h("inst_client", "client")
    assert pub.get("/api/agent/installer", headers=H).status_code == 403            # nothing claimed yet
    import workflow
    _h("inst_pen", "pentester")
    workflow.transition(_prop(H).json()["id"], "scan/pending", "inst_pen", org_id=None)
    r = pub.get("/api/agent/installer", headers={**H, "x-forwarded-proto": "https", "x-forwarded-host": "varuna.example"})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and "Install-Varuna.cmd" in r.headers["content-disposition"]
    body = r.text
    assert "\r\n" in body and "pause" in body and "https://varuna.example/dist/install.ps1" in body
    tok = body.split("VARUNA_TOKEN=\'")[1].split("\'")[0] if "VARUNA_TOKEN=\'" in body else body.split("VARUNA_TOKEN='")[1].split("'")[0]
    assert tokens.consume_enrollment_token(tok) == "inst_client"                     # a real token for THIS client
    assert tokens.consume_enrollment_token(tok) is None                              # and it works once
    assert pub.get("/api/agent/installer").status_code == 401                        # not for anonymous callers



def test_concurrent_manager_approvals_deliver_exactly_once(tmp_path):
    import store as report_store
    from conftest import ready_pdf
    report_store.REPORTS_DIR = str(tmp_path)
    Hm = _h("bayu9", "manager")
    org = db.create_org("org-dan")
    tid = db.create_proposal({"submitter": "dan", "target": "http://t", "org_id": org, "stage": "review_manager", "job_id": "jr"})
    rid = db.create_report("jr", org, "dan")
    stored = db.get_pdf(ready_pdf(tid))["stored_name"]
    go = lambda _: priv.post(f"/api/tasks/{tid}/transition", headers=Hm, json={"to": "delivered", "version": 0}).status_code
    with cf.ThreadPoolExecutor(8) as ex:
        codes = list(ex.map(go, range(8)))
    assert codes.count(200) == 1, codes                       # one delivery wins, the rest are refused
    assert set(codes) <= {200, 409}, codes
    rep = db.get_report(rid, org_id=None)
    assert rep["stage"] == models.REPORT_DELIVERED and rep["delivered_pdf"] == stored
    assert db.get_proposal(tid, org_id=None)["stage"] == "delivered"


def test_delivery_without_a_pdf_puts_the_task_back():
    Hm = _h("bayu10", "manager")
    org = db.create_org("org-dan")
    tid = db.create_proposal({"submitter": "dan", "target": "http://t", "org_id": org, "stage": "review_manager", "job_id": "jr2"})
    db.create_report("jr2", org, "dan")
    assert priv.post(f"/api/tasks/{tid}/transition", headers=Hm, json={"to": "delivered", "version": 0}).status_code == 409
    assert db.get_proposal(tid, org_id=None)["stage"] == "review_manager", "not stuck in a transient stage"


def test_the_client_password_is_the_same_for_every_request_even_in_parallel():
    redis_store._client = FakeRedis()
    import pdfpass
    Hc = _h("vera", "client")
    rid = db.create_report("jv", _org("vera"), "vera", stage=models.REPORT_DELIVERED)
    db.set_report(rid, pdf_password=pdfpass.seal("s3cr3t"), delivered_pdf="x.pdf")
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda _: pub.get(f"/api/reports/{rid}/password", headers=Hc), range(8)))
    assert {r.status_code for r in res} == {200} and {r.json()["password"] for r in res} == {"s3cr3t"}


def test_recreated_account_does_not_accept_old_tokens():
    auth.create_account("gone-user", "pw-Aa1234567", "pentester")
    old = db.get_account("gone-user")["token_version"]
    db.get_conn().execute("DELETE FROM accounts WHERE username='gone-user'"); db.get_conn().commit()
    auth.create_account("gone-user", "pw-Aa1234567", "pentester")
    assert db.get_account("gone-user")["token_version"] != old
