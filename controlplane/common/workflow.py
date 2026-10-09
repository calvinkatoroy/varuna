"""Task workflow (step 2): the one place that moves a task between stages.

A task is a row in `proposals` (the table keeps its name). `stage` + `scan_state` drive the board, the
client timeline and the scheduler. transition() is the only function that changes them: it checks RULES,
the actor's CURRENT role (read from the DB, never from a token), validates, then compare-and-sets on
`version` and writes exactly one task_events row in the same transaction. The loser of any race gets
Conflict (HTTP 409).
"""
from __future__ import annotations

import datetime
import json
import os
import uuid
from typing import Callable, Optional
from urllib.parse import urlsplit, urlunsplit

import audit
import classifier
import db
import dispatch
import models
import notify
import redis_store
import tokens

UTC = datetime.UTC
SYSTEM = "sys:agent"          # job results from the agent API and the stall reaper
SCHEDULER = "sys:scheduler"   # usernames cannot contain ':' (sysadmin._USERNAME): no account can act as these
FULL_STACK = ["katana", "nuclei", "sqlmap"]
DEFAULT_MINUTES = 240
DELIVERING = "delivering"     # transient: the manager's approval is producing the protected PDF
MOVED = "this task was just changed by someone else; refresh"


class WorkflowError(Exception):
    status = 409


class NotFound(WorkflowError):
    status = 404


class Forbidden(WorkflowError):
    status = 403


class Conflict(WorkflowError):
    status = 409


