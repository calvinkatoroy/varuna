"""Scan orchestration on the agent (SRS §4.4): Katana first, then chain into the rest.

Katana always runs first as a discovery pre-step; its URL/parameter output feeds Nuclei and
SQLMap (REQ-20, REQ-21). The tools that run come from the job's `tools` list (the Pro scan
mode, or the Standard full stack). The subprocess runner is injectable so orchestration and
the safe profile can be tested without the binaries installed.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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


_STATIC = re.compile(r"\.(js|mjs|css|map|png|jpe?g|gif|svg|ico|webp|woff2?|ttf|eot|otf|mp[34]|webm|pdf|zip|gz|txt|xml)$", re.I)
_PAGE = re.compile(r"(^[^.]*$|\.(html?|php|aspx?|jsp|do|action)$)", re.I)   # could hold a form
MAX_FORM_PAGES = 25   # extra form-candidate pages handed to SQLMap on top of parameter URLs


def _shape(url: str) -> str:
    """Dedupe key: same path (numeric ids folded) + same parameter NAMES = same test."""
    p = urlsplit(url)
    path = re.sub(r"/\d+(?=/|$)", "/{n}", p.path)
    names = sorted(k for k, _ in parse_qsl(p.query, keep_blank_values=True))
    return f"{p.scheme}://{p.netloc}{path}?{'&'.join(names)}"


def _fill_blank_params(url: str) -> str:
    """`?q=` (discovered from JS with no value) -> `?q=1`: DAST fuzzing and SQLMap skip
    parameters that have no value to mutate."""
    p = urlsplit(url)
    if "=" not in p.query:
        return url
    q = urlencode([(k, v or "1") for k, v in parse_qsl(p.query, keep_blank_values=True)])
    return urlunsplit(p._replace(query=q))


def filter_targets(urls, seed: str) -> tuple[list[str], list[str]]:
    """(nuclei_targets, sqlmap_targets). Static assets are dropped (nothing to test) and URLs
    that only differ by parameter values / numeric ids are collapsed. SQLMap only needs URLs
    with parameters plus a bounded set of pages that may hold forms: feeding it every crawled
    URL made it the slowest phase by far (195 targets, ~10 of them with parameters)."""
    seen, nuclei_t = set(), []
    home = urlsplit(seed)
    for u in sorted({_fill_blank_params(x) for x in urls} | {seed}):
        p = urlsplit(u)
        # SCOPE: only the authorized host. JS bundles and crawls are full of third-party URLs
        # (CDNs, social, analytics); scanning those would be testing systems nobody authorized.
        if (p.hostname or "").lower() != (home.hostname or "").lower() or p.port != home.port:
            continue
        if _STATIC.search(p.path):
            continue
        k = _shape(u)
        if k not in seen:
            seen.add(k)
            nuclei_t.append(u)
    with_params = [u for u in nuclei_t if urlsplit(u).query]
    pages = [u for u in nuclei_t if not urlsplit(u).query and _PAGE.search(urlsplit(u).path)]
    pages = ([seed] if seed in pages else []) + [u for u in pages if u != seed]
    return nuclei_t, list(dict.fromkeys(with_params + pages[:MAX_FORM_PAGES]))


def authenticate(auth: dict, seed: str, post=None) -> dict:
    """Log in once (team-supplied credentials, advanced scans only) and return session material
    for the tools: {"cookie": "a=b; c=d", "header": "Authorization: Bearer ..."} (either may be
    absent). auth: login_url, username, password, username_field/password_field (default
    username/password), json (send JSON instead of a form), token_path (dotted path to a bearer
    token in the JSON response, e.g. "authentication.token"). The login URL must be on the
    scanned host: credentials are never sent anywhere else."""
    import httpx
    login = auth.get("login_url") or ""
    if not login.startswith("http"):
        login = seed.rstrip("/") + "/" + login.lstrip("/")
    lp, sp = urlsplit(login), urlsplit(seed)
    if (lp.hostname, lp.port) != (sp.hostname, sp.port):
        raise RuntimeError("login_url must be on the scanned host")
    body = {auth.get("username_field", "username"): auth.get("username", ""),
            auth.get("password_field", "password"): auth.get("password", "")}
    with httpx.Client(timeout=20, follow_redirects=True, verify=False) as c:
        r = (post or c.post)(login, **({"json": body} if auth.get("json") else {"data": body}))
        if r.status_code >= 400:
            raise RuntimeError(f"login failed (HTTP {r.status_code})")
        out = {}
        cookies = "; ".join(f"{k}={v}" for k, v in c.cookies.items())
        if cookies:
            out["cookie"] = cookies
        if auth.get("token_path"):
            node = r.json()
            for part in auth["token_path"].split("."):
                node = node[part]
            out["header"] = f"Authorization: Bearer {node}"
        if not out:
            raise RuntimeError("login returned no session cookie or token")
        return out


def normalize_target(target: str) -> str:
    """Tools' own resolvers fail on the name `localhost` on some hosts (Nuclei reports "no
    address found" and silently scans nothing), so scan the loopback IP instead."""
    t = target if "://" in target else "http://" + target
    p = urlsplit(t)
    if (p.hostname or "").lower() != "localhost":
        return target
    netloc = "127.0.0.1" + (f":{p.port}" if p.port else "")
    return urlunsplit(p._replace(netloc=netloc))


