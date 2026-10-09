"""Plain-text cleaning for text a model wrote. Whatever comes in, what leaves is inert plain text: no control or
invisible characters, no HTML, no markdown that renders (images, links, emphasis, lists), no URL except
http(s) shown as text. Text a PERSON typed (manual findings, evidence) only gets `strip_controls` /
`plain_lines`: evidence legitimately contains tags and payloads."""
from __future__ import annotations

import re
import unicodedata

MAX_INPUT = 10000   # anything longer is cut before the regexes run; callers reject over-long results anyway

_SCRIPT = re.compile(r"(?is)<(script|style)\b.*?(?:</\1\s*>|$)")
_TAG = re.compile(r"</?[A-Za-z!?][^>]*>")
_ENTITY = re.compile(r"&(?:#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
_PARENS = r"\((?:[^()]|\([^()]*\))*\)"      # a (...) group with one level of nested parentheses
_IMAGE = re.compile(r"!\[[^\]]*\]" + _PARENS)
_LINK = re.compile(r"\[([^\]]*)\]" + _PARENS)
_SLASH_URL = re.compile(r"\b([A-Za-z][A-Za-z0-9+.\-]*)://[^\s<>\"']*")
_BARE_SCHEME = re.compile(r"\b(?:javascript|vbscript|data|file|mailto|tel|blob|about):\S+", re.I)
_FENCE = re.compile(r"`+")
_EMPH = re.compile(r"\*{1,3}|_{2,3}|~{2}")
_LEAD = re.compile(r"^(?:#{1,6}|[>*+\-]|\d{1,3}[.)])\s+")


def strip_controls(s: str, keep_newlines: bool = False) -> str:
    """NFC, then drop every Unicode "C" character (control, zero-width, bidi, BOM, private use, unassigned).
    Tabs and line breaks become a space (or a newline when asked)."""
    s = unicodedata.normalize("NFC", str(s)).replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for ch in s:
        if ch == "\n":
            out.append("\n" if keep_newlines else " ")
        elif ch == "\t" or unicodedata.category(ch) in ("Zl", "Zp"):
            out.append(" ")
        elif not unicodedata.category(ch).startswith("C"):
            out.append(ch)
    return "".join(out)


def plain_lines(s: str) -> str:
    """Human-typed multi-line text: controls out, line breaks kept, everything else as typed."""
    return strip_controls(s, keep_newlines=True)


def clean_plain(text: str) -> str:
    s = strip_controls(str(text)[:MAX_INPUT])
    s = _SCRIPT.sub(" ", s)
    s = _IMAGE.sub(" ", s)
    s = _LINK.sub(r"\1", s)
    s = _TAG.sub(" ", s)
    s = _ENTITY.sub(" ", s)
    s = _SLASH_URL.sub(lambda m: m.group(0) if m.group(1).lower() in ("http", "https") else " ", s)
    s = _BARE_SCHEME.sub(" ", s)
    s = _FENCE.sub("", s)
    s = _EMPH.sub("", s)
    s = " ".join(s.split())
    return _LEAD.sub("", s).strip()
