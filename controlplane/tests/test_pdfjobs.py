"""PDF jobs: one active job per task, idempotent clicks, rate limit, failure isolation, filename, password."""
import concurrent.futures as cf
import io
import os
import sys

import pytest
from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(__file__))
from audit_helpers import PW, fake_pdf, world  # noqa: E402,F401
import db  # noqa: E402
import pdf_deliver  # noqa: E402
import pdfjobs  # noqa: E402
import pdfpass  # noqa: E402
import ratelimit  # noqa: E402
import reportdoc  # noqa: E402
import store as report_store  # noqa: E402


def _tok(priv, who):
    return priv.login(who, PW)


def _gen(priv, tid, who="rizky"):
    return priv.post(f"/api/tasks/{tid}/report/generate", _tok(priv, who))


def test_generate_makes_a_named_encrypted_pdf(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    r = _gen(priv, w.tid)
    assert r.status_code == 202, r.text
    job = r.json()["job"]
    assert job["status"] == "ready" and job["n"] == 1                       # inline runner finished it
    assert job["filename"] == "PT_A_8_8_8_8_Pentest_Report_1.pdf"
    tok = _tok(priv, "budi")                                                  # any team member reads and downloads
    st = priv.get(f"/api/tasks/{w.tid}/report/jobs/{job['id']}", tok).json()
    assert st["status"] == "ready" and "stored_name" not in st and "digest" not in st
    dl = priv.get(f"/api/tasks/{w.tid}/report/pdfs/{job['id']}/download", tok)
    assert dl.status_code == 200 and dl.headers["content-disposition"].startswith(
        'attachment; filename="PT_A_8_8_8_8_Pentest_Report_1.pdf"')
    pw = priv.get(f"/api/tasks/{w.tid}/report/password", tok).json()["password"]
    reader = PdfReader(io.BytesIO(dl.content))
    assert reader.is_encrypted and reader.decrypt(pw) != 0
    assert db.get_pdf(job["id"])["stored_name"].startswith("pdf-")          # never the user-facing name on disk
    assert not any(f.endswith("Pentest_Report_1.pdf") for f in os.listdir(tmp_path))


def test_regenerating_keeps_the_password_and_counts_up(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    first = _gen(priv, w.tid).json()["job"]
    pw1 = pdfpass.ensure(db.report_for_task(w.tid)["id"])
    db.set_finding(w.fids["Missing header"], verdict="fp")                    # the report changes
    second = _gen(priv, w.tid)
    assert second.status_code == 202
    job2 = second.json()["job"]
    assert job2["id"] != first["id"] and job2["n"] == 2 and job2["filename"].endswith("Pentest_Report_2.pdf")
    assert pdfpass.ensure(db.report_for_task(w.tid)["id"]) == pw1
    stored = db.report_for_task(w.tid)["pdf_password"]
    assert stored.startswith("enc1:") and pw1 not in stored                   # sealed at rest
    dl = priv.get(f"/api/tasks/{w.tid}/report/pdfs/{job2['id']}/download", _tok(priv, "rizky"))
    assert PdfReader(io.BytesIO(dl.content)).decrypt(pw1) != 0


def test_a_current_pdf_is_returned_not_rebuilt(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    a = _gen(priv, w.tid).json()["job"]
    again = _gen(priv, w.tid)
    assert again.status_code == 200 and again.json()["job"]["id"] == a["id"]
    assert len(db.list_pdfs(w.tid)) == 1


def test_double_click_is_one_job(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    queued = []
    monkeypatch.setattr(pdfjobs, "_submit", queued.append)                    # the worker never starts: job stays queued
    tok = _tok(priv, "rizky")
    first = priv.post(f"/api/tasks/{w.tid}/report/generate", tok)
    second = priv.post(f"/api/tasks/{w.tid}/report/generate", tok)
    assert first.status_code == second.status_code == 202
    assert first.json()["job"]["id"] == second.json()["job"]["id"] and first.json()["job"]["status"] == "queued"
    assert len(queued) == 1 and len(db.list_pdfs(w.tid)) == 1


def test_ten_parallel_clicks_make_one_job(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    queued = []
    monkeypatch.setattr(pdfjobs, "_submit", queued.append)
    tok = _tok(priv, "rizky")
    with cf.ThreadPoolExecutor(10) as ex:
        res = list(ex.map(lambda _: priv.post(f"/api/tasks/{w.tid}/report/generate", tok), range(10)))
    assert {r.status_code for r in res} <= {202, 429}
    assert len({r.json()["job"]["id"] for r in res if r.status_code == 202}) == 1
    assert len(queued) == 1 and len(db.list_pdfs(w.tid)) == 1


def test_generate_is_rate_limited_per_user(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    monkeypatch.setattr(pdfjobs, "_submit", lambda jid: db.set_pdf_state(jid, "failed", "x"))
    monkeypatch.setattr(pdfjobs, "GEN_LIMIT", 2)
    tok = _tok(priv, "rizky")
    codes = [priv.post(f"/api/tasks/{w.tid}/report/generate", tok).status_code for _ in range(3)]
    assert codes == [202, 202, 429]
    assert "too many" in priv.post(f"/api/tasks/{w.tid}/report/generate", tok).json()["detail"].lower()


def test_a_failed_job_leaves_the_previous_pdf_alone(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    ok = _gen(priv, w.tid).json()["job"]
    before = db.get_pdf(ok["id"])
    db.set_finding(w.fids["Missing header"], verdict="fp")
    monkeypatch.setattr(pdf_deliver, "CONVERT", lambda _: (_ for _ in ()).throw(RuntimeError("soffice /secret/path died")))
    bad = _gen(priv, w.tid).json()["job"]
    assert bad["status"] == "failed" and "secret" not in (bad["error"] or "") and bad["n"] is None
    assert db.latest_ready_pdf(w.tid)["id"] == ok["id"] and db.get_pdf(ok["id"]) == before
    assert reportdoc.pdf_gap(db.get_proposal(w.tid, org_id=None))                     # and it is now out of date
    dl = priv.get(f"/api/tasks/{w.tid}/report/pdfs/{ok['id']}/download", _tok(priv, "rizky"))
    assert dl.status_code == 200
    monkeypatch.setattr(pdf_deliver, "CONVERT", fake_pdf)
    assert _gen(priv, w.tid).json()["job"]["n"] == 2                                  # the failure used no number


def test_conversion_timeout_and_missing_converter_have_plain_messages(monkeypatch, tmp_path):
    import subprocess
    w = world(monkeypatch, tmp_path)
    t = db.get_proposal(w.tid, org_id=None)
    monkeypatch.setattr(pdf_deliver, "CONVERT", lambda _: (_ for _ in ()).throw(subprocess.TimeoutExpired("soffice", 180)))
    job, _ = pdfjobs.request_pdf(t, "rizky", inline=True)
    assert "timed out" in db.get_pdf(job["id"])["error"]
    monkeypatch.setattr(pdf_deliver, "CONVERT", lambda _: (_ for _ in ()).throw(FileNotFoundError("soffice")))
    job2, _ = pdfjobs.request_pdf(t, "rizky", inline=True)
    assert "not installed" in db.get_pdf(job2["id"])["error"]


def test_stale_active_jobs_are_reaped_by_the_next_request(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    monkeypatch.setattr(pdfjobs, "_submit", lambda jid: None)
    stuck = priv.post(f"/api/tasks/{w.tid}/report/generate", _tok(priv, "rizky")).json()["job"]
    db.get_conn().execute("UPDATE report_pdfs SET updated_at='2000-01-01 00:00:00' WHERE id=?", (stuck["id"],))
    db.get_conn().commit()
    monkeypatch.setattr(pdfjobs, "_submit", pdfjobs.run_job)
    fresh = priv.post(f"/api/tasks/{w.tid}/report/generate", _tok(priv, "rizky")).json()["job"]
    assert fresh["id"] != stuck["id"] and fresh["status"] == "ready"
    assert db.get_pdf(stuck["id"])["status"] == "failed"


def test_who_may_generate(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    assert _gen(priv, w.tid, "budi").status_code == 403                       # a pentester who is not the assignee
    assert _gen(priv, w.tid, "sari").status_code == 403                       # a reviewer
    assert _gen(priv, w.tid, "dewi").status_code == 202                       # a lead pentester may
    assert priv.post("/api/tasks/nope/report/generate", _tok(priv, "rizky")).status_code == 404
    db.get_conn().execute("UPDATE proposals SET stage='review_lead_pentester' WHERE id=?", (w.tid,))
    db.get_conn().commit()
    assert _gen(priv, w.tid, "rizky").status_code == 409                      # wrong stage, even for the owner
    other = priv.get(f"/api/tasks/{w.tid}/report/jobs/nope", _tok(priv, "sari"))
    assert other.status_code == 404


def test_download_and_password_need_a_ready_pdf(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    tok = _tok(priv, "sari")
    assert priv.get(f"/api/tasks/{w.tid}/report/password", tok).status_code == 409
    assert priv.get(f"/api/tasks/{w.tid}/report/pdfs/nope/download", tok).status_code == 404
    monkeypatch.setattr(pdfjobs, "_submit", lambda jid: None)
    job = priv.post(f"/api/tasks/{w.tid}/report/generate", _tok(priv, "rizky")).json()["job"]
    assert priv.get(f"/api/tasks/{w.tid}/report/pdfs/{job['id']}/download", tok).status_code == 404   # queued, not ready


def test_ratelimit_counts_and_expires_by_key():
    from _fakeredis import FakeRedis
    import redis_store
    redis_store._client = FakeRedis()
    for _ in range(3):
        ratelimit.hit("k", 3, 60)
    with pytest.raises(ratelimit.RateLimited):
        ratelimit.hit("k", 3, 60)
    ratelimit.hit("other", 3, 60)
