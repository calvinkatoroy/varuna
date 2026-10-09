"""Agent tokens + job-ownership checks (SRS NFR-23, NFR-26, REQ-73, REQ-74).

Two token kinds:
  - Enrollment token: one-time, short-TTL, binds an enrollment attempt to an account.
    Generated when a user starts Install Agent (Phase D UI); consumed by POST /agent/enroll.
  - Bearer (agent) token: persistent (no TTL, C-5/REQ-73). Stored server-side ONLY as a
    SHA-256 hash, never the raw token, and reverse-indexed for O(1) verification.
    Revocable by a Pro user (NFR-26).

Ownership (NFR-26): a job may only be read/written by the agent of the account that
submitted it. Lives in common/ because both the api and the ui import it (enroll-token
generation and revocation are UI actions; verification is an api action).
"""
from __future__ import annotations

import datetime
import hashlib
import secrets

import db
import models
import redis_store

ENROLL_TTL = 3600   # one-time enrollment token lifetime (seconds)
STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def generate_enrollment_token(username: str) -> str:
    token = secrets.token_urlsafe(32)
    redis_store.get_redis().set(redis_store.enroll_token_key(token), username, ex=ENROLL_TTL)
    return token


def consume_enrollment_token(token: str) -> str | None:
    """Return the bound username and burn the token (one-time)."""
    r = redis_store.get_redis()
    key = redis_store.enroll_token_key(token)
    username = r.get(key)
    if username:
        r.delete(key)
    return username


def issue_agent_token(username: str) -> str:
    """Bind a fresh bearer token to an account; return the raw token once.

    Any prior binding for this account is revoked first, so re-enrollment (a new
    machine) leaves no orphaned reverse-index key behind.
    """
    revoke_agent(username)   # clear a previous binding before issuing a new one
    token = secrets.token_urlsafe(32)
    th = _hash(token)
    org_id = (db.get_account(username) or {}).get("org_id")   # dispatch refuses jobs of any other org
    redis_store.set_agent(username, {"status": STATUS_ONLINE, "last_seen": _now(), "token_hash": th, "org_id": org_id})
    redis_store.get_redis().set(redis_store.agent_token_key(th), username)
    return token


def verify_agent_token(token: str) -> str | None:
    """Return the owning username for a valid, non-revoked token, else None."""
    if not token:
        return None
    th = _hash(token)
    username = redis_store.get_redis().get(redis_store.agent_token_key(th))
    if not username:
        return None
    agent = redis_store.get_agent(username)
    if not agent or agent.get("token_hash") != th:   # binding revoked/rotated
        return None
    return username


def revoke_agent(username: str) -> None:
    """Invalidate an account's agent (NFR-26). Next poll/upload with it is rejected."""
    agent = redis_store.get_agent(username)
    if agent and agent.get("token_hash"):
        redis_store.get_redis().delete(redis_store.agent_token_key(agent["token_hash"]))
    redis_store.get_redis().delete(redis_store.agent_key(username))


def agent_allowed(username: str) -> bool:
    """May this account's agent still work? Its account must exist and be enabled, and its org (if
    any) active. Varuna's own cloud scanner belongs to no account and is always allowed."""
    if username == models.CLOUD_AGENT:
        return True
    acct = db.get_account(username)
    if not acct or acct["disabled"]:
        return False
    if acct["org_id"]:
        org = db.get_org(acct["org_id"])
        return bool(org and org["status"] == "active")
    return True


def touch_agent(username: str) -> None:
    """Refresh liveness on poll/heartbeat (REQ-75)."""
    agent = redis_store.get_agent(username) or {}
    agent["status"] = STATUS_ONLINE
    agent["last_seen"] = _now()
    redis_store.set_agent(username, agent)


ONLINE_THRESHOLD = 30   # seconds since last poll/heartbeat to still count as online (REQ-75)


def is_online(username: str, now: datetime.datetime | None = None) -> bool:
    """Liveness derived from last_seen freshness, not a static flag (REQ-75)."""
    agent = redis_store.get_agent(username)
    if not agent or not agent.get("last_seen"):
        return False
    try:
        seen = datetime.datetime.fromisoformat(agent["last_seen"])
    except (ValueError, TypeError):
        return False
    now = now or datetime.datetime.now(datetime.UTC)
    return (now - seen).total_seconds() <= ONLINE_THRESHOLD


def offline_seconds(username: str, now: datetime.datetime | None = None) -> float | None:
    """Seconds since the agent last checked in; None if it never has (or the stamp is unreadable)."""
    agent = redis_store.get_agent(username)
    try:
        seen = datetime.datetime.fromisoformat((agent or {}).get("last_seen") or "")
    except (ValueError, TypeError):
        return None
    return ((now or datetime.datetime.now(datetime.UTC)) - seen).total_seconds()


def owns_job(username: str, job: dict | None) -> bool:
    return bool(job) and username in (job.get("submitter"), job.get("executor"))
