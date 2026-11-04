import pytest

from orebody.core.npv import NpvInputs, npv


def test_npv_clean_fixture() -> None:
    # Year 1: -100 (capex). Production years 2, 3: revenue 10,000 t × 10,000 $/t / 1e6 = 100,
    # opex 10,000 × 5,000 / 1e6 = 50, no sustaining, no tax → cf 50 each.
    # NPV @10% = -100/1.1 + 50/1.21 + 50/1.331 = -90.909 + 41.322 + 37.566 = -12.02
    # IRR: -100y² + 50y + 50 = 0 with y = 1+x → 2y² - y - 1 = 0 → y = 1 → x = 0.
    # Payback: cumulative after production year 1 = -50, after year 2 = 0 → 2.0 production years.
    inp = NpvInputs(
        mine_life_years=2,
        annual_payable_metal_t=10_000,
        unit_cost_usd_per_t=5_000,
        initial_capex_usd_m=100,
        sustaining_capex_usd_m=0,
        tax_rate=0.0,
        discount_rate=0.10,
        construction_years=1,
        ramp_up_year1=1.0,
    )
    res = npv(inp, price_usd_per_t=10_000)
    assert res.cashflows_usd_m == pytest.approx([-100, 50, 50])
    assert res.npv_usd_m == pytest.approx(-12.02, abs=0.01)
    assert res.irr == pytest.approx(0.0, abs=1e-6)
    assert res.payback_years == pytest.approx(2.0)


def test_npv_with_tax_and_ramp() -> None:
    # Year 1: -120. Prod year 1 (ramp 0.5 → 10,000 t): revenue 90, opex 40, sustaining 30/3 = 10,
    # pretax 40, tax 25% = 10 → cf 30. Prod years 2-3 (20,000 t): revenue 180, opex 80,
    # sustaining 10, pretax 90, tax 22.5 → cf 67.5.
    # NPV @8% = -120/1.08 + 30/1.08² + 67.5/1.08³ + 67.5/1.08⁴
    #         = -111.111 + 25.720 + 53.584 + 49.615 = 17.81
    inp = NpvInputs(
        mine_life_years=3,
        annual_payable_metal_t=20_000,
        unit_cost_usd_per_t=4_000,
        initial_capex_usd_m=120,
        sustaining_capex_usd_m=30,
        tax_rate=0.25,
        discount_rate=0.08,
        construction_years=1,
        ramp_up_year1=0.5,
    )
    res = npv(inp, price_usd_per_t=9_000)
    assert res.cashflows_usd_m == pytest.approx([-120, 30, 67.5, 67.5])
    assert res.npv_usd_m == pytest.approx(17.81, abs=0.02)
    assert res.irr is not None and 0.10 < res.irr < 0.20
    # Payback: cumulative -90 after prod year 1, -22.5 after year 2, +45 after year 3
    # → 2 + 22.5/67.5 = 2.333
    assert res.payback_years == pytest.approx(2.333, abs=0.001)


def test_negative_project_irr_none_when_no_sign_change() -> None:
    # Price 0 → revenue 0; every year's cash flow is negative (opex 50 per year).
    inp = NpvInputs(
        mine_life_years=2,
        annual_payable_metal_t=10_000,
        unit_cost_usd_per_t=5_000,
        initial_capex_usd_m=100,
        sustaining_capex_usd_m=0,
        tax_rate=0.3,
        discount_rate=0.10,
        construction_years=1,
        ramp_up_year1=1.0,
    )
    res = npv(inp, price_usd_per_t=0)
    assert all(cf < 0 for cf in res.cashflows_usd_m)
    assert res.irr is None
    assert res.payback_years is None
    assert res.npv_usd_m < 0


def test_default_construction_years_spreads_capex() -> None:
    # Defaults: construction 2 years, ramp 0.7 → capex 100 split as -50, -50.
    inp = NpvInputs(
        mine_life_years=1,
        annual_payable_metal_t=10_000,
        unit_cost_usd_per_t=5_000,
        initial_capex_usd_m=100,
        sustaining_capex_usd_m=0,
        tax_rate=0.0,
        discount_rate=0.10,
    )
    res = npv(inp, price_usd_per_t=10_000)
    # production year: 7,000 t → revenue 70, opex 35 → cf 35
    assert res.cashflows_usd_m == pytest.approx([-50, -50, 35])


def test_zero_mine_life_raises() -> None:
    inp = NpvInputs(
        mine_life_years=0,
        annual_payable_metal_t=10_000,
        unit_cost_usd_per_t=5_000,
        initial_capex_usd_m=100,
        sustaining_capex_usd_m=0,
        tax_rate=0.0,
        discount_rate=0.10,
    )
    with pytest.raises(ValueError):
        npv(inp, price_usd_per_t=10_000)
