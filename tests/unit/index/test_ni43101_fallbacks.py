"""F2.1 fallbacks for un-numbered item headings. Hand-built pages mimic the two real layouts;
expected spans are stated per case. Existing numbered-heading tests stay in test_ni43101.py."""

from pathlib import Path

import pytest

from orebody.index.ni43101 import (
    ItemSpan,
    build_index,
    detect_index,
    load_patterns,
    page_marker_index,
    subsection_index,
)

ROOT = Path(__file__).resolve().parents[3]
PATTERNS = load_patterns(ROOT / "config" / "sections.yaml")
HEADER = "Project X PFS – NI 43-101 Technical Report\nProject No.: 1\nPage {n} of 99\n"


def _toc_page() -> str:
    # dot-leader lines; "21.1 Capital Cost" here must not count as Item 21
    return "\n".join(f"{i}.1 Some Heading ........ {100 + i}" for i in range(1, 25))


# --- page_marker (Copperwood layout) -----------------------------------------------------------

COPPERWOOD = [
    "Feasibility Study Update\nCopperwood Project",  # 1 cover
    "Section 1\nApril 2023\nPage 1-1\n SUMMARY\n1.1\nIntroduction\nbody",  # 2
    "Section 1\nApril 2023\nPage 1-2\nbody",  # 3
    "Section 1\nApril 2023\nPage 1-10\nbody",  # 4  "1-10" is not "1-1"
    "Section 21\nApril 2023\nPage 21-1\n CAPITAL AND OPERATING COSTS\n21.1 Capital\nbody",  # 5
    "Section 21\nApril 2023\nPage 21-2\nbody",  # 6
    "Section 22\nApril 2023\nPage 22-1\n ECONOMIC ANALYSIS\nbody",  # 7
]


def test_page_marker_index() -> None:
    assert page_marker_index(COPPERWOOD) == {
        1: ItemSpan(1, 2, 4),
        21: ItemSpan(21, 5, 6),
        22: ItemSpan(22, 7, 7),
    }


def test_page_marker_index_empty_without_markers() -> None:
    assert page_marker_index(["1 Summary\ntext", "21 Capital and Operating Costs"]) == {}


# --- subsection (Lion layout) ------------------------------------------------------------------

LION = [
    "Cover page",  # 1
    _toc_page(),  # 2
    _toc_page(),  # 3
    HEADER.format(n=1) + "\nINTRODUCTION\nLion Copper is a mine development company.",  # 4
    HEADER.format(n=2) + "Figure 1.1: Site Layout\n1.1\nLOCATION AND PROPERTY\nbody",  # 5
    HEADER.format(n=3) + "Table 21.4\n22.1\n4.25\n3.90\n",  # 6  table cell, not Item 22
    HEADER.format(n=4) + "\nCAPITAL AND OPERATING COSTS\n21.1\nCAPITAL COST\nbody",  # 7
    HEADER.format(n=5) + "21.2\nOPERATING COST\nbody",  # 8
    HEADER.format(n=6) + "\nECONOMIC ANALYSIS\n22.1\nCAUTIONARY STATEMENT\nbody",  # 9
    HEADER.format(n=7) + "14.1\nRESOURCE NOTE\nbody",  # 10 out of order: 14 after 22 is ignored
]


def test_subsection_index() -> None:
    idx = subsection_index(LION)
    # Item 1: "1.1" is on page 5, but page 4 holds the un-numbered heading and no subsections
    assert idx[1] == ItemSpan(1, 4, 6)
    assert idx[21] == ItemSpan(21, 7, 8)  # not page 2-3 (TOC)
    assert idx[22].start == 9  # not page 6 (table cell "22.1" followed by numbers)
    assert 14 not in idx  # "14.1" on page 10 comes after Item 22: start pages must increase


def test_subsection_index_requires_an_uppercase_title_after_n1() -> None:
    pages = ["x", "Results\n3.1\n0.45\n0.52\n", "Results\n3.1\nGEOLOGY OF THE AREA\ntext"]
    assert subsection_index(pages)[3].start == 3


# --- detect_index / build_index ----------------------------------------------------------------


def test_detect_prefers_numbered_headings(fixture_pages_numbered: list[str]) -> None:
    idx, method = detect_index(fixture_pages_numbered, PATTERNS)
    assert method == "numbered"
    assert {1, 14, 21, 22} <= set(idx)


def test_detect_uses_page_markers_for_copperwood_layout() -> None:
    idx, method = detect_index(COPPERWOOD, PATTERNS)
    assert method == "page_marker"
    assert idx[21] == ItemSpan(21, 5, 6)


def test_detect_uses_subsections_for_lion_layout() -> None:
    idx, method = detect_index(LION, PATTERNS)
    assert method == "subsection"
    assert idx[21].start == 7


def test_build_index_falls_back() -> None:
    # build_index keeps its signature (eligibility and `run` call it) and now uses detect_index
    assert build_index(LION, PATTERNS)[22].start == 9
    assert build_index(COPPERWOOD, PATTERNS)[1] == ItemSpan(1, 2, 4)


@pytest.fixture
def fixture_pages_numbered(fixture_extracted) -> list[str]:
    from orebody.ingest.extract import read_page

    return [
        read_page(fixture_extracted.pages_dir, n) for n in range(1, fixture_extracted.n_pages + 1)
    ]


# --- real reports (skipped on a fresh clone); expected pages read by hand on 2026-11-11 ---------

RAW = ROOT / "data" / "raw"
LION_PDF = RAW / "LEO" / "2025-05-31_yerington-pfs_ni43-101.pdf"
CW_PDF = RAW / "HI" / "2023-03-06_copperwood-fs-update_ni43-101.pdf"
MARI_PDF = RAW / "MARI" / "2025-08-25_MarimacaOxide_FS_NI43-101.pdf"


def _pdf_pages(path: Path) -> list[str]:
    import pymupdf

    with pymupdf.open(path) as pdf:
        return [p.get_text() for p in pdf]


@pytest.mark.skipif(not LION_PDF.exists(), reason="LEO not fetched")
def test_real_lion_pfs() -> None:
    # p.24 "Page 1 of 369 / INTRODUCTION"; p.336 "CAPITAL AND OPERATING COSTS / 21.1";
    # p.361 "ECONOMIC ANALYSIS / 22.1" (a "22.1" table cell on p.342 must be skipped)
    idx, method = detect_index(_pdf_pages(LION_PDF), PATTERNS)
    assert method == "subsection"
    assert (idx[1].start, idx[21].start, idx[22].start) == (24, 336, 361)


@pytest.mark.skipif(not CW_PDF.exists(), reason="HI not fetched")
def test_real_copperwood_fs() -> None:
    # "Page 1-1" on p.29, "Page 21-1" on p.413, "Page 22-1" on p.441; all 27 sections marked
    idx, method = detect_index(_pdf_pages(CW_PDF), PATTERNS)
    assert method == "page_marker"
    assert len(idx) == 27
    assert (idx[1].start, idx[21].start, idx[22].start) == (29, 413, 441)


@pytest.mark.skipif(not MARI_PDF.exists(), reason="MARI not fetched")
def test_real_mari_unchanged() -> None:
    # Regression: MARI's numbered headings still win (27 items, D4)
    idx, method = detect_index(_pdf_pages(MARI_PDF), PATTERNS)
    assert method == "numbered"
    assert len(idx) == 27
