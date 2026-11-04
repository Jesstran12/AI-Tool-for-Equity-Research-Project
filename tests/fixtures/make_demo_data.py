"""Build the synthetic demo company FIX so a fresh clone can run `orebody run FIX --provider fake`.

Usage: uv run python tests/fixtures/make_demo_data.py [DATA_DIR]   (default: data)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from orebody.agents.context import build_context  # noqa: E402
from orebody.agents.financial_analyst import load_prompt  # noqa: E402
from orebody.index.ni43101 import build_index, load_patterns  # noqa: E402
from orebody.ingest.extract import extract_pages, read_page  # noqa: E402
from tests.fixtures.llm_fixtures import happy_financial_output, write_fixture  # noqa: E402
from tests.fixtures.make_pdf import make_report  # noqa: E402

MANIFEST = """# Synthetic demo company built by tests/fixtures/make_demo_data.py. Not a real filing.
ticker: FIX
name: Fixture Copper Corp
exchange: none
flagship_project: Fixture Copper Project
reporting_currency: USD
documents:
  - file: fixture_report.pdf
    type: technical_report
    standard: NI43-101
    effective_date: 2025-08-25
    filing_date: 2025-10-09
    title: Fixture Copper Project NI 43-101 Technical Report
    project: Fixture Copper Project
"""


def make_demo_data(data_dir: Path, fixtures_dir: Path = ROOT / "tests" / "fixtures" / "llm") -> str:
    """Write data_dir/raw/FIX/{fixture_report.pdf,manifest.yaml}; record the replay fixture."""
    raw = Path(data_dir) / "raw" / "FIX"
    raw.mkdir(parents=True, exist_ok=True)
    pdf = make_report(raw / "fixture_report.pdf")
    (raw / "manifest.yaml").write_text(MANIFEST)
    ex = extract_pages(pdf, Path(data_dir) / "pages")
    pages = [read_page(ex.pages_dir, n) for n in range(1, ex.n_pages + 1)]
    index = build_index(pages, load_patterns(ROOT / "config" / "sections.yaml"))
    bundle = build_context(ex.pages_dir, index)
    _, system = load_prompt(ROOT / "prompts" / "financial_analyst.md")
    return write_fixture(
        fixtures_dir,
        system=system,
        user=bundle.text,
        model="claude-opus-5-5",
        parsed=happy_financial_output(ex.doc_id),
    )


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    key = make_demo_data(target)
    print(f"wrote {target / 'raw' / 'FIX'} and tests/fixtures/llm/{key}.json")
