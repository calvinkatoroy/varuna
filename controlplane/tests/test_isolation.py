"""A client of org A must never reach org B's data through ANY route. Fails when a route is added unscoped.

The sweep walks app.openapi() for both apps and calls every route with org B's real ids (proposal,
report, finding, job, report file). Org B's rows carry the markers "beta"/"jobB", so any leak shows
up in the response text; org B's state is re-checked afterwards so a write that "succeeded" quietly
is caught too.
"""
import itertools
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "report"))
import auth  # noqa: E402
import db  # noqa: E402
import redis_store  # noqa: E402
from conftest import make_client  # noqa: E402

PW = "Passw0rd!x"
# Another org's id is "no such row" (404). The one other accepted answer is a 403 from a role gate
# ("... role required"), which fires before any lookup on staff-only routes. Nothing else may refuse.
# One body that satisfies every action model (status/reject/verdict/template), so a refusal comes from
# the tenancy check and not from body validation. Nothing in it names org B.
BODY = {"status": "fixed", "reason": "x", "verdict": "fp", "template": "Full Technical",
        "to": "declined", "version": 0, "comment": "x"}


def _seed_org(name, user, host, job_id, reports_dir):
    import store
    org = make_client(user, name, PW)
    pid = db.create_proposal({"submitter": user, "target": f"http://{host}", "org_id": org,
                              "stage": "delivered", "job_id": job_id})
    redis_store.set_job({"id": job_id, "target": f"http://{host}", "submitter": user, "org_id": org,
                         "status": "done", "per_tool_status": {"katana": "done"}})
    redis_store.add_org_job(org, job_id)
    db.save_findings(job_id, user, org, [{"name": "XSS", "severity": "high", "host": host}])
    rid = db.create_report(job_id, org, user, stage="delivered")
    db.add_report_version(rid, filename=f"{rid}_v1.docx", editor="pen")
    db.set_report(rid, delivered_pdf=f"{rid}_delivered.pdf", pdf_password=f"pw-{user}", password_viewed=0)
    store.REPORTS_DIR = reports_dir
    store.save_report_file(f"{rid}_delivered.pdf", b"%PDF-1.4 " + user.encode())
    store.save_report_file(f"{rid}_v1.docx", b"PK " + user.encode())
    legacy = store.save_report(user, job_id, "Executive Summary", b"PK " + user.encode(), org_id=org)["file"]
    fid = db.list_findings(org_id=org)[0]["id"]
    return {"org": org, "pid": pid, "rid": rid, "fid": fid, "job_id": job_id, "fname": legacy}


def _seed_two_orgs(tmp_path):
    a = _seed_org("PT Alpha", "alpha", "alpha.co.id", "jobA", str(tmp_path))
    b = _seed_org("PT Beta", "beta", "beta.co.id", "jobB", str(tmp_path))
    return a, b


def _candidates(b):
    """Every path parameter name the two apps use, mapped to org B's real ids."""
    return {
        "pid": [b["pid"]], "tid": [b["pid"]], "rid": [b["rid"]], "fid": [b["fid"]], "job_id": [b["job_id"]],
        "fname": [b["fname"], f"{b['rid']}_delivered.pdf", f"{b['rid']}_v1.docx"],
        "id": [b["pid"], b["rid"]], "n": ["1"], "username": ["beta"], "action": ["disable"], "org_id": [b["org"]],
    }


def _sweep(app_api, token, b):
    cands = _candidates(b)
    hit = 0
    wrong = []
    for path, ops in app_api.app.openapi()["paths"].items():
        names = re.findall(r"\{(\w+)\}", path)
        for name in names:
            assert name in cands, f"new path parameter {name!r} in {path}: map it to an org-B id"
        for combo in itertools.product(*(cands[n] for n in names)):
            url = path
            for n, v in zip(names, combo):
                url = url.replace("{" + n + "}", v)
            for method in ops:
                r = app_api.request(method.upper(), url, token, json=BODY)
                hit += 1
                if names and not (r.status_code == 404 or
                                  (r.status_code == 403 and "role required" in r.text) or
                                  (path.startswith("/api/sysadmin/") and r.status_code == 403
                                   and "system administrator required" in r.text)):
                    wrong.append((method.upper(), path, url, r.status_code, r.text[:80]))
                body = r.text.replace(url, "")
                for marker in ("beta", "jobB", "PT Beta", b["pid"], b["rid"], b["fid"], "pw-beta"):
                    assert marker not in body, (method, url, marker, body[:200])
    assert not wrong, "org-B ids must be refused with 404:\n" + "\n".join(map(str, wrong))
    return hit


def _org_b_untouched(b):
    p = db.get_proposal(b["pid"], org_id=b["org"])
    assert p["stage"] == "delivered" and p["version"] == 0 and db.list_task_events(b["pid"]) == []
    f = db.get_finding(b["fid"], org_id=b["org"])
    assert f["status"] == "open" and f["verdict"] == "tp"
    r = db.get_report(b["rid"], org_id=b["org"])
    assert r["stage"] == "delivered" and r["password_viewed"] is False
    assert len(db.list_report_versions(b["rid"])) == 1
    assert redis_store.is_suspended(b["job_id"]) is False
    assert db.get_account("beta")["disabled"] == 0


def test_org_a_cannot_reach_org_b_on_public_plane(api, tmp_path):
    _, b = _seed_two_orgs(tmp_path)
    tok = api.login("alpha", PW)
    assert _sweep(api, tok, b) >= 32   # every public route (some with several org-B ids)
    _org_b_untouched(b)


