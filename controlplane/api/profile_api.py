"""Self-service profile, shared by the public and private planes."""
from __future__ import annotations

import hashlib
import os
import secrets
import threading
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import audit
import auth
import db
import mailer
from deps import current_user

router = APIRouter(prefix="/api/profile")
EMAIL_TTL = 1800


class ProfileBody(BaseModel):   # only these two keys; role/org/username/email and unknown keys are ignored
    display_name: str | None = None
    phone: str | None = None


class EmailBody(BaseModel):
    email: str


class ConfirmBody(BaseModel):
    token: str


def _clean(v: str) -> str:
    return "".join(c for c in v if c.isprintable()).strip()[:120]


@router.get("")
def get_profile(user: dict = Depends(current_user)):
    a = db.get_account(user["username"])
    org = db.get_org(a["org_id"]) if a["org_id"] else None
    return {"username": a["username"], "role": a["role"], "org_name": org["name"] if org else None,
            "display_name": a["display_name"], "email": a["email"], "phone": a["phone"],
            "totp_enabled": bool(a["totp_enabled"])}


@router.put("")
def update_profile(body: ProfileBody, user: dict = Depends(current_user)):
    fields = {k: _clean(v) for k, v in body.model_dump().items() if v is not None}
    if fields:
        db.set_account(user["username"], **fields)
        audit.log("profile_updated", actor=user["username"], fields=sorted(fields))
    return {"ok": True}


@router.post("/email")
def request_email_change(body: EmailBody, user: dict = Depends(current_user)):
    try:
        email = auth._clean_email(body.email)
    except auth.AuthError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not email:
        raise HTTPException(status_code=422, detail="email required")
    token = secrets.token_urlsafe(32)
    db.add_email_change(hashlib.sha256(token.encode()).hexdigest(), user["username"], email, int(time.time()) + EMAIL_TTL)
    public = os.environ.get("VARUNA_PUBLIC_URL") or "http://localhost:5173"
    base = ((os.environ.get("VARUNA_TEAM_URL") or public) if user["role"] != "client" else public).rstrip("/")
    text = (f"Open this link within 30 minutes to confirm this address for your Varuna account:\n\n"
            f"{base}/confirm-email?token={token}\n\nIf this wasn't you, ignore this email.\n")
    threading.Thread(target=mailer.send, args=(email, "Confirm your Varuna email", text), daemon=True).start()
    audit.log("email_change_requested", actor=user["username"])
    return {"ok": True, "emailed": mailer.enabled()}


@router.post("/email/confirm")
def confirm_email(body: ConfirmBody, user: dict = Depends(current_user)):
    got = db.claim_email_change(hashlib.sha256(body.token.encode()).hexdigest(), int(time.time()))
    if not got or got[0] != user["username"]:
        raise HTTPException(status_code=422, detail="this confirmation link is invalid or has expired")
    db.set_account(user["username"], email=got[1])
    audit.log("email_changed", actor=user["username"])
    return {"ok": True}
