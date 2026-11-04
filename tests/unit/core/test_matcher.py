import pytest

from orebody.core.matcher import normalize_ws, number_on_page, quote_on_page

PAGE = (
    "21 Capital and Operating Costs\n"
    "Initial capital cost is estimated at US$1,240\n"
    "million.  Sustaining capital totals US$310 million over the life of mine.\n"
    "The project’s C1 cash cost is US$1.85/lb – net of by-products.\n"
    "The IRR is 22.8% and the comparison case shows 11,240 and 22.85.\n"
)


def test_normalize_ws_collapses_and_unifies() -> None:
    assert normalize_ws("  a\n b\t c  ") == "a b c"
    assert normalize_ws("project’s – x") == "project's - x"


def test_quote_found_despite_line_breaks() -> None:
    assert quote_on_page(PAGE, "estimated at US$1,240 million. Sustaining")


def test_quote_is_case_sensitive() -> None:
    assert not quote_on_page(PAGE, "initial capital cost is estimated")


def test_quote_missing() -> None:
    assert not quote_on_page(PAGE, "Initial capital cost is about US$1,240 million")


@pytest.mark.parametrize(
    ("value_orig", "expected"),
    [
        ("US$1,240 million", True),  # test_number_found_with_commas
        ("US$1240 million", True),  # separators stripped on both sides
        ("1,240", True),
        ("US$310 million", True),
        ("US$12 million", False),  # "12" would only be a substring of 1,240 / 11,240
        ("22.8%", True),  # test_number_decimal_precision
        ("22.85", True),
        ("22.9%", False),
        ("US$1.85/lb", True),
        ("US$2,100 million", False),  # test_number_missing
        ("no number", False),
    ],
)
def test_number_on_page(value_orig: str, expected: bool) -> None:
    assert number_on_page(PAGE, value_orig) is expected


def test_number_not_substring() -> None:
    # "1,240" appears in "11,240" but must only match the standalone token.
    assert number_on_page("The figure is 11,240.", "1,240") is False
    assert number_on_page("The figure is 1,240.", "1,240") is True
    assert number_on_page("The figure is 1,2405.", "1,240") is False
