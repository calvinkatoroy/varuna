"""System administrator: the only role that provisions organizations, client users and staff."""
from __future__ import annotations

import re
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import audit
import auth
import db
import models
import redis_store
import tokens
from deps import require_sysadmin

router = APIRouter(prefix="/api/sysadmin")
_USERNAME = re.compile(r"[A-Za-z0-9._-]{3,32}")


def _temp_password() -> str:
    return secrets.token_urlsafe(12)


def _active_sysadmins() -> list[dict]:
    return [a for a in db.list_accounts() if a["role"] == models.ROLE_SYSADMIN and not a["disabled"]]


def _not_last_sysadmin(username: str) -> None:
    a = db.get_account(username)
    if a and a["role"] == models.ROLE_SYSADMIN and not a["disabled"] and len(_active_sysadmins()) <= 1:
        raise HTTPException(status_code=409, detail="at least one active system administrator is required")


class OrgBody(BaseModel):
    name: str


class AccountBody(BaseModel):
    username: str
    role: str
    org_id: str | None = None
    display_name: str | None = None
    email: str | None = None


class RoleBody(BaseModel):
    role: str


@router.get("/orgs")
def list_orgs(user: dict = Depends(require_sysadmin)):
    return db.list_orgs()


@router.post("/orgs")
def create_org(body: OrgBody, user: dict = Depends(require_sysadmin)):
    name = body.name.strip()
    if not 2 <= len(name) <= 120:
        raise HTTPException(status_code=422, detail="organization name must be 2-120 characters")
    try:
        oid = db.create_org(name)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="an organization with that name already exists")
    audit.log("org_created", actor=user["username"], org=oid)
    return {"id": oid, "name": name}


@router.post("/orgs/{org_id}/{action}")
def set_org(org_id: str, action: str, user: dict = Depends(require_sysadmin)):
    if action not in ("enable", "disable"):
        raise HTTPException(status_code=404)
    if not db.set_org_status(org_id, "active" if action == "enable" else "disabled"):
        raise HTTPException(status_code=404, detail="no such organization")
    if action == "disable":
        redis_store.drop_org_jobs(org_id)
    audit.log(f"org_{action}d", actor=user["username"], org=org_id)
    return {"ok": True}


@router.get("/accounts")
def list_accounts(user: dict = Depends(require_sysadmin)):
    return db.list_accounts()


@router.post("/accounts")
def create_account(body: AccountBody, user: dict = Depends(require_sysadmin)):
    if not _USERNAME.fullmatch(body.username) or body.username.lower().startswith("varuna-"):
        raise HTTPException(status_code=422, detail="username must be 3-32 letters, digits, dot, dash or underscore")
    if body.role not in models.ROLES:
        raise HTTPException(status_code=422, detail="unknown role")
    if (body.role == models.ROLE_CLIENT) != bool(body.org_id):
        raise HTTPException(status_code=422, detail="clients need an organization; staff must not have one")
    if body.org_id and not (db.get_org(body.org_id) or {}).get("status") == "active":
        raise HTTPException(status_code=422, detail="organization does not exist or is disabled")
    if db.get_account_ci(body.username):
        raise HTTPException(status_code=409, detail="username already taken")
    try:
        email = auth._clean_email(body.email or "") or None
    except auth.AuthError as e:
        raise HTTPException(status_code=422, detail=str(e))
    pw = _temp_password()
    auth.create_account(body.username, pw, body.role, org_id=body.org_id)
    db.set_account(body.username, must_change_password=1, display_name=body.display_name, email=email)
    audit.log("account_created", actor=user["username"], account=body.username, role=body.role, org=body.org_id)
    return {"username": body.username, "role": body.role, "temp_password": pw}


@router.post("/accounts/{username}/reset-password")
def reset_password(username: str, user: dict = Depends(require_sysadmin)):
    pw = _temp_password()
    try:
        auth.admin_reset_password(username, pw)
    except auth.AuthError:
        raise HTTPException(status_code=404, detail="no such account")
    db.set_account(username, must_change_password=1)
    audit.log("password_reset", actor=user["username"], account=username)
    return {"temp_password": pw}


@router.post("/accounts/{username}/reset-mfa")
def reset_mfa(username: str, user: dict = Depends(require_sysadmin)):
    if not auth.mfa_reset(username):
        raise HTTPException(status_code=404, detail="no such account")
    audit.log("mfa_reset", actor=user["username"], account=username)
    return {"ok": True}


@router.post("/accounts/{username}/{action}")
def set_disabled(username: str, action: str, user: dict = Depends(require_sysadmin)):
    if action not in ("enable", "disable"):
        raise HTTPException(status_code=404)
    if action == "disable":
        if username == user["username"]:
            raise HTTPException(status_code=409, detail="you cannot disable your own account")
        _not_last_sysadmin(username)
    if not db.set_account(username, disabled=1 if action == "disable" else 0):
        raise HTTPException(status_code=404, detail="no such account")
    if action == "disable":
        tokens.revoke_agent(username)
    audit.log(f"account_{action}d", actor=user["username"], account=username)
    return {"ok": True}


@router.put("/accounts/{username}/role")
def set_role(username: str, body: RoleBody, user: dict = Depends(require_sysadmin)):
    a = db.get_account(username)
    if not a:
        raise HTTPException(status_code=404, detail="no such account")
    if models.ROLE_CLIENT in (a["role"], body.role) or body.role not in models.ROLES:
        raise HTTPException(status_code=422, detail="only staff roles can be changed here")
    if username == user["username"]:
        raise HTTPException(status_code=409, detail="you cannot change your own role")
    _not_last_sysadmin(username)
    db.set_account(username, role=body.role)
    audit.log("role_changed", actor=user["username"], account=username, role=body.role)
    return {"ok": True}
