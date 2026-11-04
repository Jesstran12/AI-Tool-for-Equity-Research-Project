"""Section 3 (Economics) Markdown, rendered by code from structured output (CLAUDE.md rule 3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from orebody.agents.schemas import EconInputs
from orebody.core.npv import NpvResult
from orebody.core.units import LB_PER_T
from orebody.verify.tier1 import VerifiedClaim

DISCLAIMER = (
    "This note is an automated synthesis of the company's public disclosures as of the stated "
    "date. It is not investment advice, contains no forecast of returns, and the stance expressed "
    "describes disclosed fundamentals only. Every figure links to its source page; figures marked "
    '"unverified" could not be matched to a source and should not be relied on.'
)

_FIELD_FORMAT: dict[str, str] = {
    "mine_life_years": "{:g} years",
    "annual_payable_metal_t": "{:,.0f} t/yr",
    "unit_cost_usd_per_t": "US${:,.2f}/t",
    "initial_capex_usd_m": "US${:,.0f} M",
    "sustaining_capex_usd_m": "US${:,.0f} M",
    "tax_rate": "{:.1%}",
    "discount_rate": "{:.1%}",
    "company_base_price_usd_per_t": "US${:,.2f}/t",
    "company_npv_usd_m": "US${:,.0f} M",
    "company_irr": "{:.1%}",
    "fx_stated_local_per_usd": "{:.4g} local per USD",
}

_ROW_LABELS = {"base": "base", "spot": "spot", "deck_a": "deck A", "deck_b": "deck B"}
_ESCAPE = str.maketrans({"\\": "\\\\", "|": "\\|", "[": "\\[", "]": "\\]", "`": "\\`", "<": "&lt;"})


@dataclass(frozen=True)
class PriceDeck:
    spot_usd_per_t: float
    deck_a_usd_per_t: float | None
    deck_b_usd_per_t: float | None
    source: str


def _safe(text: str) -> str:
    """Model-supplied text goes into tables and footnotes: neutralise Markdown control chars."""
    return " ".join(text.split()).translate(_ESCAPE)


def _fmt_value(field: str, value: float) -> str:
    return _FIELD_FORMAT.get(field, "{:,.4g}").format(value)


def _fmt_pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def _fmt_years(x: float | None) -> str:
    return "never" if x is None else f"{x:.1f}"


def _npv_table(inputs: EconInputs, deck: PriceDeck, results: dict[str, NpvResult]) -> list[str]:
    prices = {
        "base": inputs.company_base_price_usd_per_t,
        "spot": deck.spot_usd_per_t,
        "deck_a": deck.deck_a_usd_per_t,
        "deck_b": deck.deck_b_usd_per_t,
    }
    lines = [
        "**Rebuilt NPV**",
        "",
        "| Case | Price (USD/lb) | Price (USD/t) | NPV (USD M) | IRR | Payback (yrs) |",
        "|---|---|---|---|---|---|",
    ]
    for key, label in _ROW_LABELS.items():
        res = results.get(key)
        price = prices.get(key)
        if res is None or price is None:
            continue
        lines.append(
            f"| {label} | {price / LB_PER_T:,.2f} | {price:,.0f} | {res.npv_usd_m:,.0f} | "
            f"{_fmt_pct(res.irr)} | {_fmt_years(res.payback_years)} |"
        )
    return lines


def render_section3(
    *,
    ticker: str,
    name: str,
    as_of: date,
    doc_id: str,
    inputs: EconInputs,
    claims: list[VerifiedClaim],
    deck: PriceDeck,
    results: dict[str, NpvResult] | None,
    missing: list[str],
    run_id: str,
    cost_usd: float,
) -> str:
    verified = sum(1 for c in claims if c.final_status == "verified")
    footnote_of = {c.field: n for n, c in enumerate(claims, start=1)}
    out: list[str] = [
        f"# {name} ({ticker}) — Economics, as of {as_of.isoformat()}",
        "",
        f"Verification: {verified}/{len(claims)} claims verified · run {run_id} · "
        f"cost US${cost_usd:.2f}",
        "",
        "## 3. Economics",
        "",
        "| Field | Value (USD, metric) | As printed | Source |",
        "|---|---|---|---|",
    ]
    by_field = {c.field: c for c in claims}
    for field in type(inputs).model_fields:
        value = getattr(inputs, field)
        if value is None:
            continue
        claim = by_field.get(field)
        printed = _safe(claim.value_orig) if claim else "—"
        source = f"[^{footnote_of[field]}]" if claim else "no claim"
        if claim and claim.final_status != "verified":
            source += " ⚠ unverified"
        out.append(f"| {field} | {_fmt_value(field, value)} | {printed} | {source} |")
    out.append("")
    if results is None:
        out.append(f"NPV not computable: missing {missing}")
    else:
        out.extend(_npv_table(inputs, deck, results))
        base = results.get("base")
        if base is not None and inputs.company_npv_usd_m:
            gap = (base.npv_usd_m - inputs.company_npv_usd_m) / inputs.company_npv_usd_m
            out.append("")
            out.append(
                f"Reconciliation: rebuilt base-case NPV US${base.npv_usd_m:,.0f} M vs "
                f"company-stated US${inputs.company_npv_usd_m:,.0f} M → gap {gap * 100:+.1f}%"
            )
    out.append("")
    for n, c in enumerate(claims, start=1):
        out.append(f'[^{n}]: {_safe(c.doc_id)}, p.{c.page}: "{_safe(c.quote)}"')
    out.extend(["", DISCLAIMER, ""])
    return "\n".join(out)
