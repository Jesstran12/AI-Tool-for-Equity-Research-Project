"""F2.1b contents cross-check. Expected offsets on real reports measured by hand 2026-11-11."""

from pathlib import Path

import pytest

from orebody.index.ni43101 import ItemSpan, detect_index, load_patterns
from orebody.index.sk1300 import SK1300_SECTIONS, html_pages, sk1300_index
from orebody.index.toc import MIN_AGREEING, cross_check, printed_pages

ROOT = Path(__file__).resolve().parents[3]
NI = load_patterns(ROOT / "config" / "sections.yaml")
SK = load_patterns(SK1300_SECTIONS)


def _span(start: int) -> ItemSpan:
    return ItemSpan(0, start, start)  # item number is the dict key; span end unused here


# --- printed_pages ---------------------------------------------------------------------------


def test_dot_leader_contents(fixture_pages_toc: list[str]) -> None:
    # Fixture report p.2: "1 Summary ........ 3", "2 Introduction ........ 3",
    # "14 Mineral Resource Estimates ........ 4", "21 ... 5", "22 ... 6"
    assert printed_pages(fixture_pages_toc, NI) == {1: 3, 2: 3, 14: 4, 21: 5, 22: 6}


def test_three_line_contents() -> None:
    toc = "\n".join(
        ["Table of Contents", "1.0", "EXECUTIVE SUMMARY", "1", "1.1", "LOCATION", "2"]
        + ["18.0", "CAPITAL AND OPERATING COSTS", "325"]
    )
    assert printed_pages(["Cover", toc], SK) == {1: 1, 18: 325}


def test_lines_whose_title_does_not_match_are_ignored() -> None:
    toc = "21 Figures and Tables ........ 99\n22 Economic Analysis ........ 120\n"
    assert printed_pages([toc], NI) == {22: 120}


def test_first_occurrence_wins() -> None:
    # A list of tables later in the front matter repeats a heading with another page
    pages = ["22 Economic Analysis ........ 120", "22 Economic Analysis ........ 7"]
    assert printed_pages(pages, NI) == {22: 120}


def test_only_the_first_pages_are_read() -> None:
    pages = ["x"] * 40 + ["22 Economic Analysis ........ 120"]
    assert printed_pages(pages, NI) == {}


# --- cross_check -----------------------------------------------------------------------------


def test_consistent_index_has_no_flags() -> None:
    printed = {1: 1, 14: 40, 21: 200, 22: 230}
    index = {n: _span(p + 25) for n, p in printed.items()}
    r = cross_check(index, printed)
    assert (r.offset, r.checked, r.flagged) == (25, 4, [])


def test_planted_wrong_start_is_flagged() -> None:
    printed = {1: 1, 14: 40, 21: 200, 22: 230}
    index = {n: _span(p + 25) for n, p in printed.items()}
    index[21] = _span(31)  # the index took a heading on p.31 (say, a contents continuation)
    r = cross_check(index, printed)
    assert r.offset == 25
    flags = [(f.item, f.index_start, f.printed, f.expected) for f in r.flagged]
    assert flags == [(21, 31, 200, 225)]


def test_one_page_slack_is_not_flagged() -> None:
    printed = {1: 1, 14: 40, 21: 200, 22: 230}
    index = {n: _span(p + 25) for n, p in printed.items()}
    index[22] = _span(256)  # 1 page late: heading at the foot of the previous page, say
    assert cross_check(index, printed).flagged == []


def test_too_few_agreeing_items_gives_no_offset() -> None:
    printed = {1: 1, 21: 200}
    index = {1: _span(26), 21: _span(225)}
    r = cross_check(index, printed)
    assert MIN_AGREEING == 3
    assert r.offset is None and r.flagged == []
    assert "too few" in r.note


def test_items_missing_from_either_side_are_not_checked() -> None:
    printed = {1: 1, 2: 5, 14: 40, 21: 200}
    index = {1: _span(26), 14: _span(65), 21: _span(225), 27: _span(400)}
    assert cross_check(index, printed).checked == 3


@pytest.fixture
def fixture_pages_toc(fixture_extracted) -> list[str]:
    from orebody.ingest.extract import read_page

    return [
        read_page(fixture_extracted.pages_dir, n) for n in range(1, fixture_extracted.n_pages + 1)
    ]


# --- real reports (skipped on a fresh clone) -------------------------------------------------

RAW = ROOT / "data" / "raw"
MARI = RAW / "MARI" / "2025-08-25_MarimacaOxide_FS_NI43-101.pdf"
SURG = RAW / "SURG" / "2026-06-12_berg_ni43-101-pfs.pdf"
LION = RAW / "LEO" / "2025-05-31_yerington-pfs_sk1300_ex99-1.htm"


def _pdf_pages(path: Path) -> list[str]:
    import pymupdf

    with pymupdf.open(path) as pdf:
        return [p.get_text() for p in pdf]


@pytest.mark.skipif(not MARI.exists(), reason="MARI not fetched")
def test_real_mari_no_false_flags() -> None:
    # F2.1b AC: no false flags on MARI. All 27 items in the contents, offset +25.
    pages = _pdf_pages(MARI)
    r = cross_check(detect_index(pages, NI)[0], printed_pages(pages, NI))
    assert (r.offset, r.checked, r.flagged) == (25, 27, [])


@pytest.mark.skipif(not SURG.exists(), reason="SURG not fetched")
def test_real_surg_no_flags() -> None:
    pages = _pdf_pages(SURG)
    r = cross_check(detect_index(pages, NI)[0], printed_pages(pages, NI))
    assert r.offset == 25 and r.flagged == []


@pytest.mark.skipif(not LION.exists(), reason="LEO not fetched")
def test_real_lion_sk1300_no_flags() -> None:
    pages = html_pages(LION.read_text(errors="ignore"))
    r = cross_check(sk1300_index(pages, SK), printed_pages(pages, SK))
    assert r.offset == 20 and r.flagged == []
