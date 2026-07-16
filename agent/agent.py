"""Varuna agent, thin version (Phase C).

Proves the enroll -> poll -> status/findings protocol against the control plane end to
end. Real scan execution (Katana -> Nuclei/SQLMap) lands in Phase D; here `handle()`
ships a placeholder so the transport can be exercised.

First run:  python agent.py <enrollment_token>   (enrolls, saves bearer token)
Later runs: python agent.py                       (polls using the saved token)

Token is kept in a local file for now; Phase I packaging moves it to the OS keyring
(NFR-26). Control-plane URL comes from VARUNA_URL (default http://localhost:8000).
"""
from __future__ import annotations

import os
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(__file__))
import scan  # noqa: E402

BASE = os.environ.get("VARUNA_URL", "http://localhost:8000")
TOKEN_FILE = os.path.expanduser("~/.varuna-agent-token")
POLL_INTERVAL = 5


def _save_token(t: str) -> None:
    with open(TOKEN_FILE, "w") as f:
        f.write(t)


def _load_token() -> str | None:
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE) as f:
        return f.read().strip()


def enroll(enrollment_token: str) -> str:
    r = httpx.post(f"{BASE}/agent/enroll", json={"enrollment_token": enrollment_token})
    r.raise_for_status()
    data = r.json()
    _save_token(data["token"])
    print("enrolled as", data["username"])
    return data["token"]


def handle(job: dict, headers: dict) -> None:
    jid = job["id"]
    print("got job", jid, "->", job.get("target"))
    httpx.post(f"{BASE}/agent/jobs/{jid}/status", headers=headers, json={"status": "running"})
    try:
        raw, tool_status = scan.run_scan(job)   # Katana -> Nuclei/SQLMap, chained
    except Exception as e:
        httpx.post(f"{BASE}/agent/jobs/{jid}/status", headers=headers,
                   json={"status": "failed", "error": str(e)})
        print("job", jid, "failed:", e)
        return
    httpx.post(f"{BASE}/agent/jobs/{jid}/status", headers=headers,
               json={"per_tool_status": tool_status})
    httpx.post(f"{BASE}/agent/jobs/{jid}/findings", headers=headers, json={"raw": raw})
    # Overall failed only if every tool failed; partial success stays "done" (REQ-56, §4.10).
    all_failed = bool(tool_status) and all(v == "failed" for v in tool_status.values())
    httpx.post(f"{BASE}/agent/jobs/{jid}/status", headers=headers,
               json={"status": "failed" if all_failed else "done"})
    print("job", jid, "failed" if all_failed else "done")


def run(token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    print("agent polling", BASE, "every", POLL_INTERVAL, "s")
    while True:
        r = httpx.get(f"{BASE}/agent/poll", headers=headers)
        if r.status_code == 401:
            print("token rejected (revoked?). re-enroll needed.")
            return
        job = r.json().get("job")
        if job:
            handle(job, headers)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    tok = _load_token()
    if not tok:
        if len(sys.argv) < 2:
            print("usage: python agent.py <enrollment_token>   (first run)")
            sys.exit(1)
        tok = enroll(sys.argv[1])
    run(tok)
