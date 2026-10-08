import auth
import db


def _root():
    auth.create_account("root", "Passw0rd!x", "sysadmin")


def test_only_sysadmin_provisions(priv):
    _root()
    auth.create_account("dimas", "Passw0rd!x", "pentester")
    tok = priv.login("dimas", "Passw0rd!x")
    assert priv.post("/api/sysadmin/orgs", tok, {"name": "PT X"}).status_code == 403


def test_create_org_user_and_forced_password_change(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    oid = priv.post("/api/sysadmin/orgs", tok, {"name": "PT Samudera"}).json()["id"]
    r = priv.post("/api/sysadmin/accounts", tok, {"username": "budi", "role": "client", "org_id": oid})
    assert r.status_code == 200 and len(r.json()["temp_password"]) >= 12
    a = db.get_account("budi")
    assert a["org_id"] == oid and a["must_change_password"] == 1


def test_client_needs_org_staff_must_not_have_one(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    oid = priv.post("/api/sysadmin/orgs", tok, {"name": "PT Y"}).json()["id"]
    assert priv.post("/api/sysadmin/accounts", tok, {"username": "c1", "role": "client"}).status_code == 422
    assert priv.post("/api/sysadmin/accounts", tok, {"username": "s1", "role": "pentester", "org_id": oid}).status_code == 422
    assert priv.post("/api/sysadmin/accounts", tok, {"username": "x", "role": "reporter"}).status_code == 422


def test_cannot_disable_or_demote_last_sysadmin(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    assert priv.post("/api/sysadmin/accounts/root/disable", tok).status_code == 409
    assert priv.put("/api/sysadmin/accounts/root/role", tok, {"role": "manager"}).status_code == 409


def test_sysadmin_has_no_tenant_access(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    for path in ("/api/findings", "/api/pipeline/board", "/api/pipeline/reports", "/api/reports/all"):
        assert priv.get(path, tok).status_code == 403


def test_public_plane_refuses_non_clients(api, monkeypatch):
    _root()
    auth.create_account("dimas", "Passw0rd!x", "pentester")
    monkeypatch.delenv("VARUNA_PUBLIC_TEAM_LOGIN", raising=False)
    assert api.raw_login("root", "Passw0rd!x").status_code == 403
    assert api.raw_login("dimas", "Passw0rd!x").status_code == 403
    monkeypatch.setenv("VARUNA_PUBLIC_TEAM_LOGIN", "1")      # dev opt-in is for team roles only
    assert api.raw_login("dimas", "Passw0rd!x").status_code == 200
    assert api.raw_login("root", "Passw0rd!x").status_code == 403


def test_username_rules_case_collision_and_reserved_names(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    oid = priv.post("/api/sysadmin/orgs", tok, {"name": "PT Z"}).json()["id"]
    for u in ("ab", "a b c", "<script>", "u" * 40, "varuna-cloud", "Varuna-Cloud", "varuna-anything"):
        r = priv.post("/api/sysadmin/accounts", tok, {"username": u, "role": "client", "org_id": oid})
        assert r.status_code == 422, (u, r.text)
    assert priv.post("/api/sysadmin/accounts", tok, {"username": "gina", "role": "client", "org_id": oid}).status_code == 200
    assert priv.post("/api/sysadmin/accounts", tok, {"username": "GINA", "role": "client", "org_id": oid}).status_code == 409

