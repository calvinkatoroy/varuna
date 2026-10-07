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
    assert api.get("/api/proposals", tok).status_code == 403
