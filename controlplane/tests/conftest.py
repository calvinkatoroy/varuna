import os
import sys

import pytest

# The apps load the repo-root .env. Tests must not depend on a developer's deployment settings:
# pin the ones that change behaviour (set-but-empty wins over .env, dotenv never overrides).
os.environ["VARUNA_REQUIRE_MFA"] = ""
os.environ.setdefault("NOTIFY_WEBHOOK_URL", "")
os.environ["BCRYPT_ROUNDS"] = "4"   # tests hash a lot of passwords; production keeps the default cost 12
os.environ["VARUNA_SCHEDULER"] = "0"   # no background scheduler thread in tests; tests call scheduler.tick()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))
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


def window(start_min=-5, minutes=480):
    """A client time limit as UTC ISO strings: starts `start_min` minutes from now, lasts `minutes`."""
    import datetime
    start = datetime.datetime.now(datetime.UTC).replace(microsecond=0) + datetime.timedelta(minutes=start_min)
    return start.isoformat(), (start + datetime.timedelta(minutes=minutes)).isoformat()


def start_task(tid, pentester="rizky"):
    """Claim and start a task through the workflow, with its scanner online; returns the job id."""
    import auth
    import models
    import tokens
    import workflow
    t = db.get_proposal(tid, org_id=None)
    tokens.issue_agent_token(models.CLOUD_AGENT if t["scan_mode"] == models.SCAN_CLOUD else t["submitter"])
    if not db.get_account(pentester):
        auth.create_account(pentester, "Passw0rd!x", "pentester")
    workflow.transition(tid, "scan/pending", pentester, org_id=None)
    return workflow.transition(tid, "scan/in_progress", pentester, org_id=None)["job_id"]


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


def ready_pdf(tid, org_name="PT A"):
    """Give task `tid` content v1 and a ready, CURRENT PDF row (no LibreOffice): what Submit for review needs."""
    import reportcontent
    import reportdoc
    t = db.get_proposal(tid, org_id=None)
    c = reportcontent.ensure_v1(t)
    job, _ = db.claim_pdf(tid, t["org_id"], c["version"], "tester")
    db.finish_pdf(job["id"], tid, reportdoc.digest(reportdoc.findings_for(t)), f"pdf-{job['id']}.pdf",
                  lambda n: reportdoc.pdf_filename(org_name, t["target"], n))
    return job["id"]