def check_reachable(target: str, timeout: float = 15.0) -> None:
    """Fail fast if the target does not answer at all (any HTTP status counts as reachable).
    Without this a dead target ran three tools that all produced nothing and the job was
    reported "done" with zero findings, indistinguishable from a clean bill of health."""
    import httpx
    try:
        httpx.get(normalize_target(target), timeout=timeout, follow_redirects=True, verify=False)
    except httpx.HTTPError as e:
        raise RuntimeError(f"target unreachable from the agent: {type(e).__name__}") from e


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
    header = None
    if opts.get("auth"):   # log in first; a failed login fails the scan rather than scanning anonymously
        sess = authenticate(opts["auth"], job["target"] if "://" in job["target"] else "http://" + job["target"])
        cookie = "; ".join(x for x in (cookie, sess.get("cookie")) if x) or None
        header = sess.get("header")
    tools = job.get("tools", [])
    seed = normalize_target(job["target"])
    raw: dict = {}
    status: dict = {}

    checkpoint({"katana": "running"})
    katana_out = os.path.join(workdir, "katana.jsonl")
    print(f"[{seed}] running katana (up to {KATANA_TIMEOUT}s)...")
    try:
        raw["katana"] = run(katana.build(
            seed, katana_out, cookie=cookie, header=header,
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
    if "katana" in raw:   # nothing downstream reads katana's full request/response dump (MBs); ship the URL list
        raw["katana"] = "\n".join(sorted(targets))
    try:
        targets.update(discover.js_endpoints(seed, fetch or discover.default_fetch))
    except Exception:
        pass
    nuclei_targets, sqlmap_targets = filter_targets(targets, seed)
    targets_file = os.path.join(workdir, "targets.txt")
    with open(targets_file, "w") as f:
        f.write("\n".join(nuclei_targets) + "\n")
    sqlmap_file = os.path.join(workdir, "sqlmap_targets.txt")
    with open(sqlmap_file, "w") as f:
        f.write("\n".join(sqlmap_targets) + "\n")

    # Local/staging targets tolerate a faster Nuclei; public ones keep the conservative rate (NFR-17).
    rate = opts.get("rate") or (nuclei.LOCAL_RATE if job.get("target_class") == "local" else nuclei.SAFE_RATE)

    def _nuclei_dast():
        print(f"[{seed}] running nuclei (DAST) on {len(nuclei_targets)} target(s) (up to {TOOL_TIMEOUT}s)...")
        try:
            return run(nuclei.build(
                targets_file, os.path.join(workdir, "nuclei.jsonl"),
                interactsh=opts.get("interactsh"), cookie=cookie, header=header, rate=int(rate),
            ))
        except Exception:
            return None

    def _nuclei_surface():
        # Host-level checks (exposed files, misconfiguration, tech) once against the origin.
        origin_file = os.path.join(workdir, "origin.txt")
        p = urlsplit(seed)
        with open(origin_file, "w") as f:
            f.write(f"{p.scheme}://{p.netloc}" + chr(10))
        print(f"[{seed}] running nuclei (surface{', deep' if opts.get('deep') else ''}) on the origin...")
        try:
            return run(nuclei.build(
                origin_file, os.path.join(workdir, "nuclei_surface.jsonl"), cookie=cookie, header=header,
                rate=int(rate), surface=True, deep=bool(opts.get("deep", False)),
            ))
        except Exception:
            return None

    def _nuclei():
        # Two passes, one after the other: run together, the broad surface pass loaded a
        # single-process target enough that DAST's SQL-injection probes timed out and the
        # critical finding vanished. The tool is "done" if either produced output (an empty
        # string is a clean result), "failed" only if both broke.
        outs = [_nuclei_dast(), _nuclei_surface()]
        if all(o is None for o in outs):
            return "nuclei", None, "failed"
        return "nuclei", chr(10).join(o for o in outs if o), "done"

    def _sqlmap():
        print(f"[{seed}] running sqlmap on {len(sqlmap_targets)} target(s) (up to {TOOL_TIMEOUT}s)...")
        try:
            out = run(sqlmap.build(
                sqlmap_file, os.path.join(workdir, "sqlmap"),
                aggressive=bool(opts.get("aggressive", False)),
                dump=bool(opts.get("dump", False)), os_shell=bool(opts.get("os_shell", False)),
                tamper=opts.get("tamper"), cookie=cookie, header=header,
            ))
            return "sqlmap", out, "done"
        except Exception:
            return "sqlmap", None, "failed"

    # Nuclei and SQLMap only depend on Katana's output, not on each other: run them together
    # (total time = the slower one, not the sum). One checkpoint covers both phases.
    phases = [fn for name, fn in (("nuclei", _nuclei), ("sqlmap", _sqlmap)) if name in tools]
    if phases:
        checkpoint({**status, **{fn.__name__[1:]: "running" for fn in phases}})
        with concurrent.futures.ThreadPoolExecutor(len(phases)) as ex:
            for name, out, st in [f.result() for f in [ex.submit(fn) for fn in phases]]:
                if out is not None:
                    raw[name] = out
                status[name] = st
                print(f"[{seed}] {name} {st}")

    return raw, status


if __name__ == "__main__":
    assert normalize_target("http://localhost:3000/x") == "http://127.0.0.1:3000/x"
    assert normalize_target("https://example.com") == "https://example.com"
    assert normalize_target("http://10.0.0.5:80") == "http://10.0.0.5:80"
    n, q = filter_targets(["http://a/x.js", "http://a/item/1", "http://a/item/2", "http://a/s?q=1",
                           "http://a/s?q=2", "http://a/logo.png", "http://a/login"], "http://a")
    assert "http://a/x.js" not in n and "http://a/logo.png" not in n
    assert len([u for u in n if "/item/" in u]) == 1 and len([u for u in n if "/s?" in u]) == 1
    assert "http://a/s?q=1" in q and "http://a/login" in q and "http://a/x.js" not in q
    # Self-check: checkpoint(status) runs once per phase group (katana, then nuclei+sqlmap together),
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
    assert len(calls) == 2, f"expected 2 checkpoints (katana; nuclei+sqlmap together), got {len(calls)}"
    assert calls[0] == {"katana": "running"}
    assert calls[1] == {"katana": "done", "nuclei": "running", "sqlmap": "running"}

    calls.clear()
    run_scan({**job, "tools": []}, run=_fake_run, checkpoint=lambda status: calls.append(status))
    assert len(calls) == 1, "katana-only run should checkpoint once"
    assert calls[0] == {"katana": "running"}

    run_scan({**job, "tools": []}, run=_fake_run)   # no checkpoint passed: must not raise
    print("scan.py self-check OK")
