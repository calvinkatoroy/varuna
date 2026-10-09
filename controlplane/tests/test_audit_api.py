"""Audit routes: who may do what at which stage, finding edits, manual findings, the verdict guard, the trail,
content versions, and the submit guard."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from audit_helpers import PW, world  # noqa: E402,F401
import db  # noqa: E402
import reportdoc  # noqa: E402
import workflow  # noqa: E402

MANUAL = {"name": "Exposed admin panel", "severity": "High", "host": "8.8.8.8", "url": "/admin",
          "description": "Reachable without VPN.", "evidence": "GET /admin -> 200 <title>Admin</title>",
          "remediation": "Restrict by IP.", "impact": "Takeover risk."}


def tok(priv, who):
    return priv.login(who, PW)


def test_summary_for_owner_and_reviewer(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    own = priv.get(f"/api/tasks/{w.tid}/audit", tok(priv, "rizky")).json()
    assert own["can_audit"] is True and own["content_version"] == 1 and own["ai_chat"] is True
    assert own["counts"]["total"] == 2 and own["counts"]["tp"] == 2 and own["pdf"]["current"] is False
    assert own["task"]["client"] == "PT A" and own["task"]["stage"] == "completed"
    for who in ("sari", "budi"):
        assert priv.get(f"/api/tasks/{w.tid}/audit", tok(priv, who)).json()["can_audit"] is False
    assert priv.get(f"/api/tasks/{w.tid}/audit", tok(priv, "dewi")).json()["can_audit"] is True
    assert priv.get("/api/tasks/nope/audit", tok(priv, "rizky")).status_code == 404
    early = db.create_proposal({"submitter": "alice", "org_id": w.org, "target": "http://t", "stage": "task"})
    assert priv.get(f"/api/tasks/{early}/audit", tok(priv, "rizky")).status_code == 409


def test_reviewers_read_everything_and_change_nothing(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    rev = tok(priv, "sari")
    base = f"/api/tasks/{w.tid}"
    for path in (f"{base}/audit", f"{base}/audit/trail", f"{base}/report/content", f"/api/findings?task_id={w.tid}"):
        assert priv.get(path, rev).status_code == 200, path
    for path, body in ((f"{base}/findings/manual", MANUAL), (f"{base}/findings/{w.fids['Missing header']}/edit", {"severity": "low"}),
                       (f"{base}/report/restore", {"version": 1, "base_version": 1}), (f"{base}/report/generate", None)):
        assert priv.post(path, rev, body).status_code == 403, path
    db.get_conn().execute("UPDATE proposals SET stage='review_lead_pentester' WHERE id=?", (w.tid,))
    db.get_conn().commit()
    assert priv.get(f"{base}/audit", rev).status_code == 200                      # still readable after the stage moved on
    own = tok(priv, "rizky")
    for path, body in ((f"{base}/findings/manual", MANUAL), (f"{base}/report/restore", {"version": 1, "base_version": 1})):
        assert priv.post(path, own, body).status_code == 409, path               # the owner too: Completed only


def test_manual_finding_flows_into_the_report_and_the_trail(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    r = priv.post(f"/api/tasks/{w.tid}/findings/manual", tok(priv, "rizky"), MANUAL)
    assert r.status_code == 200, r.text
    f = db.get_finding(r.json()["id"], org_id=w.org)
    assert (f["tool"], f["severity"], f["org_id"], f["job_id"], f["verdict"]) == ("manual", "high", w.org, "j1", "tp")
    assert f["remediation"] == "Restrict by IP." and "<title>Admin</title>" in f["evidence"]   # human text kept as typed
    t = db.get_proposal(w.tid, org_id=None)
    assert "Exposed admin panel" in {x["name"] for x in reportdoc.findings_for(t)}
    assert priv.get(f"/api/findings?task_id={w.tid}", tok(priv, "rizky")).json()["total"] == 3
    trail = priv.get(f"/api/tasks/{w.tid}/audit/trail", tok(priv, "sari")).json()
    assert trail[0]["action"] == "manual_add" and trail[0]["actor"] == "rizky" and trail[0]["subject"] == r.json()["id"]


def test_manual_finding_validation_and_roles(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    own, url = tok(priv, "rizky"), f"/api/tasks/{w.tid}/findings/manual"
    assert priv.post(url, own, {**MANUAL, "severity": "scary"}).status_code == 422
    assert priv.post(url, own, {**MANUAL, "name": "   "}).status_code == 422
    assert priv.post(url, own, {**MANUAL, "name": "x" * 301}).status_code == 422
    ok = priv.post(url, own, {**MANUAL, "host": ""})                              # blank host = the task's host
    assert db.get_finding(ok.json()["id"], org_id=w.org)["host"] == "8.8.8.8"
    assert priv.post(url, tok(priv, "budi"), MANUAL).status_code == 403
    assert priv.post(url, tok(priv, "dewi"), MANUAL).status_code == 200            # a lead may
    nojob = db.create_proposal({"submitter": "alice", "org_id": w.org, "target": "http://t", "stage": "completed",
                                "assignee": "rizky"})
    assert priv.post(f"/api/tasks/{nojob}/findings/manual", own, MANUAL).status_code == 409


def test_a_repeated_scan_upload_does_not_erase_manual_findings():
    org = db.create_org("PT A")
    db.save_findings("j1", "alice", org, [{"name": "A", "severity": "low", "host": "h"}])
    tid = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://t", "stage": "completed", "job_id": "j1"})
    t = db.get_proposal(tid, org_id=None)
    fid = db.insert_manual_finding(t, {"name": "Manual", "severity": "high", "host": "h"})
    db.save_findings("j1", "alice", org, [{"name": "B", "severity": "low", "host": "h"}])
    assert {f["name"] for f in db.get_findings("j1")} == {"B", "Manual"}
    db.save_findings("j1", "alice", org, [])
    assert [f["id"] for f in db.get_findings("j1")] == [fid]


def test_edit_a_finding(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    own, fid = tok(priv, "rizky"), w.fids["Missing header"]
    url = f"/api/tasks/{w.tid}/findings/{fid}/edit"
    assert priv.post(url, own, {"severity": "Medium", "impact": "New impact.", "remediation": "New fix."}).status_code == 200
    f = db.get_finding(fid, org_id=w.org)
    assert (f["severity"], f["impact"], f["remediation"]) == ("medium", "New impact.", "New fix.")
    assert priv.post(url, own, {"severity": "scary"}).status_code == 422
    assert priv.post(url, own, {}).status_code == 422
    assert priv.post(url, tok(priv, "budi"), {"severity": "low"}).status_code == 403
    other = db.create_proposal({"submitter": "alice", "org_id": w.org, "target": "http://o", "stage": "completed",
                                "assignee": "rizky", "job_id": "j2"})
    assert priv.post(f"/api/tasks/{other}/findings/{fid}/edit", own, {"severity": "low"}).status_code == 404   # not that task's
    row = priv.get(f"/api/tasks/{w.tid}/audit/trail", own).json()[0]
    assert row["action"] == "finding_edit" and row["detail"]["after"]["severity"] == "medium"


def test_verdict_is_guarded_for_task_findings_but_not_for_direct_scans(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    fid, url = w.fids["Missing header"], lambda f: f"/api/findings/{f}/verdict"
    assert priv.post(url(fid), tok(priv, "budi"), {"verdict": "fp"}).status_code == 403     # not the assignee
    assert priv.post(url(fid), tok(priv, "sari"), {"verdict": "fp"}).status_code == 403
    assert priv.post(url(fid), tok(priv, "rizky"), {"verdict": "fp"}).status_code == 200
    assert db.get_finding(fid, org_id=w.org)["verdict"] == "fp"
    assert priv.post(url(fid), tok(priv, "dewi"), {"verdict": "tp"}).status_code == 200
    assert priv.post(url(fid), tok(priv, "rizky"), {"verdict": "maybe"}).status_code == 422
    assert priv.post(url("nope"), tok(priv, "rizky"), {"verdict": "fp"}).status_code == 404
    acts = [a["action"] for a in priv.get(f"/api/tasks/{w.tid}/audit/trail", tok(priv, "rizky")).json()]
    assert acts == ["verdict", "verdict"]
    db.get_conn().execute("UPDATE proposals SET stage='review_lead_pentester' WHERE id=?", (w.tid,))
    db.get_conn().commit()
    assert priv.post(url(fid), tok(priv, "rizky"), {"verdict": "fp"}).status_code == 409    # after Completed: send it back first
    db.save_findings("direct", "budi", "", [{"name": "X", "severity": "low", "host": "h"}])
    direct = db.get_findings("direct")[0]["id"]                                              # a staff scan has no task or audit page
    assert priv.post(url(direct), tok(priv, "budi"), {"verdict": "fp"}).status_code == 200
    assert priv.post(url(direct), tok(priv, "sari"), {"verdict": "tp"}).status_code == 200


def test_content_preview_versions_and_restore(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    own, base = tok(priv, "rizky"), f"/api/tasks/{w.tid}"
    c = priv.get(f"{base}/report/content", own).json()
    assert c["version"] == 1 and [s["id"] for s in c["preview"]][:2] == ["cover", "executive_summary"]
    assert [v["version"] for v in c["versions"]] == [1]
    edited = db.latest_content(w.tid)["content"]
    edited["sections"][1]["blocks"][0]["text"] = "Edited."
    assert db.add_content(w.tid, w.org, edited, "rizky", "x", base_version=1) == 2
    r = priv.post(f"{base}/report/restore", own, {"version": 1, "base_version": 2})
    assert r.status_code == 200 and r.json()["version"] == 3
    assert db.latest_content(w.tid)["content"] == db.get_content(w.tid, 1)["content"]
    assert priv.post(f"{base}/report/restore", own, {"version": 1, "base_version": 2}).status_code == 409   # stale tab
    assert priv.post(f"{base}/report/restore", own, {"version": 99, "base_version": 3}).status_code == 404
    assert priv.post(f"{base}/report/restore", tok(priv, "budi"), {"version": 1, "base_version": 3}).status_code == 403
    assert priv.get(f"{base}/audit/trail", own).json()[0]["action"] == "content_restore"


def test_submit_for_review_needs_a_current_pdf(priv, monkeypatch, tmp_path):
    w = world(monkeypatch, tmp_path)
    submit = lambda who, to="review_lead_pentester": priv.post(
        f"/api/tasks/{w.tid}/transition", tok(priv, who),
        {"to": to, "version": db.get_proposal(w.tid, org_id=None)["version"], "comment": "back to you"})
    r = submit("rizky")
    assert r.status_code == 409 and "PDF" in r.json()["detail"]
    acts = {a["kind"]: a for a in workflow.actions(db.get_proposal(w.tid, org_id=None), "rizky")}
    assert acts["submit"]["allowed"] is False and "PDF" in acts["submit"]["why"]
    assert priv.post(f"/api/tasks/{w.tid}/report/generate", tok(priv, "rizky")).status_code == 202
    acts = {a["kind"]: a for a in workflow.actions(db.get_proposal(w.tid, org_id=None), "rizky")}
    assert acts["submit"]["allowed"] is True
    db.set_finding(w.fids["Missing header"], verdict="fp")                               # changed after the PDF
    assert submit("rizky").status_code == 409
    assert priv.post(f"/api/tasks/{w.tid}/report/generate", tok(priv, "rizky")).status_code == 202
    assert submit("budi").status_code == 403                                              # still only the owner
    assert submit("rizky").status_code == 200
    assert db.get_proposal(w.tid, org_id=None)["stage"] == "review_lead_pentester"
    assert submit("dewi", "completed").status_code == 200                                 # the lead sends it back
    assert submit("rizky").status_code == 200                                             # nothing changed: the PDF is still current
