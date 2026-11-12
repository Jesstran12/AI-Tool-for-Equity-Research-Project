"""F1.8 pure comparison. Hand-built texts; expected results stated per case."""

from datetime import date

import pytest

from orebody.core.crosscheck import MIN_OVERLAP, compare, effective_date_in, numbers_in

# Primary: 6 distinct numbers {20, 369, 975, 694, 16.9, 14.6}
PRIMARY = "Page 20 of 369. NPV (7%) $975 pre-tax, $694 post-tax. IRR 16.9% / 14.6%."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("NPV US$694 M", {"694": 1}),
        ("Payable 1,443 Mlbs and 1,443 again", {"1443": 2}),  # thousands separator removed
        ("IRR 14.6%", {"14.6": 1}),
        ("721,352 tons", {"721352": 1}),
        ("no numbers here", {}),
        ("Item 22.1 Economic Analysis", {"22.1": 1}),
    ],
)
def test_numbers_in(text: str, expected: dict[str, int]) -> None:
    assert dict(numbers_in(text)) == expected


def test_identical_after_whitespace_normalization() -> None:
    r = compare(PRIMARY, PRIMARY.replace(" ", "\n  "), ["694"])
    assert r.status == "identical"


def test_consistent_when_layout_differs_but_numbers_agree() -> None:
    # Same six numbers, different words and order (HTML exhibit vs PDF): overlap 6/6 = 1.0
    alt = "IRR: 14.6% post / 16.9% pre. NPV7: 694 post, 975 pre. (page 20 of 369)"
    r = compare(PRIMARY, alt, ["694", "14.6"])
    assert r.status == "consistent"
    assert r.key_found_in_both == ["694", "14.6"]
    assert r.number_overlap == 1.0


def test_differs_when_a_key_figure_is_missing_from_the_alternate() -> None:
    # Alternate states NPV 649 (transposed digits): key 694 missing even though overlap is 5/6
    alt = "Page 20 of 369. NPV (7%) $975 pre-tax, $649 post-tax. IRR 16.9% / 14.6%."
    r = compare(PRIMARY, alt, ["694"])
    assert r.status == "differs"
    assert r.key_missing_in_alternate == ["694"]
    assert "694" in r.only_in_primary and "649" in r.only_in_alternate


def test_key_missing_in_primary_is_reported() -> None:
    r = compare(PRIMARY, PRIMARY + " Payback 6.7 years", ["6.7"])
    assert r.status == "differs"
    assert r.key_missing_in_primary == ["6.7"]


def test_differs_when_overlap_below_threshold_even_with_keys_present() -> None:
    # Primary distinct numbers: 694 + 1..19 = 20; alternate shares only 694 and 1: overlap 2/20
    primary = "694 " + " ".join(str(n) for n in range(1, 20))
    alt = "694 1 500 501 502"
    r = compare(primary, alt, ["694"])
    assert r.number_overlap == pytest.approx(2 / 20)
    assert r.number_overlap < MIN_OVERLAP
    assert r.status == "differs"


def test_key_figures_are_normalized_like_the_text() -> None:
    # "1,443" as a key matches "1443" in the text and vice versa
    r = compare("Payable 1,443 Mlbs", "Payable 1443 Mlbs", ["1,443"])
    assert r.status == "consistent"


# Real-data lesson (Gunnison, 2026-11-11): the 2025 and 2026 Johnson Camp reports share 92% of
# their numbers, so numeric overlap alone matched the wrong version. The stated effective date
# tells them apart.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The effective date of this technical report is March 18, 2026.", date(2026, 3, 18)),
        ("Effective Date:\nMarch 12, 2025\nIssue Date:\nMarch 31, 2025", date(2025, 3, 12)),
        ("Effective Date: 12 June 2026", date(2026, 6, 12)),
        ("with an effective date of May 31, 2025.", date(2025, 5, 31)),
        ("The report has no date statement.", None),
    ],
)
def test_effective_date_in(text: str, expected: date | None) -> None:
    assert effective_date_in(text) == expected
