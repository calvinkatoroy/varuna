"""Two-factor (TOTP) for team accounts: enrolment, login, replay, lockout, recovery."""
import os
import sys
import time

HERE = os.path.dirname(__file__)
os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"
for sub in ("common", "api", "pipeline", "report"):
    sys.path.insert(0, os.path.join(HERE, "..", sub))
sys.path.insert(0, HERE)

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import db  # noqa: E402
import jwt_auth  # noqa: E402
import private_api  # noqa: E402
import totp  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

priv = TestClient(private_api.app)


def _account(name, role="pentester", pw="password1"):
    auth.create_account(name, pw, role, org_id=db.create_org("org-" + name) if role == "client" else None)
    return {"Authorization": "Bearer " + jwt_auth.login(name, pw, "ip")}


def _login(name, code=None, pw="password1"):
    body = {"username": name, "password": pw, **({"code": code} if code else {})}
    return priv.post("/api/login", json=body)


def _enrol(name):
    H = _account(name)
    secret = priv.post("/api/mfa/setup", headers=H).json()["secret"]
    step_code = totp.code_at(secret)
    r = priv.post("/api/mfa/enable", json={"code": step_code}, headers=H).json()
    assert r["enabled"] is True
    return {"Authorization": "Bearer " + r["token"]}, secret, step_code    # enabling bumps token_version


def test_rfc_vectors():
    import base64
    rfc = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    assert totp.code_at(rfc, 59) == "287082" and totp.code_at(rfc, 1234567890) == "005924"


def test_enrolment_needs_a_correct_code_and_only_then_enforces_login():
    redis_store._client = FakeRedis()
    H = _account("mfa1")
    secret = priv.post("/api/mfa/setup", headers=H).json()["secret"]
    assert _login("mfa1").status_code == 200                       # set up but not confirmed: not enforced yet
    assert priv.post("/api/mfa/enable", json={"code": "000000"}, headers=H).status_code == 422
    r = priv.post("/api/mfa/enable", json={"code": totp.code_at(secret)}, headers=H)
    assert r.status_code == 200
    H = {"Authorization": "Bearer " + r.json()["token"]}
    assert priv.get("/api/mfa", headers=H).json()["enabled"] is True
    r = _login("mfa1")
    assert r.status_code == 401 and r.json()["detail"] == "mfa_required"      # password alone is no longer enough


def test_required_policy_locks_unenrolled_team_out_of_everything_but_enrolment(monkeypatch):
    redis_store._client = FakeRedis()
    monkeypatch.setenv("VARUNA_REQUIRE_MFA", "1")
    H = _account("mfa_req")
    r = priv.get("/api/pipeline/board", headers=H)
    assert r.status_code == 403 and r.json()["detail"] == "mfa_enrolment_required"
    assert priv.get("/api/mfa", headers=H).json() == {"enabled": False, "required": True}
    secret = priv.post("/api/mfa/setup", headers=H).json()["secret"]
    assert priv.get("/api/pipeline/board", headers=H).status_code == 403     # set up but not confirmed
    r = priv.post("/api/mfa/enable", json={"code": totp.code_at(secret)}, headers=H)
    assert r.status_code == 200
    H = {"Authorization": "Bearer " + r.json()["token"]}
    assert priv.get("/api/pipeline/board", headers=H).status_code == 200     # enrolled: unlocked
    monkeypatch.delenv("VARUNA_REQUIRE_MFA")
    assert priv.get("/api/pipeline/board", headers=_account("mfa_off")).status_code == 200   # policy off: unchanged


def test_login_with_code_and_replay_protection():
    redis_store._client = FakeRedis()
    H, secret, used = _enrol("mfa2")
    assert _login("mfa2", used).status_code == 401                 # the enrolment code's step is already spent
    later = totp.code_at(secret, time.time() + totp.STEP)          # next step: fresh
    ok = _login("mfa2", later)
    assert ok.status_code == 200 and "token" in ok.json()
    assert _login("mfa2", later).status_code == 401                # replaying the same code fails
    assert _login("mfa2", "12345").status_code == 401              # malformed
    assert _login("mfa2", totp.code_at(secret, time.time() + 2 * totp.STEP), pw="WRONGPASS").status_code == 401


def test_bad_codes_count_toward_lockout():
    redis_store._client = FakeRedis()
    _enrol("mfa3")
    for _ in range(auth.FAIL_LIMIT):
        assert _login("mfa3", "000000").status_code == 401
    assert _login("mfa3", "000000").status_code == 429


def test_disable_needs_password_and_code_and_lead_can_reset_lost_phone():
    redis_store._client = FakeRedis()
    H, secret, used = _enrol("mfa4")
    fresh = totp.code_at(secret, time.time() + totp.STEP)
    assert priv.post("/api/mfa/disable", json={"password": "nope", "code": fresh}, headers=H).status_code == 403
    assert priv.post("/api/mfa/disable", json={"password": "password1", "code": "111111"}, headers=H).status_code == 403
    Hl = _account("boss2", "lead_pentester")
    assert priv.post("/api/admin/accounts/mfa4/reset-mfa", headers=_account("pen5")).status_code == 403   # lead only
    assert priv.post("/api/admin/accounts/mfa4/reset-mfa", headers=Hl).status_code == 200
    assert _login("mfa4").status_code == 200                       # lost phone recovered: password alone works again
    assert priv.post("/api/admin/accounts/ghost/reset-mfa", headers=Hl).status_code == 404


def test_admin_roster_shows_mfa_state_without_secrets():
    redis_store._client = FakeRedis()
    _enrol("mfa5")
    rows = priv.get("/api/admin/accounts", headers=_account("boss3", "lead_pentester")).json()
    row = next(r for r in rows if r["username"] == "mfa5")
    assert row["totp_enabled"] == 1 and "totp_secret" not in row and "password_hash" not in row


def test_public_login_of_a_two_factor_account_is_a_clean_refusal_not_a_500():
    import browser
    redis_store._client = FakeRedis()
    _enrol("mfa6")
    r = TestClient(browser.app).post("/api/login", json={"username": "mfa6", "password": "password1"})
    assert r.status_code == 403 and "private plane" in r.json()["detail"]
