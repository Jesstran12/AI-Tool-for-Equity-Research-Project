"""F6.4 run stats (pure). Counts worked by hand in the comments."""

import pytest

from orebody.verify.stats import run_stats, stats_line
from orebody.verify.tier1 import VerifiedClaim


def _vc(ok: bool, field: str = "x") -> VerifiedClaim:
    return VerifiedClaim(
        field=field,
        claim_type="number",
        value_orig="1",
        doc_id="d",
        page=1,
        quote="q",
        tier1_status="pass" if ok else "fail",
        tier1_reason="",
        final_status="verified" if ok else "unverified",
    )


def test_counts_and_rates() -> None:
    # 4 claims, 3 pass tier 1 -> verified 3/4 = 0.75; the failure is in Section 3
    s = run_stats([_vc(True), _vc(True), _vc(False), _vc(True)], cost_usd=0.3391, seconds=4.24)
    assert (s.total, s.verified, s.tier1_pass) == (4, 3, 3)
    assert s.verification_rate == pytest.approx(0.75)
    assert s.tier1_rate == pytest.approx(0.75)
    assert s.unverified_by_section == {3: 1}
    assert (s.cost_usd, s.seconds) == (0.3391, 4.24)


def test_all_verified_has_no_unverified_sections() -> None:
    s = run_stats([_vc(True)] * 10, cost_usd=0.0, seconds=0.1)
    assert s.unverified_by_section == {} and s.verification_rate == 1.0


def test_empty_run_has_zero_rates() -> None:
    s = run_stats([], cost_usd=0.0, seconds=0.0)
    assert (s.total, s.verification_rate, s.tier1_rate) == (0, 0.0, 0.0)


def test_section_argument_is_used() -> None:
    assert run_stats([_vc(False)], 0.0, 0.0, section=2).unverified_by_section == {2: 1}


def test_stats_line() -> None:
    s = run_stats([_vc(True)] * 9 + [_vc(False)], cost_usd=0.33914, seconds=4.24)
    assert stats_line("MARI-2026-11-05-104923", s) == (
        "MARI-2026-11-05-104923: verified 9/10 rate=0.90 tier1=0.90 unverified={3: 1} "
        "cost=US$0.3391 seconds=4.2"
    )
