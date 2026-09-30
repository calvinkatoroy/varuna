import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import db  # noqa: E402

# db is reset per-test by the autouse _fresh_db fixture in conftest.py


def test_account_round_trip():
    db.upsert_account("alice", "hash1", "client")
    row = db.get_account("alice")
    assert row == {"username": "alice", "password_hash": "hash1", "role": "client"} \
        or (row["username"], row["password_hash"], row["role"]) == ("alice", "hash1", "client")


def test_upsert_updates_existing():
    db.upsert_account("bob", "h1", "client")
    db.upsert_account("bob", "h2", "pentester")
    row = db.get_account("bob")
    assert row["password_hash"] == "h2" and row["role"] == "pentester"


def test_missing_account_is_none():
    assert db.get_account("nobody") is None
