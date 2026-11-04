from orebody.agents.context import build_context
from orebody.index.ni43101 import ItemSpan


def test_build_context_marks_pages(fixture_extracted, fixture_index) -> None:
    bundle = build_context(fixture_extracted.pages_dir, fixture_index)
    assert "=== Item 21: pages 5-5 ===" in bundle.text
    assert "--- page 5 ---" in bundle.text
    assert "US$1,240 million" in bundle.text
    assert bundle.pages == {3, 5, 6}
    assert bundle.items_found == [1, 21, 22]
    assert bundle.items_missing == []


def test_build_context_reports_missing_item(fixture_extracted, fixture_index) -> None:
    index = {k: v for k, v in fixture_index.items() if k != 22}
    bundle = build_context(fixture_extracted.pages_dir, index)
    assert bundle.items_missing == [22]
    assert 6 not in bundle.pages


def test_build_context_caps_pages_per_item(fixture_extracted) -> None:
    index = {1: ItemSpan(item=1, start=1, end=6)}
    bundle = build_context(fixture_extracted.pages_dir, index, items=(1,), max_pages_per_item=2)
    assert bundle.pages == {1, 2}
