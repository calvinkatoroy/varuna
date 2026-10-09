"""The AI patch: the ONLY way the chat may change a report. Pure functions, no I/O.

A patch is {"summary": str, "ops": [...]} with at most 12 ops of four kinds. Everything not named here (section
titles, computed tables, the coverage disclaimer, counts, severities, ids) cannot be touched: `validate` refuses the
whole patch on the first violation and `check_structure` re-proves after applying that the skeleton is unchanged."""
from __future__ import annotations

import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import textsafe  # noqa: E402


class PatchError(ValueError):
    """Messages are written for the retry prompt and for logs: no user data in them."""


MAX_OPS = 12
MAX_ADDED = 12          # blocks the assistant may have added per section
MAX_BLOCKS = 60         # per document
MAX_OVERRIDES = 100
MAX_CONTEXT = 12000     # characters of report data sent to the model
LIMIT = {"paragraph": 1500, "bullet": 400, "finding": 2000, "summary": 300}
FINDING_FIELDS = ("impact", "remediation")
_SHAPES = {
    "replace_text": {"op", "id", "text"},
    "insert_after": {"op", "id", "type", "text"},
    "remove": {"op", "id"},
    "set_finding_text": {"op", "finding_id", "field", "text"},
}
_TEXT = ("paragraph", "bullet")


def _blocks(content):
    for sec in content["sections"]:
        for b in sec["blocks"]:
            yield sec, b


def _index(content) -> dict:
    return {b["id"]: (sec, b) for sec, b in _blocks(content)}


def _overrides(content) -> dict:
    for _, b in _blocks(content):
        if b["type"] == "finding_overrides":
            return b["overrides"]
    raise PatchError("the report has no findings block")


def _find(content, bid):
    for sec in content["sections"]:
        for i, b in enumerate(sec["blocks"]):
            if b["id"] == bid:
                return sec, i
    return None


def _next_id(content) -> str:
    nums = [int(m.group(1)) for _, b in _blocks(content) if (m := re.fullmatch(r"b(\d+)", b["id"]))]
    return f"b{max(nums, default=0) + 1}"


def context_for(content: dict, stubs: list[dict]) -> dict:
    """What the model may see: editable text blocks and one short stub per confirmed finding. Never evidence."""
    blocks = [{"id": b["id"], "section": sec["id"], "type": b["type"], "text": b["text"]}
              for sec, b in _blocks(content) if b["type"] in _TEXT and b.get("editable")]
    sections = [{"id": s["id"], "title": s["title"], "can_insert": bool(s.get("ai_insert"))}
                for s in content["sections"] if s["id"] != "cover"]
    findings = [{"finding_id": s["finding_id"], "ref": s["ref"], "name": str(s["name"])[:120], "severity": s["severity"],
                 "impact": str(s.get("impact") or "")[:300], "remediation": str(s.get("remediation") or "")[:300]}
                for s in stubs]
    ctx = {"sections": sections, "blocks": blocks, "findings": findings}
    size = lambda: len(json.dumps(ctx, ensure_ascii=True))   # noqa: E731
    while size() > MAX_CONTEXT and ctx["findings"]:
        ctx["findings"].pop()
    if size() > MAX_CONTEXT:
        for b in blocks:
            b["text"] = b["text"][:300]
    if size() > MAX_CONTEXT:
        raise PatchError("the report is too long to edit with the assistant")
    return ctx


def parse_patch(raw) -> dict:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        raise PatchError("the reply was not valid JSON")
    if not isinstance(data, dict) or set(data) != {"summary", "ops"}:
        raise PatchError('the reply must be a JSON object with exactly the keys "summary" and "ops"')
    return data


def _text(op: dict, limit: int, label: str):
    v = op.get("text")
    if not isinstance(v, str):
        raise PatchError(f"{label}: text must be a string")
    clean = textsafe.clean_plain(v)
    if not clean:
        raise PatchError(f"{label}: text is empty after cleaning")
    if len(clean) > limit:
        raise PatchError(f"{label}: text is longer than {limit} characters")
    return clean, clean != " ".join(v.split())