class Unavailable(Conflict):
    """The scan cannot start right now; the scheduler retries. `reason` is shown as the suspend reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class Invalid(WorkflowError):
    status = 422


STAGE_ROLE = {"review_lead_pentester": models.ROLE_LEAD, "review_lead_cyber": models.ROLE_LEAD_CYBER,
              "review_governance": models.ROLE_GOVERNANCE, "review_manager": models.ROLE_MANAGER}
PENTESTERS = frozenset({models.ROLE_PENTESTER, models.ROLE_LEAD})
ANY_PENTESTER = "any_pentester"   # any pentester or lead pentester
OWNER = "owner"                   # the task's assignee (still a pentester) or any lead pentester


def _rule(who: set, kind: str, comment: bool = False) -> dict:
    return {"who": frozenset(who), "kind": kind, "comment": comment}


# (from, to) -> who may do it, what it is, whether a comment is required. Anything else is 409.
RULES = {
    ("task", "scan/pending"): _rule({ANY_PENTESTER}, "claim"),
    ("task", "declined"): _rule({ANY_PENTESTER}, "decline", True),
    ("task", "expired"): _rule({SCHEDULER}, "expire"),
    ("scan/pending", "scan/in_progress"): _rule({OWNER}, "start"),
    ("scan/pending", "scan/scheduled"): _rule({OWNER}, "schedule"),
    ("scan/pending", "expired"): _rule({SCHEDULER}, "expire"),
    ("scan/scheduled", "scan/pending"): _rule({OWNER}, "unschedule"),
    ("scan/scheduled", "scan/in_progress"): _rule({SCHEDULER}, "start"),
    ("scan/scheduled", "scan/suspended"): _rule({SCHEDULER}, "suspend", True),
    ("scan/scheduled", "expired"): _rule({SCHEDULER}, "expire"),
    ("scan/in_progress", "scan/suspended"): _rule({OWNER, SCHEDULER, SYSTEM}, "suspend", True),
    ("scan/in_progress", "completed"): _rule({SYSTEM}, "complete"),
    ("scan/suspended", "scan/in_progress"): _rule({OWNER}, "resume"),
    ("scan/suspended", "scan/scheduled"): _rule({OWNER}, "schedule"),
    ("scan/suspended", "completed"): _rule({SYSTEM}, "complete"),
    ("scan/suspended", "expired"): _rule({OWNER}, "close", True),
    ("completed", "review_lead_pentester"): _rule({OWNER}, "submit"),
    ("review_lead_pentester", "review_lead_cyber"): _rule({models.ROLE_LEAD}, "approve"),
    ("review_lead_pentester", "completed"): _rule({models.ROLE_LEAD}, "send_back", True),
    ("review_lead_cyber", "review_governance"): _rule({models.ROLE_LEAD_CYBER}, "approve"),
    ("review_lead_cyber", "review_lead_pentester"): _rule({models.ROLE_LEAD_CYBER}, "send_back", True),
    ("review_governance", "review_manager"): _rule({models.ROLE_GOVERNANCE}, "approve"),
    ("review_governance", "review_lead_cyber"): _rule({models.ROLE_GOVERNANCE}, "send_back", True),
    ("review_manager", "delivered"): _rule({models.ROLE_MANAGER}, "deliver"),
    ("review_manager", "review_governance"): _rule({models.ROLE_MANAGER}, "send_back", True),
    # recovery of a delivery that crashed mid-way (scheduler.tick): no person can make these moves
    ("delivering", "delivered"): _rule({SCHEDULER}, "recover_delivered"),
    ("delivering", "review_manager"): _rule({SCHEDULER}, "recover_returned"),
}
_SYSTEM_ONLY = frozenset({SYSTEM, SCHEDULER})

# Client vocabulary: no assignee, no internal wording.
_CLIENT = {"task": "waiting", "scan/pending": "accepted", "scan/scheduled": "scheduled",
           "scan/in_progress": "scanning", "scan/suspended": "paused", "delivered": "delivered",
           "declined": "declined", "expired": "expired"}


def _key(stage: str, scan_state: Optional[str]) -> str:
    return f"scan/{scan_state}" if stage == "scan" else stage


def state_key(task: dict) -> str:
    return _key(task["stage"], task.get("scan_state"))


def _split(to: str) -> tuple[str, Optional[str]]:
    return ("scan", to[5:]) if to.startswith("scan/") else (to, None)


def parse_utc(value, name: str = "time") -> datetime.datetime:
    """Offset-aware ISO 8601 -> aware UTC datetime. A time without an offset is refused."""
    try:
        t = datetime.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if t.tzinfo is None:
            raise Invalid(f"{name} must include a timezone offset (for example +07:00)")
        return t.astimezone(UTC)
    except (ValueError, OverflowError):
        raise Invalid(f"{name} must be an ISO 8601 date and time")


def _iso(t: datetime.datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def scan_url(task: dict) -> str:
    """The address the agent scans: the client's target with the optional port and path applied."""
    t = task["target"].strip()
    u = urlsplit(t if "://" in t else "http://" + t)
    netloc = u.netloc
    if task.get("port"):
        host = u.hostname or ""
        netloc = f"[{host}]:{task['port']}" if ":" in host else f"{host}:{task['port']}"
    return urlunsplit((u.scheme, netloc, task.get("path") or u.path, u.query, ""))


def _tags(actor: str, task: dict) -> frozenset:
    """What `actor` counts as for this task, from the DB at call time."""
    if actor in _SYSTEM_ONLY:
        return frozenset({actor})
    acct = db.get_account(actor)
    if not acct or acct["disabled"] or not models.is_team(acct["role"]):
        return frozenset()
    role = acct["role"]
    tags = {role}
    if role in PENTESTERS:
        tags.add(ANY_PENTESTER)
        if role == models.ROLE_LEAD or task.get("assignee") == actor:
            tags.add(OWNER)
    return frozenset(tags)


def _why(who: frozenset) -> str:
    if OWNER in who:
        return "only the assignee or a lead pentester can do this"
    if ANY_PENTESTER in who:
        return "only pentesters can do this"
    roles = sorted(r for r in who if r in models.ROLES)
    if roles:
        return f"only the {roles[0].replace('_', ' ')} can do this"
    return "only the system does this"


