"""mailer.send tolerates compose's empty-string env defaults."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import mailer  # noqa: E402


@pytest.mark.parametrize("mode,port", [("starttls", 587), ("none", 587), ("ssl", 465)])
def test_empty_smtp_port_uses_the_default_for_the_mode(monkeypatch, mode, port):
    seen = {}

    class Fake:
        def __init__(self, host, p, timeout=None):
            seen["port"] = p
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, m): seen["sent"] = True

    monkeypatch.setattr(mailer.smtplib, "SMTP", Fake)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", Fake)
    monkeypatch.setenv("SMTP_HOST", "mail.example")
    monkeypatch.setenv("SMTP_PORT", "")
    monkeypatch.setenv("SMTP_SECURITY", mode)
    monkeypatch.setenv("SMTP_FROM", "v@example.com")
    assert mailer.send("a@b.c", "s", "b") is True
    assert seen == {"port": port, "sent": True}