def validate(data: dict, content: dict, finding_ids) -> dict:
    """-> {"summary", "ops"} with every string cleaned and each op flagged `sanitized` when cleaning changed it."""
    summary = data.get("summary")
    if not isinstance(summary, str):
        raise PatchError("summary must be a string")
    summary = textsafe.clean_plain(summary)[:LIMIT["summary"]]
    ops = data.get("ops")
    if not isinstance(ops, list) or len(ops) > MAX_OPS:
        raise PatchError(f"ops must be a list of at most {MAX_OPS} items")
    idx, seen, out = _index(content), set(), []
    for i, op in enumerate(ops, 1):
        label = f"op {i}"
        if not isinstance(op, dict) or op.get("op") not in _SHAPES:
            raise PatchError(f"{label}: unknown op")
        kind = op["op"]
        if set(op) != _SHAPES[kind]:
            raise PatchError(f"{label}: {kind} needs exactly the keys {sorted(_SHAPES[kind])}")
        cleaned = False
        if kind == "set_finding_text":
            fid, field = op["finding_id"], op["field"]
            if not isinstance(fid, str) or fid not in finding_ids:
                raise PatchError(f"{label}: unknown finding")
            if field not in FINDING_FIELDS:
                raise PatchError(f"{label}: field must be impact or remediation")
            text, cleaned = _text(op, LIMIT["finding"], label)
            item, key = {"op": kind, "finding_id": fid, "field": field, "text": text}, ("f", fid, field)
        else:
            bid = op["id"]
            if not isinstance(bid, str) or bid not in idx:
                raise PatchError(f"{label}: unknown block id")
            sec, blk = idx[bid]
            if kind == "insert_after":
                if not sec.get("ai_insert"):
                    raise PatchError(f"{label}: nothing can be added to {sec['title']}")
                if op["type"] not in _TEXT:
                    raise PatchError(f"{label}: type must be paragraph or bullet")
                text, cleaned = _text(op, LIMIT[op["type"]], label)
                item, key = {"op": kind, "id": bid, "type": op["type"], "text": text}, ("i", i)
            else:
                if blk["type"] not in _TEXT or not blk.get("editable"):
                    raise PatchError(f"{label}: block {bid} is locked")
                key = ("b", bid)
                if kind == "replace_text":
                    text, cleaned = _text(op, LIMIT[blk["type"]], label)
                    item = {"op": kind, "id": bid, "text": text}
                else:
                    item = {"op": kind, "id": bid}
        if key in seen:
            raise PatchError(f"{label}: the same target is changed twice")
        seen.add(key)
        item["sanitized"] = bool(cleaned)
        out.append(item)
    apply_ops(content, out)   # dry run: an op that cannot be applied (removed anchor, too many blocks) refuses the patch
    return {"summary": summary, "ops": out}


def _skeleton(content) -> list:
    return [(s["id"], s["title"], bool(s.get("ai_insert")),
             [(b["id"], b["type"]) for b in s["blocks"] if b["type"] not in _TEXT]) for s in content["sections"]]


def _locked(content) -> list:
    return [(b["id"], b["text"]) for _, b in _blocks(content) if b["type"] in _TEXT and not b.get("editable")]


def check_structure(old: dict, new: dict) -> None:
    if _skeleton(old) != _skeleton(new):
        raise PatchError("the report structure cannot change")
    if _locked(old) != _locked(new):
        raise PatchError("locked text cannot change")
    if sum(len(s["blocks"]) for s in new["sections"]) > MAX_BLOCKS:
        raise PatchError("the report would get too long")


def apply_ops(content: dict, ops: list[dict]) -> dict:
    """A new content document; `content` is never modified."""
    new = copy.deepcopy(content)
    for op in ops:
        kind = op["op"]
        if kind == "set_finding_text":
            ov = _overrides(new)
            if op["finding_id"] not in ov and len(ov) >= MAX_OVERRIDES:
                raise PatchError("too many finding texts are changed in this report")
            ov.setdefault(op["finding_id"], {})[op["field"]] = op["text"]
            continue
        found = _find(new, op["id"])
        if found is None:
            raise PatchError(f"block {op['id']} no longer exists")
        sec, i = found
        blocks = sec["blocks"]
        if kind in ("replace_text", "remove") and not blocks[i].get("editable"):
            raise PatchError(f"block {op['id']} is locked")
        if kind == "replace_text":
            blocks[i]["text"] = op["text"]
        elif kind == "remove":
            del blocks[i]
        else:
            if not sec.get("ai_insert"):
                raise PatchError(f"nothing can be added to {sec['title']}")
            if sum(1 for b in blocks if b.get("ai")) >= MAX_ADDED:
                raise PatchError(f"too many blocks were added to {sec['title']}")
            blocks.insert(i + 1, {"id": _next_id(new), "type": op["type"], "text": op["text"], "editable": True, "ai": True})
    check_structure(content, new)
    return new


def diff(content: dict, ops: list[dict], findings: dict) -> list[dict]:
    """Before/after per op for the preview. `findings`: finding id -> {"label", "impact", "remediation"} (current text)."""
    idx, rows = _index(content), []
    for op in ops:
        kind, flag = op["op"], bool(op.get("sanitized"))
        if kind == "set_finding_text":
            f = findings.get(op["finding_id"], {})
            rows.append({"op": kind, "where": f"{f.get('label', 'finding')}: {op['field']}",
                         "before": f.get(op["field"]), "after": op["text"], "sanitized": flag})
            continue
        sec, blk = idx[op["id"]]
        if kind == "replace_text":
            rows.append({"op": kind, "where": sec["title"], "before": blk["text"], "after": op["text"], "sanitized": flag})
        elif kind == "remove":
            rows.append({"op": kind, "where": sec["title"], "before": blk["text"], "after": None, "sanitized": False})
        else:
            near = (blk.get("text") or "")[:40]
            rows.append({"op": kind, "where": f"{sec['title']}, after \"{near}\"" if near else sec["title"],
                         "before": None, "after": op["text"], "sanitized": flag})
    return rows
