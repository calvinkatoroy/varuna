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
    scan_mode              TEXT NOT NULL DEFAULT 'local',
    target                 TEXT NOT NULL,
    in_scope               TEXT DEFAULT '',
    out_of_scope           TEXT DEFAULT '',
    division               TEXT DEFAULT '',
    purpose                TEXT DEFAULT '',
    environment            TEXT DEFAULT '',
    test_window            TEXT DEFAULT '',
    roe_json               TEXT DEFAULT '{}',
    org_id                 TEXT NOT NULL DEFAULT '',
    authorization_attested INTEGER NOT NULL DEFAULT 0,
    emergency_contact      TEXT DEFAULT '',
    tools_json             TEXT DEFAULT '[]',
    opts_json              TEXT DEFAULT '{}',
    job_id                 TEXT,
    reject_reason          TEXT,
    stage                  TEXT NOT NULL DEFAULT 'task',
    scan_state             TEXT,
    path                   TEXT,
    port                   INTEGER,
    notes                  TEXT,
    not_before             TEXT,
    not_after              TEXT,
    max_minutes            INTEGER,
    scheduled_at           TEXT,
    assignee               TEXT,
    suspend_reason         TEXT,
    decline_cause          TEXT,
    version                INTEGER NOT NULL DEFAULT 0,
    due_since              TEXT,
    target_class           TEXT,
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_proposals_submitter ON proposals(submitter);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);

