"""report/store.py: per-user + global report index and file round-trip (REQ-50, REQ-50a)."""
import os
import sys
import tempfile

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "report"))

import redis_store  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402

redis_store._client = FakeRedis()

import store  # noqa: E402

store.REPORTS_DIR = tempfile.mkdtemp()   # don't pollute the repo


def test_per_user_and_global_index():
    redis_store._client = FakeRedis()
    store.save_report("alice", "j1", "Executive Summary", b"alice-data", org_id="org-a")
    store.save_report("bob", "j2", "Full Technical", b"bob-data", org_id="org-b")
    assert store.org_of("j1_Executive_Summary.docx") == "org-a"
    assert store.org_of("j2_Full_Technical.docx") == "org-b" and store.org_of("nope.docx") is None

    alice = store.list_reports("alice")
    assert len(alice) == 1 and alice[0]["template"] == "Executive Summary"
    assert store.list_reports("bob")[0]["user"] == "bob"

    # Pro full archive sees both users (REQ-50a).
    everyone = store.list_all_reports()
    assert {r["user"] for r in everyone} == {"alice", "bob"}


def test_file_round_trip():
    redis_store._client = FakeRedis()
    meta = store.save_report("alice", "j9", "Executive Summary", b"the-bytes", org_id="org-a")
    assert store.read_report(meta["file"]) == b"the-bytes"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_store: all green")
