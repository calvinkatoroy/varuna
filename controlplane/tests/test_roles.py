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


def test_capabilities():
    assert models.can_approve("lead_pentester") and not models.can_approve("pentester")
    for r in ("pentester", "lead_pentester", "governance"):
        assert models.can_review(r)
    for r in ("client", "sysadmin", "manager"):
        assert not models.can_review(r)


def test_removed_roles_are_gone():
    assert "reporter" not in models.ROLES and "soc" not in models.ROLES
