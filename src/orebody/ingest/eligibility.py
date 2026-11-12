"""F1.6 eligibility check: apply SPEC §10.1 to a drop folder.

Rules, each reported separately with a message that names it:
1. listed_owner      manifest has a ticker and an exchange
2. report_filed      at least one technical report filed on or before as-of; the first such report
                     in manifest order is the one checked by rules 4-5
3. primary_commodity manifest `primary_commodity` is in COMMODITIES_IN_SCOPE (Cu for the PoC);
                     missing counts as a failure, never a guess
4. text_layer        PDF: at least MIN_TEXT_SHARE of pages have >= MIN_PAGE_CHARS characters;
                     HTML: non-empty text. A page "has text" at >= 20 chars: a scan without a
                     text layer has 0, so the bar only separates nothing from something.
5. items_found       NI 43-101 section index finds Item 1 and at least MIN_ITEMS items; S-K 1300
                     reports fail until F2.2 exists

Also reported (not a rule): section3_path = "economics" if Items 21 and 22 are found, else
"no_study" (ground rule 4). Deterministic: no LLM, no network.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import pymupdf
from pydantic import BaseModel

from orebody.index.ni43101 import detect_index, load_patterns
from orebody.ingest.alternate import document_text
from orebody.ingest.manifest import load_manifest

COMMODITIES_IN_SCOPE = frozenset({"Cu"})
MIN_TEXT_SHARE = 0.90
MIN_PAGE_CHARS = 20  # a scanned page has 0; a cover page with a title has ~50-80 (fixture: 75)
MIN_ITEMS = 4

RuleName = Literal["listed_owner", "report_filed", "primary_commodity", "text_layer", "items_found"]
RULES: tuple[RuleName, ...] = (
    "listed_owner",
    "report_filed",
    "primary_commodity",
    "text_layer",
    "items_found",
)


class RuleResult(BaseModel):
    rule: RuleName
    passed: bool
    message: str  # always starts with the rule name


class Eligibility(BaseModel):
    ticker: str
    as_of: date
    report_file: str | None  # the technical report rules 4-5 checked
    passed: bool
    rules: list[RuleResult]
    section3_path: Literal["economics", "no_study"] | None = None
    # Recorded for every project, in scope or not, so other commodities can get their own
    # report section on the website later (CLAUDE.md product vision, SPEC L10).
    primary_commodity: str = ""
    by_products: list[str] = []
    commodity_note: str = ""


def _pages(path: Path) -> list[str]:
    with pymupdf.open(path) as pdf:
        return [page.get_text() for page in pdf]


def check_folder(folder: Path, as_of: date, sections_yaml: Path) -> Eligibility:
    """Run all five rules (never stop at the first failure) and return every result."""
    folder = Path(folder)
    m = load_manifest(folder / "manifest.yaml")
    results: list[RuleResult] = []

    def add(rule: RuleName, passed: bool, detail: str) -> None:
        results.append(RuleResult(rule=rule, passed=passed, message=f"{rule}: {detail}"))

    # 1. listed owner
    if m.ticker and m.exchange:
        add("listed_owner", True, f"{m.ticker} on {m.exchange}")
    else:
        add("listed_owner", False, "manifest has no exchange; a listed owner is required")

    # 2. technical report filed on or before as-of (manifest order: the current study first)
    reports = [d for d in m.documents if d.type == "technical_report"]
    filed = [d for d in reports if d.filing_date <= as_of]
    report = filed[0] if filed else (reports[0] if reports else None)
    if filed:
        add("report_filed", True, f"{report.file} filed {report.filing_date} <= as-of {as_of}")
    elif reports:
        dates = ", ".join(str(d.filing_date) for d in reports)
        add(
            "report_filed",
            False,
            f"no technical report filed on or before as-of {as_of} (filed: {dates})",
        )
    else:
        add("report_filed", False, "no technical report in the manifest")

    # 3. primary commodity, from the manifest only
    commodity = m.primary_commodity.strip()
    note = ""
    if commodity in COMMODITIES_IN_SCOPE:
        add("primary_commodity", True, f"{commodity} is in scope")
    elif commodity:
        note = (
            f"primary commodity {commodity}: outside the PoC scope "
            f"({', '.join(sorted(COMMODITIES_IN_SCOPE))}); keep for a separate "
            f"{commodity} report section"
        )
        add("primary_commodity", False, note)
    else:
        add(
            "primary_commodity", False, "manifest does not state primary_commodity (never inferred)"
        )
    if m.by_products:
        extra = f"by-products noted: {', '.join(m.by_products)}"
        note = f"{note}; {extra}" if note else extra

    # 4-5 read the report itself (even one filed after as-of: readability does not depend on date)
    path3: Literal["economics", "no_study"] | None = None
    if report is None:
        add("text_layer", False, "no technical report to check")
        add("items_found", False, "no technical report to check")
    else:
        path = folder / report.file
        is_pdf = path.suffix.lower() == ".pdf"
        pages = _pages(path) if is_pdf else []
        if is_pdf:
            with_text = sum(len(p.strip()) >= MIN_PAGE_CHARS for p in pages)
            share = with_text / len(pages) if pages else 0.0
            add(
                "text_layer",
                share >= MIN_TEXT_SHARE,
                f"{with_text}/{len(pages)} pages have text (need {MIN_TEXT_SHARE:.0%})",
            )
        else:
            text = document_text(path)
            add("text_layer", bool(text), f"HTML report, {len(text)} characters of text")

        if report.standard == "SK1300":
            add("items_found", False, "S-K 1300 report; its section index is F2.2 (not built)")
        elif not is_pdf:
            add("items_found", False, "HTML report; the NI 43-101 index reads PDF pages only")
        else:
            index, method = detect_index(pages, load_patterns(sections_yaml))
            ok = 1 in index and len(index) >= MIN_ITEMS
            add(
                "items_found",
                ok,
                f"{len(index)} items found via {method} headings (Item 1 "
                f"{'found' if 1 in index else 'missing'}; need Item 1 and >= {MIN_ITEMS})",
            )
            if ok:
                path3 = "economics" if 21 in index and 22 in index else "no_study"

    return Eligibility(
        ticker=m.ticker,
        as_of=as_of,
        report_file=report.file if report else None,
        passed=all(r.passed for r in results),
        rules=results,
        section3_path=path3,
        primary_commodity=commodity,
        by_products=m.by_products,
        commodity_note=note,
    )
