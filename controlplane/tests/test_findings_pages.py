"""Findings by target (step 3): grouped per task, paged on demand, one-record read. Clients keep seeing only
confirmed (tp) findings of their own organization; another organization's ids are 404."""
import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import auth  # noqa: E402
import db  # noqa: E402
from conftest import make_client  # noqa: E402

PW = "Passw0rd!x"
ORDER = ["critical", "high", "medium", "low", "info"]


def _rows(host, spec):
    return [{"name": f"{sev} issue {i:03d}", "severity": sev, "host": host, "url": f"https://{host}/p{i}",
             "evidence": "e" * 200, "remediation": "fix it"} for sev, n in spec.items() for i in range(n)]


def _seed(user, org_name, host, job_id, spec):
    org = make_client(user, org_name, PW)
    pid = db.create_proposal({"submitter": user, "org_id": org, "target": f"https://{host}",
                              "stage": "completed", "job_id": job_id})
    db.save_findings(job_id, user, org, _rows(host, spec))
    return org, pid


def _staff(priv, name="staff1", role="pentester"):
    auth.create_account(name, PW, role)
    return priv.login(name, PW)


def _by_name(job_id):
    return {f["name"]: f["id"] for f in db.get_findings(job_id)}


def test_targets_count_severity_fixed_and_hide_false_positives_from_clients(api):
    _, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"critical": 2, "high": 1, "low": 2, "info": 1})
    _seed("beta", "PT Beta", "b.co.id", "jobB", {"medium": 3})
    ids = _by_name("jobA")
    db.set_finding(ids["critical issue 000"], status="fixed")
    db.set_finding(ids["low issue 001"], verdict="fp")
    r = api.get("/api/findings/targets", api.login("alpha", PW))
    assert r.status_code == 200
    (t,) = r.json()
    assert t.pop("scanned_at")
    assert t == {"task_id": pid, "target": "https://a.co.id", "total": 5, "fixed": 1,
                 "counts": {"critical": 2, "high": 1, "medium": 0, "low": 1, "info": 1}}


def test_staff_targets_show_org_name_and_false_positive_count(priv):
    _, pa = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"critical": 2, "high": 1, "low": 2, "info": 1})
    _, pb = _seed("beta", "PT Beta", "b.co.id", "jobB", {"medium": 3})
    db.set_finding(_by_name("jobA")["low issue 001"], verdict="fp")
    rows = {t["task_id"]: t for t in priv.get("/api/findings/targets", _staff(priv)).json()}
    assert set(rows) == {pa, pb}
    assert rows[pa]["org_name"] == "PT Alpha" and rows[pa]["total"] == 6 and rows[pa]["fp"] == 1
    assert rows[pa]["counts"]["low"] == 2
    assert rows[pb]["org_name"] == "PT Beta" and rows[pb]["fp"] == 0


def test_pages_are_ordered_complete_and_light(api):
    _, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"critical": 30, "high": 70, "medium": 100, "low": 40, "info": 10})
    tok = api.login("alpha", PW)
    got, cursor, pages = [], None, 0
    while True:
        r = api.get(f"/api/findings?task_id={pid}&limit=100" + (f"&cursor={cursor}" if cursor else ""), tok)
        assert r.status_code == 200, r.text
        body = r.json()
        pages += 1
        got += body["items"]
        assert body["total"] == 250
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert pages == 3 and len(got) == 250 and len({f["id"] for f in got}) == 250
    ranks = [ORDER.index(f["severity"]) for f in got]
    assert ranks == sorted(ranks)
    assert [f["name"] for f in got[:3]] == ["critical issue 000", "critical issue 001", "critical issue 002"]
    assert set(got[0]) == {"id", "task_id", "name", "severity", "host", "url", "tool", "cve", "cwe", "verdict", "status"}
    assert got[0]["task_id"] == pid


def test_upto_returns_whole_pages_through_the_finding(api):
    _, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"critical": 30, "high": 70, "medium": 100, "low": 40, "info": 10})
    tok = api.login("alpha", PW)
    ids = [f["id"] for f in api.get(f"/api/findings?task_id={pid}&limit=200", tok).json()["items"]]
    assert len(ids) == 200
    r = api.get(f"/api/findings?task_id={pid}&limit=100&upto={ids[150]}", tok).json()
    assert [f["id"] for f in r["items"]] == ids and r["total"] == 250 and r["next_cursor"]
    rest = api.get(f"/api/findings?task_id={pid}&limit=100&cursor={r['next_cursor']}", tok).json()
    assert len(rest["items"]) == 50 and rest["next_cursor"] is None
    assert len(api.get(f"/api/findings?task_id={pid}&upto={ids[0]}", tok).json()["items"]) == 100
    assert len(api.get(f"/api/findings?task_id={pid}&upto={ids[99]}", tok).json()["items"]) == 100
    assert len(api.get(f"/api/findings?task_id={pid}&upto={ids[100]}", tok).json()["items"]) == 200
    last = api.get(f"/api/findings?task_id={pid}&upto={rest['items'][-1]['id']}", tok).json()
    assert len(last["items"]) == 250 and last["next_cursor"] is None


