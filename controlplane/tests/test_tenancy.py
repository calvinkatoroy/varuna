import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import tenancy  # noqa: E402


def test_client_sees_only_own_org():
    s = tenancy.scope_for({"role": "client", "org_id": "o1"})
    assert tenancy.visible(s, "o1")
    assert not tenancy.visible(s, "o2")


def test_team_sees_all():
    for r in ("pentester", "lead_pentester", "lead_cyber", "governance", "manager"):
        assert tenancy.visible(tenancy.scope_for({"role": r, "org_id": None}), "o2")


def test_client_without_org_denied():
    try:
        tenancy.scope_for({"role": "client", "org_id": None})
        assert False
    except PermissionError:
        pass
