"""Authentication + login brute-force throttle (SRS NFR-22, NFR-25, REQ-65..70).

Passwords are bcrypt-hashed (NFR-22). The public-plane login is internet-facing in
front of a tool that launches attacks, so failed logins are rate-limited per-account
AND per-source-IP with a temporary lockout (NFR-25), this is not optional hardening.

`bcrypt` is imported lazily so the throttle logic stays testable without the package.
"""
from __future__ import annotations

import db
import redis_store
import totp
from models import Account, ROLES

FAIL_LIMIT = 5          # lock a source IP (or IP+account pair) after this many failures
USER_FAIL_LIMIT = 25    # account-wide cap across all IPs: high enough that one attacker cannot
                        # lock a real user out (M7), low enough to stop a distributed guess
FAIL_WINDOW = 900       # seconds (15 min)


class AuthError(Exception):
    pass


class UsernameTaken(AuthError):
    pass


class MfaRequired(AuthError):
    """Password was right, but this account has two-factor enabled and no valid code was given."""


class BadCredentials(AuthError):
    pass


class LockedOut(AuthError):
    pass


def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def create_account(username: str, password: str, role: str, org_id: str | None = None) -> Account:
    """Provision an account (REQ-69: no self-registration; a Pro user calls this)."""
    if role not in ROLES:
        raise ValueError(f"invalid role: {role}")
    if (role == "client") != bool(org_id):
        raise ValueError("clients need an organization; staff must not have one")
    acct = Account(username=username, password_hash=hash_password(password), role=role)
    db.upsert_account(acct.username, acct.password_hash, acct.role, org_id=org_id)
    return acct


def _clean_email(email: str) -> str:
    import re
    email = (email or "").strip()
    if email and (len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)):
        raise AuthError("that email address doesn't look right")
    return email


def set_email(username: str, email: str) -> None:
    db.set_account(username, email=_clean_email(email) or None)


RESET_TTL = 1800        # a reset link works for 30 minutes
RESET_LIMIT = 5         # requests per source IP and per address per hour


def start_reset(email: str, ip: str) -> list[tuple[str, str]]:
    """Mint reset tokens for the client accounts on this address -> [(username, raw token)].
    Empty for unknown/invalid/throttled requests: the caller answers identically either way."""
    import hashlib
    import secrets
    import time
    email = (email or "").strip().lower()
    if not email:
        return []
    r = redis_store.get_redis()
    for key in (f"reset_req_ip:{ip}", f"reset_req:{email}"):
        if r.incr(key) == 1:
            r.expire(key, 3600)
        if int(r.get(key) or 0) > RESET_LIMIT:
            return []
    out = []
    for name in db.client_usernames_by_email(email):
        token = secrets.token_urlsafe(32)
        db.add_reset_token(hashlib.sha256(token.encode()).hexdigest(), name, int(time.time()) + RESET_TTL)
        out.append((name, token))
    return out


def finish_reset(token: str, new: str) -> None:
    """Spend a reset token and set the new password. A weak password is refused BEFORE the token is spent."""
    import hashlib
    import time
    _check_new_password(new)
    name = db.claim_reset_token(hashlib.sha256((token or "").encode()).hexdigest(), int(time.time()))
    if not name:
        raise AuthError("this reset link is invalid or has expired")
    db.set_account(name, password_hash=hash_password(new))
    redis_store.get_redis().delete(redis_store.login_fail_key(name))   # they may be locked out from guessing


def _record_fail(username: str, ip: str) -> None:
    r = redis_store.get_redis()
    for key in (redis_store.login_fail_key(username), redis_store.login_fail_key(f"{username}|{ip}"),
                redis_store.login_fail_ip_key(ip)):
        if r.incr(key) == 1:
            r.expire(key, FAIL_WINDOW)


def _is_locked(username: str, ip: str) -> bool:
    r = redis_store.get_redis()
    u = int(r.get(redis_store.login_fail_key(username)) or 0)
    up = int(r.get(redis_store.login_fail_key(f"{username}|{ip}")) or 0)
    i = int(r.get(redis_store.login_fail_ip_key(ip)) or 0)
    return u >= USER_FAIL_LIMIT or up >= FAIL_LIMIT or i >= FAIL_LIMIT


def _clear_fails(username: str, ip: str) -> None:
    redis_store.get_redis().delete(
        redis_store.login_fail_key(username), redis_store.login_fail_key(f"{username}|{ip}"),
        redis_store.login_fail_ip_key(ip)
    )


def _canonical(username: str) -> str:
    """The stored spelling of a username: registration treats names case-insensitively, so login
    must too (phones capitalise the first letter), and the throttle must count every spelling as one account."""
    username = (username or "").strip()
    if db.get_account(username):
        return username
    ci = db.get_account_ci(username)
    return ci["username"] if ci else username


