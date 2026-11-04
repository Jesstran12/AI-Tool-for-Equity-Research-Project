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
