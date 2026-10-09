"""Self-service profile: read-only fields stay put, email changes only after a single-use confirm."""
import hashlib
import sys
import time
import types

import pytest

import auth
import audit
import db


@pytest.fixture
def sent(monkeypatch):
    """Capture outgoing mail; run the mail thread inline so tests can read it right away."""
    box = {}
    monkeypatch.setattr("mailer.send", lambda to, subj, body: box.update(to=to, body=body) or True)

    class Inline:
        def __init__(self, target, args=(), daemon=None):
            self.t, self.a = target, args

        def start(self):
            self.t(*self.a)
    monkeypatch.setattr(sys.modules["profile_api"], "threading", types.SimpleNamespace(Thread=Inline))
    return box


def _client(name="rina", org="PT A"):
    oid = db.create_org(org)
    auth.create_account(name, "Passw0rd!x", "client", org_id=oid)
    return oid


def test_profile_read_only_fields_ignored(api):
    oid = _client()
    tok = api.login("rina", "Passw0rd!x")
    r = api.put("/api/profile", tok, {"display_name": "Rina S", "phone": "0812-3456", "role": "sysadmin",
                                      "org_id": "x", "username": "evil", "email": "x@y.zz", "bogus": 1})
    assert r.status_code == 200
    a = db.get_account("rina")
    assert a["display_name"] == "Rina S" and a["role"] == "client" and a["org_id"] == oid
    assert a["email"] in (None, "") and db.get_account("evil") is None
    assert api.get("/api/profile", tok).json()["org_name"] == "PT A"


def test_profile_strips_caps_and_cleans_control_chars(api):
    _client()
    tok = api.login("rina", "Passw0rd!x")
    api.put("/api/profile", tok, {"display_name": "  Ri\x00na\x07 \n" + "x" * 300, "phone": " 08 "})
    a = db.get_account("rina")
    assert a["display_name"].startswith("Rina") and len(a["display_name"]) == 120 and "\x00" not in a["display_name"]
    assert a["phone"] == "08"


def test_get_profile_leaks_no_secrets(api):
    _client()
    db.set_account("rina", totp_secret="JBSWY3DPEHPK3PXP")
    tok = api.login("rina", "Passw0rd!x")
    body = api.get("/api/profile", tok)
    assert set(body.json()) == {"username", "role", "org_name", "display_name", "email", "phone", "totp_enabled"}
    assert "JBSWY3DP" not in body.text and "$2" not in body.text


def test_email_changes_only_after_confirm(api, sent):
    _client()
    tok = api.login("rina", "Passw0rd!x")
    assert api.post("/api/profile/email", tok, {"email": "rina@samudera.co.id"}).status_code == 200
    assert db.get_account("rina")["email"] in (None, "")
    token = sent["body"].split("token=")[1].split()[0]
    assert api.post("/api/profile/email/confirm", tok, {"token": token}).status_code == 200
    assert db.get_account("rina")["email"] == "rina@samudera.co.id"
    assert api.post("/api/profile/email/confirm", tok, {"token": token}).status_code == 422   # single use


def test_link_uses_public_url_and_token_hashed_at_rest(api, sent, monkeypatch):
    _client()
    monkeypatch.setenv("VARUNA_PUBLIC_URL", "https://varuna.example/")
    tok = api.login("rina", "Passw0rd!x")
    api.post("/api/profile/email", tok, {"email": "rina@samudera.co.id"})
    assert "https://varuna.example/confirm-email?token=" in sent["body"]
    token = sent["body"].split("token=")[1].split()[0]
    rows = db.get_conn().execute("SELECT token_hash FROM email_changes").fetchall()
    assert [r["token_hash"] for r in rows] == [hashlib.sha256(token.encode()).hexdigest()]
    assert token not in rows[0]["token_hash"]


def test_email_token_expires(api, sent):
    _client()
    tok = api.login("rina", "Passw0rd!x")
    api.post("/api/profile/email", tok, {"email": "rina@samudera.co.id"})
    token = sent["body"].split("token=")[1].split()[0]
    c = db.get_conn()
    c.execute("UPDATE email_changes SET expires_at=?", (int(time.time()) - 1,))
    c.commit()
    assert api.post("/api/profile/email/confirm", tok, {"token": token}).status_code == 422
    assert db.get_account("rina")["email"] in (None, "")


def test_other_users_token_is_refused_and_changes_nothing(api, sent):
    _client("rina")
    _client("budi", "PT B")
    t_rina = api.login("rina", "Passw0rd!x")
    t_budi = api.login("budi", "Passw0rd!x")
    api.post("/api/profile/email", t_rina, {"email": "rina@samudera.co.id"})
    token = sent["body"].split("token=")[1].split()[0]
    assert api.post("/api/profile/email/confirm", t_budi, {"token": token}).status_code == 422
    assert db.get_account("budi")["email"] in (None, "") and db.get_account("rina")["email"] in (None, "")


def test_email_request_same_answer_for_taken_address_and_no_email_in_audit(api, sent, monkeypatch):
    _client("rina")
    _client("budi", "PT B")
    db.set_account("budi", email="budi@x.co")
    logged = []
    monkeypatch.setattr(audit, "log", lambda t, **f: logged.append((t, f)))
    tok = api.login("rina", "Passw0rd!x")
    taken = api.post("/api/profile/email", tok, {"email": "budi@x.co"})
    free = api.post("/api/profile/email", tok, {"email": "free@x.co"})
    assert taken.status_code == free.status_code == 200 and taken.json() == free.json()
    assert "budi@x.co" not in repr(logged) and "free@x.co" not in repr(logged)
    assert api.post("/api/profile/email", tok, {"email": "bad"}).status_code == 422


def test_sysadmin_and_staff_can_use_profile_on_private_plane(priv):
    auth.create_account("root", "Passw0rd!x", "sysadmin")
    tok = priv.login("root", "Passw0rd!x")
    assert priv.put("/api/profile", tok, {"display_name": "Root"}).status_code == 200
    assert priv.get("/api/profile", tok).json()["display_name"] == "Root"


def test_password_change_needs_current_and_keeps_session(api):
    _client()
    tok = api.login("rina", "Passw0rd!x")
    assert api.post("/api/password", tok, {"current": "wrong", "new": "N3wPassw0rd!"}).status_code == 403
    r = api.post("/api/password", tok, {"current": "Passw0rd!x", "new": "N3wPassw0rd!"})
    assert api.get("/api/me", tok).status_code == 401
    assert api.get("/api/me", r.json()["token"]).status_code == 200


def test_confirmation_link_base_depends_on_role(api, priv, sent, monkeypatch):
    _client()
    auth.create_account("dimas", "Passw0rd!x", "pentester")
    monkeypatch.setenv("VARUNA_PUBLIC_URL", "https://public.example")
    monkeypatch.setenv("VARUNA_TEAM_URL", "https://team.example/")
    ctok = api.login("rina", "Passw0rd!x")
    api.post("/api/profile/email", ctok, {"email": "rina@x.co"})
    assert "https://public.example/confirm-email?token=" in sent["body"]
    stok = priv.login("dimas", "Passw0rd!x")
    priv.post("/api/profile/email", stok, {"email": "dimas@x.co"})
    assert "https://team.example/confirm-email?token=" in sent["body"]
    monkeypatch.delenv("VARUNA_TEAM_URL")
    priv.post("/api/profile/email", stok, {"email": "dimas@x.co"})
    assert "https://public.example/confirm-email?token=" in sent["body"]   # falls back to the public URL
