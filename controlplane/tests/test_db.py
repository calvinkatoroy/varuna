import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import db  # noqa: E402


def setup_function(_):
    # fresh in-file DB per test (WAL needs a real file, not :memory:)
    db.reset_for_test(os.path.join(os.path.dirname(__file__), "_test.db"))


def teardown_function(_):
    db.close()
    for suffix in ("", "-wal", "-shm"):
        p = os.path.join(os.path.dirname(__file__), "_test.db" + suffix)
        if os.path.exists(p):
            os.remove(p)


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
