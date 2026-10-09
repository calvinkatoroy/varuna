"""Self-issued JWT sessions for the browser API (SRS C-6, NFR-22, NFR-25).

The browser logs in once (username/password), gets a short-lived signed JWT, and sends it
as a bearer token on every subsequent request. Credentials are still checked by auth.py
(bcrypt + the NFR-25 login throttle); this module only mints/verifies the token on top.

No corporate SSO or paid identity provider (all free, self-hosted). HS256 with a secret from
the environment. Set JWT_SECRET in production; the default is for local dev only.
"""
from __future__ import annotations

import datetime
import os

import jwt   # PyJWT

import auth
import db

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-change-me")
JWT_ALG = "HS256"
JWT_TTL = int(os.environ.get("JWT_TTL_SECONDS") or "3600")   # 1h session


def issue(username: str) -> str:
    """Mint a JWT for an existing account, stamped with its current token_version."""
    acct = db.get_account(username)
    now = datetime.datetime.now(datetime.UTC)
    return jwt.encode({"sub": username, "role": acct["role"], "tv": acct["token_version"], "iat": now,
                       "exp": now + datetime.timedelta(seconds=JWT_TTL)}, JWT_SECRET, algorithm=JWT_ALG)


def login(username: str, password: str, ip: str, otp: str | None = None) -> str:
    """Verify credentials (bcrypt + throttle) and return a signed JWT. Raises on failure."""
    acct = auth.authenticate(username, password, ip, otp)   # BadCredentials / LockedOut / MfaRequired propagate
    return issue(acct.username)


def verify(token: str) -> dict:
    """Return {username, role, tv} for a valid, unexpired token; raise jwt exceptions otherwise."""
    data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    return {"username": data["sub"], "role": data["role"], "tv": data.get("tv", -1)}
