"""REQ-80 evasion suite for the target classifier. MUST stay green before release.

Runs standalone (`python controlplane/tests/test_classifier.py`) and under pytest.
DNS is faked so the suite is deterministic and offline.
"""
import os
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import classifier as C  # noqa: E402

# Fake DNS: only these names resolve; anything else raises (NXDOMAIN).
FAKE_DNS = {
    "evil.com": ["93.184.216.34"],
    "corp.internal-app.com": ["93.184.216.34"],  # public; ".internal-app" must NOT read as .internal
    "8.8.8.8.nip.io": ["8.8.8.8"],
    "127.0.0.1.nip.io": ["127.0.0.1"],
    "split.example.com": ["10.0.0.1", "93.184.216.34"],  # mixed → must reject
}


def fake_resolve(host):
    if host in FAKE_DNS:
        return FAKE_DNS[host]
    raise socket.gaierror(f"NXDOMAIN {host}")


def cls(t):
    return C.classify(t, resolve=fake_resolve)


LOCAL_CASES = [
    "http://127.0.0.1",
    "http://10.0.0.5:3000",
    "http://192.168.1.10",
    "172.16.0.1",
    "http://169.254.1.1",        # link-local
    "http://[::1]",              # IPv6 loopback
    "::ffff:127.0.0.1",          # IPv4-mapped private
    "localhost",
    "app.internal",
    "staging.local",             # .local by rule, never resolved
    "http://127.0.0.1.nip.io",   # wildcard DNS honestly pointing at loopback
]

CLOUD_CASES = [
    "https://evil.com",
    "http://8.8.8.8",
    "http://8.8.8.8.nip.io",     # wildcard DNS honestly pointing at a public IP
    "http://corp.internal-app.com",  # ".internal-app.com" is NOT the .internal suffix
    "::ffff:8.8.8.8",            # IPv4-mapped public
]

# The dangerous class: each MUST reject, never silently become `local`.
REJECT_CASES = [
    "",
    "http://0x7f000001",             # hex-packed loopback
    "http://2130706433",             # dotless-decimal loopback
    "http://0177.0.0.1",             # dotted-octal
    "http://127.0.0.1@evil.com",     # embedded creds (host after @ is evil.com)
    "http://evil.com@127.0.0.1",     # embedded creds (host after @ is loopback)
    "http://split.example.com",      # resolves to mixed local+cloud
    "http://nonexistent.invalid",    # unresolvable
]


def test_local_cases():
    for t in LOCAL_CASES:
        assert cls(t) == C.CLASS_LOCAL, f"{t!r} should be local, got {cls(t)!r}"


def test_cloud_cases():
    for t in CLOUD_CASES:
        assert cls(t) == C.CLASS_CLOUD, f"{t!r} should be cloud, got {cls(t)!r}"


def test_reject_cases():
    for t in REJECT_CASES:
        try:
            got = cls(t)
        except C.ClassifyRejected:
            continue
        raise AssertionError(f"{t!r} should be rejected, got {got!r}")


def test_never_cloud_as_local():
    # The one invariant that matters most: nothing that isn't provably local
    # (cloud cases + reject cases) is ever labelled local.
    for t in CLOUD_CASES + REJECT_CASES:
        try:
            assert cls(t) != C.CLASS_LOCAL, f"BYPASS: {t!r} classified local"
        except C.ClassifyRejected:
            pass  # rejecting is the safe outcome


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} OK")
    print("test_classifier: all green")


def test_absurd_hostnames_and_unfriendly_messages():
    import pytest
    import classifier
    for bad in ("http://" + "a" * 300 + ".com", "http://" + "a" * 64 + ".example.com"):
        with pytest.raises(classifier.ClassifyRejected, match="too long"):
            classifier.validate_syntax(bad)
    with pytest.raises(classifier.ClassifyRejected, match="web address"):
        classifier.validate_syntax("javascript:alert(1)")
    classifier.validate_syntax("https://" + "a" * 63 + ".example.com")   # 63-char label is legal
