import re
from datetime import date
from pathlib import Path

from orebody.agents.schemas import EconInputs
from orebody.core.npv import NpvResult
from orebody.render.markdown import DISCLAIMER, PriceDeck, render_section3
from orebody.verify.tier1 import VerifiedClaim

SPEC = Path(__file__).resolve().parents[3] / "SPEC.md"


def _vc(field: str, value_orig: str, page: int, quote: str, verified: bool = True) -> VerifiedClaim:
    return VerifiedClaim(
        field=field,
        claim_type="number",
        value_orig=value_orig,
        doc_id="fixture_report",
        page=page,
        quote=quote,
        tier1_status="pass" if verified else "fail",
        tier1_reason="" if verified else "quote not found on page",
        final_status="verified" if verified else "unverified",
    )


INPUTS = EconInputs(
    mine_life_years=18,
    initial_capex_usd_m=1240,
    company_npv_usd_m=2100,
    company_base_price_usd_per_t=8818.48,
)
CLAIMS = [
    _vc("mine_life_years", "18 years", 3, "mine life of 18 years"),
    _vc("initial_capex_usd_m", "US$1,240 million", 5, "estimated at US$1,240 million."),
    _vc("company_npv_usd_m", "US$2,100 million", 6, "is US$2,100 million", verified=False),
    _vc("company_base_price_usd_per_t", "US$4.00/lb", 6, "price of US$4.00/lb"),
]
DECK = PriceDeck(
    spot_usd_per_t=9920.79, deck_a_usd_per_t=7716.17, deck_b_usd_per_t=None, source="cli"
)


def _res(npv: float) -> NpvResult:
    return NpvResult(npv_usd_m=npv, irr=0.21, payback_years=3.4, cashflows_usd_m=[-1.0, 1.0])


def _render(**overrides: object) -> str:
    kwargs: dict = dict(
        ticker="FIX",
        name="Fixture Copper Corp",
        as_of=date(2026, 11, 5),
        doc_id="fixture_report",
        inputs=INPUTS,
        claims=CLAIMS,
        deck=DECK,
        results={"base": _res(1850.0), "spot": _res(2400.0), "deck_a": _res(900.0)},
        missing=[],
        run_id="FIX-2026-11-05-101500",
        cost_usd=0.4321,
    )
    kwargs.update(overrides)
    return render_section3(**kwargs)


def test_header_and_status_line() -> None:
    md = _render()
    assert md.startswith("# Fixture Copper Corp (FIX) — Economics, as of 2026-11-05")
    assert "Verification: 3/4 claims verified · run FIX-2026-11-05-101500 · cost US$0.43" in md


def test_render_contains_footnote_per_claim() -> None:
    md = _render()
    for n, c in enumerate(CLAIMS, start=1):
        assert f"[^{n}]" in md
        assert f'[^{n}]: fixture_report, p.{c.page}: "{c.quote}"' in md
    assert len(re.findall(r"^\[\^\d+\]:", md, re.M)) == len(CLAIMS)


def test_footnote_shows_original_value() -> None:
    claims = [_vc("initial_capex_usd_m", "C$1,674 million", 5, "estimated at C$1,674 million")]
    inputs = EconInputs(initial_capex_usd_m=1240, fx_stated_local_per_usd=1.35)
    md = _render(inputs=inputs, claims=claims, results=None, missing=["mine_life_years"])
    row = next(line for line in md.splitlines() if line.startswith("| initial_capex_usd_m"))
    assert "C$1,674 million" in row
    assert "1,240" in row or "1240" in row


def test_unverified_row_tagged() -> None:
    md = _render()
    row = next(line for line in md.splitlines() if line.startswith("| company_npv_usd_m"))
    assert "⚠ unverified" in row
    capex = next(line for line in md.splitlines() if line.startswith("| initial_capex_usd_m"))
    assert "unverified" not in capex


def test_rebuilt_npv_table_rows() -> None:
    md = _render()
    assert "**Rebuilt NPV**" in md
    assert "| base |" in md and "| spot |" in md and "| deck A |" in md
    assert "| deck B |" not in md  # no deck B price given
    base = next(line for line in md.splitlines() if line.startswith("| base |"))
    assert "4.00" in base and "8,818" in base and "1,850" in base and "21.0%" in base


def test_reconciliation_line() -> None:
    md = _render()
    # (1850 - 2100) / 2100 = -11.9%
    assert (
        "Reconciliation: rebuilt base-case NPV US$1,850 M vs company-stated US$2,100 M → gap -11.9%"
        in md
    )


def test_render_missing_inputs() -> None:
    md = _render(results=None, missing=["sustaining_capex_usd_m"])
    assert "NPV not computable: missing ['sustaining_capex_usd_m']" in md
    assert "Reconciliation:" not in md
    assert "**Rebuilt NPV**" not in md


def test_disclaimer_verbatim() -> None:
    md = _render()
    assert md.rstrip().endswith(DISCLAIMER)
    assert f"> {DISCLAIMER}" in SPEC.read_text()
