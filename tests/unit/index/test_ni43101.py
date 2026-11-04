from pathlib import Path

import pytest

from orebody.index.ni43101 import ItemSpan, build_index, load_patterns, toc_end
from orebody.ingest.extract import extract_pages, read_page

SECTIONS_YAML = Path(__file__).resolve().parents[3] / "config" / "sections.yaml"


@pytest.fixture(scope="module")
def fixture_pages(fixture_pdf: Path, tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    ex = extract_pages(fixture_pdf, tmp_path_factory.mktemp("pages"))
    return [read_page(ex.pages_dir, n) for n in range(1, ex.n_pages + 1)]


@pytest.fixture(scope="module")
def index(fixture_pages: list[str]) -> dict[int, ItemSpan]:
    return build_index(fixture_pages, load_patterns(SECTIONS_YAML))


def test_load_patterns_has_27_items() -> None:
    pats = load_patterns(SECTIONS_YAML)
    assert sorted(pats) == list(range(1, 28))
    assert pats[22].startswith("Economic Analysis")


def test_index_skips_toc(index: dict[int, ItemSpan]) -> None:
    # The TOC on page 2 lists "21 Capital and Operating Costs"; the real heading is on page 5.
    assert index[21].start == 5
    assert index[1].start == 3


def test_index_ends_at_next_item(index: dict[int, ItemSpan]) -> None:
    assert index[21].end == 5
    assert index[22] == ItemSpan(item=22, start=6, end=6)
    assert index[1].end == 3  # item 14 starts on page 4


def test_missing_item_omitted(index: dict[int, ItemSpan]) -> None:
    assert 27 not in index
    assert 2 not in index


def _toc_page(n_lines: int) -> str:
    return "\n".join(f"{i}.{i} Some Heading ........ {100 + i}" for i in range(n_lines))


def test_toc_end_follows_long_contiguous_toc() -> None:
    # Real reports (MARI FS): cover pages, then a 16-page TOC, then body pages whose running
    # headers end in digits ("Page 1", "August 25, 2025"), then a data table full of numbers.
    body = "Page 1\nAugust 25, 2025\n1 \nSUMMARY\n1.1\nIntroduction\n2024\n2025\n2026\n"
    table = "\n".join(f"Row {i} 123 456 {i}" for i in range(75))
    pages = ["Cover", "Title page"] + [_toc_page(40)] * 16 + [body, table] + ["x"] * 10
    assert toc_end(pages) == 18
    # A table of numbers after the TOC must not extend it.
    assert toc_end(["Cover", _toc_page(10), "1 SUMMARY\nbody", table]) == 2
    # No TOC at all → 0.
    assert toc_end(["1 SUMMARY\nbody", "2 INTRODUCTION"]) == 0


def test_index_on_long_toc_skips_front_matter() -> None:
    pages = (
        ["Cover"]
        + [_toc_page(40)] * 16
        + [
            "1 \nSUMMARY\ntext",
            "21 \nCAPITAL AND OPERATING COSTS\ntext",
            "22 \nECONOMIC ANALYSIS\ntext",
        ]
    )
    idx = build_index(
        pages, {1: "Summary", 21: "Capital and Operating Costs", 22: "Economic Analysis"}
    )
    assert idx[1].start == 18 and idx[21].start == 19 and idx[22] == ItemSpan(22, 20, 20)
