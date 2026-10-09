"""Report helpers: filename rules, findings digest, "is the PDF current", and the SQLite job/content claims."""
import os
import sqlite3
import sys
import threading

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "report"))
import db  # noqa: E402
import reportdoc  # noqa: E402
from conftest import make_client, ready_pdf, window  # noqa: E402

BIG = "A" * 90


@pytest.mark.parametrize("org,target,n,expected", [
    ("PT Samudera Logistik", "https://portal.samudera-logistik.co.id/app", 1,
     "PT_Samudera_Logistik_portal_samudera_logistik_co_id_Pentest_Report_1.pdf"),
    ("Caf\u00e9 M\u00fcller & S\u00f6hne", "http://8.8.8.8:8080", 12, "Cafe_Muller_Sohne_8_8_8_8_Pentest_Report_12.pdf"),
    ("\u65e5\u672c\u8a9e", "", 3, "Client_Target_Pentest_Report_3.pdf"),
    ("../../etc/passwd\r\nX: y", "http://a.b", 2, "etc_passwd_X_y_a_b_Pentest_Report_2.pdf"),
    (BIG, "http://" + "b" * 90 + ".com", 1, "A" * 40 + "_" + "b" * 40 + "_Pentest_Report_1.pdf"),
])
def test_pdf_filename(org, target, n, expected):
    assert reportdoc.pdf_filename(org, target, n) == expected


def test_every_generated_name_passes_the_header_check():
    for org in ("x", "\"; rm -rf", "a\nb", "\u202e", "..", "A" * 500):
        name = reportdoc.pdf_filename(org, "http://t.example", 7)
        assert reportdoc.FILENAME_RE.fullmatch(name) and reportdoc.safe_filename(name) == name


@pytest.mark.parametrize("bad", ["x.pdf\n", 'a"b.pdf', "a b.pdf", "../x.pdf", "x.docx", "", None, "\u00e9.pdf"])
def test_safe_filename_refuses_anything_not_made_by_the_slugger(bad):
    assert reportdoc.safe_filename(bad) == reportdoc.FALLBACK_FILENAME


def test_content_disposition_is_quoted_and_has_the_5987_twin():
    assert reportdoc.content_disposition("PT_A_t_Pentest_Report_1.pdf") == \
        "attachment; filename=\"PT_A_t_Pentest_Report_1.pdf\"; filename*=UTF-8''PT_A_t_Pentest_Report_1.pdf"
    assert "\n" not in reportdoc.content_disposition("evil\r\nSet-Cookie: a=b.pdf")


def _f(i, **kw):
    return {"id": f"f{i}", "verdict": "tp", "severity": "high", "name": f"n{i}", "host": "h", "url": "/", "description": "d",
            "impact": "i", "remediation": "r", "evidence": "e", "cve": None, "cvss": None, "cwe": None, "owasp": None,
            "risk_rating": None, "tool": "nuclei", "status": "open", **kw}


def test_digest_tracks_what_reaches_the_document_only():
    base = [_f(1), _f(2)]
    d = reportdoc.digest(base)
    assert reportdoc.digest(list(reversed(base))) == d                      # order is not content
    assert reportdoc.digest([_f(1), _f(2, status="fixed")]) == d            # status is not printed in a way that matters
    for change in ({"verdict": "fp"}, {"severity": "low"}, {"remediation": "other"}, {"name": "x"}):
        assert reportdoc.digest([_f(1), _f(2, **change)]) != d, change
    assert reportdoc.digest(base + [_f(3)]) != d


def test_counts():
    fs = [_f(1), _f(2, verdict="fp"), _f(3, severity="weird"), _f(4, tool="manual", severity="low")]
    c = reportdoc.counts(fs)
    assert (c["total"], c["tp"], c["fp"], c["manual"]) == (4, 3, 1, 1)
    assert c["severity"] == {"critical": 0, "high": 1, "medium": 0, "low": 1, "info": 1}


def _task(stage="completed"):
    org = make_client("alice", "PT A")
    nb, na = window()
    tid = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8", "stage": stage,
                              "assignee": "rizky", "job_id": "j1", "not_before": nb, "not_after": na})
    db.save_findings("j1", "alice", org, [{"name": "XSS", "severity": "high", "host": "h", "url": "/a"}])
    return tid


def test_pdf_gap_walks_through_every_reason():
    tid = _task()
    t = lambda: db.get_proposal(tid, org_id=None)
    assert "audit" in reportdoc.pdf_gap(t()).lower()                       # no content yet
    ready_pdf(tid)
    assert reportdoc.pdf_gap(t()) is None
    fid = db.get_findings("j1")[0]["id"]
    db.set_finding(fid, verdict="fp")
    assert "changed" in reportdoc.pdf_gap(t())
    db.set_finding(fid, verdict="tp")
    assert reportdoc.pdf_gap(t()) is None
    db.add_content(tid, t()["org_id"], db.latest_content(tid)["content"], "x", base_version=1)
    assert "changed" in reportdoc.pdf_gap(t())


