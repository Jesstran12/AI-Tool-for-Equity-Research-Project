import pytest
from pydantic import ValidationError

from orebody.agents.schemas import Claim, EconInputs, FinancialAnalystOutput


def _claim(field: str) -> Claim:
    return Claim(
        field=field,
        claim_type="number",
        value_orig="18 years",
        doc_id="doc",
        page=3,
        quote="mine life of 18 years",
    )


def test_output_requires_claim_per_input() -> None:
    inputs = EconInputs(mine_life_years=18)
    with pytest.raises(ValidationError, match="mine_life_years"):
        FinancialAnalystOutput(inputs=inputs, claims=[], notes="")
    ok = FinancialAnalystOutput(inputs=inputs, claims=[_claim("mine_life_years")], notes="")
    assert ok.inputs.mine_life_years == 18


def test_output_rejects_duplicate_claims_for_one_field() -> None:
    inputs = EconInputs(mine_life_years=18)
    with pytest.raises(ValidationError, match="mine_life_years"):
        FinancialAnalystOutput(
            inputs=inputs, claims=[_claim("mine_life_years"), _claim("mine_life_years")], notes=""
        )


def test_missing_lists_none_fields() -> None:
    inputs = EconInputs(mine_life_years=18, initial_capex_usd_m=1240)
    missing = inputs.missing()
    assert "mine_life_years" not in missing
    assert "sustaining_capex_usd_m" in missing and "tax_rate" in missing
    assert EconInputs().missing() == list(EconInputs.model_fields)


def test_claim_quote_max_300_chars() -> None:
    with pytest.raises(ValidationError):
        Claim(field="x", claim_type="number", value_orig="1", doc_id="d", page=1, quote="q" * 301)
