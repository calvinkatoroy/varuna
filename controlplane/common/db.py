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

import threading

# One connection per thread: FastAPI runs sync endpoints on a threadpool, and sharing a single
# sqlite3 connection across those threads corrupted commits ("not an error" 500s under load).
_local = threading.local()
_lock = threading.Lock()
_conns: list[sqlite3.Connection] = []
_gen = 0          # bumped by close() so stale per-thread connections are reopened
_schema_ready = -1
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

CREATE TABLE IF NOT EXISTS findings (
    id            TEXT PRIMARY KEY,
    job_id        TEXT NOT NULL,
    owner         TEXT NOT NULL,
    name          TEXT NOT NULL,
    severity      TEXT NOT NULL,
    host          TEXT NOT NULL,
    url           TEXT DEFAULT '',
    description   TEXT DEFAULT '',
    cve           TEXT,
    cvss          REAL,
    cwe           TEXT,
    tool          TEXT DEFAULT '',
    evidence      TEXT DEFAULT '',
    owasp         TEXT,
    impact        TEXT,
    remediation   TEXT,
    risk_rating   TEXT,
    verdict       TEXT NOT NULL DEFAULT 'tp',
    status        TEXT NOT NULL DEFAULT 'open',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_findings_job ON findings(job_id);
CREATE INDEX IF NOT EXISTS idx_findings_owner ON findings(owner);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);

-- Password-reset links: only a hash of the token is stored; single use, short expiry.
CREATE TABLE IF NOT EXISTS reset_tokens (
    token_hash TEXT PRIMARY KEY,
    username   TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # Migrations for databases created before a column existed (CREATE IF NOT EXISTS won't add it).
    cols = {r[1] for r in conn.execute("PRAGMA table_info(accounts)")}
    if "disabled" not in cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0")
    for col, ddl in (("email", "TEXT"), ("totp_secret", "TEXT"), ("totp_enabled", "INTEGER NOT NULL DEFAULT 0"),
                     ("totp_last_step", "INTEGER NOT NULL DEFAULT 0")):
        if col not in cols:
            conn.execute(f"ALTER TABLE accounts ADD COLUMN {col} {ddl}")
    conn.commit()


def get_conn() -> sqlite3.Connection:
    global _schema_ready
    conn = getattr(_local, "conn", None)
    if conn is not None and getattr(_local, "gen", -1) == _gen:
        return conn
    path = _db_path()
    with _lock:
        if path == ":memory:" and _conns:   # in-memory DB exists per connection: share one (tests)
            _local.conn, _local.gen = _conns[0], _gen
            return _conns[0]
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        if _schema_ready != _gen:
            init_db(conn)
            _schema_ready = _gen
        _conns.append(conn)
    _local.conn, _local.gen = conn, _gen
    return conn


def close() -> None:
    global _gen
    with _lock:
        for c in _conns:
            try:
                c.close()
            except sqlite3.Error:
                pass
        _conns.clear()
        _gen += 1


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
        "SELECT username, password_hash, role, disabled, totp_secret, totp_enabled, totp_last_step "
        "FROM accounts WHERE username=?", (username,)
    ).fetchone()
    return dict(row) if row else None


def list_accounts() -> list[dict]:
    """Account roster for admin screens: never includes password hashes."""
    return [dict(r) for r in get_conn().execute(
        "SELECT username, role, disabled, totp_enabled, created_at FROM accounts ORDER BY role, username").fetchall()]


def set_account(username: str, **fields) -> bool:
    """Update password_hash / disabled. True if the account exists."""
    allowed = {k: v for k, v in fields.items()
               if k in ("password_hash", "disabled", "email", "totp_secret", "totp_enabled", "totp_last_step")}
    if not allowed:
        return False
    sets = ", ".join(f"{k}=?" for k in allowed)
    cur = get_conn().execute(f"UPDATE accounts SET {sets} WHERE username=?", [*allowed.values(), username])
    get_conn().commit()
    return cur.rowcount == 1


def client_usernames_by_email(email: str) -> list[str]:
    """Active client accounts registered with this address (team accounts never reset by email)."""
    return [r[0] for r in get_conn().execute(
        "SELECT username FROM accounts WHERE email=? COLLATE NOCASE AND role='client' AND disabled=0", (email,))]


def add_reset_token(token_hash: str, username: str, expires_at: int) -> None:
    """One live link per account: a new request voids the previous one."""
    c = get_conn()
    c.execute("DELETE FROM reset_tokens WHERE username=?", (username,))
    c.execute("INSERT INTO reset_tokens (token_hash, username, expires_at) VALUES (?, ?, ?)", (token_hash, username, expires_at))
    c.commit()


def claim_reset_token(token_hash: str, now: int) -> Optional[str]:
    """Atomically spend a valid unused token; returns its username, or None."""
    c = get_conn()
    cur = c.execute("UPDATE reset_tokens SET used=1 WHERE token_hash=? AND used=0 AND expires_at>?", (token_hash, now))
    c.commit()
    if cur.rowcount != 1:
        return None
    return c.execute("SELECT username FROM reset_tokens WHERE token_hash=?", (token_hash,)).fetchone()[0]


def get_account_ci(username: str) -> Optional[dict]:
    """Case-insensitive lookup, so `ACME` cannot register next to `acme`."""
    row = get_conn().execute(
        "SELECT username FROM accounts WHERE username=? COLLATE NOCASE", (username,)).fetchone()
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


def get_proposal_by_job(job_id: str) -> Optional[dict]:
    row = get_conn().execute("SELECT * FROM proposals WHERE job_id=?", (job_id,)).fetchone()
    return _proposal_row_to_dict(row) if row else None


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


