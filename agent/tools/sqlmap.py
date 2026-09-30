"""SQLMap command builder (SRS §4.4, REQ-21c, NFR-18). Runs on the agent.

Tests Katana's discovered URLs/forms for SQL injection. SAFE by default: detection-only at
`--level 1 --risk 1`, and the destructive flags (`--dump`, `--os-shell`, elevated
level/risk) are reachable ONLY through the Pro `aggressive` opt-in (NFR-18). The Standard
safe profile can never enable them, because `dump`/`os_shell` are ignored unless
`aggressive` is set. `--tamper` provides WAF evasion (REQ-21c).
"""
from __future__ import annotations


THREADS = 4


def build(urls_file: str, outdir: str, aggressive: bool = False,
          tamper: str | None = None, cookie: str | None = None, header: str | None = None,
          dump: bool = False, os_shell: bool = False,
          level: int | None = None, risk: int | None = None, technique: str | None = None) -> list[str]:
    cmd = [
        "sqlmap", "-m", urls_file,   # Katana's output (REQ-21)
        "--batch", "--forms",
        "--threads", str(THREADS),   # detection-only, so parallel requests are safe; ~4x faster per target
        "--output-dir", outdir,
    ]
    if technique:
        cmd += ["--technique", technique]    # subset of BEUSTQ, validated server-side
    if aggressive:
        # Lead-pentester opt-in ONLY (NFR-18). Nothing here is reachable from the safe profile.
        cmd += ["--level", str(level or 3), "--risk", str(risk or 2)]
        if dump:
            cmd.append("--dump")
        if os_shell:
            cmd.append("--os-shell")
    else:
        # Safe profile: detection-only, never destructive (NFR-18). Level 2 only adds cookie/header
        # parameter tests; risk stays 1 (no heavy/time-based-write payloads).
        cmd += ["--level", str(min(level or 1, 2)), "--risk", "1"]
    if tamper:
        cmd += ["--tamper", tamper]          # WAF evasion (REQ-21c)
    if cookie:
        cmd += ["--cookie", cookie]          # authenticated context (REQ-21a)
    if header:
        cmd += ["--headers", header]
    return cmd
