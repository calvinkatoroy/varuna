"""Shared FastAPI auth dependencies for the browser-facing APIs (JWT).

Used by both the public-plane API (browser.py) and the private-plane API (private_api.py),
so the JWT check and the Pro role gate live in one place.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))

from fastapi import Depends, Header, HTTPException  # noqa: E402

import db  # noqa: E402
import jwt_auth  # noqa: E402
import models  # noqa: E402


def current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    try:
        user = jwt_auth.verify(token)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    # Tokens outlive an account being disabled by up to their TTL: re-check on every request.
    acct = db.get_account(user["username"])
    if acct and acct.get("disabled"):
        raise HTTPException(status_code=401, detail="account disabled")
    return user


def mfa_required() -> bool:
    """Read per call so the policy can be flipped (and tested) without a restart."""
    return os.environ.get("VARUNA_REQUIRE_MFA", "").lower() in ("1", "true", "yes")


def require_team_setup(user: dict = Depends(current_user)) -> dict:
    """Team role only, WITHOUT the two-factor gate: for the endpoints a member needs in order to enrol."""
    if not models.is_team(user["role"]):
        raise HTTPException(status_code=403, detail="security team role required")
    return user


def require_team(user: dict = Depends(require_team_setup)) -> dict:
    """Any security-team role (v2: pentester/lead/reporter/governance/soc). Clients are denied.
    With VARUNA_REQUIRE_MFA on, a member who has not enrolled two-factor can do nothing else."""
    if mfa_required() and not (db.get_account(user["username"]) or {}).get("totp_enabled"):
        raise HTTPException(status_code=403, detail="mfa_enrolment_required")
    return user


# Back-compat alias: v1 endpoints imported require_pro for team-only gating.
require_pro = require_team


def require_lead(user: dict = Depends(current_user)) -> dict:
    """Only the lead pentester approves/rejects proposals (v2)."""
    if not models.can_approve(user["role"]):
        raise HTTPException(status_code=403, detail="lead pentester role required")
    return user