def test_severity_filter_changes_total(api):
    _, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"critical": 3, "high": 7, "info": 2})
    tok = api.login("alpha", PW)
    r = api.get(f"/api/findings?task_id={pid}&severity=HIGH", tok).json()
    assert r["total"] == 7 and {f["severity"] for f in r["items"]} == {"high"}
    assert api.get(f"/api/findings?task_id={pid}&severity=info", tok).json()["total"] == 2
    assert api.get(f"/api/findings?task_id={pid}&severity=medium", tok).json() == {"items": [], "next_cursor": None, "total": 0}


def test_bad_paging_input_is_422(api):
    _, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"high": 3})
    tok = api.login("alpha", PW)
    bad_cursor = base64.urlsafe_b64encode(b"o-5").decode()
    for q in (f"task_id={pid}&limit=0", f"task_id={pid}&limit=201", f"task_id={pid}&cursor=!!!",
              f"task_id={pid}&cursor={bad_cursor}", f"task_id={pid}&cursor=b2Fh&upto=x",
              f"task_id={pid}&severity=bogus", "cursor=b28w", "upto=x", "severity=high"):
        r = api.get(f"/api/findings?{q}", tok)
        assert r.status_code == 422, (q, r.status_code)
    assert api.get(f"/api/findings?task_id={pid}&upto=nope", tok).status_code == 404
    assert api.get("/api/findings?task_id=nope", tok).status_code == 404


def test_other_orgs_are_404(api):
    _, pa = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"high": 2})
    _, pb = _seed("beta", "PT Beta", "b.co.id", "jobB", {"high": 2})
    afid, bfid = db.get_findings("jobA")[0]["id"], db.get_findings("jobB")[0]["id"]
    ta = api.login("alpha", PW)
    for url in (f"/api/findings?task_id={pb}", "/api/findings?task_id=jobB", f"/api/findings?task_id={pa}&upto={bfid}",
                f"/api/findings/id/{bfid}"):
        r = api.get(url, ta)
        assert r.status_code == 404, url
        assert "beta" not in r.text.lower() and bfid not in r.text
    assert api.get(f"/api/findings/id/{afid}", ta).status_code == 200
    assert api.get(f"/api/findings?task_id={pa}", ta).json()["total"] == 2


def test_client_cannot_read_false_positives_by_id(api, priv):
    _, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"low": 2})
    fp = _by_name("jobA")["low issue 001"]
    db.set_finding(fp, verdict="fp")
    ta = api.login("alpha", PW)
    assert api.get(f"/api/findings/id/{fp}", ta).status_code == 404
    page = api.get(f"/api/findings?task_id={pid}", ta).json()
    assert page["total"] == 1 and fp not in [f["id"] for f in page["items"]]
    assert api.get(f"/api/findings?task_id={pid}&upto={fp}", ta).status_code == 404
    one = priv.get(f"/api/findings/id/{fp}", _staff(priv)).json()
    assert one["verdict"] == "fp" and one["org_name"] == "PT Alpha" and one["task_id"] == pid and one["evidence"]


def test_direct_scan_findings_are_their_own_target(api, priv):
    _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"high": 1})
    db.save_findings("jobS", "staff1", "", _rows("10.0.0.5", {"high": 2}))
    tok = _staff(priv)
    rows = {t["task_id"]: t for t in priv.get("/api/findings/targets", tok).json()}
    assert rows["jobS"]["target"] == "10.0.0.5" and rows["jobS"]["org_name"] == "Internal" and rows["jobS"]["total"] == 2
    assert priv.get("/api/findings?task_id=jobS", tok).json()["total"] == 2
    ta = api.login("alpha", PW)
    assert all(t["task_id"] != "jobS" for t in api.get("/api/findings/targets", ta).json())
    assert api.get("/api/findings?task_id=jobS", ta).status_code == 404


