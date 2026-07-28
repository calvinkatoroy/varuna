"""SQLite durable store for the control plane (v2). Stdlib sqlite3, no ORM.

Holds the relational, long-lived data: accounts now; proposals, jobs, findings, reports +
versions, and audit as later plans migrate them off Redis. Redis stays only for ephemeral
coordination (agent job queue, login-throttle counters, agent-online liveness).

WAL + busy_timeout let the three API containers share one DB file on a NAMED docker volume
(ext4 in the Linux VM). Do NOT put the file on a Windows bind mount: SQLite locking breaks
across the container boundary there. Path comes from VARUNA_DB (default /data/varuna.db).
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Optional

_conn: Optional[sqlite3.Connection] = None
_path: Optional[str] = None


def _db_path() -> str:
    return _path or os.environ.get("VARUNA_DB", "/data/varuna.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proposals (
    id                     TEXT PRIMARY KEY,
    submitter              TEXT NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'pending',
    mode                   TEXT NOT NULL DEFAULT 'standard',
    target                 TEXT NOT NULL,
    in_scope               TEXT DEFAULT '',
    out_of_scope           TEXT DEFAULT '',
    division               TEXT DEFAULT '',
    purpose                TEXT DEFAULT '',
    environment            TEXT DEFAULT '',
    test_window            TEXT DEFAULT '',
    roe_json               TEXT DEFAULT '{}',
    authorization_attested INTEGER NOT NULL DEFAULT 0,
    emergency_contact      TEXT DEFAULT '',
    tools_json             TEXT DEFAULT '[]',
    opts_json              TEXT DEFAULT '{}',
    job_id                 TEXT,
    reject_reason          TEXT,
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_proposals_submitter ON proposals(submitter);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);

CREATE TABLE IF NOT EXISTS reports (
    id              TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    owner           TEXT NOT NULL,
    stage           TEXT NOT NULL DEFAULT 'in_review_reporter',
    template        TEXT NOT NULL DEFAULT 'Full Technical',
    delivered_pdf   TEXT,
    pdf_password    TEXT,
    password_viewed INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS report_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id  TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    filename   TEXT NOT NULL,
    editor     TEXT NOT NULL,
    note       TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reports_owner ON reports(owner);
CREATE INDEX IF NOT EXISTS idx_reports_stage ON reports(stage);
CREATE INDEX IF NOT EXISTS idx_versions_report ON report_versions(report_id);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = _db_path()
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=5000")
        _conn.execute("PRAGMA foreign_keys=ON")
        init_db(_conn)
    return _conn


def close() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def reset_for_test(path: str) -> None:
    """Point the singleton at a fresh DB file and re-init the schema (tests only)."""
    global _path
    close()
    _path = path
    if path != ":memory:":
        for suffix in ("", "-wal", "-shm"):
            p = path + suffix
            if os.path.exists(p):
                os.remove(p)
    get_conn()


# --- accounts ---
def upsert_account(username: str, password_hash: str, role: str) -> None:
    get_conn().execute(
        "INSERT INTO accounts (username, password_hash, role) VALUES (?, ?, ?) "
        "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash, role=excluded.role",
        (username, password_hash, role),
    )
    get_conn().commit()


def get_account(username: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT username, password_hash, role FROM accounts WHERE username=?", (username,)
    ).fetchone()
    return dict(row) if row else None


# --- proposals (v2) ---
_PROP_JSON = {"tools": "tools_json", "opts": "opts_json", "roe": "roe_json"}


def _proposal_row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for friendly, col in _PROP_JSON.items():
        d[friendly] = json.loads(d.pop(col) or ("[]" if friendly == "tools" else "{}"))
    d["authorization_attested"] = bool(d["authorization_attested"])
    return d


def create_proposal(p: dict) -> str:
    import uuid
    pid = p.get("id") or str(uuid.uuid4())
    get_conn().execute(
        "INSERT INTO proposals (id, submitter, status, mode, target, in_scope, out_of_scope, "
        "division, purpose, environment, test_window, roe_json, authorization_attested, "
        "emergency_contact, tools_json, opts_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, p["submitter"], p.get("status", "pending"), p.get("mode", "standard"),
         p["target"], p.get("in_scope", ""), p.get("out_of_scope", ""), p.get("division", ""),
         p.get("purpose", ""), p.get("environment", ""), p.get("test_window", ""),
         json.dumps(p.get("roe", {})), 1 if p.get("authorization_attested") else 0,
         p.get("emergency_contact", ""), json.dumps(p.get("tools", [])),
         json.dumps(p.get("opts", {}))),
    )
    get_conn().commit()
    return pid


def get_proposal(pid: str) -> Optional[dict]:
    row = get_conn().execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
    return _proposal_row_to_dict(row) if row else None


def list_proposals(status: Optional[str] = None, submitter: Optional[str] = None) -> list[dict]:
    q, args = "SELECT * FROM proposals", []
    where = []
    if status:
        where.append("status=?"); args.append(status)
    if submitter:
        where.append("submitter=?"); args.append(submitter)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY created_at DESC"
    return [_proposal_row_to_dict(r) for r in get_conn().execute(q, args).fetchall()]


def update_proposal(pid: str, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = "now"  # sentinel replaced below
    sets, args = [], []
    for k, v in fields.items():
        if k == "updated_at":
            sets.append("updated_at=datetime('now')")
        else:
            sets.append(f"{k}=?"); args.append(v)
    args.append(pid)
    get_conn().execute(f"UPDATE proposals SET {', '.join(sets)} WHERE id=?", args)
    get_conn().commit()


# --- reports + versions (v2 review pipeline) ---
def create_report(job_id: str, owner: str, template: str = "Full Technical",
                  stage: str = "in_review_reporter") -> str:
    import uuid
    rid = str(uuid.uuid4())
    get_conn().execute(
        "INSERT INTO reports (id, job_id, owner, stage, template) VALUES (?,?,?,?,?)",
        (rid, job_id, owner, stage, template),
    )
    get_conn().commit()
    return rid


def get_report(rid: str) -> Optional[dict]:
    row = get_conn().execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["password_viewed"] = bool(d["password_viewed"])
    return d


def list_reports(owner: Optional[str] = None, stage: Optional[str] = None) -> list[dict]:
    q, args, where = "SELECT * FROM reports", [], []
    if owner:
        where.append("owner=?"); args.append(owner)
    if stage:
        where.append("stage=?"); args.append(stage)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY created_at DESC"
    out = []
    for row in get_conn().execute(q, args).fetchall():
        d = dict(row); d["password_viewed"] = bool(d["password_viewed"]); out.append(d)
    return out


def set_report(rid: str, **fields) -> None:
    if not fields:
        return
    sets, args = ["updated_at=datetime('now')"], []
    for k, v in fields.items():
        sets.append(f"{k}=?"); args.append(v)
    args.append(rid)
    get_conn().execute(f"UPDATE reports SET {', '.join(sets)} WHERE id=?", args)
    get_conn().commit()


def add_report_version(rid: str, filename: str, editor: str, note: str = "") -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(MAX(version_no), 0) AS mx FROM report_versions WHERE report_id=?", (rid,)
    ).fetchone()
    n = row["mx"] + 1
    conn.execute(
        "INSERT INTO report_versions (report_id, version_no, filename, editor, note) "
        "VALUES (?,?,?,?,?)", (rid, n, filename, editor, note),
    )
    conn.commit()
    return n


def list_report_versions(rid: str) -> list[dict]:
    return [dict(r) for r in get_conn().execute(
        "SELECT * FROM report_versions WHERE report_id=? ORDER BY version_no", (rid,)).fetchall()]


def latest_version(rid: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM report_versions WHERE report_id=? ORDER BY version_no DESC LIMIT 1", (rid,)
    ).fetchone()
    return dict(row) if row else None


if __name__ == "__main__":
    reset_for_test(":memory:")
    upsert_account("calvin", "h", "client")
    assert get_account("calvin")["role"] == "client"
    upsert_account("calvin", "h2", "pentester")
    assert get_account("calvin")["password_hash"] == "h2", "upsert should update"
    assert get_account("nope") is None
    print("db.py self-check OK")
