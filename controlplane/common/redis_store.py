"""Single point of Redis access for the control plane.

Every key name is built here, so the schema lives in one place
(IMPLEMENTATION-PLAN §4). TTL policy (SRS C-5, NFR-27):
  - job / findings / raw / approval : SCAN_TTL_SECONDS (24h)
  - account / agent / audit         : no TTL (persist via Redis AOF)

`redis` is imported lazily inside get_redis() so the pure key-builder functions
below stay importable (and unit-testable) without the package or a live server.
"""
from __future__ import annotations

import json
import os
from typing import Optional

SCAN_TTL_SECONDS = int(os.environ.get("SCAN_TTL_SECONDS", "86400"))


# --- key builders (pure; no connection needed) ---
def job_key(job_id: str) -> str: return f"job:{job_id}"
def findings_key(job_id: str) -> str: return f"findings:{job_id}"
def raw_key(job_id: str) -> str: return f"raw:{job_id}"
def approval_key(job_id: str) -> str: return f"approval:{job_id}"
def account_key(username: str) -> str: return f"account:{username}"
def agent_key(username: str) -> str: return f"agent:{username}"
def agent_token_key(token_hash: str) -> str: return f"agent_token:{token_hash}"  # reverse index
def enroll_token_key(token: str) -> str: return f"enroll:{token}"
def agentqueue_key(username: str) -> str: return f"agentqueue:{username}"
def login_fail_key(username: str) -> str: return f"login_fail:{username}"
def login_fail_ip_key(ip: str) -> str: return f"login_fail_ip:{ip}"

AUDIT_KEY = "audit"


# --- connection (lazy singleton) ---
_client = None


def get_redis():
    global _client
    if _client is None:
        import redis  # lazy: keeps key builders importable without the package
        _client = redis.from_url(
            os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
        )
    return _client


# --- scan data (24h TTL) ---
def set_job(job: dict) -> None:
    get_redis().set(job_key(job["id"]), json.dumps(job), ex=SCAN_TTL_SECONDS)


def get_job(job_id: str) -> Optional[dict]:
    v = get_redis().get(job_key(job_id))
    return json.loads(v) if v else None


def set_findings(job_id: str, findings: list) -> None:
    get_redis().set(findings_key(job_id), json.dumps(findings), ex=SCAN_TTL_SECONDS)


def get_findings(job_id: str) -> list:
    v = get_redis().get(findings_key(job_id))
    return json.loads(v) if v else []


def set_raw(job_id: str, raw: dict) -> None:
    get_redis().set(raw_key(job_id), json.dumps(raw), ex=SCAN_TTL_SECONDS)


def set_approval(job_id: str, entry: dict) -> None:
    get_redis().set(approval_key(job_id), json.dumps(entry), ex=SCAN_TTL_SECONDS)


def get_approval(job_id: str) -> Optional[dict]:
    v = get_redis().get(approval_key(job_id))
    return json.loads(v) if v else None


# --- pending-approval index (so the Approval Queue lists without scanning all keys) ---
APPROVAL_PENDING_KEY = "approval_pending"


def add_pending_approval(job_id: str) -> None:
    get_redis().sadd(APPROVAL_PENDING_KEY, job_id)


def remove_pending_approval(job_id: str) -> None:
    get_redis().srem(APPROVAL_PENDING_KEY, job_id)


def list_pending_approvals() -> list:
    return list(get_redis().smembers(APPROVAL_PENDING_KEY))


# --- persistent data (no TTL) ---
def set_account(acct: dict) -> None:
    get_redis().set(account_key(acct["username"]), json.dumps(acct))


def get_account(username: str) -> Optional[dict]:
    v = get_redis().get(account_key(username))
    return json.loads(v) if v else None


def set_agent(username: str, data: dict) -> None:
    get_redis().set(agent_key(username), json.dumps(data))


def get_agent(username: str) -> Optional[dict]:
    v = get_redis().get(agent_key(username))
    return json.loads(v) if v else None


# --- per-user dispatch queue (agent polls its own queue; REQ-74) ---
def enqueue_job(username: str, job_id: str) -> None:
    get_redis().lpush(agentqueue_key(username), job_id)


def dequeue_job(username: str) -> Optional[str]:
    # ponytail: RPOP loses a job if the agent dies mid-scan; add an in-flight list
    # only if that failure mode ever bites (one scan per agent, C-5/TBD-3, makes it rare).
    return get_redis().rpop(agentqueue_key(username))


# --- audit log (append-only, no TTL, NFR-27) ---
def audit_append(entry: dict) -> None:
    get_redis().rpush(AUDIT_KEY, json.dumps(entry))


# --- offboarding wipe (NFR-28) ---
def _scan_delete(pattern: str) -> int:
    r = get_redis()
    keys = list(r.scan_iter(match=pattern))
    if keys:
        r.delete(*keys)
    return len(keys)


def wipe_scan_data() -> dict:
    """Delete all job/findings/raw/approval keys and the pending-approval index (NFR-28)."""
    counts = {p: _scan_delete(f"{p}:*") for p in ("job", "findings", "raw", "approval")}
    get_redis().delete(APPROVAL_PENDING_KEY)
    return counts


def wipe_audit() -> None:
    """Clear the audit log. Only ever called by the deliberate offboarding wipe (DAT-4)."""
    get_redis().delete(AUDIT_KEY)


if __name__ == "__main__":
    # Self-check for the pure key builders (no Redis needed).
    assert job_key("x") == "job:x"
    assert findings_key("x") == "findings:x"
    assert approval_key("x") == "approval:x"
    assert account_key("calvin") == "account:calvin"
    assert agent_key("calvin") == "agent:calvin"
    assert login_fail_key("calvin") == "login_fail:calvin"
    assert AUDIT_KEY == "audit"
    print("redis_store.py key-builder self-check OK")
