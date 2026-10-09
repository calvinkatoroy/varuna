"""Outgoing email (password reset). Standard-library SMTP; configured entirely by environment.

SMTP_HOST (unset = email disabled), SMTP_PORT (587), SMTP_USER / SMTP_PASSWORD (optional),
SMTP_FROM (defaults to SMTP_USER), SMTP_SECURITY = starttls (default) | ssl | none.
Never raises: a dead mail server must not break a request. Returns whether it was sent.
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def enabled() -> bool:
    return bool(os.environ.get("SMTP_HOST"))


def send(to: str, subject: str, body: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    if not host:
        print(f"MAIL not sent (SMTP_HOST is not set): '{subject}' for {to}", flush=True)
        return False
    user = os.environ.get("SMTP_USER", "")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = os.environ.get("SMTP_FROM") or user, to, subject
    msg.set_content(body)
    mode = os.environ.get("SMTP_SECURITY", "starttls").lower()
    try:
        port = int(os.environ.get("SMTP_PORT") or ("465" if mode == "ssl" else "587"))
        with (smtplib.SMTP_SSL(host, port, timeout=10) if mode == "ssl" else smtplib.SMTP(host, port, timeout=10)) as s:
            if mode == "starttls":
                s.starttls()
            if user:
                s.login(user, os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"MAIL failed: {type(e).__name__}", flush=True)
        return False
