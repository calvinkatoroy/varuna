import db
import auth


def _client(org="PT A", name="rina", pw="Passw0rd!x"):
    oid = db.create_org(org)
    auth.create_account(name, pw, "client", org_id=oid)
    return oid


def test_token_dies_on_disable(api):
    _client()
    tok = api.login("rina", "Passw0rd!x")
    assert api.get("/api/me", tok).status_code == 200
    db.set_account("rina", disabled=1)
    assert api.get("/api/me", tok).status_code == 401


def test_token_dies_on_role_change_password_change_and_org_disable(api):
    oid = _client()
    tok = api.login("rina", "Passw0rd!x")
    db.set_org_status(oid, "disabled")
    assert api.get("/api/me", tok).status_code == 401
    db.set_org_status(oid, "active")
    assert api.get("/api/me", tok).status_code == 200    # same tv, org active again
    db.set_account("rina", password_hash="x")             # bumps tv
    assert api.get("/api/me", tok).status_code == 401


def test_identity_comes_from_db_not_token(api):
    _client()
    tok = api.login("rina", "Passw0rd!x")
    me = api.get("/api/me", tok).json()
    assert me["org_id"] and me["role"] == "client"


def test_refresh_issues_working_token(api):
    _client()
    tok = api.login("rina", "Passw0rd!x")
    new = api.post("/api/refresh", tok).json()["token"]
    assert api.get("/api/me", new).status_code == 200


def test_must_change_password_blocks_everything_else(api):
    _client()
    db.set_account("rina", must_change_password=1)
    tok = api.login("rina", "Passw0rd!x")
    assert api.get("/api/me", tok).status_code == 200
    assert api.get("/api/tasks", tok).status_code == 403


def test_org_change_ends_old_token(api):
    _client()
    other = db.create_org("PT B")
    tok = api.login("rina", "Passw0rd!x")
    db.set_account("rina", org_id=other)
    assert api.get("/api/me", tok).status_code == 401


def test_mfa_enable_and_disable_end_old_tokens(priv):
    import totp
    auth.create_account("dimas", "Passw0rd!x", "pentester")
    tok = priv.login("dimas", "Passw0rd!x")
    secret = priv.post("/api/mfa/setup", tok).json()["secret"]
    r = priv.post("/api/mfa/enable", tok, {"code": totp.code_at(secret)})
    assert r.status_code == 200
    assert priv.get("/api/me", tok).status_code == 401           # enabling bumped the version
    tok2 = r.json()["token"]
    assert priv.get("/api/me", tok2).status_code == 200
    # the enrolment step is spent; disabling needs the next one, so bypass the replay guard
    code = totp.code_at(secret, __import__("time").time() + 30)
    r = priv.post("/api/mfa/disable", tok2, {"password": "Passw0rd!x", "code": code})
    assert r.status_code == 200, r.text
    assert priv.get("/api/me", tok2).status_code == 401
    assert priv.get("/api/me", r.json()["token"]).status_code == 200


def test_token_without_tv_claim_is_refused(api):
    import datetime
    import jwt
    import jwt_auth
    _client()
    now = datetime.datetime.now(datetime.UTC)
    tok = jwt.encode({"sub": "rina", "role": "client", "iat": now, "exp": now + datetime.timedelta(hours=1)},
                     jwt_auth.JWT_SECRET, algorithm=jwt_auth.JWT_ALG)
    assert api.get("/api/me", tok).status_code == 401


def test_refresh_with_stale_token_is_refused(api):
    _client()
    tok = api.login("rina", "Passw0rd!x")
    db.set_account("rina", password_hash="x")
    assert api.post("/api/refresh", tok).status_code == 401


def test_must_change_password_clears_after_password_change(api):
    _client()
    db.set_account("rina", must_change_password=1)
    tok = api.login("rina", "Passw0rd!x")
    r = api.post("/api/password", tok, {"current": "Passw0rd!x", "new": "N3wPassw0rd!"})
    assert r.status_code == 200
    assert db.get_account("rina")["must_change_password"] == 0
    assert api.get("/api/tasks", r.json()["token"]).status_code == 200


def test_new_password_must_differ_from_current(api):
    _client()
    db.set_account("rina", must_change_password=1)
    tok = api.login("rina", "Passw0rd!x")
    assert api.post("/api/password", tok, {"current": "Passw0rd!x", "new": "Passw0rd!x"}).status_code == 422
    assert db.get_account("rina")["must_change_password"] == 1
    assert api.post("/api/password", tok, {"current": "Passw0rd!x", "new": "N3wPassw0rd!"}).status_code == 200


def test_demoted_reviewer_cannot_claim_a_stage(priv):
    import models
    auth.create_account("root", "Passw0rd!x", "sysadmin")
    auth.create_account("riyan", "Passw0rd!x", "lead_pentester")
    rid = db.create_report("j1", db.create_org("PT Q"), "alice", stage=models.REPORT_LEAD)
    old = priv.login("riyan", "Passw0rd!x")
    root = priv.login("root", "Passw0rd!x")
    assert priv.put("/api/sysadmin/accounts/riyan/role", root, {"role": "pentester"}).status_code == 200
    assert priv.post(f"/api/pipeline/reports/{rid}/forward", old).status_code == 401
    fresh = priv.login("riyan", "Passw0rd!x")
    assert priv.post(f"/api/pipeline/reports/{rid}/forward", fresh).status_code == 403
    assert db.get_report(rid, org_id=None)["stage"] == models.REPORT_LEAD
