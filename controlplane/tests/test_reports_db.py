import os
import sys
import sqlite3

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import db  # noqa: E402
import models  # noqa: E402

# db reset per-test by the autouse _fresh_db fixture in conftest.py


def test_create_report_starts_as_draft():
    rid = db.create_report("j1", "org-a", "alice", template="Full Technical")
    r = db.get_report(rid, org_id="org-a")
    assert r["owner"] == "alice" and r["job_id"] == "j1" and r["org_id"] == "org-a"
    assert r["stage"] == models.REPORT_DRAFT
    assert r["password_viewed"] is False




def test_list_reports_by_org_and_stage():
    a = db.create_report("ja", "org-a", "alice")
    db.create_report("jb", "org-b", "bob")
    assert {r["id"] for r in db.list_reports(org_id="org-a")} == {a}
    assert len(db.list_reports(stage=models.REPORT_DRAFT, org_id=None)) == 2


def test_set_report_fields():
    rid = db.create_report("j1", "org-a", "alice")
    db.set_report(rid, stage=models.REPORT_DELIVERED, delivered_pdf="r.pdf",
                  pdf_password="secret", password_viewed=1)
    r = db.get_report(rid, org_id="org-a")
    assert r["stage"] == models.REPORT_DELIVERED and r["delivered_pdf"] == "r.pdf"
    assert r["pdf_password"] == "secret" and r["password_viewed"] is True


def test_missing_report_is_none():
    assert db.get_report("nope", org_id=None) is None
    rid = db.create_report("j1", "org-a", "alice")
    assert db.get_report(rid, org_id="org-b") is None   # another org's row reads as missing


def test_report_is_linked_to_its_task_once():
    org = db.create_org("PT A")
    tid = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://t", "stage": "completed", "job_id": "j1"})
    rid = db.create_report("j1", org, "alice", task_id=tid)
    assert db.report_for_task(tid)["id"] == rid
    with pytest.raises(sqlite3.IntegrityError):
        db.create_report("j1", org, "alice", task_id=tid)
    legacy = db.create_report("j2", org, "alice")                    # made before task_id existed: found through the job
    tid2 = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://t", "stage": "completed", "job_id": "j2"})
    assert db.report_for_task(tid2)["id"] == legacy
    assert db.report_for_task("nope") is None


def test_password_is_set_once():
    rid = db.create_report("j1", "org-a", "alice")
    assert db.set_report_password_if_empty(rid, "enc1:first") and not db.set_report_password_if_empty(rid, "enc1:second")
    assert db.get_report(rid, org_id=None)["pdf_password"] == "enc1:first"