def create_task(submitter: str, org_id: str, *, target: str, path: str = "", port: Optional[int] = None,
                notes: str = "", not_before: str, not_after: str, scan_mode: str = models.SCAN_LOCAL,
                now: Optional[datetime.datetime] = None) -> dict:
    """The (new) -> task row: validate the client's fields and create the task with its first event."""
    now = now or datetime.datetime.now(UTC)
    if scan_mode not in (models.SCAN_LOCAL, models.SCAN_CLOUD):
        raise Invalid("scan_mode must be local or cloud")
    try:
        classifier.validate_syntax(target)
        if scan_mode == models.SCAN_CLOUD:
            classifier.require_public_syntax(target)
    except classifier.ClassifyRejected as e:
        raise Invalid(f"invalid target: {e}")
    path = (path or "").strip()
    if path and (not path.startswith("/") or any(ord(c) < 33 or ord(c) == 127 for c in path)):
        raise Invalid("path must start with / and contain no spaces")
    if port is not None and not 1 <= port <= 65535:
        raise Invalid("port must be between 1 and 65535")
    start, end = parse_utc(not_before, "not_before"), parse_utc(not_after, "not_after")
    if start >= end:
        raise Invalid("the time limit must end after it starts")
    if end <= now:
        raise Invalid("the time limit has already ended")
    row = {"submitter": submitter, "org_id": org_id, "target": target.strip(), "path": path, "port": port,
           "notes": (notes or "").strip(), "not_before": _iso(start), "not_after": _iso(end),
           "scan_mode": scan_mode, "stage": "task"}
    pid = db.create_proposal(row, event={"actor": submitter, "to_stage": "task", "at": _iso(now)})
    audit.log("task_created", actor=submitter, task=pid)
    notify.notify(f"New task {pid[:8]} is waiting for a pentester")
    return db.get_proposal(pid, org_id=org_id)


def _window(task: dict) -> tuple[datetime.datetime, datetime.datetime]:
    return parse_utc(task["not_before"], "not_before"), parse_utc(task["not_after"], "not_after")


def _minutes(max_minutes, room: int) -> int:
    if room < 1:
        raise Invalid("not enough time left in the client's time limit window")
    try:
        if isinstance(max_minutes, bool):
            raise TypeError
        minutes = int(max_minutes)
    except (TypeError, ValueError, OverflowError):
        raise Invalid("max_minutes must be a whole number of minutes")
    if not 1 <= minutes <= room:
        raise Invalid(f"the scan may run 1 to {room} minutes inside the client's time limit")
    return minutes


def _classify(task: dict) -> str:
    """DNS classification of the scan address, with the cloud rule (public target unless the owner listed it)."""
    try:
        cls = classifier.classify(scan_url(task))
    except classifier.ClassifyRejected:
        raise Unavailable("target unreachable")
    if task["scan_mode"] == models.SCAN_CLOUD and cls != classifier.CLASS_CLOUD:
        own = {h.strip().lower() for h in os.environ.get("VARUNA_CLOUD_ALLOW_HOSTS", "").split(",") if h.strip()}
        if classifier._extract_host(task["target"]).lower() not in own:
            raise Invalid("cloud scan needs a public target; this one resolves to a private or local address. "
                          "Ask the client to choose a local scan.")
    return cls


