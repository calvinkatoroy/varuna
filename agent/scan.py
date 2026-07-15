"""Scan orchestration on the agent (SRS §4.4): Katana first, then chain into the rest.

Katana always runs first as a discovery pre-step; its URL/parameter output feeds Nuclei and
SQLMap (REQ-20, REQ-21). The tools that run come from the job's `tools` list (the Pro scan
mode, or the Standard full stack). The subprocess runner is injectable so orchestration and
the safe profile can be tested without the binaries installed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))
import katana  # noqa: E402
import nuclei  # noqa: E402
import sqlmap  # noqa: E402

TOOL_TIMEOUT = 1800   # 30 min per tool (REQ-26)


def default_run(argv: list[str]) -> str:
    """Run a tool and return its raw output text. File-output tools (-o) return the file;
    SQLMap returns stdout."""
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=TOOL_TIMEOUT)
    if "-o" in argv:
        outfile = argv[argv.index("-o") + 1]
        try:
            with open(outfile) as f:
                return f.read()
        except OSError:
            return ""
    return proc.stdout


def run_scan(job: dict, run=default_run, workdir: str | None = None):
    """Run the scan and return (raw, tool_status).

    Katana runs first; Nuclei/SQLMap chain off its output. Per-tool failures are isolated
    (REQ-54 to REQ-56): one tool failing does NOT cancel the others, and only successful
    tools contribute raw output. If Katana (the pre-step) fails, the downstream tools that
    depend on its URL list are marked failed and skipped (§4.10). tool_status maps each
    tool to "done" or "failed".
    """
    workdir = workdir or tempfile.mkdtemp(prefix="varuna-")
    opts = job.get("opts", {})
    cookie = opts.get("cookie") or None
    tools = job.get("tools", [])
    raw: dict = {}
    status: dict = {}

    katana_out = os.path.join(workdir, "katana.jsonl")
    try:
        raw["katana"] = run(katana.build(job["target"], katana_out, cookie=cookie))
        status["katana"] = "done"
    except Exception:
        status["katana"] = "failed"
        for t in ("nuclei", "sqlmap"):
            if t in tools:
                status[t] = "failed"   # depends on Katana's output (§4.10)
        return raw, status

    if "nuclei" in tools:
        try:
            raw["nuclei"] = run(nuclei.build(
                katana_out, os.path.join(workdir, "nuclei.jsonl"),
                interactsh=opts.get("interactsh"), cookie=cookie,
            ))
            status["nuclei"] = "done"
        except Exception:
            status["nuclei"] = "failed"   # REQ-55: does not cancel SQLMap below

    if "sqlmap" in tools:
        try:
            raw["sqlmap"] = run(sqlmap.build(
                katana_out, os.path.join(workdir, "sqlmap"),
                aggressive=bool(opts.get("aggressive", False)),
                dump=bool(opts.get("dump", False)), os_shell=bool(opts.get("os_shell", False)),
                tamper=opts.get("tamper"), cookie=cookie,
            ))
            status["sqlmap"] = "done"
        except Exception:
            status["sqlmap"] = "failed"

    return raw, status
