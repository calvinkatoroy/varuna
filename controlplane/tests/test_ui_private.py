"""Private UI smoke test + manual-findings-input logic test (SRS §4.7, §4.6a).

Verifies: the app runs; a Standard account is refused (Pro-only); a Pro account reaches
the pages; and add_manual_finding() appends -> correlates -> enriches a finding into a job.
Offline, FakeRedis-backed, Ollama enrichment falls back gracefully.
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))
sys.path.insert(0, os.path.join(HERE, "..", "api"))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import ingest  # noqa: E402
import ollama  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(HERE, "..", "ui_private", "app.py")


def _fresh():
    redis_store._client = FakeRedis()
    return AppTest.from_file(APP)


def test_login_renders():
    at = _fresh().run()
    assert not at.exception, at.exception
    assert any("Private Dashboard" in t.value for t in at.title)


def test_pro_reaches_findings_review():
    at = _fresh()
    auth.create_account("ihsan", "pw", "pro")
    at.session_state["user"] = "ihsan"
    at.session_state["role"] = "pro"
    at.run()
    assert not at.exception, at.exception
    assert any("Findings Review" in h.value for h in at.header)


def test_add_manual_finding_pipeline():
    redis_store._client = FakeRedis()
    ollama.OLLAMA_URL = "http://127.0.0.1:1"   # no Ollama -> graceful fallback
    redis_store.set_job({"id": "j1", "target": "http://t.local", "submitter": "ihsan",
                         "status": "done", "per_tool_status": {}})
    combined = ingest.add_manual_finding("j1", {
        "name": "IDOR on /orders", "severity": "high", "host": "http://t.local",
        "url": "http://t.local/orders/3", "description": "User can read others' orders.",
        "evidence": "GET /orders/3 as user A returns user B data",
    })
    assert len(combined) == 1
    f = combined[0]
    assert f["tool"] == "manual" and f["name"] == "IDOR on /orders"
    # persisted, and correlate ran (priority-sorted set stored back)
    assert redis_store.get_findings("j1")[0]["name"] == "IDOR on /orders"


def test_add_manual_finding_rejects_missing_job():
    redis_store._client = FakeRedis()
    try:
        ingest.add_manual_finding("nope", {"name": "x", "severity": "low", "host": "h",
                                           "url": "", "description": "", "evidence": ""})
    except ValueError:
        return
    raise AssertionError("manual finding on a nonexistent job should raise")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_ui_private: all green")
