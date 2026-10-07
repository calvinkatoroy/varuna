import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import tenancy  # noqa: E402


def test_client_sees_only_own():
    assert tenancy.visible_to("client", "alice", "alice")
    assert not tenancy.visible_to("client", "alice", "bob")


def test_team_sees_all():
    for r in ("pentester", "lead_pentester", "lead_cyber", "governance", "manager"):
        assert tenancy.visible_to(r, "riyan", "bob")


def test_filter_owned():
    rows = [{"submitter": "alice", "id": 1}, {"submitter": "bob", "id": 2}]
    assert tenancy.filter_owned("client", "alice", rows) == [{"submitter": "alice", "id": 1}]
    assert len(tenancy.filter_owned("lead_pentester", "riyan", rows)) == 2
