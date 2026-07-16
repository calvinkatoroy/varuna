"""Katana command builder (SRS §4.4, NFR-17, NFR-19). Runs on the agent.

Discovery pre-step: crawl + extract URLs and parameters/forms as JSONL. Built to stay robust
on heavy targets, not just easy ones:
  - JS endpoint parsing (`-jc`) pulls API routes out of a SPA's JavaScript bundle;
  - a crawl-duration cap plus bounded depth and rate limiting so a large or slow target stays
    bounded (NFR-17);
  - headless rendering is available as an opt-in for SPAs whose routes only appear after the
    page renders. It is OFF by default because a headless browser launch is environment
    dependent (it can hang where no usable browser is present); the scan orchestrator also
    always scans the seed target directly, so coverage never depends on the crawl alone.
Safe by default: destructive paths are excluded and forms are never auto-submitted (NFR-19).
"""
from __future__ import annotations

# NFR-19 destructive-path deny-list, applied as an out-of-scope crawl regex.
DENY_PATHS = "logout|signout|signoff|delete|remove|destroy|drop|admin/delete"

DEFAULT_DEPTH = 3
DEFAULT_CRAWL_DURATION = "3m"   # cap: heavy targets finish and yield coverage, never hang
DEFAULT_RATE = 100              # requests/sec (NFR-17)


def build(target: str, outfile: str, cookie: str | None = None, headless: bool = False,
          depth: int = DEFAULT_DEPTH, crawl_duration: str = DEFAULT_CRAWL_DURATION,
          rate: int = DEFAULT_RATE) -> list[str]:
    cmd = [
        "katana", "-u", target,
        "-jsonl", "-o", outfile,
        "-kf", "all",                 # known-files probing
        "-jc",                        # parse JavaScript for endpoints
        "-d", str(depth),             # bounded crawl depth
        "-ct", str(crawl_duration),   # crawl-time cap: bound heavy/slow targets
        "-rl", str(rate),             # rate limit (NFR-17)
        "-cos", DENY_PATHS,           # exclude destructive paths (NFR-19)
        "-silent",
    ]
    if headless:
        cmd.append("-headless")       # render JS SPAs so client-side routes are discovered
    # -aff (automatic form fill/submit) intentionally NOT set, so destructive forms are never
    # auto-submitted (NFR-19).
    if cookie:
        cmd += ["-H", f"Cookie: {cookie}"]   # authenticated crawl (REQ-21a)
    return cmd
