"""Best-effort event notifications (optional).

Set NOTIFY_WEBHOOK_URL to a Slack/Teams/Discord-compatible incoming webhook and the team gets a
message when work is waiting on them (new task, a suspended scan, a task reaching a review stage).
Unset = silent no-op. Never raises and never blocks a request for long: a dead webhook must not
break transitions or reviews. No finding detail is sent, only event names and ids.
"""
from __future__ import annotations

import os
import threading

import httpx


def notify(text: str) -> None:
    url = os.environ.get("NOTIFY_WEBHOOK_URL")
    if not url:
        return

    def _send() -> None:
        try:
            httpx.post(url, json={"text": f"[Varuna] {text}", "content": f"[Varuna] {text}"}, timeout=5)
        except Exception:
            pass   # webhook down / misconfigured: notifications are best-effort

    threading.Thread(target=_send, daemon=True).start()
