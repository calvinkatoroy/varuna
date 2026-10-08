import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))
import auth  # noqa: E402
import db  # noqa: E402
import models  # noqa: E402
import redis_store  # noqa: E402
import seed_account  # noqa: E402
import tenancy  # noqa: E402
from _fakeredis import FakeRedis  # noqa: E402


@pytest.fixture
def seeded(tmp_path):
    """Demo data seeded into the per-test DB; LibreOffice and the reports dir are stubbed."""
    import io
    import pdf_deliver
    import seed_demo
    import store as report_store
    from reportlab.pdfgen import canvas

    def fake_pdf(_):
        b = io.BytesIO(); c = canvas.Canvas(b); c.drawString(72, 720, "x"); c.showPage(); c.save()
        return b.getvalue()

    old = (redis_store._client, pdf_deliver.CONVERT, report_store.REPORTS_DIR)
    redis_store._client = FakeRedis()
    pdf_deliver.CONVERT = fake_pdf
    report_store.REPORTS_DIR = str(tmp_path / "reports")
    os.makedirs(report_store.REPORTS_DIR)
    creds = tmp_path / "demo-creds.txt"
    try:
        yield seed_demo.seed(str(creds)), creds
    finally:
        redis_store._client, pdf_deliver.CONVERT, report_store.REPORTS_DIR = old


def test_bootstrap_creates_one_sysadmin_and_refuses_a_second(tmp_path):
    creds = tmp_path / "admin.txt"
    pw = seed_account.bootstrap(str(creds))
    admins = [a for a in db.list_accounts() if a["role"] == "sysadmin"]
    assert [a["username"] for a in admins] == ["admin"] and admins[0]["org_id"] is None
    assert creds.read_text().split() == ["admin", pw]
    redis_store._client = FakeRedis()
    assert auth.authenticate("admin", pw, "1.2.3.4").role == "sysadmin"
    with pytest.raises(RuntimeError, match="already exists"):
        seed_account.bootstrap(str(tmp_path / "again.txt"))
    assert not (tmp_path / "again.txt").exists()


def test_team_defaults_creates_exactly_the_five_staff_without_org():
    seed_account.team_defaults()
    staff = {a["username"]: a for a in db.list_accounts()}
    assert {u: a["role"] for u, a in staff.items()} == {
        "rizky": "pentester", "dewi": "lead_pentester", "agus": "lead_cyber",
        "sari": "governance", "hendra": "manager"}
    assert all(not a["org_id"] for a in staff.values())


def test_generic_client_needs_an_org():
    with pytest.raises(ValueError):
        auth.create_account("x", "Passw0rd!x", "client")
    oid = seed_account.get_or_create_org("PT Uji")
    assert seed_account.get_or_create_org("PT Uji") == oid
    auth.create_account("uji", "Passw0rd!x", "client", org_id=oid)
    assert db.get_account("uji")["org_id"] == oid


def test_demo_orgs_users_and_rows_carry_the_right_org(seeded):
    org_ids, creds = seeded
    assert len(db.list_orgs()) == 3
    expect = {"budi.santoso": "PT Samudera Logistik Nusantara", "siti.rahayu": "PT Samudera Logistik Nusantara",
              "agung.wijaya": "PT Pelabuhan Bahari Sejahtera", "dewi.lestari": "CV Mitra Kargo Jaya"}
    for user, org in expect.items():
        assert db.get_account(user)["org_id"] == org_ids[org] and db.get_account(user)["role"] == "client"
    assert sorted(l.split()[0] for l in creds.read_text().splitlines()) == sorted(expect)

    props = db.list_proposals(org_id=None)
    reports = db.list_reports(org_id=None)
    findings = db.list_findings(org_id=None)
    assert len(props) == 4 and reports and findings
    for p in props:
        assert p["org_id"] and p["org_id"] == db.get_account(p["submitter"])["org_id"]
        assert p["target"].split("://")[1].endswith(".co.id")
    for row in reports + findings:
        assert row["org_id"] and row["org_id"] == db.get_account(row["owner"])["org_id"]
    stages = {p["stage"] for p in props}
    assert {"task", "delivered", "review_governance", "declined"} <= stages
    assert any(r["stage"] == models.REPORT_DELIVERED for r in reports)
    assert next(p for p in props if p["stage"] == "declined")["decline_cause"]
    assert len(db.list_task_events(next(p["id"] for p in props if p["stage"] == "delivered"))) == 5


def test_demo_refuses_to_run_twice(seeded, tmp_path):
    import seed_demo
    with pytest.raises(RuntimeError, match="already exist"):
        seed_demo.seed(str(tmp_path / "again.txt"))


def test_client_scope_sees_only_its_own_org(seeded):
    org_ids, _ = seeded
    for user in ("budi.santoso", "agung.wijaya", "dewi.lestari"):
        acct = db.get_account(user)
        scope = tenancy.scope_for(acct)
        assert scope.org_id == acct["org_id"]
        for rows in (db.list_proposals(org_id=scope.org_id), db.list_reports(org_id=scope.org_id),
                     db.list_findings(org_id=scope.org_id)):
            assert all(r["org_id"] == scope.org_id for r in rows)
    sam = tenancy.scope_for(db.get_account("budi.santoso")).org_id
    other = db.list_reports(org_id=tenancy.scope_for(db.get_account("agung.wijaya")).org_id)
    assert other and all(db.get_report(r["id"], org_id=sam) is None for r in other)
    mitra = tenancy.scope_for(db.get_account("dewi.lestari")).org_id
    assert db.list_reports(org_id=mitra) == [] and db.list_findings(org_id=mitra) == []
    assert len(db.list_proposals(org_id=sam)) == 2


def test_wipe_all_clears_accounts_and_orgs(seeded):
    import wipe_data
    wipe_data.wipe(everything=False)
    assert db.list_orgs() and db.list_accounts()
    wipe_data.wipe(everything=True)
    assert db.list_orgs() == [] and db.list_accounts() == [] and db.list_proposals(org_id=None) == []


def test_wipe_all_clears_agent_redis_keys(seeded):
    import redis_store
    import wipe_data
    r = redis_store.get_redis()
    for k in ("agent:a", "agent_token:h", "agentqueue:a", "suspended:j", "enroll:t", "org_jobs:o"):
        r.set(k, "1")
    wipe_data.wipe(everything=False)
    assert r.get("agent:a") == "1"            # kept without --all
    wipe_data.wipe(everything=True)
    assert all(r.get(k) is None for k in ("agent:a", "agent_token:h", "agentqueue:a", "suspended:j", "enroll:t", "org_jobs:o"))
