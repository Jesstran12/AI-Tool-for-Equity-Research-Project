from pathlib import Path

import pytest

from orebody.ingest.manifest import load_manifest

VALID = """
ticker: FIX
name: Fixture Copper Corp
exchange: TSXV
flagship_project: Fixture
reporting_currency: USD
documents:
  - file: 2025-08-25_FS_report.pdf
    type: technical_report
    standard: NI43-101
    effective_date: 2025-08-25
    filing_date: 2025-10-09
    title: Fixture FS
    project: Fixture
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "manifest.yaml"
    p.write_text(text)
    return p


def test_load_valid_manifest(tmp_path: Path) -> None:
    m = load_manifest(_write(tmp_path, VALID))
    assert m.ticker == "FIX"
    assert m.technical_report().file == "2025-08-25_FS_report.pdf"
    assert m.documents[0].standard == "NI43-101"


def test_missing_filing_date_raises(tmp_path: Path) -> None:
    bad = VALID.replace("    filing_date: 2025-10-09\n", "")
    with pytest.raises(ValueError, match="filing_date"):
        load_manifest(_write(tmp_path, bad))


def test_no_technical_report_raises(tmp_path: Path) -> None:
    text = VALID.replace("type: technical_report", "type: news_release")
    m = load_manifest(_write(tmp_path, text))
    with pytest.raises(ValueError, match="technical_report"):
        m.technical_report()


# Real-data lesson (F1.4, 2026-11-11): YAML turns unquoted all-digit hashes into numbers.
@pytest.mark.parametrize(
    "raw",
    [
        "0" * 64,  # would be int 0
        "0" + "7" * 63,  # would be read as octal
        "1" * 64,  # would be a large int
        "ab" * 32,  # ordinary hex
    ],
)
def test_sha256_stays_text(tmp_path: Path, raw: str) -> None:
    m = load_manifest(_write(tmp_path, VALID + f"    sha256: {raw}\n"))
    assert m.documents[0].sha256 == raw


def test_dates_still_parse_with_text_loader(tmp_path: Path) -> None:
    from datetime import date

    m = load_manifest(_write(tmp_path, VALID))
    assert m.documents[0].filing_date == date(2025, 10, 9)
