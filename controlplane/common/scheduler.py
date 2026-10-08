"""Scheduler (step 2): starts scheduled scans at their time, expires work past the client's window,
suspends what cannot run. tick(now) is one pass over the DB and Redis; run() calls it every 30 s from a
daemon thread in the private API, guarded by a Redis lock so two containers never both run it."""
from __future__ import annotations

import datetime
import threading
import uuid

import board
import db
import models
import notify
import redis_store
import workflow

TICK_SECONDS = 30
LOCK_KEY = "scheduler:lock"
LOCK_TTL = 60
DELIVERY_STUCK = datetime.timedelta(minutes=10)   # `delivering` this long means the delivery crashed
GRACE = datetime.timedelta(minutes=15)   # a due scan that cannot start for this long is suspended


def _past(t: dict, now: datetime.datetime, field: str = "not_after") -> bool:
    return bool(t.get(field)) and now > workflow.parse_utc(t[field])


def _move(t: dict, to: str, now: datetime.datetime, comment: str | None = None) -> bool:
    try:
        workflow.transition(t["id"], to, workflow.SCHEDULER, org_id=None, version=t["version"],
                            comment=comment, now=now)
        return True
    except workflow.WorkflowError:   # someone else moved it first
        return False


def _suspend(t: dict, now: datetime.datetime, reason: str, out: dict) -> None:
    if _move(t, "scan/suspended", now, reason):
        out["suspended"] += 1
        notify.notify(f"@{t.get('assignee') or 'team'}: scan for task {t['id'][:8]} suspended: {reason}")


def _each(rows: list, handle, now: datetime.datetime, out: dict) -> None:
    """Run `handle` on every row; one bad row is logged and skipped, never aborts the pass."""
    for t in rows:
        try:
            handle(t, now, out)
        except Exception as e:
            print(f"WARNING: scheduler skipped task {str(t.get('id'))[:8]}: {type(e).__name__}", flush=True)


def _expire_waiting(t: dict, now: datetime.datetime, out: dict) -> None:
    if _past(t, now) and _move(t, "expired", now):
        out["expired"] += 1


def _start_scheduled(t: dict, now: datetime.datetime, out: dict) -> None:
    if _past(t, now):
        if _move(t, "expired", now):
            out["expired"] += 1
        return
    if not t.get("scheduled_at") or workflow.parse_utc(t["scheduled_at"]) > now:
        return
    try:
        workflow.transition(t["id"], "scan/in_progress", workflow.SCHEDULER, org_id=None,
                            version=t["version"], now=now)
        out["started"] += 1
    except (workflow.Unavailable, workflow.Invalid) as e:
        reason = getattr(e, "reason", None) or str(e)
        first = t.get("due_since")
        if not first:
            first = now.isoformat()
            db.update_proposal(t["id"], due_since=first)
        if now - workflow.parse_utc(first) >= GRACE:
            _suspend(t, now, reason, out)
        else:
            out["waiting"] += 1
    except workflow.WorkflowError:
        pass   # the other tick (or a person) moved it first
    except Exception as e:   # a start side effect failed after the task moved: pause it for a person
        print(f"WARNING: scan start failed for task {t['id'][:8]}: {type(e).__name__}", flush=True)
        fresh = db.get_proposal(t["id"], org_id=None)
        if fresh and workflow.state_key(fresh) == "scan/in_progress":
            _suspend(fresh, now, "could not dispatch the scan", out)


def _check_running(t: dict, now: datetime.datetime, out: dict) -> None:
    if _past(t, now):
        _suspend(t, now, "client window ended", out)
    elif t.get("scheduled_at") and t.get("max_minutes") and             now > workflow.parse_utc(t["scheduled_at"]) + datetime.timedelta(minutes=t["max_minutes"]):
        _suspend(t, now, "maximum scan duration reached", out)


def _recover_delivery(t: dict, now: datetime.datetime, out: dict) -> None:
    """A task stuck in `delivering` (the delivery crashed): finish it if the client was already served,
    else hand it back to the manager."""
    changed = datetime.datetime.strptime(t["updated_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.UTC)
    if now - changed < DELIVERY_STUCK:
        return
    r = db.get_report_by_job(t["job_id"]) if t.get("job_id") else None
    if r and r["stage"] == models.REPORT_DELIVERED:
        ok = _move(t, "delivered", now)
    else:
        ok = _move(t, "review_manager", now, "delivery did not finish, returned to manager review")
    if ok:
        out["recovered"] += 1


def tick(now: datetime.datetime) -> dict:
    out = {"started": 0, "expired": 0, "suspended": 0, "waiting": 0, "recovered": 0}
    board.reap_stalled(now)
    waiting = db.list_proposals(stage="task", org_id=None) +         db.list_proposals(stage="scan", scan_state="pending", org_id=None)
    _each(waiting, _expire_waiting, now, out)
    _each(db.list_proposals(stage="scan", scan_state="scheduled", org_id=None), _start_scheduled, now, out)
    _each(db.list_proposals(stage="scan", scan_state="in_progress", org_id=None), _check_running, now, out)
    _each(db.list_proposals(stage=workflow.DELIVERING, org_id=None), _recover_delivery, now, out)
    return out


def _acquire(r, token: str) -> bool:
    """Take the lock, or renew it if we already hold it."""
    if r.set(LOCK_KEY, token, nx=True, ex=LOCK_TTL):
        return True
    if r.get(LOCK_KEY) == token:
        r.set(LOCK_KEY, token, ex=LOCK_TTL)
        return True
    return False


def run(stop: threading.Event, clock=lambda: datetime.datetime.now(datetime.UTC),
        interval: float = TICK_SECONDS) -> None:
    token = str(uuid.uuid4())
    while True:
        try:
            if _acquire(redis_store.get_redis(), token):
                tick(clock())
        except Exception as e:   # a bad pass must not kill the loop
            print(f"WARNING: scheduler pass failed: {e}", flush=True)
        if stop.wait(interval):
            return


def start() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=run, args=(stop,), daemon=True, name="varuna-scheduler").start()
    return stop
