"""F2.2 S-K 1300 index. Hand-built HTML and pages mimic the Lion Ex. 99.1 layout."""

from pathlib import Path

import pytest

from orebody.index.ni43101 import ItemSpan, load_patterns
from orebody.index.sk1300 import ECONOMICS_ITEMS, SK1300_SECTIONS, html_pages, sk1300_index

SK = load_patterns(SK1300_SECTIONS)


def test_patterns_have_25_items_with_costs_at_18_and_economics_at_19() -> None:
    assert sorted(SK) == list(range(1, 26))
    assert SK[18].startswith("Capital and Operating Costs")
    assert SK[19].startswith("Economic Analysis")
    assert ECONOMICS_ITEMS == {"NI43-101": (21, 22), "SK1300": (18, 19)}


HTML = """<html><head><style>p {color: red}</style><script>var x = 1;</script></head><body>
<p>Cover&nbsp;page</p>
<div style="page-break-before: always"></div>
<p>Table of Contents</p>
<hr style="PAGE-BREAK-AFTER: always">
<p>1.0</p><p>EXECUTIVE SUMMARY</p><p>Body &amp; text</p>
<p style="margin: 0; page-break-before:always">19.0</p><p>ECONOMIC ANALYSIS</p>
</body></html>"""


def test_html_pages_split_at_css_page_breaks() -> None:
    pages = html_pages(HTML)
    assert len(pages) == 4
    assert pages[0].strip() == "Cover page"  # &nbsp; unescaped, style/script dropped
    assert "Table of Contents" in pages[1]
    assert "1.0\nEXECUTIVE SUMMARY\nBody & text" in pages[2]
    assert "ECONOMIC ANALYSIS" in pages[3]
    assert all("var x" not in p and "color: red" not in p for p in pages)


def test_html_without_page_breaks_is_one_page() -> None:
    assert len(html_pages("<p>one</p><p>two</p>")) == 1


TOC = "Table of Contents\n" + "\n".join(
    f"{n}.0\n{SK[n].upper()}\n{n * 10}" for n in (1, 2, 3, 18, 19, 25)
)
TABLE = "Results\n" + "\n".join(f"{n}.0\n{n * 7}.5" for n in range(1, 12))  # numbers, no titles
PAGES = [
    "Cover",
    TOC,  # 2: contents, six headings -> skipped
    "1.0\nEXECUTIVE SUMMARY\nThe project ...",  # 3
    TABLE,  # 4: bare N.0 numbers are not headings or contents
    "18.0\nCAPITAL AND OPERATING COSTS\n18.1\nCAPITAL COST",  # 5
    "body",  # 6
    "19.0 ECONOMIC ANALYSIS\n19.1 CAUTIONARY STATEMENT",  # 7, number and title on one line
    "25.0\nRELIANCE ON INFORMATION PROVIDED BY THE REGISTRANT",  # 8
]


def test_sk1300_index_skips_contents() -> None:
    idx = sk1300_index(PAGES, SK)
    assert idx[1] == ItemSpan(1, 3, 4)
    assert idx[18] == ItemSpan(18, 5, 6)
    assert idx[19] == ItemSpan(19, 7, 7)
    assert idx[25] == ItemSpan(25, 8, 8)
    assert 2 not in idx  # only listed in the contents


def test_too_few_headings_is_not_contents() -> None:
    # A page naming four items (a cross-reference list) is body, not contents
    four = "\n".join(f"{n}.0\n{SK[n].upper()}" for n in (1, 2, 3, 18))
    assert sk1300_index(["x", four], SK)[1].start == 2


def test_contents_continuation_page_is_skipped() -> None:
    # Real-data lesson (Lion p.6): a contents page listing only Items 18-19 and sub-sections has
    # two item headings but many "N.M / title / page" entries.
    cont = "\n".join(
        ["18.0", "CAPITAL AND OPERATING COSTS", "345"]
        + [x for k in range(1, 6) for x in (f"18.{k}", f"COST ITEM {k}", str(345 + k))]
        + ["19.0", "ECONOMIC ANALYSIS", "372"]
        + [x for k in range(1, 5) for x in (f"19.{k}", f"ECONOMIC ITEM {k}", str(372 + k))]
    )
    pages = ["Cover", cont, "18.0\nCAPITAL AND OPERATING COSTS\nbody", "19.0\nECONOMIC ANALYSIS"]
    idx = sk1300_index(pages, SK)
    assert (idx[18].start, idx[19].start) == (3, 4)


# --- real exhibit, skipped on a fresh clone --------------------------------------------------

LION = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "raw"
    / "LEO"
    / "2025-05-31_yerington-pfs_sk1300_ex99-1.htm"
)


@pytest.mark.skipif(not LION.exists(), reason="LEO not fetched")
def test_real_lion_sk1300_exhibit() -> None:
    # Hand-checked 2026-11-11: 412 pages; contents on pp. 3-7; body headings "1.0 EXECUTIVE
    # SUMMARY" p.21, "18.0 CAPITAL AND OPERATING COSTS" p.345, "19.0 ECONOMIC ANALYSIS" p.372,
    # "25.0 RELIANCE ON INFORMATION" p.406.
    pages = html_pages(LION.read_text(errors="ignore"))
    assert len(pages) == 412
    idx = sk1300_index(pages, SK)
    assert (idx[1].start, idx[18].start, idx[19].start, idx[25].start) == (21, 345, 372, 406)
