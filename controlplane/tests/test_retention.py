"""Report retention + offboarding wipe (SRS NFR-28, DAT-4)."""
import os
import sys
import tempfile

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "report"))

import db  # noqa: E402
import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import audit  # noqa: E402
import store  # noqa: E402

store.REPORTS_DIR = tempfile.mkdtemp()


def test_retention_purges_old_keeps_recent():
    redis_store._client = FakeRedis()
    meta = store.save_report("alice", "j1", "Executive Summary", b"data", org_id="org-a")
    assert len(store.list_all_reports()) == 1

    # A generous window keeps it; a negative window treats everything as expired.
    assert store.purge_old_reports(max_age_days=3650) == 0
    assert len(store.list_all_reports()) == 1
    assert os.path.exists(os.path.join(store.REPORTS_DIR, meta["file"]))

    assert store.purge_old_reports(max_age_days=-1) == 1
    assert store.list_all_reports() == []
    assert not os.path.exists(os.path.join(store.REPORTS_DIR, meta["file"])), "old report file not deleted"


def test_wipe_all_clears_data_but_keeps_accounts():
    redis_store._client = FakeRedis()
    # seed data across every store (accounts now live in SQLite via db, reset per-test by conftest)
    db.upsert_account("ihsan", "x", "pentester")
    redis_store.set_job({"id": "j1", "target": "http://t", "submitter": "ihsan", "status": "done"})
    db.save_findings("j1", "ihsan", "", [{"name": "SQLi", "severity": "critical", "host": "h"}])
    audit.log(audit.SUBMIT, submitter="ihsan", target="http://t")
    store.save_report("ihsan", "j1", "Full Technical", b"bytes", org_id=None)

    counts = store.wipe_all()

    # scan data, findings, reports, and audit are gone...
    assert redis_store.get_job("j1") is None
    assert db.get_findings("j1") == []
    assert store.list_all_reports() == []
    assert audit.read_all() == []
    assert counts["report_files"] >= 1
    # ...but accounts survive (offboarding removes them separately)
    assert db.get_account("ihsan") is not None, "wipe must not delete accounts"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_retention: all green")
