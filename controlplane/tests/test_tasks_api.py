"""Task API (step 2): client routes on the public plane, staff transitions on the private plane."""
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
import auth  # noqa: E402
import db  # noqa: E402
import workflow  # noqa: E402
from conftest import make_client, window  # noqa: E402

PW = "Passw0rd!x"


def _body(**over):
    nb, na = window()
    return {"target": "http://8.8.8.8", "path": "/app", "port": 8080, "notes": "login: demo/demo",
            "not_before": nb, "not_after": na, "scan_mode": "cloud", **over}


def test_client_creates_task_org_and_submitter_from_the_account(api):
    org = make_client("alice", "PT A")
    make_client("bob", "PT B")
    tok = api.login("alice", PW)
    r = api.post("/api/tasks", tok, _body(org_id=db.get_account("bob")["org_id"], submitter="bob", stage="delivered"))
    assert r.status_code == 200, r.text
    t = db.get_proposal(r.json()["id"], org_id=None)
    assert (t["org_id"], t["submitter"], t["stage"]) == (org, "alice", "task")
    assert r.json()["status"] == "waiting" and "assignee" not in r.json()


@pytest.mark.parametrize("over", [
    {"not_before": "2026-10-08T09:00:00"},                    # naive
    {"not_after": "2001-01-01T00:00:00+00:00", "not_before": "2000-01-01T00:00:00+00:00"},
    {"target": "javascript:alert(1)"}, {"path": "no-slash"}, {"port": 0}, {"port": "80; rm -rf"},
    {"scan_mode": "bogus"}, {"target": "http://10.0.0.5", "scan_mode": "cloud"},
])
def test_bad_task_fields_are_422(api, over):
    make_client("alice", "PT A")
    tok = api.login("alice", PW)
    assert api.post("/api/tasks", tok, _body(**over)).status_code == 422


def test_task_lists_and_reads_are_org_scoped(api):
    make_client("alice", "PT A")
    make_client("carol", "PT A")                               # colleague, same organization
    make_client("bob", "PT B")
    tid = api.post("/api/tasks", api.login("alice", PW), _body()).json()["id"]
    assert [t["id"] for t in api.get("/api/tasks", api.login("carol", PW)).json()] == [tid]
    bob = api.login("bob", PW)
    assert api.get("/api/tasks", bob).json() == []
    assert api.get(f"/api/tasks/{tid}", bob).status_code == 404
    assert api.get(f"/api/tasks/{tid}/events", bob).status_code == 404
    one = api.get(f"/api/tasks/{tid}", api.login("carol", PW)).json()
    assert one["timeline"] == [{"status": "waiting", "at": one["timeline"][0]["at"]}]


def test_client_sees_decline_cause_but_no_staff_detail(api):
    make_client("alice", "PT A")
    auth.create_account("rizky", PW, "pentester")
    tok = api.login("alice", PW)
    tid = api.post("/api/tasks", tok, _body()).json()["id"]
    workflow.transition(tid, "declined", "rizky", org_id=None, comment="Mohon kirim bukti kepemilikan")
    row = api.get("/api/tasks", tok).json()[0]
    assert row["status"] == "declined" and row["reason"] == "Mohon kirim bukti kepemilikan"
    assert "rizky" not in api.get(f"/api/tasks/{tid}", tok).text
    assert api.get(f"/api/tasks/{tid}/events", tok).json()[-1]["note"] == "Mohon kirim bukti kepemilikan"


def test_staff_cannot_create_tasks(api):
    auth.create_account("rizky", PW, "pentester")              # the api fixture enables dev team login
    assert api.post("/api/tasks", api.login("rizky", PW), _body()).status_code == 403
