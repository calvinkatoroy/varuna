"""Board (step 2): columns by role, filtered in the query, refused when not visible."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import auth  # noqa: E402
import board  # noqa: E402
import db  # noqa: E402
from conftest import make_client, window  # noqa: E402

PW = "Passw0rd!x"
ALL = ["task", "scan", "completed", "review_lead_pentester", "review_lead_cyber", "review_governance",
       "review_manager", "delivered", "closed"]


def _seed():
    org = make_client("alice", "PT A")
    nb, na = window()
    ids = {}
    for stage, state in (("task", None), ("scan", "scheduled"), ("completed", None), ("review_lead_pentester", None),
                         ("review_lead_cyber", None), ("review_governance", None), ("review_manager", None),
                         ("delivered", None), ("declined", None), ("expired", None)):
        ids[stage] = db.create_proposal({"submitter": "alice", "org_id": org, "target": "http://8.8.8.8",
                                         "stage": stage, "scan_state": state, "assignee": "rizky",
                                         "not_before": nb, "not_after": na, "scheduled_at": na})
    return ids


@pytest.mark.parametrize("role", ["pentester", "lead_pentester"])
def test_pentesters_see_every_column(priv, role):
    _seed()
    auth.create_account("staff", PW, role)
    cols = priv.get("/api/board", priv.login("staff", PW)).json()
    assert [c["id"] for c in cols] == ALL and all(len(c["cards"]) >= 1 for c in cols)
    scan = next(c for c in cols if c["id"] == "scan")["cards"][0]
    assert scan["scanState"] == "scheduled" and scan["assignee"] == "rizky"
    assert len(next(c for c in cols if c["id"] == "closed")["cards"]) == 2


@pytest.mark.parametrize("role,own", [("lead_cyber", "review_lead_cyber"), ("governance", "review_governance"),
                                      ("manager", "review_manager")])
def test_reviewers_see_only_their_approval_list_and_delivered(priv, role, own):
    ids = _seed()
    auth.create_account("rev", PW, role)
    tok = priv.login("rev", PW)
    cols = priv.get("/api/board", tok).json()
    assert [c["id"] for c in cols] == [own, "delivered"]
    assert [k["id"] for k in cols[0]["cards"]] == [ids[own]]
    assert [a["kind"] for a in cols[0]["cards"][0]["actions"] if a["allowed"]] == \
        (["deliver", "send_back"] if role == "manager" else ["approve", "send_back"])
    assert priv.get("/api/board?column=task", tok).status_code == 403
    assert priv.get(f"/api/board?column={own}", tok).status_code == 200


def test_board_is_team_only(priv, api):
    make_client("alice", "PT A")
    assert priv.get("/api/board", api.login("alice", PW)).status_code == 403
    auth.create_account("root", PW, "sysadmin")
    assert priv.get("/api/board", priv.login("root", PW)).status_code == 403


def test_build_board_filters_by_stage_in_the_query(monkeypatch):
    _seed()
    seen = []
    real = db.list_proposals
    monkeypatch.setattr(board.db, "list_proposals", lambda *a, **k: seen.append(k.get("stage")) or real(*a, **k))
    board.build_board({"username": "x", "role": "governance"})
    assert seen == ["review_governance", "delivered"]
