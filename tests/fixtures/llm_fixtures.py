"""Hand-authored Financial Analyst output for the synthetic fixture report (make_pdf.py)."""

from __future__ import annotations

import json
from pathlib import Path

from orebody.llm.provider import request_key


def _claim(field: str, value_orig: str, page: int, quote: str, doc_id: str, **kw) -> dict:
    return {
        "field": field,
        "claim_type": "number",
        "value_orig": value_orig,
        "doc_id": doc_id,
        "page": page,
        "quote": quote,
        **kw,
    }


def happy_financial_output(doc_id: str) -> dict:
    """Inputs 18 / 50000 / 4078.55 / 1240 / 310 / 0.27 / 0.08 / 8818.48 / 2100 / 0.228 / None."""
    return {
        "inputs": {
            "mine_life_years": 18,
            "annual_payable_metal_t": 50000,
            "unit_cost_usd_per_t": 4078.55,
            "initial_capex_usd_m": 1240,
            "sustaining_capex_usd_m": 310,
            "tax_rate": 0.27,
            "discount_rate": 0.08,
            "company_base_price_usd_per_t": 8818.48,
            "company_npv_usd_m": 2100,
            "company_irr": 0.228,
            "fx_stated_local_per_usd": None,
        },
        "claims": [
            _claim(
                "mine_life_years",
                "18 years",
                3,
                "The Project has a mine life of 18 years",
                doc_id,
                unit_orig="years",
            ),
            _claim(
                "annual_payable_metal_t",
                "50,000 tonnes",
                3,
                "50,000 tonnes of payable copper per year",
                doc_id,
                unit_orig="tonnes per year",
            ),
            _claim(
                "unit_cost_usd_per_t",
                "US$1.85/lb",
                5,
                "C1 cash cost is US$1.85/lb.",
                doc_id,
                unit_orig="/lb",
                currency_orig="USD",
            ),
            _claim(
                "initial_capex_usd_m",
                "US$1,240 million",
                5,
                "Initial capital cost is estimated at US$1,240 million.",
                doc_id,
                unit_orig="million",
                currency_orig="USD",
            ),
            _claim(
                "sustaining_capex_usd_m",
                "US$310 million",
                5,
                "Sustaining capital totals US$310 million over the life of mine.",
                doc_id,
                unit_orig="million",
                currency_orig="USD",
            ),
            _claim("tax_rate", "27%", 6, "The effective tax rate is 27%.", doc_id, unit_orig="%"),
            _claim(
                "discount_rate",
                "8%",
                6,
                "post-tax NPV at an 8% discount rate",
                doc_id,
                unit_orig="%",
            ),
            _claim(
                "company_base_price_usd_per_t",
                "US$4.00/lb",
                6,
                "At a base case copper price of US$4.00/lb",
                doc_id,
                unit_orig="/lb",
                currency_orig="USD",
            ),
            _claim(
                "company_npv_usd_m",
                "US$2,100 million",
                6,
                "discount rate is US$2,100 million",
                doc_id,
                unit_orig="million",
                currency_orig="USD",
            ),
            _claim("company_irr", "22.8%", 6, "with an IRR of 22.8%", doc_id, unit_orig="%"),
        ],
        "notes": "All inputs stated in Items 1, 21 and 22. Report is in USD; no FX needed.",
    }


def write_fixture(fixture_dir: Path, *, system: str, user: str, model: str, parsed: dict) -> str:
    """Record `parsed` as a FakeProvider fixture for this exact request; returns the key."""
    key = request_key(system, user, "FinancialAnalystOutput", model)
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / f"{key}.json").write_text(
        json.dumps(
            {
                "parsed": parsed,
                "raw_text": json.dumps(parsed),
                "usage": {"input_tokens": 3000, "output_tokens": 900},
                "model": model,
            }
        )
    )
    return key
