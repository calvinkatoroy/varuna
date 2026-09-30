"""TOTP (RFC 6238) for team-account two-factor login. Stdlib only: no extra dependency.

30-second steps, 6 digits, HMAC-SHA1: what Google Authenticator, Microsoft Authenticator, Authy
and 1Password all expect. Accepts the current step and one either side (clock drift), and refuses
to accept the same step twice so a code sniffed over a shoulder cannot be replayed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP = 30
DIGITS = 6
WINDOW = 1   # accept +-1 step of clock drift


def new_secret() -> str:
    """160-bit random secret, base32 without padding (what authenticator apps show/expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    num = (struct.unpack(">I", digest[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITS)
    return str(num).zfill(DIGITS)


def code_at(secret: str, at: float | None = None) -> str:
    return _hotp(secret, int((time.time() if at is None else at) // STEP))


def verify(secret: str, code: str, last_step: int = 0, at: float | None = None) -> int | None:
    """Return the matching time step (store it as the new last_step), or None if the code is
    wrong or that step was already used."""
    code = (code or "").strip().replace(" ", "")
    if not (code.isdigit() and len(code) == DIGITS):
        return None
    now_step = int((time.time() if at is None else at) // STEP)
    for step in range(now_step - WINDOW, now_step + WINDOW + 1):
        if step > last_step and hmac.compare_digest(_hotp(secret, step), code):
            return step
    return None


def otpauth_uri(username: str, secret: str, issuer: str = "Varuna") -> str:
    return (f"otpauth://totp/{quote(issuer)}:{quote(username)}?secret={secret}"
            f"&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={STEP}")


if __name__ == "__main__":
    # RFC 6238 Appendix B test vector (SHA1, secret "12345678901234567890"), 6-digit truncation.
    rfc = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    assert code_at(rfc, 59) == "287082" and code_at(rfc, 1111111109) == "081804"
    assert code_at(rfc, 1234567890) == "005924"
    s = new_secret()
    step = verify(s, code_at(s))
    assert step and verify(s, code_at(s), last_step=step) is None, "same step must not verify twice"
    print("totp.py self-check OK")
