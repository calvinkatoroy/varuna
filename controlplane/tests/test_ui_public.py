"""Smoke test for the public UI via Streamlit's headless AppTest.

Verifies the app runs without exception and routes correctly: logged-out shows the login
title; a logged-in account with no agent is forced to Install Agent (REQ-71); with an agent
it reaches the scan pages. Offline, FakeRedis-backed.
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import auth  # noqa: E402
import tokens  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(HERE, "..", "ui_public", "app.py")


def _fresh():
    redis_store._client = FakeRedis()
    return AppTest.from_file(APP)


def test_logged_out_shows_login():
    at = _fresh().run()
    assert not at.exception, at.exception
    assert any("Varuna" in t.value for t in at.title), "login title missing"


def test_logged_in_without_agent_forced_to_install():
    at = _fresh()
    auth.create_account("staff", "pw", "standard")
    at.session_state["user"] = "staff"
    at.session_state["role"] = "standard"
    at.run()
    assert not at.exception, at.exception
    heads = [h.value for h in at.header]
    assert any("Install Your Agent" in h for h in heads), f"expected install gate, got {heads}"


def test_logged_in_with_agent_reaches_scan_pages():
    at = _fresh()
    auth.create_account("staff", "pw", "standard")
    tokens.issue_agent_token("staff")          # register an agent
    at.session_state["user"] = "staff"
    at.session_state["role"] = "standard"
    at.run()
    assert not at.exception, at.exception
    heads = [h.value for h in at.header]
    assert any("New Scan" in h for h in heads), f"expected scan page, got {heads}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_ui_public: all green")
