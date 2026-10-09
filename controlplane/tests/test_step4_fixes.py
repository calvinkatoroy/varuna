"""Step 4 fix pass: client status vs the audited PDF, removed public report route, recovery lookup, key rotation,
edit-vs-submit race, render-time cleaning, wipe, client visibility."""
import io
import os
import sys

import pytest
from docx import Document

sys.path.insert(0, os.path.dirname(__file__))
from audit_helpers import PW, world  # noqa: E402,F401
import db  # noqa: E402
import reportcontent  # noqa: E402
import reportdoc  # noqa: E402
import reportrender  # noqa: E402


def _docx_text(data: bytes) -> str:
    d = Document(io.BytesIO(data))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        parts += [c.text for r in t.rows for c in r.cells]
    return "\n".join(parts)


def _stage(tid, stage):
    db.get_conn().execute("UPDATE proposals SET stage=? WHERE id=?", (stage, tid))
    db.get_conn().commit()


def _render(w):
    t = db.get_proposal(w.tid, org_id=None)
    c = reportcontent.ensure_v1(t)
    return reportrender.render_docx(c["content"], t, "PT A", reportdoc.findings_for(t))


# --- 1. client status ---
def test_report_does_not_print_the_client_status(monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    before = _docx_text(_render(w))
    assert "Status" not in before
    t = db.get_proposal(w.tid, org_id=None)
    dg = reportdoc.digest(reportdoc.findings_for(t))
    db.set_finding(w.fids["SQL injection"], status="fixed")
    assert "Fixed" not in _docx_text(_render(w))
    assert reportdoc.digest(reportdoc.findings_for(t)) == dg


def test_client_status_is_blocked_until_delivery(api, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    tok = api.login("alice", PW)
    url = f"/api/findings/{w.fids['SQL injection']}/status"
    for stage in ("completed", "review_lead_pentester", "review_manager"):
        _stage(w.tid, stage)
        r = api.post(url, tok, {"status": "fixed"})
        assert r.status_code == 409 and "after the report is delivered" in r.text, stage
        assert db.get_finding(w.fids["SQL injection"], org_id=None)["status"] == "open"
    _stage(w.tid, "delivered")
    assert api.post(url, tok, {"status": "fixed"}).status_code == 200
    assert db.get_finding(w.fids["SQL injection"], org_id=None)["status"] == "fixed"


# --- 2. no unreviewed report on the public plane ---
def test_public_plane_has_no_legacy_report_routes(api, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    tok = api.login("alice", PW)
    paths = api.app.openapi()["paths"]
    assert "/api/scans/{job_id}/report" not in paths and "/api/reports/{fname}/download" not in paths
    assert api.post("/api/scans/j1/report", tok).status_code in (404, 405)
    assert api.get("/api/reports/anything.docx/download", tok).status_code in (404, 405)


# --- 3. delivery recovery finds the report by task ---
def test_recovery_uses_the_task_report_even_when_the_job_id_changed(monkeypatch, tmp_path):
    import datetime as dt
    import scheduler
    w = world(monkeypatch, tmp_path)
    monkeypatch.setattr(scheduler.notify, "notify", lambda *_: None)
    t = db.get_proposal(w.tid, org_id=None)
    rid = reportdoc.ensure_report(t)["id"]                       # made for job j1
    db.get_conn().execute("UPDATE proposals SET stage='delivering', job_id='j2-resumed' WHERE id=?", (w.tid,))
    db.get_conn().commit()
    db.set_report(rid, stage="delivered")                         # delivery died right after this
    out = scheduler.tick(dt.datetime.now(dt.UTC) + dt.timedelta(minutes=11))
    assert db.get_proposal(w.tid, org_id=None)["stage"] == "delivered" and out["recovered"] == 1


# --- 4. password sealing keys ---
@pytest.fixture
def keys(monkeypatch):
    import jwt_auth
    for k in ("VARUNA_SECRET_KEY", "VARUNA_SECRET_KEY_OLD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(jwt_auth, "JWT_SECRET", "jwt-secret-" + "x" * 30)

    def use(current=None, old=None):
        for name, val in (("VARUNA_SECRET_KEY", current), ("VARUNA_SECRET_KEY_OLD", old)):
            if val is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, val)
    return use


def test_sealed_password_survives_key_rotation(keys):
    import pdfpass
    keys("key-A")
    sealed = pdfpass.seal("hunter2")
    keys("key-B", "key-A")                       # rotate: B is current, A kept as old
    assert pdfpass.unseal(sealed) == "hunter2"
    fresh = pdfpass.seal("other")
    keys("key-B")                                 # A can be dropped once everything is re-sealed with B
    assert pdfpass.unseal(fresh) == "other"
    keys("key-C", "key-X, key-B")                 # comma separated list of old keys
    assert pdfpass.unseal(fresh) == "other"


def test_values_sealed_with_the_jwt_key_still_open_after_adding_a_secret_key(keys):
    import pdfpass
    keys(None)
    legacy = pdfpass.seal("old-password")         # what the code did before VARUNA_SECRET_KEY existed
    keys("key-A")
    assert pdfpass.unseal(legacy) == "old-password"
    assert pdfpass.unseal(pdfpass.seal("x")) == "x"


def test_unreadable_password_is_a_fixed_error_and_a_log_line(keys, caplog, api, monkeypatch, tmp_path):
    import pdfpass
    w = world(monkeypatch, tmp_path)
    keys("key-A")
    rid = reportdoc.ensure_report(db.get_proposal(w.tid, org_id=None))["id"]
    db.set_report(rid, stage="delivered", delivered_pdf="x.pdf", pdf_password=pdfpass.seal("pw"))
    keys("key-C")                                 # the key it was sealed with is gone
    with pytest.raises(pdfpass.Unavailable):
        pdfpass.unseal(db.get_report(rid, org_id=None)["pdf_password"])
    caplog.clear()
    r = api.get(f"/api/reports/{rid}/password", api.login("alice", PW))
    assert r.status_code == 503 and r.json()["detail"] == "The report password cannot be read; contact your administrator."
    assert "cannot be decrypted" in caplog.text


def test_unreadable_password_fails_the_pdf_job_with_the_fixed_sentence(keys, priv, monkeypatch, tmp_path):
    import pdfpass
    w = world(monkeypatch, tmp_path)
    keys("key-A")
    rid = reportdoc.ensure_report(db.get_proposal(w.tid, org_id=None))["id"]
    db.set_report(rid, pdf_password=pdfpass.seal("pw"))
    keys("key-C")
    r = priv.post(f"/api/tasks/{w.tid}/report/generate", priv.login("rizky", PW))
    assert r.status_code == 202 and r.json()["job"]["status"] == "failed"
    assert r.json()["job"]["error"] == "The report password cannot be read; contact your administrator."
    assert priv.get(f"/api/tasks/{w.tid}/report/password", priv.login("rizky", PW)).status_code in (409, 503)


def test_the_public_default_key_never_seals_unless_allowed(keys, monkeypatch):
    import jwt_auth
    import pdfpass
    keys(None)
    monkeypatch.setattr(jwt_auth, "JWT_SECRET", "dev-only-change-me")
    monkeypatch.delenv("VARUNA_ALLOW_DEV_KEY", raising=False)
    with pytest.raises(pdfpass.Unavailable):
        pdfpass.seal("pw")
    monkeypatch.setenv("VARUNA_ALLOW_DEV_KEY", "1")
    assert pdfpass.unseal(pdfpass.seal("pw")) == "pw"
    monkeypatch.delenv("VARUNA_ALLOW_DEV_KEY")
    keys("a-real-secret-key")                      # a configured key overrides the default
    assert pdfpass.unseal(pdfpass.seal("pw")) == "pw"


def test_startup_check_warns_when_no_key_opens_the_stored_passwords(keys, caplog, monkeypatch, tmp_path):
    import logging
    import pdfpass
    w = world(monkeypatch, tmp_path)
    rid = reportdoc.ensure_report(db.get_proposal(w.tid, org_id=None))["id"]
    keys("key-A")
    pdfpass.check_sealed()
    db.set_report(rid, pdf_password=pdfpass.seal("pw"))
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        pdfpass.check_sealed()
        assert caplog.text == ""                  # readable: silent
        keys("key-C")
        pdfpass.check_sealed()
    assert "WARNING" in caplog.text.upper() and "VARUNA_SECRET_KEY" in caplog.text
