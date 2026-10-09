"""The cleaner for model-written text: plain text out, whatever went in."""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import textsafe  # noqa: E402


@pytest.mark.parametrize("raw,expected", [
    ("**Bold** and __more__", "Bold and more"),
    ("see [the docs](javascript:alert(1)) now", "see the docs now"),
    ("![x](http://evil/p.png) text", "text"),
    ("<script>alert(1)</script>Safe", "Safe"),
    ("a <b>bold</b> move", "a bold move"),
    ("<img src=x onerror=alert(1)>hi", "hi"),
    ("&lt;b&gt; &#60;i&#62; &#x3c;u&#x3e; ok", "b i u ok"),      # entities are dropped, never decoded
    ("pay\u202eevil\u200b\ufeff text", "payevil text"),
    ("ctrl\x00\x07chars\x1b[31m", "ctrlchars[31m"),
    ("open javascript:alert(1) and data:text/html,x", "open and"),
    ("JaVa\u200bScRiPt:alert(1) bad", "bad"),
    ("go to ftp://host/x or https://example.com/a", "go to or https://example.com/a"),
    ("file:///etc/passwd x", "x"),
    ("OWASP A03:2021 and a < b and 3 > 2", "OWASP A03:2021 and a < b and 3 > 2"),
    ("Customer data: names", "Customer data: names"),
    ("- item one", "item one"),
    ("## Heading text", "Heading text"),
    ("```py\ncode\n```", "py code"),
    ("line one\r\nline two\ttabbed", "line one line two tabbed"),
])
def test_clean_plain(raw, expected):
    assert textsafe.clean_plain(raw) == expected


def test_clean_plain_is_idempotent_and_fast_on_hostile_input():
    nasty = "<a" * 4000 + "[" * 4000 + "&" * 4000
    start = time.perf_counter()
    once = textsafe.clean_plain(nasty)
    assert time.perf_counter() - start < 2
    assert textsafe.clean_plain(once) == once


def test_clean_plain_cuts_absurd_input_instead_of_chewing_it():
    assert len(textsafe.clean_plain("a " * 100000)) <= 10000


def test_strip_controls_keeps_newlines_only_when_asked():
    assert textsafe.strip_controls("a\r\nb\x00c\u200bd") == "a bcd"
    assert textsafe.strip_controls("a\r\nb\x00c", keep_newlines=True) == "a\nbc"
    assert textsafe.plain_lines("x\u202ey\n<b>z</b>") == "xy\n<b>z</b>"   # human text keeps its tags