def claim_proposal(pid: str, from_status: str, **fields) -> bool:
    """Atomically move a proposal out of `from_status`; True only for the one caller that wins
    (concurrent approve/reject of the same proposal must not both proceed)."""
    sets, args = ["updated_at=datetime('now')"], []
    for k, v in fields.items():
        sets.append(f"{k}=?"); args.append(v)
    args += [pid, from_status]
    cur = get_conn().execute(
        f"UPDATE proposals SET {', '.join(sets)} WHERE id=? AND status=?", args)
    get_conn().commit()
    return cur.rowcount == 1


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


def claim_report_stage(rid: str, from_stage: str, to_stage: str) -> bool:
    """Atomic compare-and-set on a report's stage: of N concurrent reviewers acting on the same
    stage exactly one wins (True), so a report is never forwarded/delivered twice."""
    cur = get_conn().execute(
        "UPDATE reports SET stage=?, updated_at=datetime('now') WHERE id=? AND stage=?",
        (to_stage, rid, from_stage))
    get_conn().commit()
    return cur.rowcount == 1


def claim_password_view(rid: str) -> bool:
    """Atomic view-once: True only for the single caller that flips password_viewed 0 -> 1."""
    cur = get_conn().execute("UPDATE reports SET password_viewed=1 WHERE id=? AND password_viewed=0", (rid,))
    get_conn().commit()
    return cur.rowcount == 1


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


# --- findings (v2, durable - findings must outlive the 24h job/redis TTL to survive the
# multi-day review pipeline). id is deterministic (hash of job_id+name+host+url), not random,
# so re-running correlate/enrich (e.g. add_manual_finding recomputes the whole set) upserts in
# place via ON CONFLICT and does NOT clobber a verdict/status a reviewer already set. ---
_FINDING_COLS = ("name", "severity", "host", "url", "description", "cve", "cvss", "cwe",
                 "tool", "evidence", "owasp", "impact", "remediation", "risk_rating")


def _finding_id(job_id: str, f: dict) -> str:
    import hashlib
    key = f"{job_id}|{f.get('name', '')}|{f.get('host', '')}|{f.get('url', '')}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def save_findings(job_id: str, owner: str, findings: list[dict]) -> None:
    """Replace-all per job, upserting by stable id so verdict/status survive re-correlation."""
    conn = get_conn()
    ids = [_finding_id(job_id, f) for f in findings]
    for fid, f in zip(ids, findings):
        conn.execute(
            "INSERT INTO findings (id, job_id, owner, " + ", ".join(_FINDING_COLS) + ") "
            "VALUES (?,?,?," + ",".join("?" for _ in _FINDING_COLS) + ") "
            "ON CONFLICT(id) DO UPDATE SET " +
            ", ".join(f"{c}=excluded.{c}" for c in _FINDING_COLS),
            (fid, job_id, owner, *(f.get(c) for c in _FINDING_COLS)),
        )
    if ids:
        conn.execute(
            f"DELETE FROM findings WHERE job_id=? AND id NOT IN ({','.join('?' * len(ids))})",
            [job_id, *ids],
        )
    else:
        conn.execute("DELETE FROM findings WHERE job_id=?", (job_id,))
    conn.commit()


def get_findings(job_id: str) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM findings WHERE job_id=? ORDER BY created_at", (job_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_finding(fid: str) -> Optional[dict]:
    row = get_conn().execute("SELECT * FROM findings WHERE id=?", (fid,)).fetchone()
    return dict(row) if row else None


def list_findings(owner: Optional[str] = None) -> list[dict]:
    q, args = "SELECT * FROM findings", []
    if owner:
        q += " WHERE owner=?"; args.append(owner)
    q += " ORDER BY created_at DESC"
    return [dict(r) for r in get_conn().execute(q, args).fetchall()]


def set_finding(fid: str, **fields) -> None:
    if not fields:
        return
    sets, args = [], []
    for k, v in fields.items():
        sets.append(f"{k}=?"); args.append(v)
    args.append(fid)
    get_conn().execute(f"UPDATE findings SET {', '.join(sets)} WHERE id=?", args)
    get_conn().commit()


def wipe_findings() -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) AS c FROM findings").fetchone()["c"]
    conn.execute("DELETE FROM findings")
    conn.commit()
    return n


if __name__ == "__main__":
    reset_for_test(":memory:")
    upsert_account("calvin", "h", "client")
    assert get_account("calvin")["role"] == "client"
    upsert_account("calvin", "h2", "pentester")
    assert get_account("calvin")["password_hash"] == "h2", "upsert should update"
    assert get_account("nope") is None

    save_findings("j1", "alice", [{"name": "SQLi", "severity": "critical", "host": "h", "url": "/x"}])
    fs = get_findings("j1")
    assert len(fs) == 1 and fs[0]["verdict"] == "tp" and fs[0]["status"] == "open"
    fid = fs[0]["id"]
    set_finding(fid, verdict="fp")
    assert get_findings("j1")[0]["verdict"] == "fp", "verdict update failed"
    # re-saving (simulates re-correlation after a manual finding) must preserve that verdict,
    # not reset it back to the default - that's the whole point of the stable/upserted id.
    save_findings("j1", "alice", [{"name": "SQLi", "severity": "critical", "host": "h", "url": "/x"}])
    assert get_findings("j1")[0]["verdict"] == "fp", "save_findings must not clobber verdict"
    assert len(list_findings(owner="alice")) == 1
    assert list_findings(owner="bob") == []
    assert wipe_findings() == 1 and get_findings("j1") == []

    print("db.py self-check OK")