def test_content_versions_are_append_only_and_compare_and_set():
    tid = _task()
    org = db.get_proposal(tid, org_id=None)["org_id"]
    assert db.add_content(tid, org, {"a": 1}, "rizky", "first", base_version=0) == 1
    assert db.add_content(tid, org, {"a": 2}, "rizky", base_version=0) is None          # stale base
    assert db.add_content(tid, org, {"a": 2}, "rizky", base_version=1) == 2
    assert db.latest_content(tid)["content"] == {"a": 2}
    assert db.get_content(tid, 1)["content"] == {"a": 1}
    assert [v["version"] for v in db.list_content_versions(tid)] == [2, 1]


def test_two_writers_on_one_base_only_one_wins():
    tid = _task()
    org = db.get_proposal(tid, org_id=None)["org_id"]
    db.add_content(tid, org, {"v": 1}, "x", base_version=0)
    out, gate = [], threading.Barrier(8)

    def go(i):
        gate.wait()
        out.append(db.add_content(tid, org, {"v": i}, f"u{i}", base_version=1))
    ts = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(x for x in out if x) == [2] and out.count(None) == 7


def test_one_active_pdf_job_per_task_and_numbers_skip_failures():
    tid = _task()
    org = db.get_proposal(tid, org_id=None)["org_id"]
    a, created = db.claim_pdf(tid, org, 1, "rizky")
    assert created and a["status"] == "queued"
    b, created2 = db.claim_pdf(tid, org, 1, "budi")
    assert not created2 and b["id"] == a["id"]
    assert db.set_pdf_state(a["id"], "failed", "boom")
    c, created3 = db.claim_pdf(tid, org, 1, "rizky")
    assert created3 and c["id"] != a["id"]
    row = db.finish_pdf(c["id"], tid, "dg", "pdf-x.pdf", lambda n: f"F_{n}.pdf")
    assert (row["n"], row["filename"], row["status"]) == (1, "F_1.pdf", "ready")
    d, _ = db.claim_pdf(tid, org, 1, "rizky")
    assert db.finish_pdf(d["id"], tid, "dg", "pdf-y.pdf", lambda n: f"F_{n}.pdf")["n"] == 2
    assert db.latest_ready_pdf(tid)["n"] == 2 and db.pdf_filename_for_stored("pdf-x.pdf") == "F_1.pdf"
    with pytest.raises(sqlite3.IntegrityError):                              # (task_id, n) is unique
        db.get_conn().execute("INSERT INTO report_pdfs (id, task_id, n, status, content_version, requested_by) "
                              "VALUES ('dup', ?, 1, 'ready', 1, 'x')", (tid,))


def test_a_reaped_job_cannot_finish_late():
    tid = _task()
    org = db.get_proposal(tid, org_id=None)["org_id"]
    a, _ = db.claim_pdf(tid, org, 1, "rizky")
    db.get_conn().execute("UPDATE report_pdfs SET updated_at='2000-01-01 00:00:00' WHERE id=?", (a["id"],))
    db.get_conn().commit()
    assert db.reap_pdfs(300) == 1
    assert db.get_pdf(a["id"])["status"] == "failed" and "timed out" in db.get_pdf(a["id"])["error"]
    assert db.finish_pdf(a["id"], tid, "dg", "pdf-late.pdf", lambda n: "late.pdf") is None
    assert db.latest_ready_pdf(tid) is None


def test_ai_turn_claim_apply_and_audit():
    tid = _task()
    org = db.get_proposal(tid, org_id=None)["org_id"]
    db.add_content(tid, org, {"v": 1}, "x", base_version=0)
    t1, created = db.claim_turn(tid, org, "rizky", "make it shorter", 1)
    assert created and db.active_turn(tid)["id"] == t1["id"]
    again, created2 = db.claim_turn(tid, org, "rizky", "x", 1)
    assert not created2 and again["id"] == t1["id"]
    assert db.apply_turn(t1["id"], tid, org, {"v": 2}, "rizky", "n") is None          # not ready yet
    assert db.set_turn(t1["id"], status="ready", summary="s", ops_json="[]")
    assert not db.set_turn(t1["id"], status="running")                                   # a finished turn is final
    assert db.apply_turn(t1["id"], tid, org, {"v": 2}, "rizky", "n") == 2
    assert db.apply_turn(t1["id"], tid, org, {"v": 3}, "rizky", "n") is None          # applied once
    assert db.get_turn(t1["id"])["applied"] == 1 and db.get_turn(t1["id"])["applied_version"] == 2
    db.add_audit(tid, org, "rizky", "verdict", "f1", {"verdict": "fp"})
    (row,) = db.list_audit(tid)
    assert (row["actor"], row["action"], row["subject"]) == ("rizky", "verdict", "f1")
