"""Target classification: `local` vs `cloud` (SRS REQ-14, REQ-80).

This is the single control the entire Approval Gate rests on. A `cloud` target
misclassified as `local` silently skips approval (REQ-19a, BR-5), so the rule here
is: resolve to an IP and classify on the *resolved address*, and **fail closed**
(raise ClassifyRejected) on anything ambiguous, encoded, or unresolvable, never
guess `local`.

Design (IMPLEMENTATION-PLAN D-3): don't regex-blocklist every IP encoding. Reject the
packed/encoded numeric forms outright, and for real hostnames resolve then classify
every returned address. The DNS resolver is injectable so the REQ-80 suite runs
offline and deterministically.

Accepted residual limitations (documented in REQ-14, not fixed here): DNS split-horizon
and submission-time vs scan-time (agent) rebinding.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

CLASS_LOCAL = "local"
CLASS_CLOUD = "cloud"


class ClassifyRejected(ValueError):
    """Raised when a target cannot be classified unambiguously. Fail closed."""


def _default_resolve(host: str) -> list[str]:
    """Resolve a hostname to the list of its IP strings via the OS resolver."""
    infos = socket.getaddrinfo(host, None)
    return sorted({info[4][0] for info in infos})


def _extract_host(target: str) -> str:
    t = (target or "").strip()
    if not t:
        raise ClassifyRejected("empty target")
    if "://" not in t:
        t = "http://" + t  # let urlparse treat a bare host[:port] as an authority
    parsed = urlparse(t)
    # Embedded credentials (user[:pass]@host) are an evasion vector and are ambiguous
    # across parsers, reject rather than trust our own parse (REQ-14).
    if parsed.username is not None or parsed.password is not None:
        raise ClassifyRejected("embedded credentials in target")
    host = parsed.hostname
    if not host:
        raise ClassifyRejected("no host in target")
    return host.strip().lower()


def _looks_encoded_ip(host: str) -> bool:
    """Packed/encoded numeric IP forms (dotless decimal, hex, dotted-octal)."""
    if host.startswith("0x"):
        return True
    return host.replace(".", "").isdigit()


def _classify_ip(ip: ipaddress._BaseAddress) -> str:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return CLASS_CLOUD if ip.is_global else CLASS_LOCAL


def validate_syntax(target: str) -> None:
    """Cheap submit-time check (no DNS): http(s) only, sane length, real-looking host. Raises
    ClassifyRejected. Full classification (resolution, local/cloud) still happens at approval."""
    import re
    t = (target or "").strip()
    if len(t) > 2048 or any(ord(ch) < 33 or ord(ch) == 127 for ch in t):
        raise ClassifyRejected("target must be a single URL or host without spaces")
    if "://" in t and urlparse(t).scheme not in ("http", "https"):
        raise ClassifyRejected("only http(s) targets are supported")
    host = _extract_host(t)
    try:
        ipaddress.ip_address(host)
        return
    except ValueError:
        pass
    if _looks_encoded_ip(host):
        raise ClassifyRejected(f"encoded/ambiguous numeric host: {host}")
    if not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*", host):
        raise ClassifyRejected(f"invalid host: {host}")


def classify(target: str, resolve=_default_resolve) -> str:
    """Return CLASS_LOCAL or CLASS_CLOUD; raise ClassifyRejected when unsure.

    `resolve(host) -> list[str]` is injectable for testing.
    """
    raw = (target or "").strip()
    # 0. Bare IP literal (v4/v6/mapped) with no scheme or brackets → classify directly.
    #    urlparse needs brackets for IPv6, so handle the naked form before URL parsing.
    try:
        return _classify_ip(ipaddress.ip_address(raw))
    except ValueError:
        pass

    host = _extract_host(target)

    # 1. Canonical IP literal inside a URL (incl. IPv6 and IPv4-mapped) → classify directly.
    try:
        return _classify_ip(ipaddress.ip_address(host))
    except ValueError:
        pass

    # 2. Encoded numeric host that is NOT a canonical IP → evasion, reject.
    if _looks_encoded_ip(host):
        raise ClassifyRejected(f"encoded/ambiguous numeric host: {host}")

    # 3. Internal suffixes are local by rule (REQ-14).
    if host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
        return CLASS_LOCAL

    # 4. Real hostname → resolve, classify every address, fail closed on mixed/empty.
    try:
        addrs = resolve(host)
    except (socket.gaierror, OSError) as e:
        raise ClassifyRejected(f"cannot resolve host: {host}") from e
    if not addrs:
        raise ClassifyRejected(f"host resolved to no address: {host}")

    classes = set()
    for a in addrs:
        try:
            classes.add(_classify_ip(ipaddress.ip_address(a)))
        except ValueError as e:
            raise ClassifyRejected(f"resolver returned non-IP {a!r}") from e
    if len(classes) != 1:
        raise ClassifyRejected(f"host resolves to mixed local+cloud addresses: {host}")
    return classes.pop()
