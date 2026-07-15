"""Katana command builder (SRS §4.4, NFR-19). Runs on the agent.

Discovery pre-step: crawl + extract URLs and parameters/forms as JSONL. Safe by default:
a deny-list of destructive path patterns is excluded from the crawl, and automatic form
submission is never enabled, so discovery itself cannot cause data loss (NFR-19).
"""
from __future__ import annotations

# NFR-19 destructive-path deny-list, applied as an out-of-scope crawl regex.
DENY_PATHS = "logout|signout|signoff|delete|remove|destroy|drop|admin/delete"


def build(target: str, outfile: str, cookie: str | None = None) -> list[str]:
    cmd = [
        "katana", "-u", target,
        "-jc",              # crawl JS
        "-kf", "all",       # known-files
        "-jsonl", "-o", outfile,
        "-cos", DENY_PATHS,  # exclude destructive paths (NFR-19)
    ]
    # NFR-19: automatic form fill/submit (-aff) is intentionally NOT set, so forms that
    # look destructive are never auto-submitted.
    if cookie:
        cmd += ["-H", f"Cookie: {cookie}"]   # authenticated crawl (REQ-21a)
    return cmd
