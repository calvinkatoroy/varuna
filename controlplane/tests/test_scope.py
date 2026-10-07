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
    assert a["org_id"] == oid and a["token_version"] == 0 and a["must_change_password"] == 0
    for fields in ({"password_hash": "h2"}, {"role": "client"}, {"disabled": 1}, {"org_id": oid}):
        before = db.get_account("rina")["token_version"]
        db.set_account("rina", **fields)
        assert db.get_account("rina")["token_version"] == before + 1
    before = db.get_account("rina")["token_version"]
    db.set_account("rina", display_name="Rina", phone="0812")
    assert db.get_account("rina")["token_version"] == before   # cosmetic edits keep sessions
