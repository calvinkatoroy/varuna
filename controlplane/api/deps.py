"""Shared FastAPI auth dependencies for the browser-facing APIs (JWT).

Used by both the public-plane API (browser.py) and the private-plane API (private_api.py),
so the JWT check and the Pro role gate live in one place.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))

from fastapi import Depends, Header, HTTPException  # noqa: E402

import jwt_auth  # noqa: E402
import models  # noqa: E402


def current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return jwt_auth.verify(token)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid or expired token")


def require_team(user: dict = Depends(current_user)) -> dict:
    """Any security-team role (v2: pentester/lead/reporter/governance/soc). Clients are denied."""
    if not models.is_team(user["role"]):
        raise HTTPException(status_code=403, detail="security team role required")
    return user


# Back-compat alias: v1 endpoints imported require_pro for team-only gating.
require_pro = require_team


def require_lead(user: dict = Depends(current_user)) -> dict:
    """Only the lead pentester approves/rejects proposals (v2)."""
    if not models.can_approve(user["role"]):
        raise HTTPException(status_code=403, detail="lead pentester role required")
    return user
