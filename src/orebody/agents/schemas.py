"""Structured agent output: every number is a claim with a page and a verbatim quote (D9, D10)."""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Claim(BaseModel):
    field: str
    claim_type: Literal["number", "entity", "date"]
    value_orig: str
    unit_orig: str | None = None
    currency_orig: str | None = None
    doc_id: str = ""  # stamped by the pipeline; the model need not fill it
    page: int
    quote: str = Field(max_length=300)


class EconInputs(BaseModel):
    """All optional; None means the report does not disclose it (never estimated)."""

    mine_life_years: float | None = None
    annual_payable_metal_t: float | None = None
    unit_cost_usd_per_t: float | None = None
    initial_capex_usd_m: float | None = None
    sustaining_capex_usd_m: float | None = None
    tax_rate: float | None = None
    discount_rate: float | None = None
    company_base_price_usd_per_t: float | None = None
    company_npv_usd_m: float | None = None
    company_irr: float | None = None
    fx_stated_local_per_usd: float | None = None

    def missing(self) -> list[str]:
        return [name for name in type(self).model_fields if getattr(self, name) is None]


class FinancialAnalystOutput(BaseModel):
    inputs: EconInputs
    claims: list[Claim]
    notes: str

    @model_validator(mode="after")
    def _one_claim_per_input(self) -> FinancialAnalystOutput:
        counts = Counter(c.field for c in self.claims)
        problems = []
        for name in type(self.inputs).model_fields:
            if getattr(self.inputs, name) is None:
                continue
            if counts.get(name, 0) != 1:
                problems.append(f"{name} has {counts.get(name, 0)} claims (need exactly 1)")
        if problems:
            raise ValueError("; ".join(problems))
        return self
