import audit
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
    assert priv.post("/api/sysadmin/accounts", tok, {"username": "x", "role": "governance"}).status_code == 422


def test_cannot_disable_or_demote_last_sysadmin(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    assert priv.post("/api/sysadmin/accounts/root/disable", tok).status_code == 409
    assert priv.put("/api/sysadmin/accounts/root/role", tok, {"role": "manager"}).status_code == 409


def test_sysadmin_has_no_tenant_access(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    for path in ("/api/findings", "/api/board", "/api/tasks/x/detail", "/api/reports/all"):
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



def _two_sysadmins():
    _root()
    auth.create_account("root2", "Passw0rd!x", "sysadmin")


def test_sysadmin_cannot_demote_self_even_with_another_sysadmin(priv):
    _two_sysadmins()
    tok = priv.login("root", "Passw0rd!x")
    r = priv.put("/api/sysadmin/accounts/root/role", tok, {"role": "manager"})
    assert r.status_code == 409
    assert db.get_account("root")["role"] == "sysadmin"


def test_disabled_sysadmin_target_does_not_trip_last_sysadmin_guard(priv):
    _two_sysadmins()
    tok = priv.login("root", "Passw0rd!x")
    assert priv.post("/api/sysadmin/accounts/root2/disable", tok).status_code == 200
    # root2 is disabled; the only ACTIVE sysadmin is root. Demoting the disabled one is allowed.
    assert priv.put("/api/sysadmin/accounts/root2/role", tok, {"role": "manager"}).status_code == 200
    assert priv.post("/api/sysadmin/accounts/root2/disable", tok).status_code == 200


def test_sysadmin_enrols_mfa_when_required_and_stays_out_of_tenant_data(priv, monkeypatch):
    import totp
    monkeypatch.setenv("VARUNA_REQUIRE_MFA", "1")
    _root()
    tok = priv.login("root", "Passw0rd!x")
    r = priv.get("/api/sysadmin/orgs", tok)
    assert r.status_code == 403 and r.json()["detail"] == "mfa_enrolment_required"
    secret = priv.post("/api/mfa/setup", tok).json()["secret"]
    r = priv.post("/api/mfa/enable", tok, {"code": totp.code_at(secret)})
    assert r.status_code == 200
    tok2 = r.json()["token"]
    assert priv.get("/api/sysadmin/orgs", tok2).status_code == 200
    assert priv.get("/api/board", tok2).status_code == 403


def test_bad_email_leaves_no_orphan_account(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    oid = priv.post("/api/sysadmin/orgs", tok, {"name": "PT Mail"}).json()["id"]
    body = {"username": "mailu", "role": "client", "org_id": oid, "email": "not-an-email"}
    assert priv.post("/api/sysadmin/accounts", tok, body).status_code == 422
    assert db.get_account("mailu") is None
    body["email"] = "mailu@example.com"
    assert priv.post("/api/sysadmin/accounts", tok, body).status_code == 200


def test_role_change_between_staff_roles_kills_old_token(priv):
    _root()
    auth.create_account("dimas", "Passw0rd!x", "pentester")
    tok = priv.login("root", "Passw0rd!x")
    old = priv.login("dimas", "Passw0rd!x")
    assert priv.get("/api/board", old).status_code == 200
    assert priv.put("/api/sysadmin/accounts/dimas/role", tok, {"role": "governance"}).status_code == 200
    assert db.get_account("dimas")["role"] == "governance"
    assert priv.get("/api/board", old).status_code == 401


def test_temp_password_forces_change_then_clears(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    r = priv.post("/api/sysadmin/accounts", tok, {"username": "staffer", "role": "governance"})
    tmp = r.json()["temp_password"]
    t = priv.login("staffer", tmp)
    r = priv.get("/api/board", t)
    assert r.status_code == 403 and r.json()["detail"] == "password_change_required"
    r = priv.post("/api/password", t, {"current": tmp, "new": "Br4nd-new-Pass!9"})
    assert r.status_code == 200
    assert db.get_account("staffer")["must_change_password"] == 0
    assert priv.get("/api/board", r.json()["token"]).status_code == 200


def test_reset_password_kills_old_token(priv):
    _root()
    auth.create_account("dimas", "Passw0rd!x", "pentester")
    tok = priv.login("root", "Passw0rd!x")
    old = priv.login("dimas", "Passw0rd!x")
    assert priv.post("/api/sysadmin/accounts/dimas/reset-password", tok).status_code == 200
    assert priv.get("/api/board", old).status_code == 401


def test_client_for_disabled_org_is_refused(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    oid = priv.post("/api/sysadmin/orgs", tok, {"name": "PT Off"}).json()["id"]
    assert priv.post(f"/api/sysadmin/orgs/{oid}/disable", tok).status_code == 200
    r = priv.post("/api/sysadmin/accounts", tok, {"username": "offc", "role": "client", "org_id": oid})
    assert r.status_code == 422 and db.get_account("offc") is None


def test_sysadmin_token_refused_on_every_public_route_even_with_dev_opt_in(api, priv, monkeypatch):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    for opt_in in (None, "1"):
        if opt_in:
            monkeypatch.setenv("VARUNA_PUBLIC_TEAM_LOGIN", opt_in)
        else:
            monkeypatch.delenv("VARUNA_PUBLIC_TEAM_LOGIN", raising=False)
        for method, path in (("GET", "/api/me"), ("POST", "/api/refresh"), ("GET", "/api/profile")):
            assert api.request(method, path, tok).status_code == 403, (opt_in, path)


def test_set_account_email(priv):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    auth.create_account("dimas", "Passw0rd!x", "pentester")
    url = "/api/sysadmin/accounts/dimas/email"
    assert priv.put(url, tok, {"email": "dimas@ilcs.co.id"}).status_code == 200
    assert db.get_account("dimas")["email"] == "dimas@ilcs.co.id"
    assert priv.put(url, tok, {"email": "nope"}).status_code == 422
    assert priv.put("/api/sysadmin/accounts/ghost/email", tok, {"email": "a@b.co"}).status_code == 404
    assert priv.put(url, tok, {"email": ""}).status_code == 200
    assert db.get_account("dimas")["email"] in (None, "")
    dtok = priv.login("dimas", "Passw0rd!x")
    assert priv.put(url, dtok, {"email": "x@y.zz"}).status_code == 403


def test_set_account_email_audit_has_no_address(priv, monkeypatch):
    _root()
    tok = priv.login("root", "Passw0rd!x")
    auth.create_account("dimas", "Passw0rd!x", "pentester")
    logged = []
    monkeypatch.setattr(audit, "log", lambda t, **f: logged.append((t, f)))
    priv.put("/api/sysadmin/accounts/dimas/email", tok, {"email": "dimas@ilcs.co.id"})
    assert logged and "dimas@ilcs.co.id" not in repr(logged)
