"""F2.1b contents cross-check: does the index agree with the page numbers the report prints?

Printed page numbers differ from PDF/HTML page numbers by a constant offset (cover, certificates,
contents come first): MARI FS and SURG Berg PFS +25, Lion S-K 1300 exhibit +20 (2026-11-11).
The offset is the most common (index start - printed page) across items; an item whose index start
is more than TOLERANCE pages from printed + offset is flagged: either the index picked the wrong
heading or the contents is wrong. Fewer than MIN_AGREEING items sharing the offset -> no check.

Contents layouts read (title must match the item's configured title, so other lines are ignored):
  dot leaders   "21 Capital and Operating Costs ........ 226"  (NI 43-101 PDFs)
  three lines   "18.0" / "CAPITAL AND OPERATING COSTS" / "345"  (EDGAR HTML exhibits)
Pure: no I/O.
"""

from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel

from orebody.index.ni43101 import ItemSpan

TOLERANCE = 1
MIN_AGREEING = 3
MAX_CONTENTS_PAGE = 40  # contents start within the first 40 pages (as ni43101.MAX_TOC_PAGE)
TITLE_PREFIX = 8  # characters of the configured title that must match (long titles wrap or vary)

_DOT_LEADER = re.compile(r"(?m)^\s*(\d{1,2})(?:\.0)?\s+(\S[^\n]*?)\s*\.{3,}\s*(\d{1,3})\s*$")
_THREE_LINE = re.compile(r"(?m)^\s*(\d{1,2})\.0\s*\n\s*(\S[^\n]*?)\s*\n\s*(\d{1,3})\s*$")


class TocFlag(BaseModel):
    item: int
    index_start: int
    printed: int
    expected: int  # printed + offset


class TocCheck(BaseModel):
    offset: int | None  # None when too few items agree to trust one
    checked: int  # items present in both the index and the contents
    flagged: list[TocFlag]
    note: str = ""


def printed_pages(pages: list[str], patterns: dict[int, str]) -> dict[int, int]:
    """Item -> page number printed in the contents (first occurrence within MAX_CONTENTS_PAGE)."""

    def norm(text: str) -> str:
        return " ".join(text.split()).lower()[:TITLE_PREFIX]

    found: dict[int, int] = {}
    for text in pages[:MAX_CONTENTS_PAGE]:
        matches = sorted(
            [*_DOT_LEADER.finditer(text), *_THREE_LINE.finditer(text)], key=lambda m: m.start()
        )
        for m in matches:
            item, title, page = int(m.group(1)), m.group(2), int(m.group(3))
            if item in patterns and item not in found and norm(title) == norm(patterns[item]):
                found[item] = page
    return found


def cross_check(index: dict[int, ItemSpan], printed: dict[int, int]) -> TocCheck:
    both = sorted(set(index) & set(printed))
    diffs = {n: index[n].start - printed[n] for n in both}
    if not diffs:
        return TocCheck(
            offset=None, checked=0, flagged=[], note="no item in both index and contents"
        )
    offset, agreeing = Counter(diffs.values()).most_common(1)[0]
    if agreeing < MIN_AGREEING:
        return TocCheck(
            offset=None,
            checked=len(both),
            flagged=[],
            note=f"too few items agree on an offset ({agreeing} < {MIN_AGREEING})",
        )
    flagged = [
        TocFlag(
            item=n,
            index_start=index[n].start,
            printed=printed[n],
            expected=printed[n] + offset,
        )
        for n in both
        if abs(diffs[n] - offset) > TOLERANCE
    ]
    return TocCheck(offset=offset, checked=len(both), flagged=flagged)
