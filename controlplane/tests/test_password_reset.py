"""Email password reset for clients: no account oracle, single-use, expiring, throttled, clients only."""
import os
import sys
import time

HERE = os.path.dirname(__file__)
for p in ("", "../common", "../api", "../pipeline", ".."):
    sys.path.insert(0, os.path.join(HERE, p))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import browser  # noqa: E402
import db  # noqa: E402
import mailer  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

pub = TestClient(browser.app)
SENT: list = []


def _capture(monkeypatch):
    redis_store._client = FakeRedis()
    SENT.clear()
    monkeypatch.setattr(mailer, "send", lambda to, subject, body: SENT.append((to, body)) or True)


def _token(body: str) -> str:
    return body.split("token=")[1].split()[0]


def _wait_mail(n=1):
    for _ in range(50):
        if len(SENT) >= n:
            return
        time.sleep(0.05)


def test_reset_roundtrip_is_single_use_and_unlocks_login(monkeypatch):
    _capture(monkeypatch)
    assert pub.post("/api/register", json={"username": "rst1", "password": "oldpass11", "email": "Rst1@Example.com"}).status_code == 200
    assert pub.post("/api/password-reset/request", json={"email": "rst1@example.com"}).json() == {"ok": True}
    _wait_mail()
    assert len(SENT) == 1 and SENT[0][0] == "rst1@example.com"
    tok = _token(SENT[0][1])
    assert db.get_conn().execute("SELECT count(*) FROM reset_tokens WHERE token_hash=?", (tok,)).fetchone()[0] == 0   # only a hash is stored
    assert pub.post("/api/password-reset/confirm", json={"token": tok, "new": "short"}).status_code == 422          # weak: token not burned
    assert pub.post("/api/password-reset/confirm", json={"token": tok, "new": "brandnew22"}).status_code == 200
    assert pub.post("/api/password-reset/confirm", json={"token": tok, "new": "another33x"}).status_code == 422     # single use
    assert pub.post("/api/login", json={"username": "rst1", "password": "oldpass11"}).status_code == 401
    assert pub.post("/api/login", json={"username": "rst1", "password": "brandnew22"}).status_code == 200


def test_unknown_email_looks_identical_and_sends_nothing(monkeypatch):
    _capture(monkeypatch)
    a = pub.post("/api/password-reset/request", json={"email": "nobody@example.com"})
    assert a.status_code == 200 and a.json() == {"ok": True}
    assert pub.post("/api/password-reset/request", json={"email": ""}).json() == {"ok": True}
    time.sleep(0.2)
    assert SENT == []


def test_expired_and_superseded_tokens_are_refused(monkeypatch):
    _capture(monkeypatch)
    pub.post("/api/register", json={"username": "rst2", "password": "oldpass11", "email": "rst2@example.com"})
    (name, old), = auth.start_reset("rst2@example.com", "ip")
    (name, new), = auth.start_reset("rst2@example.com", "ip")          # a newer request voids the older link
    assert pub.post("/api/password-reset/confirm", json={"token": old, "new": "brandnew22"}).status_code == 422
    db.get_conn().execute("UPDATE reset_tokens SET expires_at=? WHERE username='rst2'", (int(time.time()) - 1,))
    db.get_conn().commit()
    assert pub.post("/api/password-reset/confirm", json={"token": new, "new": "brandnew22"}).status_code == 422
    assert pub.post("/api/password-reset/confirm", json={"token": "garbage", "new": "brandnew22"}).status_code == 422


def test_team_accounts_never_reset_by_email(monkeypatch):
    _capture(monkeypatch)
    auth.create_account("lead_x", "password1", "lead_pentester")
    db.set_account("lead_x", email="lead@example.com")
    assert auth.start_reset("lead@example.com", "ip") == []


def test_request_throttle_per_address(monkeypatch):
    _capture(monkeypatch)
    pub.post("/api/register", json={"username": "rst3", "password": "oldpass11", "email": "rst3@example.com"})
    got = [bool(auth.start_reset("rst3@example.com", f"ip{i}")) for i in range(auth.RESET_LIMIT + 3)]
    assert got == [True] * auth.RESET_LIMIT + [False] * 3


def test_bad_email_at_register_is_refused_and_email_can_be_added_later(monkeypatch):
    _capture(monkeypatch)
    assert pub.post("/api/register", json={"username": "rst4", "password": "oldpass11", "email": "not-an-email"}).status_code == 422
    tok = pub.post("/api/register", json={"username": "rst4", "password": "oldpass11"}).json()["token"]
    H = {"Authorization": f"Bearer {tok}"}
    assert pub.put("/api/email", json={"email": "bad"}, headers=H).status_code == 422
    assert pub.put("/api/email", json={"email": "rst4@example.com"}, headers=H).status_code == 200
    assert auth.start_reset("rst4@example.com", "ip")
