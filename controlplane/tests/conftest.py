import os
import sys

import pytest

# The apps load the repo-root .env. Tests must not depend on a developer's deployment settings:
# pin the ones that change behaviour (set-but-empty wins over .env, dotenv never overrides).
os.environ["VARUNA_REQUIRE_MFA"] = ""
os.environ.setdefault("NOTIFY_WEBHOOK_URL", "")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import db  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    """Every test gets a clean SQLite DB (accounts and, later, proposals/reports live here)."""
    db.reset_for_test(str(tmp_path / "test.db"))
    yield
    db.close()


def make_client(name="alice", org="PT A", password="Passw0rd!x"):
    """Create a client account `name` in organization `org` (created on first use); returns the org_id."""
    import auth
    oid = next((o["id"] for o in db.list_orgs() if o["name"] == org), None) or db.create_org(org)
    auth.create_account(name, password, "client", org_id=oid)
    return oid


class _Api:
    """Thin TestClient wrapper shared by API tests: .login/.get/.post/.put/.request with a bearer token."""

    def __init__(self, app):
        from fastapi.testclient import TestClient
        self.app = app
        self.c = TestClient(app)

    def raw_login(self, user, pw, **extra):
        return self.c.post("/api/login", json={"username": user, "password": pw, **extra})

    def login(self, user, pw, **extra):
        r = self.raw_login(user, pw, **extra)
        assert r.status_code == 200, r.text
        return r.json()["token"]

    def request(self, method, path, token=None, json=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.c.request(method, path, headers=headers, json=json)

    def get(self, path, token=None):
        return self.request("GET", path, token)

    def post(self, path, token=None, json=None):
        return self.request("POST", path, token, json)

    def put(self, path, token=None, json=None):
        return self.request("PUT", path, token, json)


_API_DIR = os.path.join(os.path.dirname(__file__), "..", "api")


def _fresh_app(name, monkeypatch):
    if _API_DIR not in sys.path:
        sys.path.insert(0, _API_DIR)
    monkeypatch.setenv("VARUNA_PUBLIC_TEAM_LOGIN", "1")   # restored after the test; tests may override
    import redis_store
    from _fakeredis import FakeRedis
    redis_store._client = FakeRedis()
    return __import__(name).app


@pytest.fixture
def api(monkeypatch):
    return _Api(_fresh_app("browser", monkeypatch))


@pytest.fixture
def priv(monkeypatch):
    return _Api(_fresh_app("private_api", monkeypatch))
