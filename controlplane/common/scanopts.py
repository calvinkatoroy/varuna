"""Validation of advanced-scan options (team only; clients can never set opts, see browser.py).

The advanced-scan GUI is the gate for the scan's riskier knobs, so this is an allow-list with
clamped ranges: unknown keys are dropped, types are coerced or rejected, and the destructive
SQLMap switches (dump / os_shell) are only honoured for the lead pentester AND only together
with an explicit `aggressive` opt-in (safe-profile lock, NFR-17/18/19).
Pure stdlib so it is unit-testable without Redis/DB/HTTP.
"""
from __future__ import annotations

import models

SEVERITIES = ("info", "low", "medium", "high", "critical")
# GUI label -> nuclei template tag
TAGS = {"cves": "cve", "cve": "cve", "misconfig": "misconfig", "exposures": "exposure", "exposure": "exposure",
        "xss": "xss", "sqli": "sqli", "lfi": "lfi", "rce": "rce", "takeover": "takeover", "tech": "tech"}
TECHNIQUES = set("BEUSTQ")
DBMS = {"mysql", "postgresql", "mssql", "oracle", "sqlite", "mariadb"}
AUTH_KEYS = ("login_url", "username", "password", "username_field", "password_field", "token_path")


class BadOpts(ValueError):
    pass


def _int(v, lo, hi, name):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise BadOpts(f"{name} must be a number")
    if not lo <= n <= hi:
        raise BadOpts(f"{name} must be between {lo} and {hi}")
    return n


def _str(v, name, limit=2048):
    if not isinstance(v, str) or len(v) > limit or any(ord(c) < 32 for c in v):
        raise BadOpts(f"{name} must be plain text under {limit} characters")
    return v


def sanitize(opts: dict | None, role: str) -> dict:
    """Return the safe, normalized opts dict the agent understands. Raises BadOpts."""
    o = opts or {}
    out: dict = {}
    if "depth" in o:
        out["depth"] = _int(o["depth"], 1, 5, "depth")
    if "crawl_duration" in o:                       # seconds from the GUI -> katana's "Ns"
        out["crawl_duration"] = f"{_int(o['crawl_duration'], 30, 900, 'crawl_duration')}s"
    if "rate" in o:
        out["rate"] = _int(o["rate"], 10, 300, "rate")
    for flag in ("headless", "deep", "json"):
        if flag in o:
            out[flag] = bool(o[flag])
    if "severity" in o:
        sev = [s for s in o["severity"] if s in SEVERITIES] if isinstance(o["severity"], list) else []
        if not sev:
            raise BadOpts("severity must list at least one of " + ", ".join(SEVERITIES))
        out["severity"] = sev
    if "tags" in o:
        tags = sorted({TAGS[t] for t in o["tags"] if t in TAGS}) if isinstance(o["tags"], list) else []
        if tags:
            out["tags"] = tags
    # Extra tuning knobs: all inside ranges that cannot make a scan destructive.
    for k, lo, hi in (("concurrency", 1, 50), ("timeout", 1, 60), ("retries", 0, 5), ("threads", 1, 10), ("sqlmap_timeout", 5, 120)):
        if k in o:
            out[k] = _int(o[k], lo, hi, k)
    if "delay" in o:
        try:
            d = float(o["delay"])
        except (TypeError, ValueError):
            raise BadOpts("delay must be a number")
        if not 0 <= d <= 10:
            raise BadOpts("delay must be between 0 and 10 seconds")
        out["delay"] = d
    if o.get("random_agent"):
        out["random_agent"] = True
    if o.get("dbms"):
        if str(o["dbms"]).lower() not in DBMS:
            raise BadOpts("dbms must be one of " + ", ".join(sorted(DBMS)))
        out["dbms"] = str(o["dbms"]).lower()
    if "exclude_tags" in o:
        ex = sorted({TAGS[t] for t in o["exclude_tags"] if t in TAGS}) if isinstance(o["exclude_tags"], list) else []
        if ex:
            out["exclude_tags"] = ex
    if o.get("cookie"):
        out["cookie"] = _str(o["cookie"], "cookie", 4096)
    if o.get("interactsh"):
        out["interactsh"] = _str(o["interactsh"], "interactsh", 255)
    if o.get("auth"):
        a = o["auth"]
        if not isinstance(a, dict) or not a.get("login_url") or not a.get("password"):
            raise BadOpts("auth needs login_url, username and password")
        out["auth"] = {k: _str(a[k], f"auth.{k}", 512) for k in AUTH_KEYS if a.get(k)}
        out["auth"]["json"] = bool(a.get("json"))
        out["auth"]["form"] = bool(a.get("form"))
    # SQLMap: level/risk/technique are validated; anything above the safe profile, and the
    # destructive switches, require an explicit `aggressive` opt-in.
    for k, lo, hi in (("level", 1, 5), ("risk", 1, 3)):
        if k in o:
            out[k] = _int(o[k], lo, hi, k)
    if "technique" in o:
        tech = "".join(sorted(set(str(o["technique"]).upper()) & TECHNIQUES))
        if tech:
            out["technique"] = tech
    if o.get("tamper"):
        out["tamper"] = _str(o["tamper"], "tamper", 128)
    wants_aggressive = bool(o.get("aggressive")) or out.get("level", 1) > 2 or out.get("risk", 1) > 1
    if wants_aggressive:
        if role != models.ROLE_LEAD:
            raise BadOpts("aggressive scanning (SQLMap level > 2 or risk > 1) requires the lead pentester")
        out["aggressive"] = True
    for danger in ("dump", "os_shell"):
        if o.get(danger):
            if not out.get("aggressive"):
                raise BadOpts(f"{danger} requires the aggressive opt-in")
            out[danger] = True
    return out
