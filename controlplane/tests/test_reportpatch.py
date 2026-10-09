"""The AI patch schema: what the model may change, and how everything else is refused."""
import copy
import json
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "report"))
import reportcontent  # noqa: E402
import reportpatch as rp  # noqa: E402

FIDS = {"f1", "f2"}


def _content():
    return reportcontent.baseline({"target": "http://8.8.8.8"}, "PT A")


def _sec(c, sid):
    return next(s for s in c["sections"] if s["id"] == sid)


def _bid(c, sid, i):
    return _sec(c, sid)["blocks"][i]["id"]


def _data(*ops, summary="ok"):
    return {"summary": summary, "ops": list(ops)}


def _bad(*ops, why=None, data=None):
    with pytest.raises(rp.PatchError) as e:
        rp.validate(data or _data(*ops), _content(), FIDS)
    if why:
        assert why in str(e.value)


def test_replace_text_validates_applies_and_leaves_the_original_alone():
    c = _content()
    before = copy.deepcopy(c)
    bid = _bid(c, "executive_summary", 0)
    res = rp.validate(_data({"op": "replace_text", "id": bid, "text": "A shorter summary."}), c, FIDS)
    assert res["ops"] == [{"op": "replace_text", "id": bid, "text": "A shorter summary.", "sanitized": False}]
    new = rp.apply_ops(c, res["ops"])
    assert _sec(new, "executive_summary")["blocks"][0]["text"] == "A shorter summary." and c == before


def test_insert_after_adds_a_flagged_block_with_a_server_chosen_id():
    c = _content()
    anchor = _bid(c, "methodology", 1)
    res = rp.validate(_data({"op": "insert_after", "id": anchor, "type": "bullet", "text": "Extra step."}), c, FIDS)
    new = rp.apply_ops(c, res["ops"])
    blocks = _sec(new, "methodology")["blocks"]
    added = blocks[2]
    assert added["text"] == "Extra step." and added["type"] == "bullet" and added["ai"] is True and added["editable"] is True
    ids = [b["id"] for s in new["sections"] for b in s["blocks"]]
    assert len(ids) == len(set(ids)) and added["id"] not in [b["id"] for b in _sec(c, "methodology")["blocks"]]


def test_remove_and_set_finding_text():
    c = _content()
    bid = _bid(c, "methodology", 1)
    res = rp.validate(_data({"op": "remove", "id": bid},
                            {"op": "set_finding_text", "finding_id": "f1", "field": "remediation", "text": "Patch it."}), c, FIDS)
    new = rp.apply_ops(c, res["ops"])
    assert bid not in [b["id"] for b in _sec(new, "methodology")["blocks"]]
    ov = next(b for s in new["sections"] for b in s["blocks"] if b["type"] == "finding_overrides")
    assert ov["overrides"] == {"f1": {"remediation": "Patch it."}}


def test_text_is_cleaned_and_flagged():
    c = _content()
    bid = _bid(c, "conclusion", 0)
    res = rp.validate(_data({"op": "replace_text", "id": bid,
                             "text": "**Fix** [now](javascript:alert(1)) <b>fast</b>\u202e"}), c, FIDS)
    assert res["ops"][0]["text"] == "Fix now fast" and res["ops"][0]["sanitized"] is True


def test_summary_is_cleaned_and_capped():
    res = rp.validate(_data(summary="<i>Did</i> **it** " + "x" * 400), _content(), FIDS)
    assert "<" not in res["summary"] and len(res["summary"]) <= rp.LIMIT["summary"]


def test_refusals():
    c = _content()
    ex, cov, sev = _bid(c, "executive_summary", 0), _bid(c, "scope", 1), _bid(c, "executive_summary", 1)
    _bad({"op": "replace_text", "id": cov, "text": "gone"}, why="locked")                       # the coverage disclaimer
    _bad({"op": "replace_text", "id": sev, "text": "x"}, why="locked")                           # a computed table
    _bad({"op": "remove", "id": cov}, why="locked")
    _bad({"op": "replace_text", "id": "b999", "text": "x"}, why="unknown block")
    _bad({"op": "drop_table", "id": ex}, why="unknown op")
    _bad({"op": "replace_text", "id": ex, "text": "x", "extra": 1}, why="exactly the keys")
    _bad({"op": "replace_text", "id": ex}, why="exactly the keys")
    _bad({"op": "insert_after", "id": cov, "type": "paragraph", "text": "x"}, why="nothing can be added")   # scope: no ai_insert
    _bad({"op": "insert_after", "id": ex, "type": "heading", "text": "x"}, why="paragraph or bullet")
    _bad({"op": "replace_text", "id": ex, "text": "a"}, {"op": "remove", "id": ex}, why="twice")
    _bad({"op": "replace_text", "id": ex, "text": "x" * 1501}, why="longer than 1500")
    _bad({"op": "insert_after", "id": ex, "type": "bullet", "text": "x" * 401}, why="longer than 400")
    _bad({"op": "replace_text", "id": ex, "text": "<b></b> **"}, why="empty after cleaning")
    _bad({"op": "replace_text", "id": ex, "text": 5}, why="must be a string")
    _bad({"op": "set_finding_text", "finding_id": "other", "field": "impact", "text": "x"}, why="unknown finding")
    _bad({"op": "set_finding_text", "finding_id": "f1", "field": "severity", "text": "x"}, why="impact or remediation")
    _bad(*[{"op": "replace_text", "id": ex, "text": "x"}] * 13, why="at most 12")
    _bad({"op": "remove", "id": _bid(c, "methodology", 1)}, {"op": "insert_after", "id": _bid(c, "methodology", 1),
                                                              "type": "bullet", "text": "x"}, why="no longer exists")
    _bad(data={"summary": 5, "ops": []}, why="summary")
    _bad(data={"summary": "x", "ops": "nope"}, why="list")


