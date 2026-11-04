"""Parametric project NPV, IRR and payback (SPEC §7). Pure: no I/O, no LLM."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NpvInputs:
    mine_life_years: int
    annual_payable_metal_t: float
    unit_cost_usd_per_t: float
    initial_capex_usd_m: float
    sustaining_capex_usd_m: float
    tax_rate: float
    discount_rate: float
    construction_years: int = 2
    ramp_up_year1: float = 0.7


@dataclass(frozen=True)
class NpvResult:
    npv_usd_m: float
    irr: float | None
    payback_years: float | None
    cashflows_usd_m: list[float]


def cashflows(inp: NpvInputs, price_usd_per_t: float) -> list[float]:
    """End-of-year cash flows in USD M: construction years, then production years."""
    if inp.mine_life_years <= 0:
        raise ValueError("mine_life_years must be positive")
    if inp.construction_years <= 0:
        raise ValueError("construction_years must be positive")
    flows = [-inp.initial_capex_usd_m / inp.construction_years] * inp.construction_years
    sustaining = inp.sustaining_capex_usd_m / inp.mine_life_years
    for year in range(inp.mine_life_years):
        metal = inp.annual_payable_metal_t * (inp.ramp_up_year1 if year == 0 else 1.0)
        revenue = metal * price_usd_per_t / 1e6
        opex = metal * inp.unit_cost_usd_per_t / 1e6
        pretax = revenue - opex - sustaining
        tax = max(pretax, 0.0) * inp.tax_rate
        flows.append(pretax - tax)
    return flows


def present_value(flows: list[float], rate: float) -> float:
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(flows, start=1))


def irr(flows: list[float], lo: float = -0.99, hi: float = 10.0, tol: float = 1e-9) -> float | None:
    """Bisection on [lo, hi]; None when the NPV does not change sign over the bracket."""
    f_lo, f_hi = present_value(flows, lo), present_value(flows, hi)
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if (f_lo > 0) == (f_hi > 0):
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = present_value(flows, mid)
        if abs(f_mid) < tol or hi - lo < tol:
            return mid
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return (lo + hi) / 2


def payback(flows: list[float], construction_years: int) -> float | None:
    """Production years until cumulative cash flow ≥ 0, interpolated within the year."""
    cumulative = sum(flows[:construction_years])
    for i, cf in enumerate(flows[construction_years:]):
        before = cumulative
        cumulative += cf
        if cumulative >= 0:
            if cf <= 0:
                return float(i)
            return i + (-before / cf)
    return None


def npv(inp: NpvInputs, price_usd_per_t: float) -> NpvResult:
    flows = cashflows(inp, price_usd_per_t)
    return NpvResult(
        npv_usd_m=present_value(flows, inp.discount_rate),
        irr=irr(flows),
        payback_years=payback(flows, inp.construction_years),
        cashflows_usd_m=flows,
    )
