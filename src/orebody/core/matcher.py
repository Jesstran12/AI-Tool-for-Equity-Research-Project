"""Tier-1 verification primitives: is the quote on the page, is the number on the page?"""

from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from orebody.core.units import parse_quantity

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
    # Not followed by a digit, nor by a decimal part: "708" must not match inside "708.6"
    # (bug found by the F3.6 tests, 2026-11-12). A sentence-ending "1,240." still matches.
    return re.search(rf"(?<![\d.]){re.escape(number)}(?!\d|\.\d)", page) is not None


# --- F3.6: rounding, rescaling, entities (D39) -------------------------------------------------
# number_match tries, in order:
#   exact     the claim's number is a standalone token on the page (number_on_page)
#   rounded   a page number, rounded half-up to the claim's printed decimals, equals the claim
#             ("US$709 million" vs "708.6"; "23%" vs "22.79%"). Only the claim may be rounder than
#             the page: "709.0" does not match "708.6".
#   rescaled  claim and a page quantity agree after unit scaling via core/units ("US$1.24 billion"
#             vs "US$1,240 million"; "1.2 Mt" vs "1,200 kt"), also within the claim's precision.
# A bare page number with no unit never rescales (table cells under a "US$ M" header go to
# tier 2). Currency symbols are not compared: tier 1 checks the figure, the claim records the
# currency (D39).
#
# entity_on_page: case-insensitive, accents folded (Guzmán = Guzman), punctuation ignored
# ("Royal Gold, Inc." = "ROYAL GOLD INC"), whole words only ("Teck" is not in "Teckton"), and a
# last try with spaces removed for words a PDF split across lines ("Mountai\nn").

MatchKind = Literal["exact", "rounded", "rescaled"]


_TOKEN = re.compile(r"(?<![\d.])\d+(?:\.\d+)?(?![\d])")
_PAGE_NUMBER = re.compile(r"(?<![\d.,])\d[\d,]*(?:\.\d+)?")
_RESCALABLE = frozenset({"M", "t", "lb", "oz", "t_per_year", "t_per_day"})


def _decimals(number: str) -> int:
    return len(number.split(".", 1)[1]) if "." in number else 0


def _round(value: Decimal, decimals: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def number_match(page_text: str, value_orig: str) -> MatchKind | None:
    if number_on_page(page_text, value_orig):
        return "exact"
    m = _FIRST_NUMBER.search(value_orig)
    if not m:
        return None
    claim_str = _strip_thousands(m.group(0)).strip(",")
    claim, k = Decimal(claim_str), _decimals(claim_str)
    page = normalize_ws(page_text)

    # rounded: a page token with at least the claim's decimals, rounded half up, equals the claim
    for tok in _TOKEN.findall(_strip_thousands(page)):
        if _decimals(tok) >= k and _round(Decimal(tok), k) == claim:
            return "rounded"

    # rescaled: same unit after core/units scaling, compared at the claim's printed precision
    q_claim = parse_quantity(value_orig)
    if q_claim is None or q_claim.unit not in _RESCALABLE or claim == 0:
        return None
    scale = Decimal(str(abs(q_claim.value))) / claim  # base units per printed unit
    for pm in _PAGE_NUMBER.finditer(page):
        q_page = parse_quantity(page[pm.start() : pm.start() + 40])
        if q_page is None or q_page.unit != q_claim.unit:
            continue
        if _round(Decimal(str(abs(q_page.value))) / scale, k) == claim:
            return "rescaled"
    return None


def _fold(text: str) -> str:
    """Lowercase, accents removed, every non-alphanumeric run replaced by one space."""
    text = unicodedata.normalize("NFKD", normalize_ws(text))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def entity_on_page(page_text: str, entity: str) -> bool:
    e, p = _fold(entity), _fold(page_text)
    if not e:
        return False
    if f" {e} " in f" {p} ":
        return True
    # PDF split a word across lines ("Mountai" / "n"): compare with spaces removed, only for
    # multi-word names, so a single short name cannot match inside another word ("Teck").
    return " " in e and e.replace(" ", "") in p.replace(" ", "")
