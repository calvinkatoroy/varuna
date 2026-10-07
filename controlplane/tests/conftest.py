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


def _fresh_app(name):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
    os.environ["VARUNA_PUBLIC_TEAM_LOGIN"] = "1"
    import redis_store
    from _fakeredis import FakeRedis
    redis_store._client = FakeRedis()
    return __import__(name).app


@pytest.fixture
def api():
    return _Api(_fresh_app("browser"))


@pytest.fixture
def priv():
    return _Api(_fresh_app("private_api"))
