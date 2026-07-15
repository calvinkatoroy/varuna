"""Append-only audit log (SRS NFR-27, DAT-4).

Records the accountability-relevant events — scan submissions, approval decisions,
agent enrollment/revocation, and the offboarding wipe — to a Redis list with no TTL,
so the record survives the 24h expiry of the scan data it refers to. This is what
makes the per-user agent model's accountability (§4.12) actually durable.
"""
from __future__ import annotations

import datetime
import json

import redis_store

# Event types.
SUBMIT = "submit"
APPROVE = "approve"
REJECT = "reject"
ENROLL = "enroll"
REVOKE = "revoke"
WIPE = "wipe"


def log(event_type: str, **fields) -> dict:
    entry = {
        "type": event_type,
        "ts": datetime.datetime.now(datetime.UTC).isoformat(),
        **fields,
    }
    redis_store.audit_append(entry)
    return entry


def read_all() -> list[dict]:
    r = redis_store.get_redis()
    return [json.loads(x) for x in r.lrange(redis_store.AUDIT_KEY, 0, -1)]


if __name__ == "__main__":
    class FakeRedis:
        def __init__(self): self.lists = {}
        def rpush(self, k, v): self.lists.setdefault(k, []).append(v)
        def lrange(self, k, a, b): return self.lists.get(k, [])[a: (None if b == -1 else b + 1)]

    redis_store._client = FakeRedis()

    log(SUBMIT, submitter="calvin", target="http://t.local", target_class="local")
    log(APPROVE, approver="ihsan", job="abc", reason="ok")
    entries = read_all()
    assert len(entries) == 2, "audit did not append"
    assert entries[0]["type"] == SUBMIT and "ts" in entries[0], "missing type/ts"
    assert entries[1]["approver"] == "ihsan", "fields not stored"
    print("audit.py self-check OK")
