import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import auth  # noqa: E402
import db  # noqa: E402
import models  # noqa: E402

# db is reset per-test by the autouse _fresh_db fixture in conftest.py


def test_register_creates_client_role():
    acct = auth.register_client("alice", "pw12345")
    assert acct.role == models.ROLE_CLIENT
    assert db.get_account("alice")["role"] == "client"


def test_register_rejects_duplicate():
    auth.register_client("bob", "pw12345")
    try:
        auth.register_client("bob", "other")
        raise SystemExit("expected AuthError on duplicate")
    except auth.AuthError:
        pass


def test_register_requires_username_and_password():
    for u, p in (("", "pw"), ("x", "")):
        try:
            auth.register_client(u, p)
            raise SystemExit("expected AuthError on empty field")
        except auth.AuthError:
            pass