def _schedule_fields(task: dict, scheduled_at: Optional[str], max_minutes: Optional[int], opts: Optional[dict]) -> dict:
    if not scheduled_at:
        raise Invalid("choose a start time")
    at = parse_utc(scheduled_at, "scheduled_at")
    nb, na = _window(task)
    room = int((na - at).total_seconds() // 60)
    if at < nb or room < 1:
        raise Invalid("the scan must start inside the client's time limit")
    minutes = min(DEFAULT_MINUTES, room) if max_minutes is None else _minutes(max_minutes, room)
    try:
        cls = _classify(task)
    except Unavailable:
        raise Invalid("the target cannot be resolved; check the address with the client")
    fields = {"scheduled_at": _iso(at), "max_minutes": minutes, "target_class": cls}
    if opts is not None:
        fields["opts_json"] = json.dumps(opts)
    return fields


def _live_job(task: dict) -> Optional[dict]:
    job = redis_store.get_job(task["job_id"]) if task.get("job_id") else None
    return job if job and job.get("status") in (models.STATUS_QUEUED, models.STATUS_RUNNING) else None


def _start(task: dict, actor: str, now: datetime.datetime, max_minutes: Optional[int],
           opts: Optional[dict]) -> tuple[dict, Callable[[], Optional[str]]]:
    """Checks for start/resume (window now, classification, scanner online) -> (fields, side effect).
    The side effect runs only after the compare-and-set won, so a double start dispatches once."""
    nb, na = _window(task)
    if now < nb:
        raise Invalid("the client's time limit has not started yet; schedule the scan instead")
    if now >= na:
        raise Invalid("the client's time limit has ended")
    room = int((na - now).total_seconds() // 60)
    if room < 1:
        raise Invalid("not enough time left in the client's time limit window")
    minutes = _minutes(max_minutes, room) if max_minutes is not None else \
        min(task.get("max_minutes") or DEFAULT_MINUTES, room)
    cls = _classify(task)
    if actor == SCHEDULER and task.get("target_class") and cls != task["target_class"]:
        raise Unavailable("target classification changed since it was scheduled")
    cloud = task["scan_mode"] == models.SCAN_CLOUD
    if not tokens.is_online(models.CLOUD_AGENT if cloud else task["submitter"], now):
        raise Unavailable("agent offline")
    fields = {"scheduled_at": _iso(now), "max_minutes": minutes, "target_class": cls}
    if opts is not None:
        fields["opts_json"] = json.dumps(opts)
    live = _live_job(task)
    if live:   # a paused job is still in the agent's hands: let it continue
        return fields, lambda: redis_store.set_suspended(live["id"], False)
    job = models.Job(
        id=str(uuid.uuid4()), target=scan_url(task), target_class=cls, submitter=task["submitter"],
        role=models.ROLE_CLIENT, tools=list(FULL_STACK), opts=task.get("opts") or {} if opts is None else opts,
        status=models.STATUS_QUEUED, per_tool_status={},
        scan_mode=models.SCAN_CLOUD if cloud else models.SCAN_LOCAL,
        executor=models.CLOUD_AGENT if cloud else None, org_id=task["org_id"],
    ).to_dict()
    fields["job_id"] = job["id"]

    def side() -> Optional[str]:
        redis_store.set_job(job)
        redis_store.add_org_job(task["org_id"], job["id"])
        dispatch.dispatch_job(job, pre_approved=True)   # fails the job when the agent belongs to another org
        return (job.get("error") or "scan refused") if job["status"] == models.STATUS_FAILED else None
    return fields, side


def _deliver(task: dict, fields: dict, event: dict, on_deliver: Optional[Callable[[dict], None]]) -> None:
    """Claim review_manager -> delivering first, run the delivery, then delivered; restore on failure."""
    if on_deliver is None:
        raise Conflict("delivery runs on the private plane")
    v = task["version"]
    if not db.cas_task(task["id"], v, {"stage": DELIVERING, "scan_state": None}):
        raise Conflict(MOVED)
    try:
        on_deliver(task)
    except BaseException:
        if not db.cas_task(task["id"], v + 1, {"stage": task["stage"], "scan_state": None}):
            raise Conflict("delivery failed and the task could not be restored; check it before retrying")
        raise
    if not db.cas_task(task["id"], v + 1, fields, event):
        raise Conflict(MOVED)


def transition(task_id: str, to: str, actor: str, *, org_id: Optional[str], version: Optional[int] = None,
               comment: Optional[str] = None, scheduled_at: Optional[str] = None,
               max_minutes: Optional[int] = None, opts: Optional[dict] = None,
               now: Optional[datetime.datetime] = None,
               on_deliver: Optional[Callable[[dict], None]] = None) -> dict:
    """Move a task. org_id None = staff scope (every org). Returns the updated row.
    Raises NotFound / Forbidden / Conflict (incl. Unavailable) / Invalid."""
    now = now or datetime.datetime.now(UTC)
    task = db.get_proposal(task_id, org_id=org_id)
    if not task:
        raise NotFound("no such task")
    frm = state_key(task)
    rule = RULES.get((frm, to))
    if rule is None:
        raise Conflict(f"a task cannot move from {frm} to {to}")
    if version is not None and version != task["version"]:
        raise Conflict(MOVED)
    if not (_tags(actor, task) & rule["who"]):
        raise Forbidden(_why(rule["who"]))
    note = (comment or "").strip()[:2000]
    if rule["comment"] and not note:
        raise Invalid("a reason is required")
    stage, scan_state = _split(to)
    fields: dict = {"stage": stage, "scan_state": scan_state, "due_since": None}
    side = None
    kind = rule["kind"]
    if kind == "claim":
        fields["assignee"] = actor
    elif kind == "decline":
        fields["decline_cause"] = note
    elif kind == "suspend":
        fields["suspend_reason"] = note
        if task.get("job_id"):
            side = lambda: redis_store.set_suspended(task["job_id"], True)   # agent pauses at the next phase
    elif kind == "schedule":
        fields.update(_schedule_fields(task, scheduled_at, max_minutes, opts))
    elif kind in ("start", "resume"):
        extra, side = _start(task, actor, now, max_minutes, opts)
        fields.update(extra)
    event = {"actor": actor, "comment": note or None, "at": _iso(now), "from_stage": task["stage"],
             "from_scan_state": task.get("scan_state"), "to_stage": stage, "to_scan_state": scan_state}
    if kind == "deliver":
        _deliver(task, fields, event, on_deliver)
    elif not db.cas_task(task_id, task["version"], fields, event):
        raise Conflict(MOVED)
    failure = side() if side else None
    audit.log("task_transition", actor=actor, task=task_id, frm=frm, to=to)
    if stage in STAGE_ROLE or stage in ("delivered", "declined"):
        notify.notify(f"Task {task_id[:8]} is now {to}")
    if failure:
        return transition(task_id, "scan/suspended", SYSTEM, org_id=None, comment=failure, now=now)
    return db.get_proposal(task_id, org_id=None)


def actions(task: dict, actor: str) -> list[dict]:
    """The moves a person could make from the task's current state, with whether they may and why not."""
    tags = _tags(actor, task)
    out = []
    for (frm, to), rule in RULES.items():
        if frm != state_key(task) or rule["who"] <= _SYSTEM_ONLY:
            continue
        ok = bool(tags & rule["who"])
        out.append({"to": to, "kind": rule["kind"], "comment": rule["comment"], "allowed": ok,
                    "why": None if ok else _why(rule["who"])})
    if (task["stage"] == "completed" or task["stage"] in STAGE_ROLE) and task.get("job_id")             and not db.get_report_by_job(task["job_id"]):
        ok = can_edit_report(task, actor)   # transition-free: the report is generated on demand
        out.append({"to": "", "kind": "generate_report", "comment": False, "allowed": ok,
                    "why": None if ok else "only the stage owner can do this"})
    return out


def can_edit_report(task: dict, actor: str) -> bool:
    """Upload a version / switch template: the assignee or a lead at `completed`, else the stage's role."""
    tags = _tags(actor, task)
    if task["stage"] == "completed":
        return OWNER in tags
    role = STAGE_ROLE.get(task["stage"])
    return bool(role) and role in tags


def client_status(task: dict) -> str:
    return _CLIENT.get(state_key(task), "in_review")


def client_timeline(task_id: str) -> list[dict]:
    """The client's view of task_events: status words only, plus the decline cause. Consecutive repeats
    (the four review stages) collapse into one 'in_review' entry."""
    out: list[dict] = []
    for e in db.list_task_events(task_id):
        word = _CLIENT.get(_key(e["to_stage"], e["to_scan_state"]), "in_review")
        if out and out[-1]["status"] == word:
            continue
        item = {"status": word, "at": e["at"]}
        if word == "declined":
            item["note"] = e["comment"]
        out.append(item)
    return out


def can_audit(task: dict, actor: str) -> bool:
    """Change a task's report (verdicts, findings, content, PDF, AI chat): the assignee or a lead pentester, at
    `completed` only. Reviewers never edit; they send the task back."""
    return task["stage"] == "completed" and OWNER in _tags(actor, task)