CREATE TABLE IF NOT EXISTS reports (
    id              TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    owner           TEXT NOT NULL,
    org_id          TEXT NOT NULL DEFAULT '',
    stage           TEXT NOT NULL DEFAULT 'draft',
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
    org_id        TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS orgs (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    status     TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS email_changes (
    token_hash TEXT PRIMARY KEY,
    username   TEXT NOT NULL,
    email      TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
);
-- Append-only task history: every workflow transition writes exactly one row in the same transaction.
CREATE TABLE IF NOT EXISTS task_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    org_id          TEXT NOT NULL DEFAULT '',
    from_stage      TEXT,
    from_scan_state TEXT,
    to_stage        TEXT NOT NULL,
    to_scan_state   TEXT,
    actor           TEXT NOT NULL,
    comment         TEXT,
    at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id);

-- Every scan job a task has run (a resume after a failed job starts a new one). Filled by the triggers
-- below whenever proposals.job_id is set, so findings of earlier jobs still belong to the task.
CREATE TABLE IF NOT EXISTS task_jobs (
    job_id   TEXT PRIMARY KEY,
    task_id  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_jobs_task ON task_jobs(task_id);

-- Step 4. The report is a JSON document per task (append-only versions); PDFs and AI turns are jobs; edits are audited.
CREATE TABLE IF NOT EXISTS report_content (
    task_id      TEXT NOT NULL,
    version      INTEGER NOT NULL,
    org_id       TEXT NOT NULL DEFAULT '',
    content_json TEXT NOT NULL,
    created_by   TEXT NOT NULL,
    note         TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (task_id, version)
);
CREATE TABLE IF NOT EXISTS report_pdfs (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    org_id          TEXT NOT NULL DEFAULT '',
    n               INTEGER,
    status          TEXT NOT NULL,
    content_version INTEGER NOT NULL,
    digest          TEXT,
    filename        TEXT,
    stored_name     TEXT,
    error           TEXT,
    requested_by    TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (task_id, n)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_report_pdfs_active ON report_pdfs(task_id)
    WHERE status IN ('queued','rendering','converting');
CREATE INDEX IF NOT EXISTS idx_report_pdfs_stored ON report_pdfs(stored_name);
CREATE TABLE IF NOT EXISTS task_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL,
    org_id      TEXT NOT NULL DEFAULT '',
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    subject     TEXT NOT NULL DEFAULT '',
    detail_json TEXT NOT NULL DEFAULT '{}',
    at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_audit_task ON task_audit(task_id);
CREATE TABLE IF NOT EXISTS ai_turns (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    org_id          TEXT NOT NULL DEFAULT '',
    actor           TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    status          TEXT NOT NULL,
    base_version    INTEGER NOT NULL,
    summary         TEXT,
    ops_json        TEXT,
    error           TEXT,
    applied         INTEGER NOT NULL DEFAULT 0,
    applied_version INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_turns_active ON ai_turns(task_id) WHERE status IN ('queued','running');
CREATE INDEX IF NOT EXISTS idx_ai_turns_task ON ai_turns(task_id);
CREATE TRIGGER IF NOT EXISTS trg_task_jobs_ins AFTER INSERT ON proposals WHEN NEW.job_id IS NOT NULL
BEGIN INSERT OR IGNORE INTO task_jobs (job_id, task_id) VALUES (NEW.job_id, NEW.id); END;
CREATE TRIGGER IF NOT EXISTS trg_task_jobs_upd AFTER UPDATE OF job_id ON proposals WHEN NEW.job_id IS NOT NULL
BEGIN INSERT OR IGNORE INTO task_jobs (job_id, task_id) VALUES (NEW.job_id, NEW.id); END;
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
    pcols = {r[1] for r in conn.execute("PRAGMA table_info(proposals)")}
    first_stage = "stage" not in pcols
    if "scan_mode" not in pcols:
        conn.execute("ALTER TABLE proposals ADD COLUMN scan_mode TEXT NOT NULL DEFAULT 'local'")
    for col, ddl in (("stage", "TEXT NOT NULL DEFAULT 'task'"), ("scan_state", "TEXT"), ("path", "TEXT"),
                     ("port", "INTEGER"), ("notes", "TEXT"), ("not_before", "TEXT"), ("not_after", "TEXT"),
                     ("max_minutes", "INTEGER"), ("scheduled_at", "TEXT"), ("assignee", "TEXT"),
                     ("suspend_reason", "TEXT"), ("decline_cause", "TEXT"),
                     ("version", "INTEGER NOT NULL DEFAULT 0"), ("due_since", "TEXT"), ("target_class", "TEXT")):
        if col not in pcols:
            conn.execute(f"ALTER TABLE proposals ADD COLUMN {col} {ddl}")
    if first_stage:   # rows from before the workflow existed are closed, never claimable
        conn.execute("UPDATE proposals SET stage='expired' WHERE not_after IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_proposals_stage ON proposals(stage, scan_state)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_proposals_job ON proposals(job_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_org ON findings(org_id)")
    for col, ddl in (("org_id", "TEXT"), ("display_name", "TEXT"), ("phone", "TEXT"),
                     ("token_version", "INTEGER NOT NULL DEFAULT 0"),
                     ("must_change_password", "INTEGER NOT NULL DEFAULT 0")):
        if col not in cols:
            conn.execute(f"ALTER TABLE accounts ADD COLUMN {col} {ddl}")
    for table in ("proposals", "reports", "findings"):
        tcols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if "org_id" not in tcols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN org_id TEXT NOT NULL DEFAULT ''")
        # Index after the migration: on an old DB the column does not exist when SCHEMA runs.
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_org ON {table}(org_id)")
    conn.execute("INSERT OR IGNORE INTO task_jobs (job_id, task_id) SELECT job_id, id FROM proposals WHERE job_id IS NOT NULL")
    rcols = {r[1] for r in conn.execute("PRAGMA table_info(reports)")}
    if "task_id" not in rcols:
        conn.execute("ALTER TABLE reports ADD COLUMN task_id TEXT")
        taken: set = set()   # an old database may hold two reports for one task (a resumed scan): only the oldest is linked
        for rid, jid in conn.execute("SELECT id, job_id FROM reports ORDER BY created_at, id").fetchall():
            row = conn.execute("SELECT task_id FROM task_jobs WHERE job_id=?", (jid,)).fetchone()
            if row and row[0] not in taken:
                taken.add(row[0])
                conn.execute("UPDATE reports SET task_id=? WHERE id=?", (row[0], rid))
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_reports_task ON reports(task_id) WHERE task_id IS NOT NULL")
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
def create_org(name: str) -> str:
    import uuid
    oid = str(uuid.uuid4())
    get_conn().execute("INSERT INTO orgs (id, name) VALUES (?, ?)", (oid, name.strip()))
    get_conn().commit()
    return oid


def get_org(org_id: str) -> Optional[dict]:
    row = get_conn().execute("SELECT * FROM orgs WHERE id=?", (org_id,)).fetchone()
    return dict(row) if row else None


def list_orgs() -> list[dict]:
    return [dict(r) for r in get_conn().execute("SELECT * FROM orgs ORDER BY name").fetchall()]


def set_org_status(org_id: str, status: str) -> bool:
    cur = get_conn().execute("UPDATE orgs SET status=? WHERE id=?", (status, org_id))
    get_conn().commit()
    return cur.rowcount == 1


_ACCT_COLS = ("username, password_hash, role, disabled, org_id, display_name, phone, email, token_version, "
              "must_change_password, totp_secret, totp_enabled, totp_last_step")
_BUMPS = ("password_hash", "role", "org_id", "disabled", "totp_enabled")
_SETTABLE = _BUMPS + ("display_name", "phone", "email", "must_change_password", "totp_secret", "totp_last_step")


def upsert_account(username: str, password_hash: str, role: str, org_id: Optional[str] = None) -> None:
    get_conn().execute(
        "INSERT INTO accounts (username, password_hash, role, org_id) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash, role=excluded.role, "
        "org_id=excluded.org_id, token_version=token_version+1",
        (username, password_hash, role, org_id),
    )
    get_conn().commit()


def get_account(username: str) -> Optional[dict]:
    row = get_conn().execute(f"SELECT {_ACCT_COLS} FROM accounts WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def list_accounts() -> list[dict]:
    """Roster for admin screens: never includes password hashes or 2FA secrets."""
    return [dict(r) for r in get_conn().execute(
        "SELECT username, role, org_id, display_name, email, disabled, totp_enabled, must_change_password, created_at "
        "FROM accounts ORDER BY role, username").fetchall()]


def set_account(username: str, **fields) -> bool:
    """Update account fields. True if the account exists. Security-relevant changes end old sessions."""
    allowed = {k: v for k, v in fields.items() if k in _SETTABLE}
    if not allowed:
        return False
    sets = [f"{k}=?" for k in allowed]
    if any(k in _BUMPS for k in allowed):
        sets.append("token_version=token_version+1")
    cur = get_conn().execute(f"UPDATE accounts SET {', '.join(sets)} WHERE username=?", [*allowed.values(), username])
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


def _org_where(org_id, where: list, args: list) -> None:
    if org_id is not None:
        where.append("org_id=?"); args.append(org_id)


def _insert_event(conn: sqlite3.Connection, task_id: str, org_id: str, e: dict) -> None:
    conn.execute(
        "INSERT INTO task_events (task_id, org_id, from_stage, from_scan_state, to_stage, to_scan_state, actor, comment, at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (task_id, org_id, e.get("from_stage"), e.get("from_scan_state"), e["to_stage"], e.get("to_scan_state"),
         e["actor"], e.get("comment"), e["at"]))


def create_proposal(p: dict, event: Optional[dict] = None) -> str:
    """Create a task row (the table keeps its old name). `event` = the creation row of task_events,
    written in the same transaction."""
    import uuid
    pid = p.get("id") or str(uuid.uuid4())
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO proposals (id, org_id, submitter, status, mode, target, in_scope, out_of_scope, "
            "division, purpose, environment, test_window, roe_json, authorization_attested, "
            "emergency_contact, tools_json, opts_json, scan_mode, stage, scan_state, path, port, notes, "
            "not_before, not_after, max_minutes, scheduled_at, assignee, job_id) "
            "VALUES (" + ",".join("?" * 29) + ")",
            (pid, p["org_id"], p["submitter"], p.get("status", "pending"), p.get("mode", "standard"),
             p["target"], p.get("in_scope", ""), p.get("out_of_scope", ""), p.get("division", ""),
             p.get("purpose", ""), p.get("environment", ""), p.get("test_window", ""),
             json.dumps(p.get("roe", {})), 1 if p.get("authorization_attested") else 0,
             p.get("emergency_contact", ""), json.dumps(p.get("tools", [])),
             json.dumps(p.get("opts", {})), p.get("scan_mode", "local"), p.get("stage", "task"),
             p.get("scan_state"), p.get("path", ""), p.get("port"), p.get("notes", ""), p.get("not_before"),
             p.get("not_after"), p.get("max_minutes"), p.get("scheduled_at"), p.get("assignee"), p.get("job_id")),
        )
        if event:
            _insert_event(conn, pid, p["org_id"], event)
    return pid


def get_proposal(pid: str, *, org_id: Optional[str]) -> Optional[dict]:
    q, args = "SELECT * FROM proposals WHERE id=?", [pid]
    if org_id is not None:
        q += " AND org_id=?"; args.append(org_id)
    row = get_conn().execute(q, args).fetchone()
    return _proposal_row_to_dict(row) if row else None


def list_proposals(stage: Optional[str] = None, *, org_id: Optional[str],
                   scan_state: Optional[str] = None) -> list[dict]:
    q, args = "SELECT * FROM proposals", []
    where = []
    for col, val in (("stage", stage), ("scan_state", scan_state)):
        if val:
            where.append(f"{col}=?"); args.append(val)
    _org_where(org_id, where, args)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY created_at DESC"
    return [_proposal_row_to_dict(r) for r in get_conn().execute(q, args).fetchall()]


def get_proposal_by_job(job_id: str) -> Optional[dict]:
    row = get_conn().execute("SELECT p.* FROM proposals p JOIN task_jobs tj ON tj.task_id = p.id WHERE tj.job_id=?",
                             (job_id,)).fetchone()
    return _proposal_row_to_dict(row) if row else None


_WORKFLOW_COLS = frozenset({"stage", "scan_state", "version"})


def update_proposal(pid: str, **fields) -> None:
    if _WORKFLOW_COLS & fields.keys():
        raise ValueError("stage, scan_state and version change only through workflow.transition")
    if not fields:
        return
    sets, args = ["updated_at=datetime('now')"], []
    for k, v in fields.items():
        sets.append(f"{k}=?"); args.append(v)
    args.append(pid)
    get_conn().execute(f"UPDATE proposals SET {', '.join(sets)} WHERE id=?", args)
    get_conn().commit()


def cas_task(pid: str, version: int, fields: dict, event: Optional[dict] = None) -> bool:
    """Compare-and-set on a task's version: True only for the caller whose `version` is still current.
    The event row (if any) is written in the same transaction, so history and state never disagree.
    Column names come from workflow.py, never from a request."""
    sets = [f"{k}=?" for k in fields] + ["version=version+1", "updated_at=datetime('now')"]
    conn = get_conn()
    with conn:
        cur = conn.execute(f"UPDATE proposals SET {', '.join(sets)} WHERE id=? AND version=?",
                           [*fields.values(), pid, version])
        if cur.rowcount != 1:
            return False
        if event:
            org = conn.execute("SELECT org_id FROM proposals WHERE id=?", (pid,)).fetchone()[0]
            _insert_event(conn, pid, org, event)
    return True


def list_task_events(task_id: str) -> list[dict]:
    """Unscoped: callers load the task through get_proposal(..., org_id=...) first."""
    return [dict(r) for r in get_conn().execute(
        "SELECT * FROM task_events WHERE task_id=? ORDER BY id", (task_id,)).fetchall()]


# --- reports + versions (v2 review pipeline) ---
def create_report(job_id: str, org_id: str, owner: str, template: str = "Full Technical",
                  stage: str = "draft", task_id: Optional[str] = None) -> str:
    import uuid
    rid = str(uuid.uuid4())
    get_conn().execute(
        "INSERT INTO reports (id, job_id, org_id, owner, stage, template, task_id) VALUES (?,?,?,?,?,?,?)",
        (rid, job_id, org_id, owner, stage, template, task_id),
    )
    get_conn().commit()
    return rid


def get_report(rid: str, *, org_id: Optional[str]) -> Optional[dict]:
    q, args = "SELECT * FROM reports WHERE id=?", [rid]
    if org_id is not None:
        q += " AND org_id=?"; args.append(org_id)
    row = get_conn().execute(q, args).fetchone()
    if not row:
        return None
    d = dict(row)
    d["password_viewed"] = bool(d["password_viewed"])
    return d


def list_reports(stage: Optional[str] = None, *, org_id: Optional[str]) -> list[dict]:
    q, args, where = "SELECT * FROM reports", [], []
    _org_where(org_id, where, args)
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


def save_findings(job_id: str, owner: str, org_id: str, findings: list[dict]) -> None:
    """Replace-all per job, upserting by stable id so verdict/status survive re-correlation."""
    conn = get_conn()
    ids = [_finding_id(job_id, f) for f in findings]
    for fid, f in zip(ids, findings):
        conn.execute(
            "INSERT INTO findings (id, job_id, owner, org_id, " + ", ".join(_FINDING_COLS) + ") "
            "VALUES (?,?,?,?," + ",".join("?" for _ in _FINDING_COLS) + ") "
            "ON CONFLICT(id) DO UPDATE SET " +
            ", ".join(f"{c}=excluded.{c}" for c in _FINDING_COLS),
            (fid, job_id, owner, org_id, *(f.get(c) for c in _FINDING_COLS)),
        )
    if ids:
        conn.execute(
            f"DELETE FROM findings WHERE job_id=? AND COALESCE(tool,'') != 'manual' AND id NOT IN ({','.join('?' * len(ids))})",
            [job_id, *ids],
        )
    else:
        conn.execute("DELETE FROM findings WHERE job_id=? AND COALESCE(tool,'') != 'manual'", (job_id,))
    conn.commit()


def get_findings(job_id: str) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM findings WHERE job_id=? ORDER BY created_at", (job_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_finding(fid: str, *, org_id: Optional[str]) -> Optional[dict]:
    q, args = "SELECT * FROM findings WHERE id=?", [fid]
    if org_id is not None:
        q += " AND org_id=?"; args.append(org_id)
    row = get_conn().execute(q, args).fetchone()
    return dict(row) if row else None


def list_findings(*, org_id: Optional[str]) -> list[dict]:
    q, args, where = "SELECT * FROM findings", [], []
    _org_where(org_id, where, args)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY created_at DESC"
    return [dict(r) for r in get_conn().execute(q, args).fetchall()]


# --- findings by target (step 3). A finding belongs to the task whose job produced it; a job nobody
# requested (a pentester's direct scan) is its own target, keyed by the job id. ---
_SEVS = ("critical", "high", "medium", "low")
_SEV_RANK = ("CASE LOWER(f.severity) WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
             "WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END")
_FROM = "FROM findings f LEFT JOIN task_jobs tj ON tj.job_id = f.job_id LEFT JOIN proposals p ON p.id = tj.task_id"
_TARGET = "COALESCE(p.id, f.job_id)"
_LIST_COLS = "f.id, f.name, f.severity, f.host, f.url, f.tool, f.cve, f.cwe, f.verdict, f.status"


def _finding_where(org_id: Optional[str], tp_only: bool, args: list) -> list:
    where = []
    if org_id is not None:
        where.append("f.org_id=?"); args.append(org_id)
    if tp_only:
        where.append("f.verdict='tp'")
    return where


def finding_targets(*, org_id: Optional[str], tp_only: bool) -> list[dict]:
    """One row per target the viewer has findings for, newest scan first. `info` is whatever is not one of
    the four named severities, so the counts always add up to `total`."""
    args: list = []
    where = _finding_where(org_id, tp_only, args)
    sums = ", ".join(f"SUM(LOWER(f.severity)='{s}') AS {s}" for s in _SEVS)
    q = (f"SELECT {_TARGET} AS task_id, COALESCE(p.target, MIN(f.host)) AS target, MIN(f.org_id) AS org_id, "
         f"COUNT(*) AS total, SUM(f.status='fixed') AS fixed, SUM(f.verdict='fp') AS fp, "
         f"MAX(f.created_at) AS scanned_at, {sums} {_FROM}"
         + (" WHERE " + " AND ".join(where) if where else "")
         + f" GROUP BY {_TARGET} ORDER BY scanned_at DESC, task_id")
    out = []
    for r in get_conn().execute(q, args).fetchall():
        d = dict(r)
        counts = {s: d.pop(s) or 0 for s in _SEVS}
        counts["info"] = d["total"] - sum(counts.values())
        out.append({**d, "fixed": d["fixed"] or 0, "fp": d["fp"] or 0, "counts": counts})
    return out


def list_finding_page(task_id: str, *, org_id: Optional[str], tp_only: bool, severity: Optional[str] = None,
                      limit: int = 100, offset: int = 0, upto: Optional[str] = None) -> Optional[tuple[list[dict], int]]:
    """(rows, total) for one target, most severe first (severity rank, name, id). None when the target has no
    findings in this viewer's view, or `upto` is not one of them. `upto` ignores `offset` and returns every row
    from the start through the end of the page that holds that finding."""
    conn = get_conn()
    args: list = [task_id]
    base = f"{_FROM} WHERE {_TARGET}=?"
    for w in _finding_where(org_id, tp_only, args):
        base += f" AND {w}"
    if not conn.execute(f"SELECT 1 {base} LIMIT 1", args).fetchone():
        return None
    if severity == "info":
        base += " AND LOWER(f.severity) NOT IN ('critical','high','medium','low')"
    elif severity:
        base += " AND LOWER(f.severity)=?"; args.append(severity)
    order = f" ORDER BY {_SEV_RANK}, f.name, f.id"
    total = conn.execute(f"SELECT COUNT(*) AS c {base}", args).fetchone()["c"]
    if upto is not None:
        ids = [r["id"] for r in conn.execute(f"SELECT f.id {base}{order}", args)]
        if upto not in ids:
            return None
        offset, limit = 0, (ids.index(upto) // limit + 1) * limit
    rows = conn.execute(f"SELECT {_LIST_COLS}, {_TARGET} AS task_id {base}{order} LIMIT ? OFFSET ?",
                        [*args, limit, offset]).fetchall()
    return [dict(r) for r in rows], total


def get_finding_with_task(fid: str, *, org_id: Optional[str]) -> Optional[dict]:
    q, args = f"SELECT f.*, {_TARGET} AS task_id {_FROM} WHERE f.id=?", [fid]
    if org_id is not None:
        q += " AND f.org_id=?"; args.append(org_id)
    row = get_conn().execute(q, args).fetchone()
    return dict(row) if row else None



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


STEP4_TABLES = ("report_versions", "report_content", "report_pdfs", "task_audit", "ai_turns")


def wipe_report_data() -> dict:
    """Offboarding: the report content, PDF jobs, audit trail, AI turns and old review versions (their files are
    deleted by store.wipe_all). Tasks, report rows and accounts stay."""
    conn = get_conn()
    counts = {}
    for t in STEP4_TABLES:
        counts[t] = conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    return counts


def wipe_tenancy() -> dict:
    """Full reset for `wipe_data.py --all`: accounts, orgs and everything that hangs off them
    (proposals, reports + versions, reset/email-change tokens). Findings are wiped separately."""
    conn = get_conn()
    counts = {}
    for t in ("accounts", "orgs", "proposals", "task_events", "reports", "reset_tokens", "email_changes"):
        counts[t] = conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    return counts


if __name__ == "__main__":
    reset_for_test(":memory:")
    upsert_account("calvin", "h", "client")
    assert get_account("calvin")["role"] == "client"
    upsert_account("calvin", "h2", "pentester")
    assert get_account("calvin")["password_hash"] == "h2", "upsert should update"
    assert get_account("nope") is None

    org = create_org("PT Alice")
    save_findings("j1", "alice", org, [{"name": "SQLi", "severity": "critical", "host": "h", "url": "/x"}])
    fs = get_findings("j1")
    assert len(fs) == 1 and fs[0]["verdict"] == "tp" and fs[0]["status"] == "open"
    fid = fs[0]["id"]
    set_finding(fid, verdict="fp")
    assert get_findings("j1")[0]["verdict"] == "fp", "verdict update failed"
    # re-saving (simulates re-correlation after a manual finding) must preserve that verdict,
    # not reset it back to the default - that's the whole point of the stable/upserted id.
    save_findings("j1", "alice", org, [{"name": "SQLi", "severity": "critical", "host": "h", "url": "/x"}])
    assert get_findings("j1")[0]["verdict"] == "fp", "save_findings must not clobber verdict"
    assert len(list_findings(org_id=org)) == 1 and len(list_findings(org_id=None)) == 1
    assert list_findings(org_id=create_org("PT Bob")) == []
    assert wipe_findings() == 1 and get_findings("j1") == []

    print("db.py self-check OK")


def add_email_change(token_hash: str, username: str, email: str, expires_at: int) -> None:
    get_conn().execute("INSERT INTO email_changes (token_hash, username, email, expires_at) VALUES (?,?,?,?)",
                       (token_hash, username, email, expires_at))
    get_conn().commit()


def claim_email_change(token_hash: str, now: int) -> Optional[tuple[str, str]]:
    conn = get_conn()
    cur = conn.execute("UPDATE email_changes SET used=1 WHERE token_hash=? AND used=0 AND expires_at>?",
                       (token_hash, now))
    conn.commit()
    if cur.rowcount != 1:
        return None
    r = conn.execute("SELECT username, email FROM email_changes WHERE token_hash=?", (token_hash,)).fetchone()
    return (r["username"], r["email"])

# --- step 4: report content, PDFs, audit trail, AI turns ---
PDF_STALE_S = 300     # a PDF job with no progress for this long is failed (the worker died or LibreOffice hung)
TURN_STALE_S = 480    # an AI turn may need two model calls of up to 180 s


def task_findings(task_id: str) -> list[dict]:
    """Every finding of every job the task has run (unscoped: callers load the task through get_proposal first)."""
    rows = get_conn().execute(
        "SELECT f.* FROM findings f JOIN task_jobs tj ON tj.job_id = f.job_id WHERE tj.task_id=? "
        "ORDER BY f.created_at, f.id", (task_id,)).fetchall()
    return [dict(r) for r in rows]


def _content_row(row) -> dict:
    d = dict(row)
    d["content"] = json.loads(d.pop("content_json"))
    return d


def latest_content(task_id: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM report_content WHERE task_id=? ORDER BY version DESC LIMIT 1", (task_id,)).fetchone()
    return _content_row(row) if row else None


def get_content(task_id: str, version: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM report_content WHERE task_id=? AND version=?", (task_id, version)).fetchone()
    return _content_row(row) if row else None


def list_content_versions(task_id: str) -> list[dict]:
    return [dict(r) for r in get_conn().execute(
        "SELECT version, created_by, note, created_at FROM report_content WHERE task_id=? ORDER BY version DESC",
        (task_id,)).fetchall()]


def add_content(task_id: str, org_id: str, content: dict, actor: str, note: str = "",
                base_version: Optional[int] = None) -> Optional[int]:
    """Append version max+1. With `base_version`, only if that is still the latest (0 = none yet); else None."""
    conn = get_conn()
    try:
        with conn:
            top = conn.execute("SELECT COALESCE(MAX(version), 0) FROM report_content WHERE task_id=?",
                               (task_id,)).fetchone()[0]
            if base_version is not None and base_version != top:
                return None
            conn.execute("INSERT INTO report_content (task_id, version, org_id, content_json, created_by, note) "
                         "VALUES (?,?,?,?,?,?)",
                         (task_id, top + 1, org_id, json.dumps(content, ensure_ascii=False), actor, note))
            return top + 1
    except sqlite3.IntegrityError:   # a concurrent writer took top + 1
        return None


_PDF_ACTIVE = "('queued','rendering','converting')"


def get_pdf(jid: str, task_id: Optional[str] = None) -> Optional[dict]:
    q, args = "SELECT * FROM report_pdfs WHERE id=?", [jid]
    if task_id is not None:
        q += " AND task_id=?"; args.append(task_id)
    row = get_conn().execute(q, args).fetchone()
    return dict(row) if row else None


def active_pdf(task_id: str) -> Optional[dict]:
    row = get_conn().execute(
        f"SELECT * FROM report_pdfs WHERE task_id=? AND status IN {_PDF_ACTIVE}", (task_id,)).fetchone()
    return dict(row) if row else None


def latest_ready_pdf(task_id: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM report_pdfs WHERE task_id=? AND status='ready' ORDER BY n DESC LIMIT 1", (task_id,)).fetchone()
    return dict(row) if row else None


def list_pdfs(task_id: str, limit: int = 20) -> list[dict]:
    return [dict(r) for r in get_conn().execute(
        "SELECT * FROM report_pdfs WHERE task_id=? ORDER BY rowid DESC LIMIT ?", (task_id, limit)).fetchall()]


def claim_pdf(task_id: str, org_id: str, content_version: int, actor: str) -> tuple[Optional[dict], bool]:
    """Atomic: the unique index on active jobs lets exactly one insert win. -> (job, created). The loser gets the
    active job with created=False (None only if that job finished in the meantime: the caller looks again)."""
    import uuid
    jid = str(uuid.uuid4())
    conn = get_conn()
    try:
        with conn:
            conn.execute("INSERT INTO report_pdfs (id, task_id, org_id, status, content_version, requested_by) "
                         "VALUES (?,?,?,'queued',?,?)", (jid, task_id, org_id, content_version, actor))
        return get_pdf(jid), True
    except sqlite3.IntegrityError:
        return active_pdf(task_id), False


def set_pdf_state(jid: str, status: str, error: Optional[str] = None) -> bool:
    """Move an ACTIVE job to a new state. False when it is no longer active (reaped): the worker then stops."""
    conn = get_conn()
    cur = conn.execute(
        f"UPDATE report_pdfs SET status=?, error=?, updated_at=datetime('now') WHERE id=? AND status IN {_PDF_ACTIVE}",
        (status, error, jid))
    conn.commit()
    return cur.rowcount == 1


def finish_pdf(jid: str, task_id: str, digest: str, stored_name: str, name_for) -> Optional[dict]:
    """Ready: assign the next per-task number and the user-facing filename in one transaction. None = the job was
    reaped meanwhile (the caller deletes the file it wrote)."""
    conn = get_conn()
    try:
        with conn:
            n = conn.execute("SELECT COALESCE(MAX(n), 0) + 1 FROM report_pdfs WHERE task_id=?", (task_id,)).fetchone()[0]
            cur = conn.execute(
                f"UPDATE report_pdfs SET status='ready', n=?, filename=?, stored_name=?, digest=?, error=NULL, "
                f"updated_at=datetime('now') WHERE id=? AND status IN {_PDF_ACTIVE}",
                (n, name_for(n), stored_name, digest, jid))
            if cur.rowcount != 1:
                return None
    except sqlite3.IntegrityError:
        return None
    return get_pdf(jid)


def reap_pdfs(max_age_s: int) -> int:
    conn = get_conn()
    cur = conn.execute(
        f"UPDATE report_pdfs SET status='failed', error='timed out, try again', updated_at=datetime('now') "
        f"WHERE status IN {_PDF_ACTIVE} AND updated_at < datetime('now', ?)", (f"-{int(max_age_s)} seconds",))
    conn.commit()
    return cur.rowcount


def pdf_filename_for_stored(stored_name: str) -> Optional[str]:
    row = get_conn().execute("SELECT filename FROM report_pdfs WHERE stored_name=?", (stored_name,)).fetchone()
    return row[0] if row else None


def add_audit(task_id: str, org_id: str, actor: str, action: str, subject: str = "", detail: Optional[dict] = None) -> None:
    conn = get_conn()
    conn.execute("INSERT INTO task_audit (task_id, org_id, actor, action, subject, detail_json, at) "
                 "VALUES (?,?,?,?,?,?,datetime('now'))",
                 (task_id, org_id, actor, action, subject, json.dumps(detail or {}, ensure_ascii=False)))
    conn.commit()


def list_audit(task_id: str, limit: int = 200) -> list[dict]:
    out = []
    for r in get_conn().execute("SELECT * FROM task_audit WHERE task_id=? ORDER BY id DESC LIMIT ?", (task_id, limit)):
        d = dict(r)
        d["detail"] = json.loads(d.pop("detail_json") or "{}")
        out.append(d)
    return out


_TURN_ACTIVE = "('queued','running')"
_TURN_SETTABLE = frozenset({"status", "summary", "ops_json", "error"})


def get_turn(turn_id: str, task_id: Optional[str] = None) -> Optional[dict]:
    q, args = "SELECT * FROM ai_turns WHERE id=?", [turn_id]
    if task_id is not None:
        q += " AND task_id=?"; args.append(task_id)
    row = get_conn().execute(q, args).fetchone()
    return dict(row) if row else None


def active_turn(task_id: str) -> Optional[dict]:
    row = get_conn().execute(f"SELECT * FROM ai_turns WHERE task_id=? AND status IN {_TURN_ACTIVE}", (task_id,)).fetchone()
    return dict(row) if row else None


def list_turns(task_id: str, limit: int = 30) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM (SELECT rowid AS rid, * FROM ai_turns WHERE task_id=? ORDER BY rowid DESC LIMIT ?) ORDER BY rid",
        (task_id, limit)).fetchall()
    return [{k: v for k, v in dict(r).items() if k != "rid"} for r in rows]


def claim_turn(task_id: str, org_id: str, actor: str, prompt: str, base_version: int) -> tuple[Optional[dict], bool]:
    import uuid
    tid = str(uuid.uuid4())
    conn = get_conn()
    try:
        with conn:
            conn.execute("INSERT INTO ai_turns (id, task_id, org_id, actor, prompt, status, base_version) "
                         "VALUES (?,?,?,?,?,'queued',?)", (tid, task_id, org_id, actor, prompt, base_version))
        return get_turn(tid), True
    except sqlite3.IntegrityError:
        return active_turn(task_id), False


def set_turn(turn_id: str, **fields) -> bool:
    """Update an ACTIVE turn (queued or running). A finished turn never changes again."""
    if not fields or set(fields) - _TURN_SETTABLE:
        raise ValueError("unsupported turn fields")
    sets = [f"{k}=?" for k in fields] + ["updated_at=datetime('now')"]
    conn = get_conn()
    cur = conn.execute(f"UPDATE ai_turns SET {', '.join(sets)} WHERE id=? AND status IN {_TURN_ACTIVE}",
                       [*fields.values(), turn_id])
    conn.commit()
    return cur.rowcount == 1


def apply_turn(turn_id: str, task_id: str, org_id: str, content: dict, actor: str, note: str) -> Optional[int]:
    """One transaction: claim the turn (ready, unapplied, based on the latest version) AND append the new version.
    None = already applied, not ready, stale, or lost a race."""
    conn = get_conn()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE ai_turns SET applied=1, updated_at=datetime('now') WHERE id=? AND task_id=? AND status='ready' "
                "AND applied=0 AND base_version=(SELECT COALESCE(MAX(version), 0) FROM report_content WHERE task_id=?)",
                (turn_id, task_id, task_id))
            if cur.rowcount != 1:
                return None
            v = conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM report_content WHERE task_id=?",
                             (task_id,)).fetchone()[0]
            conn.execute("INSERT INTO report_content (task_id, version, org_id, content_json, created_by, note) "
                         "VALUES (?,?,?,?,?,?)", (task_id, v, org_id, json.dumps(content, ensure_ascii=False), actor, note))
            conn.execute("UPDATE ai_turns SET applied_version=? WHERE id=?", (v, turn_id))
            return v
    except sqlite3.IntegrityError:
        return None


def reap_turns(max_age_s: int) -> int:
    conn = get_conn()
    cur = conn.execute(
        f"UPDATE ai_turns SET status='failed', error='timed out, try again', updated_at=datetime('now') "
        f"WHERE status IN {_TURN_ACTIVE} AND updated_at < datetime('now', ?)", (f"-{int(max_age_s)} seconds",))
    conn.commit()
    return cur.rowcount


def report_for_task(task_id: str) -> Optional[dict]:
    """The task's report row; a row made before `task_id` existed is found through the task's jobs."""
    row = get_conn().execute(
        "SELECT * FROM reports WHERE task_id=? OR job_id IN (SELECT job_id FROM task_jobs WHERE task_id=?) "
        "ORDER BY (task_id IS NULL), created_at LIMIT 1", (task_id, task_id)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["password_viewed"] = bool(d["password_viewed"])
    return d


def set_report_password_if_empty(rid: str, sealed: str) -> bool:
    conn = get_conn()
    cur = conn.execute("UPDATE reports SET pdf_password=? WHERE id=? AND (pdf_password IS NULL OR pdf_password='')",
                       (sealed, rid))
    conn.commit()
    return cur.rowcount == 1


_TASK_COMPLETED = "EXISTS (SELECT 1 FROM proposals WHERE id=? AND stage='completed')"


def set_finding_if_completed(fid: str, task_id: str, **fields) -> bool:
    """set_finding, but only while the task is still Completed: the check and the write are one statement, so a
    submit that lands in between wins. False = the stage moved, nothing was written."""
    conn = get_conn()
    cur = conn.execute(f"UPDATE findings SET {', '.join(k + '=?' for k in fields)} WHERE id=? AND {_TASK_COMPLETED}",
                       [*fields.values(), fid, task_id])
    conn.commit()
    return cur.rowcount == 1


def insert_manual_finding(task: dict, f: dict) -> Optional[str]:
    """A hand-entered finding of the task's latest scan: random id (never merged with a scanner finding), confirmed (tp).
    Only while the task is Completed (checked in the same statement); None = the stage moved, nothing was written."""
    import uuid
    fid = "m" + uuid.uuid4().hex[:15]
    cols = ("name", "severity", "host", "url", "description", "evidence", "remediation", "impact")
    conn = get_conn()
    cur = conn.execute("INSERT INTO findings (id, job_id, owner, org_id, tool, verdict, status, " + ", ".join(cols) + ") "
                       "SELECT ?,?,?,?,'manual','tp','open'," + ",".join("?" * len(cols)) + f" WHERE {_TASK_COMPLETED}",
                       (fid, task["job_id"], task["submitter"], task["org_id"], *(f.get(c, "") for c in cols), task["id"]))
    conn.commit()
    return fid if cur.rowcount == 1 else None
