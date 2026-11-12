"""F3.2 FX resolution. Each expected number is computed by hand in the comment beside it."""

from datetime import date

import pytest

from orebody.config import FxRate
from orebody.core.fx import resolve_fx, to_usd

AS_OF = date(2026, 11, 5)
CAD_CONFIG = {
    "CAD": FxRate(usd_per_unit=0.72, as_of=date(2026, 11, 4), source="Bank of Canada daily rate")
}


def test_usd_needs_no_rate() -> None:
    r = resolve_fx("USD", AS_OF)
    assert (r.local_per_usd, r.source) == (1.0, "identity")
    assert to_usd(709.0, r) == 709.0


def test_report_stated_rate_wins_over_config() -> None:
    # Berg-style: report states C$1.37 per US$1, config says 0.72 USD/CAD (= 1.3889 CAD/USD)
    r = resolve_fx(
        "CAD", AS_OF, stated_local_per_usd=1.37, stated_claim_id="c12", fallback=CAD_CONFIG
    )
    assert (r.local_per_usd, r.source) == (1.37, "report")
    assert "c12" in r.detail
    # C$4,600 M / 1.37 = US$3,357.664 M
    assert to_usd(4600.0, r) == pytest.approx(3357.664, abs=1e-3)


def test_config_fallback_inverts_usd_per_unit() -> None:
    # 0.72 USD per CAD -> 1 / 0.72 = 1.388889 CAD per USD
    r = resolve_fx("CAD", AS_OF, fallback=CAD_CONFIG)
    assert r.source == "config"
    assert r.local_per_usd == pytest.approx(1.388889, abs=1e-6)
    assert "Bank of Canada daily rate" in r.detail and "2026-11-04" in r.detail
    # C$100 M * 0.72 = US$72.000 M
    assert to_usd(100.0, r) == pytest.approx(72.0, abs=1e-9)


def test_config_rate_dated_after_as_of_is_refused() -> None:
    # Ground rule 5: a rate published 2026-11-10 cannot price a note as of 2026-11-05
    late = {"CAD": FxRate(usd_per_unit=0.72, as_of=date(2026, 11, 10), source="BoC")}
    with pytest.raises(ValueError, match="CAD.*2026-11-10.*after as-of 2026-11-05"):
        resolve_fx("CAD", AS_OF, fallback=late)


def test_no_rate_anywhere_is_an_error_naming_both_remedies() -> None:
    with pytest.raises(ValueError, match="CAD") as e:
        resolve_fx("CAD", AS_OF, fallback={})
    assert "report" in str(e.value) and "fx.yaml" in str(e.value)


@pytest.mark.parametrize("bad", [0.0, -1.37])
def test_non_positive_stated_rate_is_an_error(bad: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        resolve_fx("CAD", AS_OF, stated_local_per_usd=bad)


def test_currency_code_is_normalized() -> None:
    # Manifests and claims write "cad" or " CAD "
    assert resolve_fx(" cad ", AS_OF, fallback=CAD_CONFIG).currency == "CAD"


def test_other_currency_does_not_borrow_the_cad_rate() -> None:
    with pytest.raises(ValueError, match="AUD"):
        resolve_fx("AUD", AS_OF, fallback=CAD_CONFIG)
