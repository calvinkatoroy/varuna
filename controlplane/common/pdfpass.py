"""The persistent PDF password of a task's report: generated once, stored sealed (Fernet), never logged."""
from __future__ import annotations

import base64
import hashlib
import os
import secrets

from cryptography.fernet import Fernet

import db
import jwt_auth

PREFIX = "enc1:"


def _fernet() -> Fernet:
    material = (os.environ.get("VARUNA_SECRET_KEY") or jwt_auth.JWT_SECRET).encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"varuna-pdf-password|" + material).digest()))


def seal(password: str) -> str:
    return PREFIX + _fernet().encrypt(password.encode()).decode()


def unseal(stored: str) -> str:
    """A value without the prefix is a legacy plaintext password and reads as it is."""
    return _fernet().decrypt(stored[len(PREFIX):].encode()).decode() if stored.startswith(PREFIX) else stored


def ensure(report_id: str) -> str:
    """The report's password in clear, creating it on first use. Concurrent first calls agree on one value."""
    r = db.get_report(report_id, org_id=None)
    if not r["pdf_password"]:
        db.set_report_password_if_empty(report_id, seal(secrets.token_urlsafe(12)))
        r = db.get_report(report_id, org_id=None)
    return unseal(r["pdf_password"])
