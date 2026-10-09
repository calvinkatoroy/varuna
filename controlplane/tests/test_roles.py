import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import models  # noqa: E402

STAFF = {"pentester", "lead_pentester", "lead_cyber", "governance", "manager"}


def test_roles_defined():
    assert set(models.ROLES) == STAFF | {"client", "sysadmin"}


def test_team_client_sysadmin_are_disjoint():
    assert models.is_client("client") and not models.is_team("client")
    assert models.is_sysadmin("sysadmin")
    assert not models.is_team("sysadmin") and not models.is_client("sysadmin")
    for r in STAFF:
        assert models.is_team(r) and not models.is_client(r)


def test_review_stage_owners():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
    import workflow
    assert workflow.STAGE_ROLE == {"review_lead_pentester": "lead_pentester", "review_lead_cyber": "lead_cyber",
                                   "review_governance": "governance", "review_manager": "manager"}
    assert workflow.PENTESTERS == {"pentester", "lead_pentester"}


def test_removed_roles_are_gone():
    assert "reporter" not in models.ROLES and "soc" not in models.ROLES
