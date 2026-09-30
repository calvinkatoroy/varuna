"""Nuclei command builder (SRS §4.4, REQ-21b, NFR-17). Runs on the agent.

Scans Katana's discovered URL list (chaining, REQ-21). Rate limiting is on by default
(NFR-17); DAST fuzzing and a self-hosted Interactsh server enable reflected/DOM and blind
OOB detection (REQ-21b). Higher rate is a Pro opt-in via `rate`.
"""
from __future__ import annotations

SAFE_RATE = 50    # conservative default requests/sec (NFR-17); Pro may raise it
LOCAL_RATE = 150  # local/staging targets (target_class == local) can take a faster scan
# A heavy or chatty app returns errors/timeouts on many template probes; nuclei's default
# max-host-error (30) then gives up on the host entirely. Raise it so a heavy target is not
# abandoned mid-scan.
MAX_HOST_ERROR = 100


# Surface pass: non-DAST templates (exposed files/panels, misconfiguration, tech fingerprint) run
# against the site origin. Never the intrusive classes (NFR-17/19); `deep` adds CVE/vuln
# templates (thousands: slow, so opt-in).
SURFACE_TAGS = "misconfig,exposure,tech"
DEEP_TAGS = SURFACE_TAGS + ",cve,vuln"
EXCLUDE_TAGS = "dos,intrusive,brute-force,bruteforce,fuzz,dast"


def build(urls_file: str, outfile: str, severity: str = "critical,high,medium,low,info",
          dast: bool = True, interactsh: str | None = None,
          rate: int = SAFE_RATE, cookie: str | None = None, header: str | None = None,
          max_host_error: int = MAX_HOST_ERROR, surface: bool = False,
          deep: bool = False) -> list[str]:
    cmd = [
        "nuclei", "-l", urls_file,          # Katana's output (REQ-21)
        "-jsonl", "-o", outfile,
        "-severity", severity,
        "-rate-limit", str(rate),           # NFR-17 always set
        "-mhe", str(max_host_error),        # tolerate a heavy app's errors before skipping it
    ]
    if surface:
        cmd += ["-tags", DEEP_TAGS if deep else SURFACE_TAGS, "-etags", EXCLUDE_TAGS,
                "-timeout", "5", "-retries", "0", "-c", "10", "-ni"]   # -ni: no OOB callbacks
    elif dast:
        cmd.append("-dast")                 # reflected/DOM fuzzing (REQ-21b)
    if interactsh:
        cmd += ["-interactsh-server", interactsh]   # self-hosted OOB (REQ-21b)
    if cookie:
        cmd += ["-H", f"Cookie: {cookie}"]  # authenticated scan (REQ-21a)
    if header:
        cmd += ["-H", header]
    return cmd
