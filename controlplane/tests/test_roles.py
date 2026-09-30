import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import models  # noqa: E402


def test_six_roles_defined():
    assert set(models.ROLES) == {
        "client", "pentester", "lead_pentester", "reporter", "governance", "soc"
    }


def test_team_vs_client():
    assert models.is_client("client")
    assert not models.is_team("client")
    for r in ("pentester", "lead_pentester", "reporter", "governance", "soc"):
        assert models.is_team(r)
        assert not models.is_client(r)


def test_capabilities():
    assert models.can_approve("lead_pentester")
    assert not models.can_approve("pentester")
    assert models.can_review("reporter")
    assert models.can_review("governance")
    assert models.can_review("lead_pentester")
    assert not models.can_review("pentester")
    assert not models.can_review("client")


def test_backward_compat_aliases():
    assert models.ROLE_STANDARD == models.ROLE_CLIENT == "client"
    assert models.ROLE_PRO == models.ROLE_PENTESTER == "pentester"
