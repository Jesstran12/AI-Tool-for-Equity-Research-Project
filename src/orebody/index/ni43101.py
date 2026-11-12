"""Locate NI 43-101 items by page so agents receive section-targeted text (SPEC D37)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

MAX_TOC_PAGE = 40  # the TOC must start within the first 40 pages
MIN_TOC_LINES = 5  # dot-leader lines ('Heading ...... 226') per page to count as a TOC page
_TOC_LINE = re.compile(r"\.{3,}\s*\d+\s*$")


def load_patterns(path: Path = Path("config/sections.yaml")) -> dict[int, str]:
    data = yaml.safe_load(Path(path).read_text())
    return {int(k): str(v) for k, v in data["items"].items()}


@dataclass(frozen=True)
class ItemSpan:
    item: int
    start: int  # 1-indexed, inclusive
    end: int  # 1-indexed, inclusive


def heading_regex(item: int, title: str) -> re.Pattern[str]:
    return re.compile(
        rf"^\s*(?:ITEM\s+)?{item}(?:\.0)?[\s.:\-–]+{re.escape(title)}",
        re.I | re.M,
    )


def _looks_like_toc(text: str) -> bool:
    return sum(1 for line in text.splitlines() if _TOC_LINE.search(line)) >= MIN_TOC_LINES


def toc_end(pages: list[str]) -> int:
    """Last page of the first contiguous run of TOC-like pages; 0 if none starts in MAX_TOC_PAGE.

    Pinned to contiguity rather than "largest TOC-like page" because body tables full of numbers
    would otherwise extend the TOC past the first items' real headings.
    """
    start = next(
        (n for n, text in enumerate(pages[:MAX_TOC_PAGE], start=1) if _looks_like_toc(text)), 0
    )
    if start == 0:
        return 0
    end = start
    while end < len(pages) and _looks_like_toc(pages[end]):
        end += 1
    return end


def _spans(starts: dict[int, int], n_pages: int) -> dict[int, ItemSpan]:
    """Item start pages -> spans ending the page before the next item starts."""
    ordered = sorted(starts.items(), key=lambda kv: (kv[1], kv[0]))
    result: dict[int, ItemSpan] = {}
    for i, (item, start) in enumerate(ordered):
        end = ordered[i + 1][1] - 1 if i + 1 < len(ordered) else n_pages
        result[item] = ItemSpan(item=item, start=start, end=max(start, end))
    return dict(sorted(result.items()))


def numbered_index(pages: list[str], patterns: dict[int, str]) -> dict[int, ItemSpan]:
    """Headings that carry their item number ('21 Capital and Operating Costs')."""
    first_body = toc_end(pages) + 1
    starts: dict[int, int] = {}
    for item, title in patterns.items():
        rx = heading_regex(item, title)
        for n in range(first_body, len(pages) + 1):
            if rx.search(pages[n - 1]):
                starts[item] = n
                break
    return _spans(starts, len(pages))


def build_index(pages: list[str], patterns: dict[int, str]) -> dict[int, ItemSpan]:
    """Map item number → page span. Items whose heading is not found are omitted.
    Uses numbered headings, or a fallback for un-numbered layouts (F2.1, detect_index)."""
    return detect_index(pages, patterns)[0]


# --- F2.1 fallbacks for reports whose item headings carry no number (2026-11-11) ---------------
# Two layouts seen in real reports:
#   page_marker  every page carries "Section N ... Page N-k"; Item N starts at the first "Page N-1"
#                page (Highland Copperwood FS 2023: 27/27 items this way).
#   subsection   an un-numbered capitals heading followed by its first subsection "N.1" on its own
#                line and an upper-case subsection title on the next line (Lion Yerington PFS 2025).
#                A bare "N.1" followed by numbers is a table cell, not a heading. Item start pages
#                must increase with N. If the N.1 line is on the page after an un-numbered capitals
#                heading page that holds no subsection lines, the item starts on that heading page.
# detect_index tries numbered headings first, then the fallbacks, and keeps the method that finds
# the most items (ties go to numbered, then page_marker).

IndexMethod = Literal["numbered", "page_marker", "subsection"]


_PAGE_MARKER = re.compile(r"\bPage\s+(\d{1,2})-1(?!\d)")
_BARE_N1 = re.compile(r"(\d{1,2})\.1")
_SUBSECTION_LINE = re.compile(r"^\s*\d{1,2}\.\d+\b")
MAX_ITEM = 27


def page_marker_index(pages: list[str]) -> dict[int, ItemSpan]:
    starts: dict[int, int] = {}
    for n, text in enumerate(pages, start=1):
        for m in _PAGE_MARKER.finditer(text):
            item = int(m.group(1))
            if 1 <= item <= MAX_ITEM:
                starts.setdefault(item, n)
    return _spans(starts, len(pages)) if starts else {}


def _title_like(line: str) -> bool:
    """An upper-case heading line: at least 4 letters, no digits, no lower case."""
    s = line.strip()
    return sum(c.isalpha() for c in s) >= 4 and s.upper() == s and not any(c.isdigit() for c in s)


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _heading_starts_on_previous_page(pages: list[str], n: int, first_body: int) -> bool:
    """True if the N.1 line on page n has no heading above it on its page, and page n-1 holds an
    upper-case heading and no subsection lines (Lion: 'INTRODUCTION' alone, '1.1' overleaf)."""
    if n - 1 < first_body:
        return False
    here = _lines(pages[n - 1])
    k = next(i for i, ln in enumerate(here) if _BARE_N1.fullmatch(ln))
    if any(_title_like(ln) for ln in here[:k]):
        return False
    prev = _lines(pages[n - 2])
    has_heading = any(_title_like(ln) for ln in prev)
    return has_heading and not any(_SUBSECTION_LINE.match(ln) for ln in prev)


def subsection_index(pages: list[str]) -> dict[int, ItemSpan]:
    first_body = toc_end(pages) + 1
    cands: list[tuple[int, int]] = []  # (item, page of its N.1 line)
    for n in range(first_body, len(pages) + 1):
        lines = _lines(pages[n - 1])
        for k, ln in enumerate(lines[:-1]):
            m = _BARE_N1.fullmatch(ln)
            if m and 1 <= int(m.group(1)) <= MAX_ITEM and _title_like(lines[k + 1]):
                cands.append((int(m.group(1)), n))
    first: dict[int, list[int]] = {}
    for item, n in cands:
        first.setdefault(item, []).append(n)
    # Longest chain of distinct items whose pages increase with the item number (a stray "14.1"
    # after Item 22 must not block 21 and 22); among equal chains the earlier pages win.
    nodes = sorted((item, n) for item, pages_ in first.items() for n in pages_)
    best: list[tuple[int, int, int]] = []  # (length, -sum of pages, prev index)
    for i, (item, n) in enumerate(nodes):
        choice = (1, -n, -1)
        for j in range(i):
            pitem, pn = nodes[j]
            if pitem < item and pn <= n:
                cand = (best[j][0] + 1, best[j][1] - n, j)
                if cand[:2] > choice[:2]:
                    choice = cand
        best.append(choice)
    if not best:
        return {}
    i = max(range(len(best)), key=lambda k: best[k][:2])
    starts: dict[int, int] = {}
    while i != -1:
        item, n = nodes[i]
        if _heading_starts_on_previous_page(pages, n, first_body):
            n -= 1
        starts[item] = n
        i = best[i][2]
    return _spans(starts, len(pages))


def detect_index(
    pages: list[str], patterns: dict[int, str]
) -> tuple[dict[int, ItemSpan], IndexMethod]:
    results: list[tuple[dict[int, ItemSpan], IndexMethod]] = [
        (numbered_index(pages, patterns), "numbered"),
        (page_marker_index(pages), "page_marker"),
        (subsection_index(pages), "subsection"),
    ]
    return max(results, key=lambda r: len(r[0]))  # max keeps the first on ties
