"""F1.8 cross-check, pure part: does an alternate copy of a document carry the same numbers?

The primary copy comes from the company website; the alternate from EDGAR (or SEDAR+). Bytes
rarely match (PDF vs HTML exhibit), so the comparison is on normalized text and numbers:
- identical:   normalized text is equal
- consistent:  every key figure is in both copies, and the numeric overlap is at least MIN_OVERLAP
- differs:     a key figure is missing from one copy, or the overlap is below MIN_OVERLAP
No network, no LLM (ground rule 1).
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Literal

from pydantic import BaseModel

from orebody.core.matcher import normalize_ws

MIN_OVERLAP = 0.90  # share of the primary's distinct numbers also found in the alternate

Status = Literal["identical", "consistent", "differs"]


class CrossCheck(BaseModel):
    status: Status
    key_found_in_both: list[str]
    key_missing_in_primary: list[str]
    key_missing_in_alternate: list[str]
    number_overlap: float  # distinct-number overlap, 0..1
    only_in_primary: list[str]  # up to 20 numbers, for the audit trail
    only_in_alternate: list[str]


_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")
_NUMBER = re.compile(r"(?<![\d.])\d+(?:\.\d+)?")


def numbers_in(text: str) -> Counter[str]:
    """Numeric tokens with thousands separators removed: '1,443' -> '1443', '$694' -> '694'.
    Page furniture such as 'Page 20 of 369' is not removed; MIN_OVERLAP absorbs it."""
    return Counter(_NUMBER.findall(_THOUSANDS.sub("", text)))


def _key(figure: str) -> str:
    found = numbers_in(figure)
    return next(iter(found)) if found else figure


def compare(primary: str, alternate: str, key_figures: list[str]) -> CrossCheck:
    p, a = numbers_in(primary), numbers_in(alternate)
    both = [k for k in key_figures if _key(k) in p and _key(k) in a]
    miss_p = [k for k in key_figures if _key(k) not in p]
    miss_a = [k for k in key_figures if _key(k) not in a]
    overlap = len(p.keys() & a.keys()) / len(p) if p else 1.0
    if normalize_ws(primary) == normalize_ws(alternate):
        status: Status = "identical"
    elif not miss_p and not miss_a and overlap >= MIN_OVERLAP:
        status = "consistent"
    else:
        status = "differs"
    return CrossCheck(
        status=status,
        key_found_in_both=both,
        key_missing_in_primary=miss_p,
        key_missing_in_alternate=miss_a,
        number_overlap=overlap,
        only_in_primary=sorted(p.keys() - a.keys())[:20],
        only_in_alternate=sorted(a.keys() - p.keys())[:20],
    )


_MONTH_NAMES = (
    "january february march april may june july august september october november december"
)
_MONTHS = {m: i for i, m in enumerate(_MONTH_NAMES.split(), 1)}
_MON = "(" + "|".join(_MONTHS) + ")"
_EFFECTIVE = re.compile(
    r"effective\s+date(?:\s+of\s+(?:this|the)\s+(?:technical\s+)?report)?"
    r"\s*(?:is|of|:)?\s*"
    rf"(?:{_MON}\s+(\d{{1,2}}),?\s+(\d{{4}})|(\d{{1,2}})\s+{_MON},?\s+(\d{{4}}))",
    re.I,
)


def effective_date_in(text: str) -> date | None:
    """The first stated effective date ('Effective Date: March 12, 2025', 'the effective date of
    this technical report is March 18, 2026', '12 June 2026'); None if the text states none."""
    m = _EFFECTIVE.search(text)
    if not m:
        return None
    if m.group(1):
        return date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
    return date(int(m.group(6)), _MONTHS[m.group(5).lower()], int(m.group(4)))
