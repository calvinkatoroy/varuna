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
