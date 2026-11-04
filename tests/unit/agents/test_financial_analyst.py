from pathlib import Path

import pytest

from orebody.agents.context import build_context
from orebody.agents.financial_analyst import load_prompt, run_financial_analyst
from orebody.llm.fake import FakeProvider
from tests.fixtures.llm_fixtures import happy_financial_output, write_fixture

ROOT = Path(__file__).resolve().parents[3]
PROMPT = ROOT / "prompts" / "financial_analyst.md"
MODEL = "claude-opus-5-5"


def test_load_prompt_version() -> None:
    version, body = load_prompt(PROMPT)
    assert version == "1"
    assert body.startswith("You are the Financial Analyst")
    assert "version:" not in body


def _record(tmp_path: Path, bundle, parsed: dict) -> None:
    _, body = load_prompt(PROMPT)
    write_fixture(tmp_path, system=body, user=bundle.text, model=MODEL, parsed=parsed)


def test_run_financial_analyst_happy(fixture_extracted, fixture_index, tmp_path: Path) -> None:
    bundle = build_context(fixture_extracted.pages_dir, fixture_index)
    doc_id = fixture_extracted.doc_id
    _record(tmp_path, bundle, happy_financial_output(doc_id))
    out, completion = run_financial_analyst(
        FakeProvider(tmp_path), bundle, doc_id, MODEL, "medium", PROMPT
    )
    assert out.inputs.initial_capex_usd_m == 1240
    assert out.inputs.missing() == ["fx_stated_local_per_usd"]
    assert len(out.claims) == 10
    assert completion.usage.input_tokens == 3000


def test_claim_page_outside_context_rejected(
    fixture_extracted, fixture_index, tmp_path: Path
) -> None:
    bundle = build_context(fixture_extracted.pages_dir, fixture_index)
    doc_id = fixture_extracted.doc_id
    parsed = happy_financial_output(doc_id)
    parsed["claims"][0]["page"] = 9
    _record(tmp_path, bundle, parsed)
    with pytest.raises(ValueError, match="page 9"):
        run_financial_analyst(FakeProvider(tmp_path), bundle, doc_id, MODEL, "medium", PROMPT)


def test_claim_wrong_doc_id_rejected(fixture_extracted, fixture_index, tmp_path: Path) -> None:
    bundle = build_context(fixture_extracted.pages_dir, fixture_index)
    doc_id = fixture_extracted.doc_id
    parsed = happy_financial_output("other_doc")
    _record(tmp_path, bundle, parsed)
    with pytest.raises(ValueError, match="other_doc"):
        run_financial_analyst(FakeProvider(tmp_path), bundle, doc_id, MODEL, "medium", PROMPT)
