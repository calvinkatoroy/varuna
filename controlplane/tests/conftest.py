import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import db  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    """Every test gets a clean SQLite DB (accounts and, later, proposals/reports live here)."""
    db.reset_for_test(str(tmp_path / "test.db"))
    yield
    db.close()
