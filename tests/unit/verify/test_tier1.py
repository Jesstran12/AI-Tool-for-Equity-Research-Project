import pytest

from orebody.agents.schemas import Claim
from orebody.ingest.extract import read_page
from orebody.verify.tier1 import VerifiedClaim, verification_rate, verify_tier1


def _claim(value_orig: str, page: int, quote: str, field: str = "initial_capex_usd_m") -> Claim:
    return Claim(
        field=field,
        claim_type="number",
        value_orig=value_orig,
        doc_id="fixture_report",
        page=page,
        quote=quote,
    )


@pytest.fixture
def reader(fixture_extracted):
    return lambda n: read_page(fixture_extracted.pages_dir, n)


def test_good_claim_passes(reader) -> None:
    [vc] = verify_tier1(
        [_claim("US$1,240 million", 5, "Initial capital cost is estimated at US$1,240 million.")],
        reader,
    )
    assert vc.tier1_status == "pass"
    assert vc.final_status == "verified"
    assert vc.field == "initial_capex_usd_m"  # Claim fields carried over


def test_quote_not_on_page_fails(reader) -> None:
    [vc] = verify_tier1(
        [_claim("US$1,240 million", 5, "The initial capex is approximately US$1,240 million")],
        reader,
    )
    assert vc.tier1_status == "fail"
    assert "quote" in vc.tier1_reason
    assert vc.final_status == "unverified"


def test_number_not_on_page_fails(reader) -> None:
    [vc] = verify_tier1(
        [_claim("US$1,250 million", 5, "Initial capital cost is estimated at")],
        reader,
    )
    assert vc.tier1_status == "fail"
    assert "number" in vc.tier1_reason


def test_non_number_claim_skips_number_test(reader) -> None:
    c = Claim(
        field="project",
        claim_type="entity",
        value_orig="Fixture Copper Project",
        doc_id="fixture_report",
        page=1,
        quote="Fixture Copper Project NI 43-101 Technical Report",
    )
    [vc] = verify_tier1([c], reader)
    assert vc.tier1_status == "pass"


def test_rate(reader) -> None:
    vcs = verify_tier1(
        [
            _claim("US$1,240 million", 5, "Initial capital cost is estimated at US$1,240 million."),
            _claim("US$310 million", 5, "Sustaining capital totals US$310 million", "sustaining"),
            _claim("US$1,250 million", 5, "Initial capital cost", "wrong"),
        ],
        reader,
    )
    assert isinstance(vcs[0], VerifiedClaim)
    assert verification_rate(vcs) == pytest.approx(0.667, abs=0.001)
    assert verification_rate([]) == 0.0
