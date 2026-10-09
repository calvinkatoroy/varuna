import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import db  # noqa: E402

# db is reset per-test by the autouse _fresh_db fixture in conftest.py


def _sample(submitter="alice", org_id="org-a", **over):
    d = {"submitter": submitter, "org_id": org_id, "target": "http://t.example", "path": "/app", "port": 8443,
         "notes": "use the demo account", "not_before": "2026-10-08T01:00:00+00:00",
         "not_after": "2026-10-09T01:00:00+00:00", "scan_mode": "cloud"}
    d.update(over)
    return d


def test_create_get_round_trip():
    pid = db.create_proposal(_sample())
    t = db.get_proposal(pid, org_id="org-a")
    assert (t["submitter"], t["org_id"], t["stage"], t["scan_state"], t["version"]) == ("alice", "org-a", "task", None, 0)
    assert (t["path"], t["port"], t["notes"], t["scan_mode"]) == ("/app", 8443, "use the demo account", "cloud")
    assert t["not_after"] == "2026-10-09T01:00:00+00:00"


def test_list_by_org_and_stage():
    a = db.create_proposal(_sample("alice", "org-a"))
    a2 = db.create_proposal(_sample("carol", "org-a", stage="scan", scan_state="pending"))   # same org: shared
    db.create_proposal(_sample("bob", "org-b"))
    assert {t["id"] for t in db.list_proposals(org_id="org-a")} == {a, a2}
    assert len(db.list_proposals(stage="task", org_id=None)) == 2
    assert [t["id"] for t in db.list_proposals(stage="scan", scan_state="pending", org_id=None)] == [a2]


def test_update_sets_fields_but_never_the_stage():
    pid = db.create_proposal(_sample())
    db.update_proposal(pid, job_id="job-123", due_since="2026-10-08T02:00:00+00:00")
    assert db.get_proposal(pid, org_id=None)["job_id"] == "job-123"
    with pytest.raises(ValueError):
        db.update_proposal(pid, scan_state="in_progress")


def test_cas_moves_once_and_writes_one_event():
    pid = db.create_proposal(_sample())
    ev = {"actor": "rizky", "at": "2026-10-08T02:00:00+00:00", "from_stage": "task", "to_stage": "declined",
          "comment": "x"}
    assert db.cas_task(pid, 0, {"stage": "declined"}, ev) is True
    assert db.cas_task(pid, 0, {"stage": "expired"}, ev) is False
    assert db.get_proposal(pid, org_id=None)["version"] == 1 and len(db.list_task_events(pid)) == 1


def test_missing_is_none():
    assert db.get_proposal("nope", org_id=None) is None
    pid = db.create_proposal(_sample())
    assert db.get_proposal(pid, org_id="org-b") is None   # another org's row reads as missing