def test_a_section_takes_at_most_twelve_added_blocks():
    c = _content()
    anchor = _bid(c, "conclusion", 0)
    ops = [{"op": "insert_after", "id": anchor, "type": "bullet", "text": f"Item {i}."} for i in range(12)]
    new = rp.apply_ops(c, rp.validate(_data(*ops), c, FIDS)["ops"])
    again = [{"op": "insert_after", "id": anchor, "type": "bullet", "text": "One more."}]
    with pytest.raises(rp.PatchError, match="too many"):
        rp.validate(_data(*again), new, FIDS)


def test_parse_patch():
    assert rp.parse_patch('{"summary": "s", "ops": []}') == {"summary": "s", "ops": []}
    for raw in ("not json", "[]", '{"summary": "s"}', '{"summary": "s", "ops": [], "x": 1}', None):
        with pytest.raises(rp.PatchError):
            rp.parse_patch(raw)


def test_structure_cannot_change_even_if_the_ops_were_buggy():
    c = _content()
    tampered = copy.deepcopy(c)
    tampered["sections"][1]["title"] = "Executive Summary (edited)"
    with pytest.raises(rp.PatchError, match="structure"):
        rp.check_structure(c, tampered)
    locked = copy.deepcopy(c)
    _sec(locked, "scope")["blocks"][1]["text"] = "changed"
    with pytest.raises(rp.PatchError, match="locked"):
        rp.check_structure(c, locked)
    gone = copy.deepcopy(c)
    del _sec(gone, "findings_summary")["blocks"][0]
    with pytest.raises(rp.PatchError, match="structure"):
        rp.check_structure(c, gone)


def test_context_has_only_editable_text_and_short_finding_stubs():
    c = _content()
    stubs = [{"finding_id": "f1", "ref": "VAR-001", "name": "SQLi", "severity": "critical",
              "impact": "i" * 900, "remediation": "r", "evidence": "SECRET"}]
    ctx = rp.context_for(c, stubs)
    blob = json.dumps(ctx)
    assert "SECRET" not in blob and '"evidence"' not in blob            # the field is never sent
    assert all(b["type"] in ("paragraph", "bullet") for b in ctx["blocks"])
    assert not any("Coverage" in b["text"] or "NOT assessed" in b["text"] for b in ctx["blocks"])      # locked text is not offered
    assert ctx["findings"][0]["impact"] == "i" * 300
    assert [s["id"] for s in ctx["sections"]] == ["executive_summary", "scope", "methodology", "findings_summary",
                                                   "findings", "conclusion"]
    many = [{"finding_id": f"f{i}", "ref": f"VAR-{i:03d}", "name": "n" * 120, "severity": "low",
             "impact": "x" * 300, "remediation": "y" * 300} for i in range(80)]
    assert len(json.dumps(rp.context_for(c, many))) <= rp.MAX_CONTEXT


def test_diff_shows_before_and_after_for_every_op():
    c = _content()
    bid = _bid(c, "executive_summary", 0)
    res = rp.validate(_data({"op": "replace_text", "id": bid, "text": "New."},
                            {"op": "insert_after", "id": bid, "type": "paragraph", "text": "Added."},
                            {"op": "remove", "id": _bid(c, "methodology", 1)},
                            {"op": "set_finding_text", "finding_id": "f1", "field": "impact", "text": "Worse."}), c, FIDS)
    rows = rp.diff(c, res["ops"], {"f1": {"label": "VAR-001 SQLi", "impact": "Old impact.", "remediation": "r"}})
    assert [r["op"] for r in rows] == ["replace_text", "insert_after", "remove", "set_finding_text"]
    assert rows[0]["before"] == _sec(c, "executive_summary")["blocks"][0]["text"] and rows[0]["after"] == "New."
    assert rows[1]["before"] is None and rows[1]["after"] == "Added." and "Executive Summary" in rows[1]["where"]
    assert rows[2]["before"] and rows[2]["after"] is None
    assert rows[3]["where"] == "VAR-001 SQLi: impact" and rows[3]["before"] == "Old impact." and rows[3]["after"] == "Worse."
