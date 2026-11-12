"""F3.6 tier-1 matcher: rounding, rescaling and entity names (D39). The 15 exact-match cases stay
in test_matcher.py. Every expected result is reasoned in the comment beside it."""

import pytest

from orebody.core.matcher import entity_on_page, number_match

PAGE = (
    "Table A Financial Evaluation\n"  # no stray numbers: "1.9" would round to 2
    "Post-tax NPV (7%) US$708.6 million; pre-tax US$975 million.\n"
    "Post-tax IRR 22.79%; payback 2.5 years.\n"
    "Initial capital US$1,240 million (sustaining 1,239.7 in the cash flow).\n"
    "Payable copper 4,900 Mlbs over the life of mine; 1,200 kt of concentrate.\n"
    "Comparison case 11,240.\n"
)


@pytest.mark.parametrize(
    ("value_orig", "expected"),
    [
        # exact tokens still win first
        ("US$975 million", "exact"),
        ("22.79%", "exact"),
        # rounded to the claim's printed precision (round half up)
        ("US$709 million", "rounded"),  # 708.6 -> 709
        ("US$708.6 million", "exact"),
        ("US$709.0 million", None),  # claim is more precise than the page: 708.6 != 709.0
        ("22.8%", "rounded"),  # 22.79 -> 22.8
        ("23%", "rounded"),  # 22.79 -> 23
        ("1,240", "exact"),
        ("3 years", "rounded"),  # 2.5 -> 3 (half up)
        ("2 years", None),  # 2.5 does not round to 2 under half-up
        ("US$708 million", None),  # 708.6 -> 709, not 708
        ("US$12 million", None),  # 11,240 is one token; it never rounds to 12
        # rescaled through core/units
        ("US$1.24 billion", "rescaled"),  # = US$1,240 million
        ("US$1.2 billion", "rescaled"),  # 1,240 M = 1.24 B -> 1.2 at one decimal
        ("4.9 billion pounds", "rescaled"),  # = 4,900 Mlbs
        ("1.2 Mt", "rescaled"),  # = 1,200 kt
        ("1.3 Mt", None),
        # a figure that is nowhere on the page
        ("US$2,100 million", None),
        ("no number", None),
    ],
)
def test_number_match(value_orig: str, expected: str | None) -> None:
    assert number_match(PAGE, value_orig) == expected


def test_bare_table_number_does_not_rescale() -> None:
    # A cell "1,240" under a "US$ M" header carries no unit on the page: tier 2's job
    assert number_match("Initial capital | 1,240 | 310", "US$1.24 billion") is None


def test_rounding_ignores_thousands_separators() -> None:
    # "1,239.7" on the page rounds to 1,240
    assert number_match("Sustaining 1,239.7 in total", "1,240") == "rounded"


@pytest.mark.parametrize(
    ("entity", "page", "expected"),
    [
        ("Marimaca Copper Corp.", "issued by Marimaca Copper Corp under", True),
        ("Royal Gold, Inc.", "a stream held by ROYAL GOLD INC. on", True),
        ("Carlos Guzmán", "prepared by Carlos Guzman, FAusIMM", True),
        ("Ausenco Engineering Canada ULC", "Ausenco  Engineering\nCanada ULC (Ausenco)", True),
        ("Rio Tinto", "funded by Rio Tinto's Nuton venture", True),
        ("Nuton LLC", "Nuton, LLC, a subsidiary", True),
        ("Moose Mountain Technical Services", "Moose Mountai\nn Technical Services", True),
        ("Teck", "the Teckton claims", False),
        ("Gunnison Copper", "Gunnison is a town in Colorado", False),
        ("Kinterra", "no such name here", False),
    ],
)
def test_entity_on_page(entity: str, page: str, expected: bool) -> None:
    assert entity_on_page(page, entity) is expected
