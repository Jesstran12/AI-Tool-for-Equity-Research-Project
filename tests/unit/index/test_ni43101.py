from pathlib import Path

import pytest

from orebody.index.ni43101 import ItemSpan, build_index, load_patterns
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
