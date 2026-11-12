"""Parse printed quantities ("US$1,240 million", "US$4.00/lb") into scaled, unit-tagged values."""

from __future__ import annotations

import re
from dataclasses import dataclass

LB_PER_T = 2204.62
T_PER_SHORT_TON = 0.90718474  # exact by definition (2,000 lb x 0.45359237 kg/lb)

# unit ∈ {M, t, pct, per_lb, per_t, years, t_per_year, lb,                 (Phase D)
#         t_per_day, g_t, ppm, oz, per_oz}                                  (F3.1)
# value is already scaled (M = millions of currency). Tonnes are metric; "tons"/"short tons"/"st"
# are US short tons (0.90718474 t each) and are converted, because US-filed reports (Lion) use them.
Unit = str

_NUMBER = re.compile(
    r"(?P<neg>-)?\s*(?P<cur>US\$|USD|C\$|CAD|A\$|AUD|\$)?\s*"
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

_ST = T_PER_SHORT_TON
_LBS = r"(?:pounds?|lbs?)\b"
# (pattern applied at the start of the text following the number, unit, multiplier); order matters:
# longer and more specific tails first ("million pounds" is metal before "million" is money).
_TAILS: list[tuple[re.Pattern[str], Unit, float]] = [
    # throughput
    (re.compile(r"Mtpa\b"), "t_per_year", 1e6),
    (re.compile(r"ktpa\b"), "t_per_year", 1e3),
    (re.compile(r"ktpd\b"), "t_per_day", 1e3),
    (re.compile(r"(?:tpd|t/d|tonnes?\s+per\s+day)\b", re.I), "t_per_day", 1.0),
    (re.compile(r"(?:tpa|t/a|tonnes?\s+per\s+(?:year|annum))\b", re.I), "t_per_year", 1.0),
    # ounces
    (re.compile(r"Moz\b"), "oz", 1e6),
    (re.compile(r"koz\b"), "oz", 1e3),
    (re.compile(r"(?:oz|ounces?)\b", re.I), "oz", 1.0),
    # scale word + mass unit: metal, not money
    (re.compile(r"(?:billion|bn)\s+" + _LBS, re.I), "lb", 1e9),
    (re.compile(r"(?:million|mm)\s+" + _LBS, re.I), "lb", 1e6),
    (re.compile(r"million\s+(?:short\s+tons?|tons?)\b", re.I), "t", 1e6 * _ST),
    (re.compile(r"million\s+(?:tonnes?|metric\s+tons?)\b", re.I), "t", 1e6),
    # tonnes and short tons
    (re.compile(r"Mt\b"), "t", 1e6),
    (re.compile(r"kt\b"), "t", 1e3),
    (re.compile(r"Mlbs?\b"), "lb", 1e6),
    (re.compile(r"Blbs?\b"), "lb", 1e9),
    (re.compile(r"metric\s+tons?\b", re.I), "t", 1.0),
    (re.compile(r"(?:tonnes?|t)\b", re.I), "t", 1.0),
    (re.compile(r"(?:short\s+tons?|st|tons?)\b", re.I), "t", _ST),
    # money scale words
    (re.compile(r"(?:billion|bn)\b", re.I), "M", 1e3),
    (re.compile(r"B\b"), "M", 1e3),
    (re.compile(r"(?:million|mm|m)\b", re.I), "M", 1.0),
    (re.compile(r"(?:thousand|k)\b", re.I), "M", 1e-3),
    # grades
    (re.compile(r"%"), "pct", 1.0),
    (re.compile(r"g/t\b", re.I), "g_t", 1.0),
    (re.compile(r"ppm\b", re.I), "ppm", 1.0),
    # unit prices
    (re.compile(r"(?:/\s*lb|per\s+(?:pound|lb))\b", re.I), "per_lb", 1.0),
    (re.compile(r"(?:/\s*oz|per\s+(?:ounce|oz))\b", re.I), "per_oz", 1.0),
    (re.compile(r"(?:/\s*(?:tonne|t)|per\s+tonne)\b", re.I), "per_t", 1.0),
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
    # accounting negatives: a leading minus, or the whole figure in parentheses "(US$12.5 million)"
    if m.group("neg") or re.match(r"\s*\(", text[: m.start("num")]):
        number = -number
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


@dataclass(frozen=True)
class TonnageGrade:
    """A resource or reserve line: '412 Mt @ 0.48% Cu' -> 412e6 t at 0.48 pct, element 'Cu'."""

    tonnes: float
    grade: float
    grade_unit: Unit  # pct, g_t or ppm
    element: str | None


def parse_tonnage_grade(text: str) -> TonnageGrade | None:
    """Tonnage followed by '@', 'at' or 'grading' and a grade; None when either part is missing."""
    parts = re.split(r"\s*@\s*|\s+(?:at|grading)\s+", text, maxsplit=1)
    if len(parts) != 2:
        return None
    tonnage, grade = parse_quantity(parts[0]), parse_quantity(parts[1])
    if tonnage is None or tonnage.unit != "t" or grade is None:
        return None
    if grade.unit not in ("pct", "g_t", "ppm"):
        return None
    m = _ELEMENT.search(parts[1])
    element = None
    if m:
        token = m.group(0)
        element = _ELEMENT_NAMES.get(token.lower(), token)
    return TonnageGrade(
        tonnes=tonnage.value, grade=grade.value, grade_unit=grade.unit, element=element
    )


_ELEMENT_NAMES = {
    "copper": "Cu",
    "gold": "Au",
    "silver": "Ag",
    "molybdenum": "Mo",
    "zinc": "Zn",
    "nickel": "Ni",
    "lead": "Pb",
    "cobalt": "Co",
}
_ELEMENT = re.compile(
    r"\b(?:Cu|Au|Ag|Mo|Zn|Ni|Pb|Co|"
    r"(?i:copper|gold|silver|molybdenum|zinc|nickel|lead|cobalt))\b"
)
