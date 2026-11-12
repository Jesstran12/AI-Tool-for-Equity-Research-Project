"""F2.2 S-K 1300 section index (SPEC D47 reversed D45: LEO and Ivanhoe Electric file S-K 1300).

S-K 1300 summaries reach us as EDGAR HTML exhibits, not PDFs. They carry CSS page breaks
(`page-break-before/after: always`), so `html_pages` splits them into pages and claims keep a page
number (Lion Yerington PFS Ex. 99.1: 412 pages). Headings are numbered "19.0" + title, which the
NI 43-101 numbered-heading regex already matches once given S-K 1300 titles
(config/sections_sk1300.yaml). The table of contents has no dot leaders, so a page where at least
MIN_TOC_HEADINGS different item headings match is treated as contents and skipped; table pages full
of bare "N.0" numbers are not contents, because the title must follow the number. A contents page
is also recognised by its entries ("N.M" / title / page number), see MIN_TOC_ENTRIES.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from orebody.index.ni43101 import ItemSpan, _spans, heading_regex

_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_PAGE_BREAK = re.compile(r"<[^>]*page-break-(?:before|after)\s*:\s*always[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")

SK1300_SECTIONS = Path(__file__).resolve().parents[3] / "config" / "sections_sk1300.yaml"
MIN_TOC_HEADINGS = 5
# A contents entry is "N.M" / title / bare page number on three lines. Lion's contents pages hold
# 34-39 of them; no body page holds more than 4 (2026-11-11). A contents page that continues with
# only Items 18-19 and their sub-sections has few item headings but many entries.
MIN_TOC_ENTRIES = 10
_TOC_ENTRY = re.compile(r"(?m)^\d{1,2}(?:\.\d+)+\n[^\n]*[A-Z][^\n]*\n\d{1,3}$")

# Items that hold capital/operating costs and the economic analysis, per standard.
ECONOMICS_ITEMS: dict[str, tuple[int, int]] = {"NI43-101": (21, 22), "SK1300": (18, 19)}


def html_pages(raw_html: str) -> list[str]:
    """Split an HTML exhibit at CSS page breaks; drop <script>/<style>; tags become line breaks;
    entities unescaped; blank lines collapsed. Returns one text per page, in order."""
    pages = []
    for chunk in _PAGE_BREAK.split(_SCRIPT.sub(" ", raw_html)):
        text = html.unescape(_TAG.sub("\n", chunk)).replace("\xa0", " ")
        lines = [" ".join(ln.split()) for ln in text.splitlines()]
        pages.append("\n".join(ln for ln in lines if ln))
    return pages


def sk1300_index(pages: list[str], patterns: dict[int, str]) -> dict[int, ItemSpan]:
    """Item -> page span: first page (after skipping contents pages) whose text has the numbered
    heading. Missing items are omitted."""
    regexes = {item: heading_regex(item, title) for item, title in patterns.items()}
    starts: dict[int, int] = {}
    for n, text in enumerate(pages, start=1):
        found = [item for item, rx in regexes.items() if rx.search(text)]
        if len(found) >= MIN_TOC_HEADINGS or len(_TOC_ENTRY.findall(text)) >= MIN_TOC_ENTRIES:
            continue  # contents page
        for item in found:
            starts.setdefault(item, n)
    return _spans(starts, len(pages))
