"""Tool argv + safe-profile + orchestration tests (SRS §4.4, NFR-17/18/19).

The safety invariant that matters most: the Standard/safe profile can NEVER emit SQLMap's
destructive flags, and the crawler always excludes destructive paths. Pure argv construction
+ orchestration with an injected runner, so it runs offline without the binaries.
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent", "tools"))

import discover  # noqa: E402
import katana  # noqa: E402
import nuclei  # noqa: E402
import sqlmap  # noqa: E402
import scan  # noqa: E402


def test_katana_safe_denylist_and_no_form_submit():
    cmd = katana.build("http://t.local", "/tmp/k.jsonl")
    assert "-cos" in cmd and cmd[cmd.index("-cos") + 1] == katana.DENY_PATHS  # NFR-19
    assert "-aff" not in cmd, "auto form-fill/submit must never be enabled (NFR-19)"
    assert "-jsonl" in cmd


def test_katana_handles_heavy_targets():
    # Robust on heavy targets: JS endpoint parsing + crawl-time cap + bounded depth + rate.
    cmd = katana.build("http://t.local", "/tmp/k.jsonl")
    assert "-jc" in cmd, "JS parsing pulls API routes out of a SPA bundle"
    assert "-ct" in cmd, "a crawl-duration cap must bound heavy/slow targets (no hang)"
    assert "-d" in cmd and "-rl" in cmd, "bounded depth + rate limit (NFR-17)"
    # headless is environment-dependent (browser launch can hang), so it is opt-in, off by default.
    assert "-headless" not in cmd
    assert "-headless" in katana.build("http://t.local", "/tmp/k.jsonl", headless=True)


def test_js_endpoint_discovery():
    # SPA discovery: pull API routes out of the JS bundle (the robust replacement for the
    # unreliable headless crawl). Fetch is faked so this runs offline.
    def fake_fetch(url):
        if url.endswith(".js"):
            return '"api/Products" "/rest/user/login" "rest/products/search"'
        return '<script src="main.js"></script>'

    eps = discover.js_endpoints("http://t.local", fetch=fake_fetch)
    assert "http://t.local/api/Products" in eps
    assert "http://t.local/rest/user/login" in eps
    assert any("rest/products" in e for e in eps)


def test_js_endpoint_discovery_captures_query_param():
    # Template literals (`rest/products/search?q=${term}`) compile to a string literal
    # ending in "?q=" - that must survive so SQLMap has a parameter to test, not just a
    # bare path (this is what previously required a manually-supplied ?q=).
    def fake_fetch(url):
        if url.endswith(".js"):
            return '"rest/products/search?q=" + encodeURIComponent(criteria)'
        return '<script src="main.js"></script>'

    eps = discover.js_endpoints("http://t.local", fetch=fake_fetch)
    assert "http://t.local/rest/products/search?q=" in eps


def test_scan_merges_js_endpoints_into_targets():
    import tempfile
    wd = tempfile.mkdtemp()

    def fake_fetch(url):
        return '"rest/products"' if url.endswith(".js") else '<script src="main.js"></script>'

    job = {"target": "http://t.local", "tools": ["nuclei"], "opts": {}}
    scan.run_scan(job, run=lambda a: "", workdir=wd, fetch=fake_fetch)
    with open(os.path.join(wd, "targets.txt")) as f:
        content = f.read()
    assert "http://t.local/rest/products" in content, "discovered SPA endpoints must be scanned"
    assert "http://t.local" in content, "seed still present"


def test_nuclei_rate_limited_and_dast():
    cmd = nuclei.build("/tmp/k.jsonl", "/tmp/n.jsonl")
    assert "-rate-limit" in cmd, "rate limiting must always be set (NFR-17)"
    assert "-dast" in cmd
    assert "-mhe" in cmd, "must tolerate a heavy target's errors, not skip the host"
    assert cmd[cmd.index("-l") + 1] == "/tmp/k.jsonl", "must scan Katana's list (REQ-21)"


def test_sqlmap_safe_profile_is_detection_only():
    cmd = sqlmap.build("/tmp/k.jsonl", "/tmp/out")   # aggressive defaults False
    assert "--level" in cmd and cmd[cmd.index("--level") + 1] == "1"
    assert "--risk" in cmd and cmd[cmd.index("--risk") + 1] == "1"
    assert "--dump" not in cmd and "--os-shell" not in cmd, "safe profile must never be destructive (NFR-18)"


def test_sqlmap_safe_ignores_destructive_flags_without_aggressive():
    # Even if dump/os_shell are passed, they must be ignored unless aggressive is set.
    cmd = sqlmap.build("/tmp/k.jsonl", "/tmp/out", aggressive=False, dump=True, os_shell=True)
    assert "--dump" not in cmd and "--os-shell" not in cmd, "safe profile is locked (NFR-21)"


def test_sqlmap_aggressive_is_pro_opt_in():
    cmd = sqlmap.build("/tmp/k.jsonl", "/tmp/out", aggressive=True, dump=True, os_shell=True)
    assert "--dump" in cmd and "--os-shell" in cmd
    assert cmd[cmd.index("--risk") + 1] == "2"


def test_cookie_passed_to_all_tools():
    c = "session=abc"
    assert "Cookie: session=abc" in katana.build("t", "o", cookie=c)
    assert "Cookie: session=abc" in nuclei.build("u", "o", cookie=c)
    assert sqlmap.build("u", "o", cookie=c)[-1] == c and "--cookie" in sqlmap.build("u", "o", cookie=c)


def test_orchestration_katana_first_then_chained():
    calls = []

    def fake_run(argv):
        calls.append(argv)
        return f"output-of-{argv[0]}"

    import tempfile
    wd = tempfile.mkdtemp()
    job = {"target": "http://t.local", "tools": ["katana", "nuclei", "sqlmap"], "opts": {}}
    raw, status = scan.run_scan(job, run=fake_run, workdir=wd, fetch=lambda u: "")
    assert calls[0][0] == "katana", "Katana must run first (REQ-20)"
    # Nuclei + SQLMap chained to the extracted plain target list (not Katana's raw JSONL)
    assert any(a[0] == "nuclei" and any("targets.txt" in x for x in a) for a in calls)
    assert any(a[0] == "sqlmap" and any("targets.txt" in x for x in a) for a in calls)
    assert set(raw) == {"katana", "nuclei", "sqlmap"}
    assert status == {"katana": "done", "nuclei": "done", "sqlmap": "done"}
    # The seed target is always in the list, so a heavy target is scanned even if crawl finds nothing.
    with open(os.path.join(wd, "targets.txt")) as f:
        assert "http://t.local" in f.read(), "seed must always be a scan target"


def test_orchestration_respects_scan_mode():
    calls = []
    job = {"target": "http://t.local", "tools": ["katana", "nuclei"], "opts": {}}  # VA Only
    scan.run_scan(job, run=lambda a: calls.append(a[0]) or "", fetch=lambda u: "")
    assert "sqlmap" not in calls, "SQLMap must not run when not in the selected mode"


def test_one_tool_failure_does_not_cancel_others():
    # Nuclei blows up; SQLMap must still run and its findings must be kept (REQ-55, REQ-56).
    def flaky_run(argv):
        if argv[0] == "nuclei":
            raise RuntimeError("nuclei crashed")
        return f"out-{argv[0]}"

    job = {"target": "http://t.local", "tools": ["katana", "nuclei", "sqlmap"], "opts": {}}
    raw, status = scan.run_scan(job, run=flaky_run, fetch=lambda u: "")
    assert status == {"katana": "done", "nuclei": "failed", "sqlmap": "done"}
    assert "sqlmap" in raw and "nuclei" not in raw, "successful tools' output preserved"


def test_default_run_survives_non_cp1252_output():
    # Windows subprocess.run(text=True) with no explicit encoding decodes with the ANSI
    # codepage (cp1252), which raises UnicodeDecodeError on bytes like 0x9d that real tool
    # output can contain. default_run must pin encoding="utf-8", errors="replace".
    argv = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes([0x9d]))"]
    out = scan.default_run(argv)
    assert out is not None


def test_katana_failure_still_scans_seed():
    # Robust: if discovery (Katana) fails, do NOT give up. Nuclei/SQLMap still scan the seed.
    def katana_fails(argv):
        if argv[0] == "katana":
            raise RuntimeError("katana crashed")
        return f"out-{argv[0]}"

    job = {"target": "http://t.local", "tools": ["katana", "nuclei", "sqlmap"], "opts": {}}
    raw, status = scan.run_scan(job, run=katana_fails, fetch=lambda u: "")
    assert status["katana"] == "failed"
    assert status["nuclei"] == "done" and status["sqlmap"] == "done", "downstream must still scan the seed"
    assert "nuclei" in raw and "sqlmap" in raw


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_tools: all green")


def test_filter_targets_drops_static_and_collapses_shapes():
    urls = ["http://a/main.js", "http://a/logo.png", "http://a/item/1", "http://a/item/2",
            "http://a/s?q=1", "http://a/s?q=2", "http://a/login"]
    n, q = scan.filter_targets(urls, "http://a")
    assert not any(u.endswith((".js", ".png")) for u in n)
    assert len([u for u in n if "/item/" in u]) == 1, "ids folded"
    assert len([u for u in n if "/s?" in u]) == 1, "same param names = one test"
    assert "http://a/s?q=1" in q and "http://a/login" in q
    assert len(q) < len(urls)


def test_nuclei_and_sqlmap_run_concurrently_with_one_checkpoint():
    import threading
    seen, both = [], threading.Barrier(2, timeout=5)

    def fake_run(argv):
        if argv[0] in ("nuclei", "sqlmap"):
            both.wait()   # only passes if the other tool is running at the same time
        of = argv[argv.index("-o") + 1] if "-o" in argv else None
        if of:
            open(of, "w").close()
        return "x"

    cps = []
    raw, st = scan.run_scan({"target": "http://t.local", "tools": ["nuclei", "sqlmap"], "opts": {}},
                            run=fake_run, checkpoint=cps.append, fetch=lambda u: "")
    assert st == {"katana": "done", "nuclei": "done", "sqlmap": "done"}
    assert cps[-1] == {"katana": "done", "nuclei": "running", "sqlmap": "running"}


def test_sqlmap_uses_threads_and_local_nuclei_rate_is_higher():
    assert "--threads" in sqlmap.build("/tmp/u", "/tmp/o")
    assert nuclei.LOCAL_RATE > nuclei.SAFE_RATE


def test_filter_targets_keeps_only_the_authorized_host_and_fills_blank_params():
    urls = ["http://127.0.0.1:3000/rest/products/search?q=", "https://www.youtube.com/watch?v=1",
            "http://127.0.0.1:4000/other-port", "http://127.0.0.1:3000/ok"]
    n, q = scan.filter_targets(urls, "http://127.0.0.1:3000")
    assert all(u.startswith("http://127.0.0.1:3000") for u in n + q), "third-party / other-port URLs must never be scanned"
    assert "http://127.0.0.1:3000/rest/products/search?q=1" in n, "blank params get a value to fuzz"


def test_authenticate_returns_bearer_header_and_refuses_off_host_login():
    class R:
        status_code = 200
        def json(self):
            return {"authentication": {"token": "abc"}}

    auth = {"login_url": "/login", "username": "u", "password": "p", "json": True,
            "token_path": "authentication.token"}
    s = scan.authenticate(auth, "http://t.local:3000", post=lambda url, **kw: R())
    assert s["header"] == "Authorization: Bearer abc"
    try:
        scan.authenticate({**auth, "login_url": "http://evil.example/x"}, "http://t.local:3000",
                          post=lambda url, **kw: R())
        raise AssertionError("credentials must never go to another host")
    except RuntimeError:
        pass


def test_auth_header_reaches_every_tool():
    h = "Authorization: Bearer abc"
    assert h in katana.build("t", "o", header=h) and h in nuclei.build("u", "o", header=h)
    assert h in sqlmap.build("u", "o", header=h)


def test_nuclei_never_calls_public_oast_unless_a_team_server_is_given():
    assert "-ni" in nuclei.build("u", "o")                                   # DAST
    assert "-ni" in nuclei.build("u", "o", surface=True)
    own = nuclei.build("u", "o", interactsh="oast.internal.example")
    assert "-ni" not in own and own[own.index("-interactsh-server") + 1] == "oast.internal.example"


def test_nuclei_extra_knobs_never_drop_the_safety_excludes():
    cmd = nuclei.build("u", "o", surface=True, concurrency=3, timeout=9, retries=2, exclude_tags=["xss"])
    assert cmd[cmd.index("-c") + 1] == "3" and cmd[cmd.index("-timeout") + 1] == "9" and cmd[cmd.index("-retries") + 1] == "2"
    etags = cmd[cmd.index("-etags") + 1].split(",")
    assert {"dos", "intrusive", "brute-force"} <= set(etags) and "xss" in etags
    dast = nuclei.build("u", "o", concurrency=5)
    assert dast[dast.index("-c") + 1] == "5"


def test_sqlmap_extra_knobs_stay_detection_only():
    cmd = sqlmap.build("u", "o", dbms="mysql", threads=8, delay=1.5, timeout=20, retries=1, random_agent=True, dump=True, os_shell=True)
    assert cmd[cmd.index("--dbms") + 1] == "mysql" and cmd[cmd.index("--threads") + 1] == "8"
    assert cmd[cmd.index("--delay") + 1] == "1.5" and "--random-agent" in cmd
    assert "--dump" not in cmd and "--os-shell" not in cmd                    # still needs aggressive


def test_js_endpoint_discovery_keeps_literal_and_multiple_query_params():
    bundle = 'a("rest/products/search?q=apple"); b(`api/Users/list?page=1&size=20`); c("api/Orders")'
    eps = discover.js_endpoints("http://t", lambda u: '<script src="m.js"></script>' if u == "http://t" else bundle)
    assert "http://t/rest/products/search?q=apple" in eps
    assert "http://t/api/Users/list?page=1&size=20" in eps
    assert "http://t/api/Orders" in eps


def test_form_login_loads_the_page_first_and_sends_csrf_fields():
    sent = {}

    class Resp:
        def __init__(self, text="", status=200): self.text, self.status_code = text, status

    page = '<form><input type="hidden" name="csrf" value="tok123"><input name="username"><input type="password" name="password"></form>'

    def get(url): return Resp(page)
    def post(url, **kw):
        sent.update(kw.get("data", {})); return Resp("Welcome back")

    import httpx
    orig = httpx.Client
    try:
        class C(orig):
            @property
            def cookies(self):
                class J(dict): pass
                return J(sid="abc")
        httpx.Client = C
        out = scan.authenticate({"login_url": "/login", "username": "u", "password": "p", "form": True}, "http://t", post=post, get=get)
    finally:
        httpx.Client = orig
    assert sent == {"csrf": "tok123", "username": "u", "password": "p"} and out == {"cookie": "sid=abc"}

    import pytest
    with pytest.raises(RuntimeError, match="login form came back"):
        scan.authenticate({"login_url": "/login", "username": "u", "password": "bad", "form": True}, "http://t",
                          post=lambda url, **kw: Resp(page), get=get)