def test_org_a_token_cannot_reach_org_b_on_private_plane(api, priv, tmp_path):
    _, b = _seed_two_orgs(tmp_path)
    tok = api.login("alpha", PW)   # a client cannot sign in on the private plane; reuse its public token
    assert _sweep(priv, tok, b) > 40
    _org_b_untouched(b)


def test_lists_hide_other_org(api, tmp_path):
    a, b = _seed_two_orgs(tmp_path)
    tok = api.login("alpha", PW)
    seen = {
        "/api/proposals": [p["id"] for p in api.get("/api/proposals", tok).json()],
        "/api/findings": [f["id"] for f in api.get("/api/findings", tok).json()],
        "/api/reports": [r["id"] for r in api.get("/api/reports", tok).json()],
        "/api/scans": [j["id"] for j in api.get("/api/scans", tok).json()],
    }
    assert seen == {"/api/proposals": [a["pid"]], "/api/findings": [a["fid"]],
                    "/api/reports": [a["rid"]], "/api/scans": [a["job_id"]]}
    cockpit = api.get("/api/cockpit", tok).json()
    assert [e["id"] for e in cockpit["engagements"]] == [a["pid"]]
    assert "beta" not in str(cockpit)


def test_org_members_share_their_org_data(api, tmp_path):
    a, _ = _seed_two_orgs(tmp_path)
    auth.create_account("alpha2", PW, "client", org_id=a["org"])
    tok = api.login("alpha2", PW)
    assert [p["id"] for p in api.get("/api/proposals", tok).json()] == [a["pid"]]
    assert api.get(f"/api/proposals/{a['pid']}", tok).status_code == 200
    assert api.get(f"/api/scans/{a['job_id']}", tok).status_code == 200


def test_client_cannot_see_other_orgs_scan(api, tmp_path):
    _, b = _seed_two_orgs(tmp_path)
    alpha, beta = api.login("alpha", PW), api.login("beta", PW)
    assert api.get(f"/api/scans/{b['job_id']}", alpha).status_code == 404
    assert api.get(f"/api/scans/{b['job_id']}/events", alpha).status_code == 404
    assert api.get(f"/api/scans/{b['job_id']}", beta).json()["status"] == "done"
    with api.c.stream("GET", f"/api/scans/{b['job_id']}/events",
                      headers={"Authorization": f"Bearer {beta}"}) as r:
        assert r.status_code == 200 and '"status": "done"' in "".join(r.iter_text())


@pytest.mark.parametrize("role", ["pentester", "lead_pentester", "governance"])
def test_staff_sees_both_orgs(priv, tmp_path, role):
    a, b = _seed_two_orgs(tmp_path)
    auth.create_account("staff1", PW, role)
    tok = priv.login("staff1", PW)
    assert {f["id"] for f in priv.get("/api/findings", tok).json()} == {a["fid"], b["fid"]}
    assert {r["id"] for r in priv.get("/api/pipeline/reports", tok).json()} == {a["rid"], b["rid"]}
    clients = {c["client"] for col in priv.get("/api/board", tok).json() for c in col["cards"]}
    assert clients == {"PT Alpha", "PT Beta"}
    for x in (a, b):
        assert priv.get(f"/api/tasks/{x['pid']}/detail", tok).status_code == 200
        assert priv.get(f"/api/pipeline/reports/{x['rid']}/versions", tok).status_code == 200


def test_sysadmin_has_no_tenant_access(api, priv, tmp_path):
    a, b = _seed_two_orgs(tmp_path)
    auth.create_account("root", PW, "sysadmin")
    tok = priv.login("root", PW)   # sysadmins sign in on the private plane only; the token is also tried on the public app
    for path in ("/api/proposals", "/api/findings", "/api/reports", "/api/scans", f"/api/proposals/{b['pid']}",
                 f"/api/tasks/{b['pid']}"):
        assert api.get(path, tok).status_code == 403, path
    # the private plane refuses a sysadmin's token on its tenant GET routes too
    for path in ("/api/findings", "/api/board", "/api/pipeline/reports", "/api/reports/all",
                 f"/api/findings/{b['job_id']}", f"/api/tasks/{a['pid']}/detail",
                 f"/api/pipeline/reports/{a['rid']}/versions", f"/api/scans/{b['job_id']}/events"):
        assert priv.get(path, tok).status_code == 403, path


def test_org_a_own_ids_work_so_the_sweep_is_not_vacuous(api, tmp_path):
    a, _ = _seed_two_orgs(tmp_path)
    tok = api.login("alpha", PW)
    assert api.get(f"/api/proposals/{a['pid']}", tok).status_code == 200
    assert api.get(f"/api/scans/{a['job_id']}", tok).status_code == 200
    assert api.post(f"/api/findings/{a['fid']}/status", tok, json={"status": "fixed"}).status_code == 200
    assert api.get(f"/api/reports/{a['rid']}/delivered", tok).status_code == 200


def test_sysadmin_cannot_submit_a_scan(api, priv):
    auth.create_account("root", PW, "sysadmin")
    tok = priv.login("root", PW)
    r = api.post("/api/scans", tok, json={"target": "http://t.example"})
    assert r.status_code == 403, r.text


def test_staff_scan_list_covers_every_org(api, tmp_path):
    a, b = _seed_two_orgs(tmp_path)
    redis_store.set_job({"id": "jobS", "submitter": "staff1", "org_id": None, "status": "done"})
    redis_store.add_org_job(None, "jobS")
    auth.create_account("staff1", PW, "pentester")
    staff = {j["id"] for j in api.get("/api/scans", api.login("staff1", PW)).json()}
    assert staff == {a["job_id"], b["job_id"], "jobS"}
    assert [j["id"] for j in api.get("/api/scans", api.login("alpha", PW)).json()] == [a["job_id"]]