def authenticate(username: str, password: str, ip: str, otp: str | None = None) -> Account:
    """Return the Account on success; raise LockedOut, BadCredentials or MfaRequired otherwise.
    A wrong/reused/missing code is counted against the same lockout as a wrong password."""
    username = _canonical(username)
    if _is_locked(username, ip):
        raise LockedOut("too many failed attempts; try again later")
    acct = db.get_account(username)
    # A disabled account fails exactly like a wrong password (no account-status oracle).
    if not acct or acct.get("disabled") or not check_password(password, acct["password_hash"]):
        _record_fail(username, ip)
        raise BadCredentials("invalid username or password")
    if acct.get("totp_enabled"):
        if not otp:
            raise MfaRequired("two-factor code required")   # password OK; ask for the code (not a failure)
        step = totp.verify(acct["totp_secret"], otp, acct.get("totp_last_step") or 0)
        if step is None:
            _record_fail(username, ip)
            raise BadCredentials("invalid username, password or authentication code")
        db.set_account(username, totp_last_step=step)    # replay protection
    _clear_fails(username, ip)
    return Account.from_dict(acct)


def mfa_begin(username: str) -> str:
    """Start (or restart) enrolment: store a fresh secret, NOT yet enforced until confirmed."""
    secret = totp.new_secret()
    # Only touch totp_enabled when restarting an enrolled account: writing it bumps token_version and ends sessions.
    reset = {} if not (db.get_account(username) or {}).get("totp_enabled") else {"totp_enabled": 0}
    db.set_account(username, totp_secret=secret, totp_last_step=0, **reset)
    return secret


def mfa_confirm(username: str, code: str) -> None:
    acct = db.get_account(username)
    if not acct or not acct.get("totp_secret") or acct.get("totp_enabled"):
        raise AuthError("start two-factor setup first")
    step = totp.verify(acct["totp_secret"], code)
    if step is None:
        raise BadCredentials("that code is not right; check the time on your phone and try again")
    db.set_account(username, totp_enabled=1, totp_last_step=step)


def mfa_disable(username: str, password: str, code: str) -> None:
    acct = db.get_account(username)
    if not acct or not check_password(password, acct["password_hash"]):
        raise BadCredentials("current password is incorrect")
    if acct.get("totp_enabled") and totp.verify(acct["totp_secret"], code, acct.get("totp_last_step") or 0) is None:
        raise BadCredentials("that code is not right")
    db.set_account(username, totp_secret=None, totp_enabled=0, totp_last_step=0)


def mfa_reset(username: str) -> bool:
    """Admin recovery for a lost phone."""
    return db.set_account(username, totp_secret=None, totp_enabled=0, totp_last_step=0)


def _check_new_password(pw: str) -> None:
    if len(pw or "") < 8:
        raise AuthError("password must be at least 8 characters")
    if len(pw.encode()) > 72:   # bcrypt hard limit
        raise AuthError("password must be at most 72 bytes")


def change_password(username: str, current: str, new: str) -> None:
    """Self-service change: requires the current password."""
    acct = db.get_account(username)
    if not acct or not check_password(current, acct["password_hash"]):
        raise BadCredentials("current password is incorrect")
    _check_new_password(new)
    db.set_account(username, password_hash=hash_password(new), must_change_password=0)


def admin_reset_password(username: str, new: str) -> None:
    _check_new_password(new)
    if not db.set_account(username, password_hash=hash_password(new)):
        raise AuthError("no such account")


def default_password_accounts() -> list[str]:
    """Team accounts still on the seeded default password (deployment hygiene check)."""
    return [a["username"] for a in db.list_accounts()
            if a["role"] != "client" and (row := db.get_account(a["username"]))
            and check_password("changeme", row["password_hash"])]


if __name__ == "__main__":
    # Offline self-check for the throttle (the NFR-25 security control) using a tiny
    # in-memory Redis stand-in. bcrypt round-trip is checked only if the package is present.
    class FakeRedis:
        def __init__(self): self.d = {}
        def get(self, k): return self.d.get(k)
        def set(self, k, v, ex=None): self.d[k] = v
        def delete(self, *ks):
            for k in ks: self.d.pop(k, None)
        def incr(self, k):
            self.d[k] = int(self.d.get(k, 0)) + 1
            return self.d[k]
        def expire(self, k, s): pass

    redis_store._client = FakeRedis()
    db.reset_for_test(":memory:")

    # 5 failures against a missing account → 6th attempt is locked out.
    for _ in range(FAIL_LIMIT):
        try:
            authenticate("calvin", "wrong", "1.2.3.4")
        except BadCredentials:
            pass
    try:
        authenticate("calvin", "wrong", "1.2.3.4")
        raise SystemExit("FAIL: expected LockedOut after limit")
    except LockedOut:
        pass
    _clear_fails("calvin", "1.2.3.4")
    assert not _is_locked("calvin", "1.2.3.4"), "clear_fails did not reset lock"

    try:
        import bcrypt  # noqa: F401
        h = hash_password("s3cret")
        assert check_password("s3cret", h) and not check_password("nope", h), "bcrypt round-trip"
        print("auth.py self-check OK (throttle + bcrypt)")
    except ImportError:
        print("auth.py self-check OK (throttle; bcrypt not installed, skipped)")
