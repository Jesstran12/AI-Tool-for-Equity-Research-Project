"""Tier-1 verification primitives: is the quote on the page, is the number on the page?"""

from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_UNIFY = str.maketrans({"’": "'", "‘": "'", "–": "-", "—": "-", "“": '"', "”": '"', " ": " "})
_FIRST_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")


def normalize_ws(s: str) -> str:
    """Collapse whitespace, strip, and unify curly quotes and dashes to ASCII."""
    return _WS.sub(" ", s.translate(_UNIFY)).strip()


def quote_on_page(page_text: str, quote: str) -> bool:
    """Normalized, case-sensitive substring test."""
    q = normalize_ws(quote)
    return bool(q) and q in normalize_ws(page_text)


def _strip_thousands(s: str) -> str:
    return _THOUSANDS.sub("", s)


def number_on_page(page_text: str, value_orig: str) -> bool:
    """True iff the first number in value_orig appears on the page as a standalone numeric token."""
    m = _FIRST_NUMBER.search(value_orig)
    if not m:
        return False
    number = _strip_thousands(m.group(0)).strip(",")
    page = _strip_thousands(normalize_ws(page_text))
    return re.search(rf"(?<![\d.]){re.escape(number)}(?![\d])", page) is not None
