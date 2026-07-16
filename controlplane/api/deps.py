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


def require_pro(user: dict = Depends(current_user)) -> dict:
    if user["role"] != models.ROLE_PRO:
        raise HTTPException(status_code=403, detail="pro role required")
    return user
