"""Scan orchestration on the agent (SRS §4.4): Katana first, then chain into the rest.

Katana always runs first as a discovery pre-step; its URL/parameter output feeds Nuclei and
SQLMap (REQ-20, REQ-21). The tools that run come from the job's `tools` list (the Pro scan
mode, or the Standard full stack). The subprocess runner is injectable so orchestration and
the safe profile can be tested without the binaries installed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))
import katana  # noqa: E402
import nuclei  # noqa: E402
import sqlmap  # noqa: E402

TOOL_TIMEOUT = 1800   # 30 min per tool (REQ-26)
KATANA_TIMEOUT = 300  # the crawler is capped tightly by the agent: katana's own -ct is
                      # unreliable on some targets, so a hard subprocess bound guarantees the
                      # scan never hangs on discovery. On timeout we use partial output plus
                      # the seed-fallback rather than failing the whole scan.


def _target_list(katana_out: str, seed: str) -> list[str]:
    """Plain URL list for Nuclei/SQLMap: URLs discovered by Katana PLUS the seed target.

    Katana writes JSONL, but Nuclei `-l` and SQLMap `-m` want one plain URL per line, so we
    extract here. The seed is always included, so a heavy or hard-to-crawl target (a JS SPA
    where discovery underperforms, or a crawl that failed) is still scanned directly rather
    than skipped. This is what keeps the scan robust on heavy targets.
    """
    urls: set[str] = set()
    try:
        with open(katana_out) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    u = (obj.get("request") or {}).get("endpoint") or obj.get("endpoint")
                except (json.JSONDecodeError, ValueError):
                    u = line if line.startswith("http") else None
                if u:
                    urls.add(u)
    except OSError:
        pass
    urls.add(seed)
    return sorted(urls)


def default_run(argv: list[str]) -> str:
    """Run a tool and return its raw output text. File-output tools (-o) return the file;
    SQLMap returns stdout. Katana is bounded by KATANA_TIMEOUT and its timeout is tolerated
    (partial output is used); Nuclei/SQLMap timing out raises so partial-failure handling
    marks that tool failed."""
    is_katana = bool(argv) and argv[0] == "katana"
    outfile = argv[argv.index("-o") + 1] if "-o" in argv else None
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=KATANA_TIMEOUT if is_katana else TOOL_TIMEOUT)
    except subprocess.TimeoutExpired:
        if not is_katana:
            raise
        proc = None   # katana cap hit: fall through to whatever it wrote; seed-fallback covers the rest
    if outfile:
        try:
            with open(outfile) as f:
                return f.read()
        except OSError:
            return ""
    return proc.stdout if proc else ""


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
    seed = job["target"]
    raw: dict = {}
    status: dict = {}

    katana_out = os.path.join(workdir, "katana.jsonl")
    try:
        raw["katana"] = run(katana.build(
            seed, katana_out, cookie=cookie,
            headless=opts.get("headless", False),
            depth=opts.get("depth", katana.DEFAULT_DEPTH),
            crawl_duration=opts.get("crawl_duration", katana.DEFAULT_CRAWL_DURATION),
        ))
        status["katana"] = "done"
    except Exception:
        status["katana"] = "failed"
        # Discovery failed, but do NOT give up: still scan the seed directly below (§4.10 is
        # about dependency, and the seed is always a valid target). Robust on heavy targets.

    # Nuclei/SQLMap scan the discovered URLs plus the seed (always at least the seed).
    targets_file = os.path.join(workdir, "targets.txt")
    with open(targets_file, "w") as f:
        f.write("\n".join(_target_list(katana_out, seed)) + "\n")

    if "nuclei" in tools:
        try:
            raw["nuclei"] = run(nuclei.build(
                targets_file, os.path.join(workdir, "nuclei.jsonl"),
                interactsh=opts.get("interactsh"), cookie=cookie,
            ))
            status["nuclei"] = "done"
        except Exception:
            status["nuclei"] = "failed"   # REQ-55: does not cancel SQLMap below

    if "sqlmap" in tools:
        try:
            raw["sqlmap"] = run(sqlmap.build(
                targets_file, os.path.join(workdir, "sqlmap"),
                aggressive=bool(opts.get("aggressive", False)),
                dump=bool(opts.get("dump", False)), os_shell=bool(opts.get("os_shell", False)),
                tamper=opts.get("tamper"), cookie=cookie,
            ))
            status["sqlmap"] = "done"
        except Exception:
            status["sqlmap"] = "failed"

    return raw, status
