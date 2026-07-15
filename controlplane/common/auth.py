"""Authentication + login brute-force throttle (SRS NFR-22, NFR-25, REQ-65..70).

Passwords are bcrypt-hashed (NFR-22). The public-plane login is internet-facing in
front of a tool that launches attacks, so failed logins are rate-limited per-account
AND per-source-IP with a temporary lockout (NFR-25) — this is not optional hardening.

`bcrypt` is imported lazily so the throttle logic stays testable without the package.
"""
from __future__ import annotations

import redis_store
from models import Account, ROLES

FAIL_LIMIT = 5          # lock after this many failures in the window
FAIL_WINDOW = 900       # seconds (15 min)


class AuthError(Exception):
    pass


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


def create_account(username: str, password: str, role: str) -> Account:
    """Provision an account (REQ-69: no self-registration; a Pro user calls this)."""
    if role not in ROLES:
        raise ValueError(f"invalid role: {role}")
    acct = Account(username=username, password_hash=hash_password(password), role=role)
    redis_store.set_account(acct.to_dict())
    return acct


def _record_fail(username: str, ip: str) -> None:
    r = redis_store.get_redis()
    for key in (redis_store.login_fail_key(username), redis_store.login_fail_ip_key(ip)):
        if r.incr(key) == 1:
            r.expire(key, FAIL_WINDOW)


def _is_locked(username: str, ip: str) -> bool:
    r = redis_store.get_redis()
    u = int(r.get(redis_store.login_fail_key(username)) or 0)
    i = int(r.get(redis_store.login_fail_ip_key(ip)) or 0)
    return u >= FAIL_LIMIT or i >= FAIL_LIMIT


def _clear_fails(username: str, ip: str) -> None:
    redis_store.get_redis().delete(
        redis_store.login_fail_key(username), redis_store.login_fail_ip_key(ip)
    )


def authenticate(username: str, password: str, ip: str) -> Account:
    """Return the Account on success; raise LockedOut or BadCredentials otherwise."""
    if _is_locked(username, ip):
        raise LockedOut("too many failed attempts; try again later")
    acct = redis_store.get_account(username)
    if not acct or not check_password(password, acct["password_hash"]):
        _record_fail(username, ip)
        raise BadCredentials("invalid username or password")
    _clear_fails(username, ip)
    return Account.from_dict(acct)


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
