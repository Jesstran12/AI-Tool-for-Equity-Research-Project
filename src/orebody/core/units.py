"""Parse printed quantities ("US$1,240 million", "US$4.00/lb") into scaled, unit-tagged values."""

from __future__ import annotations

import re
from dataclasses import dataclass

LB_PER_T = 2204.62

# unit ∈ {M, t, pct, per_lb, per_t, years, t_per_year, lb}; value is already scaled (M = millions)
Unit = str

_NUMBER = re.compile(
    r"(?P<cur>US\$|USD|C\$|CAD|A\$|AUD|\$)?\s*"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
)

_CURRENCY = {
    "US$": "USD",
    "USD": "USD",
    "$": "USD",
    "C$": "CAD",
    "CAD": "CAD",
    "A$": "AUD",
    "AUD": "AUD",
}

# (pattern applied at the start of the text following the number, unit, multiplier); order matters.
_TAILS: list[tuple[re.Pattern[str], Unit, float]] = [
    (re.compile(r"Mt\b"), "t", 1e6),
    (re.compile(r"kt\b"), "t", 1e3),
    (re.compile(r"Mlb\b"), "lb", 1e6),
    (re.compile(r"Blb\b"), "lb", 1e9),
    (re.compile(r"(?:tpa|t/a|tonnes?\s+per\s+(?:year|annum))\b", re.I), "t_per_year", 1.0),
    (re.compile(r"(?:tonnes?|t)\b", re.I), "t", 1.0),
    (re.compile(r"(?:billion|bn)\b", re.I), "M", 1e3),
    (re.compile(r"B\b"), "M", 1e3),
    (re.compile(r"(?:million|mm|m)\b", re.I), "M", 1.0),
    (re.compile(r"(?:thousand|k)\b", re.I), "M", 1e-3),
    (re.compile(r"%"), "pct", 1.0),
    (re.compile(r"/\s*lb\b", re.I), "per_lb", 1.0),
    (re.compile(r"/\s*(?:tonne|t)\b", re.I), "per_t", 1.0),
    (re.compile(r"(?:years?|yrs?)\b", re.I), "years", 1.0),
]


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: Unit
    currency: str | None


def parse_quantity(text: str) -> Quantity | None:
    m = _NUMBER.search(text)
    if not m:
        return None
    number = float(m.group("num").replace(",", ""))
    cur_tok = m.group("cur")
    currency = _CURRENCY.get(cur_tok) if cur_tok else None
    if cur_tok == "$" and re.search(r"[CA]\$", text):
        currency = None
    rest = text[m.end() :].lstrip()
    for rx, unit, mult in _TAILS:
        if rx.match(rest):
            return Quantity(value=number * mult, unit=unit, currency=currency)
    return None


def to_usd_m(q: Quantity, fx_local_per_usd: float | None) -> float:
    if q.unit != "M":
        raise ValueError(f"expected a money quantity in millions, got unit {q.unit!r}")
    if q.currency in (None, "USD"):
        return q.value
    if fx_local_per_usd is None or fx_local_per_usd <= 0:
        raise ValueError(f"{q.currency} amount needs an FX rate (local per USD) to convert")
    return q.value / fx_local_per_usd


def to_usd_per_t(q: Quantity) -> float:
    if q.unit == "per_lb":
        return q.value * LB_PER_T
    if q.unit == "per_t":
        return q.value
    raise ValueError(f"expected a per-lb or per-tonne price, got unit {q.unit!r}")
