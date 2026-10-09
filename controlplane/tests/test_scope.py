import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import db  # noqa: E402


def test_org_roundtrip_and_unique_name():
    oid = db.create_org("PT Samudera Logistik")
    assert db.get_org(oid)["status"] == "active"
    assert [o["name"] for o in db.list_orgs()] == ["PT Samudera Logistik"]
    try:
        db.create_org("PT Samudera Logistik")
        assert False, "duplicate org name accepted"
    except Exception:
        pass
    assert db.set_org_status(oid, "disabled") and db.get_org(oid)["status"] == "disabled"


def test_account_has_org_and_token_version_bumps():
    oid = db.create_org("CV Bahari")
    db.upsert_account("rina", "h", "client", org_id=oid)
    a = db.get_account("rina")
    assert a["org_id"] == oid and a["must_change_password"] == 0
    for fields in ({"password_hash": "h2"}, {"role": "client"}, {"disabled": 1}, {"org_id": oid}):
        before = db.get_account("rina")["token_version"]
        db.set_account("rina", **fields)
        assert db.get_account("rina")["token_version"] == before + 1
    before = db.get_account("rina")["token_version"]
    db.set_account("rina", display_name="Rina", phone="0812")
    assert db.get_account("rina")["token_version"] == before   # cosmetic edits keep sessions


import pytest  # noqa: E402
import tenancy  # noqa: E402


def _two_orgs():
    a, b = db.create_org("PT A"), db.create_org("PT B")
    pa = db.create_proposal({"submitter": "ua", "target": "http://a.co.id", "org_id": a})
    pb = db.create_proposal({"submitter": "ub", "target": "http://b.co.id", "org_id": b})
    return a, b, pa, pb


def test_proposals_scoped():
    a, b, pa, pb = _two_orgs()
    assert [p["id"] for p in db.list_proposals(org_id=a)] == [pa]
    assert db.get_proposal(pb, org_id=a) is None
    assert db.get_proposal(pb, org_id=b)["id"] == pb
    assert len(db.list_proposals(org_id=None)) == 2          # staff scope


def test_reports_and_findings_scoped():
    a, b, *_ = _two_orgs()
    ra = db.create_report("j1", a, "ua")
    assert db.get_report(ra, org_id=b) is None and db.get_report(ra, org_id=a)["org_id"] == a
    assert db.list_reports(org_id=b) == []
    db.save_findings("j1", "ua", a, [{"name": "SQLi", "severity": "high", "host": "a.co.id"}])
    fid = db.list_findings(org_id=a)[0]["id"]
    assert db.get_finding(fid, org_id=b) is None and db.list_findings(org_id=b) == []


def test_org_id_is_required():
    with pytest.raises(TypeError):
        db.list_proposals()
    with pytest.raises(TypeError):
        db.get_report("x")


def test_scope_for():
    assert tenancy.scope_for({"role": "client", "org_id": "o1"}).org_id == "o1"
    assert tenancy.scope_for({"role": "pentester", "org_id": None}).org_id is None
    with pytest.raises(PermissionError):
        tenancy.scope_for({"role": "sysadmin", "org_id": None})
    assert tenancy.visible(tenancy.Scope("o1"), "o1") and not tenancy.visible(tenancy.Scope("o1"), "o2")
    assert tenancy.visible(tenancy.Scope(None), "o2")
