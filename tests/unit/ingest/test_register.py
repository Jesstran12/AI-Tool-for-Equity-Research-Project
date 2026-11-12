"""F1.4 ingest: company + documents into SQLite. Fresh database and drop folder per test."""

import hashlib
import shutil
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from orebody.db import connect, migrate
from orebody.ingest.register import doc_id_for, ingest_folder

MANIFEST = """
ticker: FIX
name: Fixture Copper Corp
exchange: TSXV
primary_commodity: Cu
by_products: [Mo, Ag]
documents:
  - file: report.pdf
    type: technical_report
    standard: NI43-101
    effective_date: 2025-08-25
    filing_date: 2025-10-09
    url: https://example.com/report.pdf
  - file: 2026-10-01_news.htm
    type: news_release
    filing_date: 2026-10-01
"""


@pytest.fixture
def setup(tmp_path: Path, fixture_pdf: Path) -> tuple[sqlite3.Connection, Path, Path]:
    data = tmp_path / "data"
    folder = data / "raw" / "FIX"
    folder.mkdir(parents=True)
    (folder / "manifest.yaml").write_text(MANIFEST)
    # One PDF only: the schema rejects two files with identical contents for one company
    # (UNIQUE ticker, sha256), and the fixture PDF is the only PDF we have (user, 2026-11-11).
    shutil.copy(fixture_pdf, folder / "report.pdf")  # 6 pages
    (folder / "2026-10-01_news.htm").write_text("<p>news</p>")
    conn = connect(tmp_path / "t.sqlite")
    migrate(conn)
    return conn, folder, data


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _doc(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row:
    return conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()


@pytest.mark.parametrize(
    ("ticker", "file", "expected"),
    [
        ("NCX", "2025-12-31_FS_annual-2025.pdf", "NCX/2025-12-31_FS_annual-2025"),
        ("fix", "report.pdf", "FIX/report"),  # ticker upper-cased
        ("LEO", "2024-12-31_yerington-ia_ex96-1.htm", "LEO/2024-12-31_yerington-ia_ex96-1"),
    ],
)
def test_doc_id_for(ticker: str, file: str, expected: str) -> None:
    assert doc_id_for(ticker, file) == expected


def test_first_ingest_registers_company_and_documents(setup) -> None:
    conn, folder, data = setup
    r = ingest_folder(conn, folder, data)
    assert r.ok
    assert sorted(r.added) == ["2026-10-01_news.htm", "report.pdf"]
    c = conn.execute("SELECT * FROM companies WHERE ticker = 'FIX'").fetchone()
    assert c["name"] == "Fixture Copper Corp"
    assert (c["exchange"], c["primary_commodity"]) == ("TSXV", "Cu")
    assert c["by_products"] == '["Mo", "Ag"]'
    rep = _doc(conn, "FIX/report")
    assert rep["sha256"] == _sha(folder / "report.pdf")
    assert rep["pages"] == 6  # the fixture report
    assert rep["path"] == "raw/FIX/report.pdf"  # relative to the data root
    assert rep["url"] == "https://example.com/report.pdf"
    assert (rep["type"], rep["standard"], rep["filing_date"]) == (
        "technical_report",
        "NI43-101",
        "2025-10-09",
    )
    assert _doc(conn, "FIX/2026-10-01_news")["pages"] is None  # HTML has no pages


def test_second_ingest_is_a_no_op(setup) -> None:
    conn, folder, data = setup
    ingest_folder(conn, folder, data)
    r = ingest_folder(conn, folder, data)
    assert r.added == [] and len(r.unchanged) == 2
    assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2


def test_missing_file_is_reported_not_registered(setup) -> None:
    conn, folder, data = setup
    (folder / "2026-10-01_news.htm").unlink()
    r = ingest_folder(conn, folder, data)
    assert not r.ok
    assert r.missing == ["2026-10-01_news.htm"]
    assert _doc(conn, "FIX/2026-10-01_news") is None
    assert _doc(conn, "FIX/report") is not None  # the rest still registers


def test_manifest_sha256_mismatch_is_not_registered(setup) -> None:
    conn, folder, data = setup
    m = MANIFEST.replace(
        "    url: https://example.com/report.pdf\n",
        "    url: https://example.com/report.pdf\n    sha256: " + "0" * 64 + "\n",
    )
    (folder / "manifest.yaml").write_text(m)
    r = ingest_folder(conn, folder, data)
    assert r.mismatch == ["report.pdf"] and not r.ok
    assert _doc(conn, "FIX/report") is None


def test_manifest_sha256_match_is_registered(setup) -> None:
    conn, folder, data = setup
    good = _sha(folder / "report.pdf")
    m = MANIFEST.replace(
        "    url: https://example.com/report.pdf\n",
        f"    url: https://example.com/report.pdf\n    sha256: {good}\n",
    )
    (folder / "manifest.yaml").write_text(m)
    assert "report.pdf" in ingest_folder(conn, folder, data).added


def test_changed_file_updates_the_row_and_is_reported(setup) -> None:
    conn, folder, data = setup
    ingest_folder(conn, folder, data)
    (folder / "2026-10-01_news.htm").write_text("<p>news, edited</p>")
    r = ingest_folder(conn, folder, data)
    assert r.changed == ["2026-10-01_news.htm"]
    assert _doc(conn, "FIX/2026-10-01_news")["sha256"] == _sha(folder / "2026-10-01_news.htm")


def test_company_row_follows_the_manifest(setup) -> None:
    conn, folder, data = setup
    ingest_folder(conn, folder, data)
    (folder / "manifest.yaml").write_text(MANIFEST.replace("exchange: TSXV", "exchange: CSE"))
    ingest_folder(conn, folder, data)
    row = conn.execute("SELECT exchange FROM companies WHERE ticker = 'FIX'").fetchone()
    assert row[0] == "CSE"


def test_same_file_name_in_two_companies(setup, fixture_pdf: Path) -> None:
    # Real case: NCX and USCU both hold 2025-12-31_FS_annual-2025.pdf; here both hold report.pdf
    conn, folder, data = setup
    other = data / "raw" / "OTH"
    other.mkdir()
    (other / "manifest.yaml").write_text(
        MANIFEST.replace("ticker: FIX", "ticker: OTH").replace("Fixture Copper Corp", "Other Corp")
    )
    shutil.copy(fixture_pdf, other / "report.pdf")
    (other / "2026-10-01_news.htm").write_text("<p>other news</p>")
    assert ingest_folder(conn, folder, data).ok
    assert ingest_folder(conn, other, data).ok
    ids = {r[0] for r in conn.execute("SELECT doc_id FROM documents")}
    assert {"FIX/report", "OTH/report"} <= ids


def test_ingest_cli(setup, tmp_path: Path) -> None:
    from orebody.cli import app

    _, folder, data = setup
    db = tmp_path / "cli.sqlite"
    args = ["ingest", "FIX", "--data-dir", str(data), "--db", str(db)]
    first = CliRunner().invoke(app, args)
    assert first.exit_code == 0, first.output
    assert "FIX: added 2, unchanged 0, changed 0, missing 0, mismatch 0" in first.output
    (folder / "report.pdf").unlink()
    again = CliRunner().invoke(app, args)
    assert again.exit_code == 1
    assert "missing: report.pdf" in again.output


# --- real drop folder, skipped on a fresh clone ------------------------------------------------

MARI = Path(__file__).resolve().parents[3] / "data" / "raw" / "MARI"


@pytest.mark.skipif(not (MARI / "manifest.yaml").exists(), reason="MARI not present")
def test_real_mari_ingests(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.sqlite")
    migrate(conn)
    r = ingest_folder(conn, MARI, MARI.parent.parent)
    # Every manifest file present on disk registers; none has a wrong sha256.
    assert r.mismatch == []
    assert len(r.added) + len(r.missing) == 27  # 8 hand-listed + 19 news appended 2026-11-11
    fs = _doc(conn, "MARI/2025-08-25_MarimacaOxide_FS_NI43-101")
    assert fs is None or fs["pages"] == 361