def test_sysadmin_has_no_findings_access(priv):
    auth.create_account("root", PW, "sysadmin")
    tok = priv.login("root", PW)
    for path in ("/api/findings/targets", "/api/findings?task_id=x", "/api/findings/id/x"):
        assert priv.get(path, tok).status_code == 403, path


def test_private_targets_route_is_not_swallowed_by_the_job_route(priv):
    _, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"high": 3})
    tok = _staff(priv, role="lead_pentester")
    r = priv.get("/api/findings/targets", tok)
    assert r.status_code == 200 and isinstance(r.json(), list) and r.json()[0]["task_id"] == pid
    legacy = priv.get("/api/findings/jobA", tok)
    assert legacy.status_code == 200 and len(legacy.json()) == 3


def test_five_hundred_findings_first_page_stays_small(api):
    _, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"critical": 20, "high": 80, "medium": 200, "low": 150, "info": 70})
    tok = api.login("alpha", PW)
    t = api.get("/api/findings/targets", tok).json()
    assert t[0]["total"] == 520 and sum(t[0]["counts"].values()) == 520
    r = api.get(f"/api/findings?task_id={pid}", tok)
    body = r.json()
    assert len(body["items"]) == 100 and body["total"] == 520 and body["next_cursor"]
    assert len(r.content) < 60_000


def test_legacy_flat_list_is_unchanged(api, priv):
    _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"high": 2})
    flat = api.get("/api/findings", api.login("alpha", PW)).json()
    assert isinstance(flat, list) and len(flat) == 2 and "evidence" in flat[0]
    assert isinstance(api.get("/api/findings?limit=50", api.login("alpha", PW)).json(), list)
    staff = priv.get("/api/findings", _staff(priv)).json()
    assert isinstance(staff, list) and staff[0]["org_name"] == "PT Alpha"


def test_huge_negative_or_garbage_cursors_are_422(api):
    _, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"high": 3})
    tok = api.login("alpha", PW)
    enc = lambda raw: base64.urlsafe_b64encode(raw).decode().rstrip("=")
    for c in (enc(b"o" + b"9" * 30), enc(b"o" + str(10**9 + 1).encode()), enc(b"o-1"), enc(b"o"), enc(b"o1.5"),
              enc(b"x5"), enc("o١".encode()), "not base64 at all", "%FF%FE", "AAAA"):
        r = api.get(f"/api/findings?task_id={pid}&cursor={c}", tok)
        assert r.status_code == 422, (c, r.status_code)
    assert api.get(f"/api/findings?task_id={pid}&cursor={enc(b'o' + str(10**9).encode())}", tok).status_code == 200


def test_staff_plane_rejects_a_huge_cursor_too(priv):
    _, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"high": 3})
    bad = base64.urlsafe_b64encode(b"o" + b"9" * 30).decode().rstrip("=")
    assert priv.get(f"/api/findings?task_id={pid}&cursor={bad}", _staff(priv)).status_code == 422


def test_findings_of_every_job_of_a_task_group_under_the_task(api):
    org, pid = _seed("alpha", "PT Alpha", "a.co.id", "jobA", {"high": 2, "info": 1})
    db.update_proposal(pid, job_id="jobA2")   # a resume after a failed job starts a new one
    db.save_findings("jobA2", "alpha", org, _rows("a.co.id", {"critical": 1, "medium": 2}))
    tok = api.login("alpha", PW)
    (t,) = api.get("/api/findings/targets", tok).json()
    assert t["task_id"] == pid and t["total"] == 6 and t["counts"] == {"critical": 1, "high": 2, "medium": 2, "low": 0, "info": 1}
    page = api.get(f"/api/findings?task_id={pid}", tok).json()
    assert page["total"] == 6 and len(page["items"]) == 6
    old = _by_name("jobA")["high issue 000"]
    assert api.get(f"/api/findings/id/{old}", tok).json()["task_id"] == pid
    assert db.get_proposal_by_job("jobA")["id"] == pid


def test_task_jobs_are_backfilled_for_existing_rows():
    org = make_client("alpha", "PT Alpha", PW)
    pid = db.create_proposal({"submitter": "alpha", "org_id": org, "target": "https://a.co.id", "job_id": "jobA"})
    conn = db.get_conn()
    conn.execute("DELETE FROM task_jobs")   # a database from before the table existed
    conn.commit()
    db.init_db(conn)
    assert [r["job_id"] for r in conn.execute("SELECT job_id FROM task_jobs WHERE task_id=?", (pid,))] == ["jobA"]
