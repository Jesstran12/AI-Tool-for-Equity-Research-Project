"""F3.1 units: the cases beyond the Phase D slice (test_units.py keeps its 12 rows).
SPEC AC: 40+ parametrized cases incl. "US$1,240 M", "C$1.2 billion", "412 Mt @ 0.48% Cu",
"2.1 Blb", "g/t", "short tons". Each value below is the hand-scaled number."""

import pytest

from orebody.core.units import T_PER_SHORT_TON, parse_quantity, parse_tonnage_grade


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # money: scale words, spacing, currencies
        ("US$1,240 M", (1240, "M", "USD")),
        ("US$1,240M", (1240, "M", "USD")),
        ("USD 587 million", (587, "M", "USD")),
        ("C$ 4.6 billion", (4600, "M", "CAD")),  # 4.6 x 1,000
        ("C$4.6B", (4600, "M", "CAD")),
        ("A$423 million", (423, "M", "AUD")),
        ("US$ 1.2 bn", (1200, "M", "USD")),
        ("US$12.5 thousand", (0.0125, "M", "USD")),  # 12.5 / 1,000
        # negatives: leading minus or accounting parentheses
        ("-US$12.5 million", (-12.5, "M", "USD")),
        ("(US$12.5 million)", (-12.5, "M", "USD")),
        # metal quantities in pounds: "million pounds" is metal, not money (Berg PFS release)
        ("1.2 Mlbs", (1.2e6, "lb", None)),
        ("1,443 Mlb", (1.443e9, "lb", None)),  # 1,443 x 1e6
        ("4.9 billion pounds", (4.9e9, "lb", None)),
        ("89 million pounds", (89e6, "lb", None)),
        # tonnes vs US short tons
        ("15.4 kt", (15400, "t", None)),
        ("100 metric tons", (100, "t", None)),
        ("100 short tons", (90.718474, "t", None)),  # 100 x 0.90718474
        ("100 st", (90.718474, "t", None)),
        ("721,352 tons", (654399.5265684801, "t", None)),  # Lion PFS "LOM Production tons"
        # throughput
        ("60,000 tpd", (60000, "t_per_day", None)),
        ("60 ktpd", (60000, "t_per_day", None)),
        ("120 ktpa", (120000, "t_per_year", None)),
        ("20 Mtpa", (20e6, "t_per_year", None)),
        # grades
        ("0.48% Cu", (0.48, "pct", None)),
        ("1.2 g/t Au", (1.2, "g_t", None)),
        ("14.9 g/t Ag", (14.9, "g_t", None)),
        ("890 ppm Mo", (890, "ppm", None)),
        # precious metal ounces and prices
        ("1.5 Moz", (1.5e6, "oz", None)),
        ("300 koz", (3e5, "oz", None)),
        ("US$45/oz", (45, "per_oz", "USD")),
        ("US$45.00 per ounce", (45, "per_oz", "USD")),
        # unit prices with a trailing qualifier
        ("US$1.92/lb payable", (1.92, "per_lb", "USD")),
        ("US$20.00/lb Mo", (20, "per_lb", "USD")),
        ("US$9,500/t Cu", (9500, "per_t", "USD")),
        ("C$15.30/t milled", (15.30, "per_t", "CAD")),
        ("US$4.25 per pound", (4.25, "per_lb", "USD")),
        # other
        ("2.9 years", (2.9, "years", None)),
        ("24%", (24, "pct", None)),
    ],
)
def test_parse_quantity_f31(text: str, expected: tuple) -> None:
    q = parse_quantity(text)
    assert q is not None, text
    value, unit, currency = expected
    assert q.value == pytest.approx(value)
    assert (q.unit, q.currency) == (unit, currency)


def test_short_ton_factor_is_exact() -> None:
    # 2,000 lb x 0.45359237 kg/lb = 907.18474 kg = 0.90718474 t
    assert T_PER_SHORT_TON == 0.90718474


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("412 Mt @ 0.48% Cu", (412e6, 0.48, "pct", "Cu")),
        ("133.4 Mt at 1.07% Cu", (133.4e6, 1.07, "pct", "Cu")),  # White Pine North indicated
        ("97.2 Mt grading 1.03% copper", (97.2e6, 1.03, "pct", "Cu")),
        ("15.2 Mt @ 1.2 g/t Au", (15.2e6, 1.2, "g_t", "Au")),
        ("2.5 Mt @ 890 ppm Mo", (2.5e6, 890, "ppm", "Mo")),
        ("10 million short tons at 0.35% Cu", (10e6 * 0.90718474, 0.35, "pct", "Cu")),
        ("412 Mt @ 0.48%", (412e6, 0.48, "pct", None)),  # no element named
    ],
)
def test_parse_tonnage_grade(text: str, expected: tuple) -> None:
    tg = parse_tonnage_grade(text)
    assert tg is not None, text
    tonnes, grade, grade_unit, element = expected
    assert tg.tonnes == pytest.approx(tonnes)
    assert tg.grade == pytest.approx(grade)
    assert (tg.grade_unit, tg.element) == (grade_unit, element)


@pytest.mark.parametrize("text", ["412 Mt", "0.48% Cu", "US$4.00/lb", "no numbers"])
def test_parse_tonnage_grade_needs_both_parts(text: str) -> None:
    assert parse_tonnage_grade(text) is None
