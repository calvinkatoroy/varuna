"""The persistent PDF password of a task's report: generated once, stored sealed (Fernet), never logged.

Keys: VARUNA_SECRET_KEY seals; it and VARUNA_SECRET_KEY_OLD (comma separated, previous keys) open; the key derived
from JWT_SECRET comes last so values sealed before VARUNA_SECRET_KEY existed still open. Losing every key that sealed
a password makes it unreadable, so the key is backed up with the database."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

import db
import jwt_auth

PREFIX = "enc1:"
DEV_KEY = "dev-only-change-me"
UNREADABLE = "The report password cannot be read; contact your administrator."
NO_KEY = "The report password key is not configured; contact your administrator."
log = logging.getLogger("varuna.pdfpass")


class Unavailable(Exception):
    """The password cannot be sealed or opened with the configured keys. str(e) is safe to show."""


def _materials() -> list[str]:
    env = os.environ
    raw = [env.get("VARUNA_SECRET_KEY", ""), *env.get("VARUNA_SECRET_KEY_OLD", "").split(","), jwt_auth.JWT_SECRET]
    out: list[str] = []
    for m in (k.strip() for k in raw):
        if m and m not in out:
            out.append(m)
    return out


def _fernet(material: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"varuna-pdf-password|" + material.encode()).digest()))


def seal(password: str) -> str:
    keys = _materials()
    if keys[0] == DEV_KEY and os.environ.get("VARUNA_ALLOW_DEV_KEY") != "1":
        log.error("refusing to seal a report password with the public default key: set VARUNA_SECRET_KEY (or JWT_SECRET)")
        raise Unavailable(NO_KEY)
    return PREFIX + _fernet(keys[0]).encrypt(password.encode()).decode()


def unseal(stored: str) -> str:
    """A value without the prefix is a legacy plaintext password and reads as it is."""
    if not stored.startswith(PREFIX):
        return stored
    try:
        return MultiFernet([_fernet(m) for m in _materials()]).decrypt(stored[len(PREFIX):].encode()).decode()
    except InvalidToken:
        log.error("a stored report password cannot be decrypted: none of VARUNA_SECRET_KEY, VARUNA_SECRET_KEY_OLD or "
                  "the JWT_SECRET key opens it (key lost or rotated without keeping the old one?)")
        raise Unavailable(UNREADABLE) from None


def check_sealed() -> None:
    """Startup: if passwords are stored but none opens with the configured keys, say so loudly (does not stop the app)."""
    rows = db.get_conn().execute("SELECT pdf_password FROM reports WHERE pdf_password LIKE ?", (PREFIX + "%",)).fetchall()
    if not rows:
        return
    for r in rows:
        try:
            unseal(r[0])
            return
        except Unavailable:
            pass
    log.warning("WARNING: %d stored report password(s) cannot be opened with the configured keys. Set VARUNA_SECRET_KEY to "
                "the key they were sealed with (or put it in VARUNA_SECRET_KEY_OLD). Clients cannot read these "
                "passwords and new PDFs fail until then.", len(rows))


def ensure(report_id: str) -> str:
    """The report's password in clear, creating it on first use. Concurrent first calls agree on one value."""
    r = db.get_report(report_id, org_id=None)
    if not r["pdf_password"]:
        db.set_report_password_if_empty(report_id, seal(secrets.token_urlsafe(12)))
        r = db.get_report(report_id, org_id=None)
    return unseal(r["pdf_password"])
