import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import db  # noqa: E402
import models  # noqa: E402

# db is reset per-test by the autouse _fresh_db fixture in conftest.py


def _sample(submitter="alice", org_id="org-a", **over):
    d = {
        "submitter": submitter, "org_id": org_id, "mode": "standard", "target": "http://t.example",
        "in_scope": "http://t.example", "division": "IT", "purpose": "pre-release",
        "authorization_attested": True, "tools": ["katana", "nuclei"], "opts": {"depth": 2},
        "roe": {"dos_allowed": False},
    }
    d.update(over)
    return d


def test_create_get_round_trip():
    pid = db.create_proposal(_sample())
    p = db.get_proposal(pid, org_id="org-a")
    assert p["submitter"] == "alice" and p["org_id"] == "org-a"
    assert p["status"] == models.PROPOSAL_PENDING
    assert p["tools"] == ["katana", "nuclei"]         # json decoded
    assert p["opts"] == {"depth": 2}
    assert p["roe"] == {"dos_allowed": False}
    assert p["authorization_attested"] is True         # bool decoded


def test_list_by_org_and_status():
    a = db.create_proposal(_sample("alice", "org-a"))
    a2 = db.create_proposal(_sample("carol", "org-a"))   # same org: shared
    db.create_proposal(_sample("bob", "org-b"))
    assert {p["id"] for p in db.list_proposals(org_id="org-a")} == {a, a2}
    assert len(db.list_proposals(status=models.PROPOSAL_PENDING, org_id=None)) == 3
    assert len(db.list_proposals(status=models.PROPOSAL_PENDING, org_id="org-b")) == 1


def test_update_sets_status_and_job():
    pid = db.create_proposal(_sample())
    db.update_proposal(pid, status=models.PROPOSAL_APPROVED, job_id="job-123")
    p = db.get_proposal(pid, org_id=None)
    assert p["status"] == models.PROPOSAL_APPROVED and p["job_id"] == "job-123"


def test_missing_is_none():
    assert db.get_proposal("nope", org_id=None) is None
    pid = db.create_proposal(_sample())
    assert db.get_proposal(pid, org_id="org-b") is None   # another org's row reads as missing
