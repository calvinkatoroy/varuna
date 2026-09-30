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
import discover  # noqa: E402
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
        with open(katana_out, encoding="utf-8", errors="replace") as f:
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
                              encoding="utf-8", errors="replace",
                              timeout=KATANA_TIMEOUT if is_katana else TOOL_TIMEOUT)
    except subprocess.TimeoutExpired:
        if not is_katana:
            raise
        proc = None   # katana cap hit: fall through to whatever it wrote; seed-fallback covers the rest
    if outfile:
        try:
            with open(outfile, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""
    return proc.stdout if proc else ""


def run_scan(job: dict, run=default_run, workdir: str | None = None, fetch=None, checkpoint=None):
    """Run the scan and return (raw, tool_status).

    Katana runs first; Nuclei/SQLMap chain off its output. Per-tool failures are isolated
    (REQ-54 to REQ-56): one tool failing does NOT cancel the others, and only successful
    tools contribute raw output. If Katana (the pre-step) fails, the downstream tools that
    depend on its URL list are marked failed and skipped (§4.10). tool_status maps each
    tool to "done" or "failed".

    `checkpoint(status)` (v2) is called before each tool phase - before Katana, before Nuclei,
    before SQLMap - with the cumulative per-tool status dict so far, including the phase that's
    about to start marked "running". It serves two purposes: it's the agent's chance to block
    (poll-and-sleep) while a job is suspended, AND it's how live progress reaches the control
    plane - without this, the agent used to report status exactly once, after the entire scan
    (all tools) finished, so a job sat at "running" with an empty per_tool_status for the whole
    duration with nothing to show a live progress UI. A no-op by default so tests and
    non-progress-aware callers don't need to know about it. This can only report phase
    boundaries, never interrupt a tool mid-run or report fractional progress within one - true
    mid-subprocess pause/progress on Windows would need fragile thread-suspend calls against an
    arbitrary third-party process, which isn't worth it here.
    """
    checkpoint = checkpoint or (lambda status: None)
    workdir = workdir or tempfile.mkdtemp(prefix="varuna-")
    opts = job.get("opts", {})
    cookie = opts.get("cookie") or None
    tools = job.get("tools", [])
    seed = job["target"]
    raw: dict = {}
    status: dict = {}

    checkpoint({"katana": "running"})
    katana_out = os.path.join(workdir, "katana.jsonl")
    print(f"[{seed}] running katana (up to {KATANA_TIMEOUT}s)...")
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
    print(f"[{seed}] katana {status['katana']}")
        # Discovery failed, but do NOT give up: still scan the seed directly below (§4.10 is
        # about dependency, and the seed is always a valid target). Robust on heavy targets.

    # Build the target list: Katana's crawl + the seed, plus API endpoints pulled from the
    # target's JS bundles (SPA discovery, since Katana's headless crawl is unreliable). Always
    # at least the seed, so a heavy target is never skipped.
    targets = set(_target_list(katana_out, seed))
    try:
        targets.update(discover.js_endpoints(seed, fetch or discover.default_fetch))
    except Exception:
        pass
    targets_file = os.path.join(workdir, "targets.txt")
    with open(targets_file, "w") as f:
        f.write("\n".join(sorted(targets)) + "\n")

    if "nuclei" in tools:
        checkpoint({**status, "nuclei": "running"})
        print(f"[{seed}] running nuclei on {len(targets)} target(s) (up to {TOOL_TIMEOUT}s)...")
        try:
            raw["nuclei"] = run(nuclei.build(
                targets_file, os.path.join(workdir, "nuclei.jsonl"),
                interactsh=opts.get("interactsh"), cookie=cookie,
            ))
            status["nuclei"] = "done"
        except Exception:
            status["nuclei"] = "failed"   # REQ-55: does not cancel SQLMap below
        print(f"[{seed}] nuclei {status['nuclei']}")

    if "sqlmap" in tools:
        checkpoint({**status, "sqlmap": "running"})
        print(f"[{seed}] running sqlmap on {len(targets)} target(s) (up to {TOOL_TIMEOUT}s)...")
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
        print(f"[{seed}] sqlmap {status['sqlmap']}")

    return raw, status


if __name__ == "__main__":
    # Self-check: checkpoint(status) runs exactly once per tool phase that actually executes,
    # each time carrying the phase about to start marked "running" plus whatever's already
    # finished - and not at all when checkpoint is omitted (default no-op).
    def _fake_run(argv):
        outfile = argv[argv.index("-o") + 1] if "-o" in argv else None
        if outfile:
            open(outfile, "w").close()
        return "ok"

    calls = []
    job = {"target": "http://t.local", "tools": ["nuclei", "sqlmap"], "opts": {}}
    run_scan(job, run=_fake_run, checkpoint=lambda status: calls.append(status))
    assert len(calls) == 3, f"expected 3 checkpoints (katana, nuclei, sqlmap), got {len(calls)}"
    assert calls[0] == {"katana": "running"}
    assert calls[1] == {"katana": "done", "nuclei": "running"}
    assert calls[2] == {"katana": "done", "nuclei": "done", "sqlmap": "running"}

    calls.clear()
    run_scan({**job, "tools": []}, run=_fake_run, checkpoint=lambda status: calls.append(status))
    assert len(calls) == 1, "katana-only run should checkpoint once"
    assert calls[0] == {"katana": "running"}

    run_scan({**job, "tools": []}, run=_fake_run)   # no checkpoint passed: must not raise
    print("scan.py self-check OK")
