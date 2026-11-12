import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from orebody.agents.context import build_context
from orebody.agents.financial_analyst import load_prompt
from orebody.cli import app
from orebody.index.ni43101 import build_index, load_patterns
from orebody.ingest.extract import extract_pages, read_page
from tests.fixtures.llm_fixtures import happy_financial_output, write_fixture

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = """
ticker: FIX
name: Fixture Copper Corp
reporting_currency: USD
documents:
  - file: fixture_report.pdf
    type: technical_report
    standard: NI43-101
    effective_date: 2025-08-25
    filing_date: 2025-10-09
"""


def test_run_fake_end_to_end(fixture_pdf: Path, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    raw = data_dir / "raw" / "FIX"
    raw.mkdir(parents=True)
    shutil.copy(fixture_pdf, raw / "fixture_report.pdf")
    (raw / "manifest.yaml").write_text(MANIFEST)

    # Record the hand-authored response under the exact key the CLI will request.
    ex = extract_pages(raw / "fixture_report.pdf", data_dir / "pages")
    pages = [read_page(ex.pages_dir, n) for n in range(1, ex.n_pages + 1)]
    index = build_index(pages, load_patterns(ROOT / "config" / "sections.yaml"))
    bundle = build_context(ex.pages_dir, index)
    _, system = load_prompt(ROOT / "prompts" / "financial_analyst.md")
    fixtures = tmp_path / "fixtures"
    write_fixture(
        fixtures,
        system=system,
        user=bundle.text,
        model="claude-opus-5-5",
        parsed=happy_financial_output("fixture_report"),
    )

    result = CliRunner().invoke(
        app,
        [
            "run",
            "FIX",
            "--as-of",
            "2026-11-05",
            "--spot",
            "4.50",
            "--deck-a",
            "3.50",
            "--deck-b",
            "5.00",
            "--provider",
            "fake",
            "--data-dir",
            str(data_dir),
            "--fixtures",
            str(fixtures),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    runs = list((data_dir / "runs").iterdir())
    assert len(runs) == 1 and runs[0].name.startswith("FIX-2026-11-05-")
    run_dir = runs[0]
    for name in ("context.txt", "output.json", "claims.json", "note.md", "stats.json"):
        assert (run_dir / name).exists(), name

    note = (run_dir / "note.md").read_text()
    assert "Reconciliation:" in note
    assert "| deck B |" in note and "| spot |" in note
    assert "Verification: 10/10 claims verified" in note

    stats = json.loads((run_dir / "stats.json").read_text())
    assert stats["total"] >= 8
    assert stats["verified"] == stats["total"]
    assert stats["rate"] == 1.0
    assert stats["model"] == "claude-opus-5-5"
    assert stats["prompt_version"] == "1"
    assert stats["items_missing"] == []
    assert stats["doc_sha256"] == ex.sha256
    assert stats["as_of"] == "2026-11-05"
    assert "rate=1.00" in result.output or "verified 10/10" in result.output


def test_run_without_manifest_errors(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "run",
            "NOPE",
            "--as-of",
            "2026-11-05",
            "--spot",
            "4.5",
            "--provider",
            "fake",
            "--data-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0


def test_demo_data_runs_on_fresh_clone(tmp_path: Path) -> None:
    # A fresh clone has no data/: `make demo-data` must create a runnable FIX company whose
    # recorded fixture is committed under tests/fixtures/llm/.
    from tests.fixtures.make_demo_data import make_demo_data

    data_dir = tmp_path / "data"
    make_demo_data(data_dir)
    assert (data_dir / "raw" / "FIX" / "manifest.yaml").exists()
    result = CliRunner().invoke(
        app,
        [
            "run",
            "FIX",
            "--as-of",
            "2026-11-05",
            "--spot",
            "4.50",
            "--provider",
            "fake",
            "--data-dir",
            str(data_dir),
            "--fixtures",
            str(ROOT / "tests" / "fixtures" / "llm"),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "verified 10/10" in result.output


def test_run_missing_pdf_errors_clearly(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "FIX"
    raw.mkdir(parents=True)
    (raw / "manifest.yaml").write_text(MANIFEST)  # names fixture_report.pdf, which is absent
    result = CliRunner().invoke(
        app,
        [
            "run",
            "FIX",
            "--as-of",
            "2026-11-05",
            "--spot",
            "4.5",
            "--provider",
            "fake",
            "--data-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 2
    assert "fixture_report.pdf" in result.output and "README" in result.output


def test_discover_cli_writes_candidates(tmp_path: Path, monkeypatch) -> None:
    from orebody.ingest import discover as disc
    from tests.unit.ingest.test_discover import RecordedFetch

    monkeypatch.setattr(disc, "http_fetch", RecordedFetch())
    out = tmp_path / "candidates.json"
    fix = ROOT / "tests" / "fixtures" / "edgar" / "candidates.yaml"
    r = CliRunner().invoke(
        app, ["discover", "--as-of", "2026-11-11", "--candidates", str(fix), "--out", str(out)]
    )
    assert r.exit_code == 0, r.output
    # Fixture Copper + Sedar Only included; REIT, Late Filer, No Report excluded
    assert "2 included, 3 excluded" in r.output
    assert len(json.loads(out.read_text())) == 5


def test_run_refuses_when_no_report_is_filed_by_as_of(tmp_path: Path) -> None:
    # F1.3: the error lists the excluded report and its date; no run directory is created.
    raw = tmp_path / "data" / "raw" / "FIX"
    raw.mkdir(parents=True)
    (raw / "manifest.yaml").write_text(MANIFEST)  # report filed 2025-10-09
    r = CliRunner().invoke(
        app,
        [
            "run",
            "FIX",
            "--as-of",
            "2025-01-01",
            "--spot",
            "4.5",
            "--provider",
            "fake",
            "--data-dir",
            str(tmp_path / "data"),
        ],
    )
    assert r.exit_code == 2
    assert "no technical report filed on or before 2025-01-01" in r.output
    assert "fixture_report.pdf (filed 2025-10-09)" in r.output
    assert not (tmp_path / "data" / "runs").exists()


def test_run_records_stats_in_the_database(fixture_pdf: Path, tmp_path: Path) -> None:
    # F6.4: the fake end-to-end run writes a 'done' run row with stats, under the data dir
    from orebody.db import connect
    from orebody.db.runs import get_run

    test_run_fake_end_to_end(fixture_pdf, tmp_path)  # same setup and run as above
    db = tmp_path / "data" / "orebody.sqlite"
    assert db.exists()
    conn = connect(db)
    (run_id,) = conn.execute("SELECT run_id FROM runs").fetchone()
    r = get_run(conn, run_id)
    assert r["status"] == "done"
    assert r["stats"]["total"] >= 1
    assert r["stats"]["tier1_rate"] == r["stats"]["verification_rate"]  # tier 2 not built yet
