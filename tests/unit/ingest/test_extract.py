from pathlib import Path

import pytest

from orebody.ingest.extract import extract_pages, read_page


def test_extract_writes_one_file_per_page(fixture_pdf: Path, tmp_path: Path) -> None:
    ex = extract_pages(fixture_pdf, tmp_path / "pages")
    assert ex.doc_id == "fixture_report"
    assert ex.n_pages == 6
    assert len(ex.sha256) == 64
    files = sorted(p.name for p in ex.pages_dir.glob("*.txt"))
    assert files == [f"{i:04d}.txt" for i in range(1, 7)]
    assert "US$1,240 million" in (ex.pages_dir / "0005.txt").read_text()


def test_extract_is_idempotent(fixture_pdf: Path, tmp_path: Path) -> None:
    first = extract_pages(fixture_pdf, tmp_path / "pages")
    mtimes = {p.name: p.stat().st_mtime_ns for p in first.pages_dir.glob("*.txt")}
    second = extract_pages(fixture_pdf, tmp_path / "pages")
    assert second == first
    assert {p.name: p.stat().st_mtime_ns for p in first.pages_dir.glob("*.txt")} == mtimes


def test_read_page_out_of_range_raises(fixture_pdf: Path, tmp_path: Path) -> None:
    ex = extract_pages(fixture_pdf, tmp_path / "pages")
    assert "22.8%" in read_page(ex.pages_dir, 6)
    with pytest.raises(ValueError):
        read_page(ex.pages_dir, 7)
    with pytest.raises(ValueError):
        read_page(ex.pages_dir, 0)
