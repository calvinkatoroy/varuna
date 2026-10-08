"""Shared FastAPI auth dependencies for the browser-facing APIs (JWT).

Used by both the public-plane API (browser.py) and the private-plane API (private_api.py),
so the JWT check and the Pro role gate live in one place.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))

from fastapi import Depends, Header, HTTPException, Request  # noqa: E402

import db  # noqa: E402
import jwt_auth  # noqa: E402
import models  # noqa: E402


_PASSWORD_CHANGE_OK = ("/api/password", "/api/me", "/api/refresh")


def current_user(request: Request, authorization: str = Header(default="")) -> dict:
    """Identity is rebuilt from the DB on every request; the token only proves a still-current session."""
    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = jwt_auth.verify(token)
    except Exception:
        raise HTTPException(status_code=401, detail="session ended")
    acct = db.get_account(claims["username"])
    if not acct or acct["disabled"] or acct["token_version"] != claims["tv"]:
        raise HTTPException(status_code=401, detail="session ended")
    if acct["org_id"]:
        org = db.get_org(acct["org_id"])
        if not org or org["status"] != "active":
            raise HTTPException(status_code=401, detail="session ended")
    if acct["must_change_password"] and request.url.path not in _PASSWORD_CHANGE_OK:
        raise HTTPException(status_code=403, detail="password_change_required")
    return {"username": acct["username"], "role": acct["role"], "org_id": acct["org_id"],
            "must_change_password": bool(acct["must_change_password"])}


def scope(user: dict = Depends(current_user)):
    import tenancy   # lazy import, per the task-4 plan
    try:
        return tenancy.scope_for(user)
    except PermissionError:
        raise HTTPException(status_code=403, detail="no access to tenant data")


def require_sysadmin(user: dict = Depends(current_user)) -> dict:
    if not models.is_sysadmin(user["role"]):
        raise HTTPException(status_code=403, detail="system administrator required")
    if mfa_required() and not (db.get_account(user["username"]) or {}).get("totp_enabled"):
        raise HTTPException(status_code=403, detail="mfa_enrolment_required")
    return user


def mfa_required() -> bool:
    """Read per call so the policy can be flipped (and tested) without a restart."""
    return os.environ.get("VARUNA_REQUIRE_MFA", "").lower() in ("1", "true", "yes")


def require_team_setup(user: dict = Depends(current_user)) -> dict:
    """Team role only, WITHOUT the two-factor gate: for the endpoints a member needs in order to enrol."""
    if not models.is_team(user["role"]):
        raise HTTPException(status_code=403, detail="security team role required")
    return user


def require_staff_setup(user: dict = Depends(current_user)) -> dict:
    """Team role or sysadmin, WITHOUT the two-factor gate: password and 2FA enrolment endpoints only."""
    if not (models.is_team(user["role"]) or models.is_sysadmin(user["role"])):
        raise HTTPException(status_code=403, detail="staff role required")
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
