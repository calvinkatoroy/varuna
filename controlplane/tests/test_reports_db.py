import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import db  # noqa: E402
import models  # noqa: E402

# db reset per-test by the autouse _fresh_db fixture in conftest.py


def test_create_report_starts_at_reporter_stage():
    rid = db.create_report(job_id="j1", owner="alice", template="Full Technical")
    r = db.get_report(rid)
    assert r["owner"] == "alice" and r["job_id"] == "j1"
    assert r["stage"] == models.REPORT_REPORTER
    assert r["password_viewed"] is False


def test_versions_increment_and_order():
    rid = db.create_report(job_id="j1", owner="alice")
    v1 = db.add_report_version(rid, filename="r_v1.docx", editor="aisah")
    v2 = db.add_report_version(rid, filename="r_v2.docx", editor="riyan", note="fixed exec summary")
    assert (v1, v2) == (1, 2)
    versions = db.list_report_versions(rid)
    assert [v["version_no"] for v in versions] == [1, 2]
    assert db.latest_version(rid)["filename"] == "r_v2.docx"


def test_list_reports_by_owner_and_stage():
    a = db.create_report(job_id="ja", owner="alice")
    db.create_report(job_id="jb", owner="bob")
    assert {r["id"] for r in db.list_reports(owner="alice")} == {a}
    assert len(db.list_reports(stage=models.REPORT_REPORTER)) == 2


def test_set_report_fields():
    rid = db.create_report(job_id="j1", owner="alice")
    db.set_report(rid, stage=models.REPORT_DELIVERED, delivered_pdf="r.pdf",
                  pdf_password="secret", password_viewed=1)
    r = db.get_report(rid)
    assert r["stage"] == models.REPORT_DELIVERED and r["delivered_pdf"] == "r.pdf"
    assert r["pdf_password"] == "secret" and r["password_viewed"] is True


def test_missing_report_is_none():
    assert db.get_report("nope") is None
