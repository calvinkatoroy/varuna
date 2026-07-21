"""SPA endpoint discovery: pull API routes out of a target's JavaScript bundles.

Katana's headless SPA crawl is unreliable (its headless engine is experimental and, in some
environments, hangs on browser launch or yields nothing). For JavaScript single-page apps we
instead fetch the page's script bundles directly and extract the API endpoint paths they
reference (Angular/React apps embed routes like `api/Products`, `rest/user/login` right in the
bundle). Those become real scan targets for Nuclei/SQLMap, which is what makes a heavy SPA
high-yield instead of just a single seed URL.

The HTTP fetch is injected, so extraction is testable offline without a live target.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

_SCRIPT_RE = re.compile(r'<script[^>]+src=["\']([^"\']+\.js)["\']', re.I)
# API-ish paths embedded as string literals: "api/Products", '/rest/user', `rest/products`...
# Template-literal query strings (`rest/products/search?q=${term}`) compile down to a plain
# string literal ending in "?q=", so the trailing query key is captured too when present -
# that's what lets SQLMap test a real parameter instead of just a bare path.
_ENDPOINT_RE = re.compile(
    r'["\'/](?:api|rest)/[A-Za-z0-9][A-Za-z0-9_/-]*(?:\?[A-Za-z0-9_]+=(?:&[A-Za-z0-9_]+=)*)?',
    re.I,
)


def js_endpoints(seed: str, fetch, max_bundles: int = 12) -> list[str]:
    """Absolute API-endpoint URLs referenced by the seed page's JS bundles.

    `fetch(url) -> str` returns the response body text; inject it for tests.
    """
    try:
        html = fetch(seed)
    except Exception:
        return []
    bundles = _SCRIPT_RE.findall(html)[:max_bundles] or ["main.js"]  # SPAs default to main.js
    endpoints: set[str] = set()
    for b in bundles:
        try:
            body = fetch(urljoin(seed, b))
        except Exception:
            continue
        for match in _ENDPOINT_RE.findall(body):
            path = match.lstrip("\"'/")            # -> api/Products
            endpoints.add(urljoin(seed, "/" + path))
    return sorted(endpoints)


def default_fetch(url: str, timeout: int = 20) -> str:
    import httpx
    return httpx.get(url, timeout=timeout, verify=False, follow_redirects=True).text
