import pytest

from orebody.core.units import LB_PER_T, Quantity, parse_quantity, to_usd_m, to_usd_per_t


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("US$1,240 million", (1240, "M", "USD")),
        ("C$1.2 billion", (1200, "M", "CAD")),
        ("$709 million", (709, "M", "USD")),
        ("412 Mt", (412e6, "t", None)),
        ("0.48%", (0.48, "pct", None)),
        ("2.1 Blb", (2.1e9, "lb", None)),
        ("US$4.00/lb", (4.0, "per_lb", "USD")),
        ("US$1.85/lb", (1.85, "per_lb", "USD")),
        ("50,000 tonnes per year", (50000, "t_per_year", None)),
        ("18 years", (18, "years", None)),
        ("US$8,800/t", (8800, "per_t", "USD")),
        ("no number here", None),
    ],
)
def test_parse_quantity(text: str, expected: tuple | None) -> None:
    q = parse_quantity(text)
    if expected is None:
        assert q is None
    else:
        assert q is not None
        value, unit, currency = expected
        assert q.value == pytest.approx(value)
        assert q.unit == unit
        assert q.currency == currency


def test_to_usd_m_with_fx() -> None:
    # 1200 M CAD / 1.35 CAD per USD = 888.89 M USD
    assert to_usd_m(Quantity(1200, "M", "CAD"), 1.35) == pytest.approx(888.89, abs=0.01)


def test_to_usd_m_usd_ignores_fx() -> None:
    assert to_usd_m(Quantity(709, "M", "USD"), None) == 709


def test_to_usd_m_cad_without_fx_raises() -> None:
    with pytest.raises(ValueError):
        to_usd_m(Quantity(1200, "M", "CAD"), None)


def test_usd_per_lb_to_per_t() -> None:
    # 4.00 USD/lb × 2204.62 lb/t = 8818.48 USD/t
    assert LB_PER_T == 2204.62
    assert to_usd_per_t(Quantity(4.0, "per_lb", "USD")) == pytest.approx(8818.48, abs=0.01)
    assert to_usd_per_t(Quantity(8800, "per_t", "USD")) == 8800
