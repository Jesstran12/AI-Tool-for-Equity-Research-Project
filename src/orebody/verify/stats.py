"""F6.4 run stats: what `orebody run` prints and stores on the run row. Pure.

verification_rate  verified / total           (tier 1 now; tier 1 or tier 2 once F6.2 exists)
tier1_rate         tier-1 passes / total      (kept separate so tier 2's contribution shows)
unverified_by_section  {section: count}       (only sections with at least one unverified claim)
Rates are 0.0 for a run with no claims.
"""

from __future__ import annotations

from pydantic import BaseModel

from orebody.verify.tier1 import VerifiedClaim


class RunStats(BaseModel):
    total: int
    verified: int
    tier1_pass: int
    verification_rate: float
    tier1_rate: float
    unverified_by_section: dict[int, int]
    cost_usd: float
    seconds: float


def run_stats(
    claims: list[VerifiedClaim], cost_usd: float, seconds: float, section: int = 3
) -> RunStats:
    """`section`: the note section these claims belong to (the Financial Analyst's claims are
    Section 3 until per-claim sections arrive with F5.1)."""
    total = len(claims)
    verified = sum(c.final_status == "verified" for c in claims)
    tier1 = sum(c.tier1_status == "pass" for c in claims)
    unverified = total - verified
    return RunStats(
        total=total,
        verified=verified,
        tier1_pass=tier1,
        verification_rate=verified / total if total else 0.0,
        tier1_rate=tier1 / total if total else 0.0,
        unverified_by_section={section: unverified} if unverified else {},
        cost_usd=cost_usd,
        seconds=seconds,
    )


def stats_line(run_id: str, s: RunStats) -> str:
    """One line, e.g. '<run_id>: verified 9/10 rate=0.90 tier1=0.90 unverified={3: 1}
    cost=US$0.3391 seconds=4.2' (on one line)."""
    return (
        f"{run_id}: verified {s.verified}/{s.total} rate={s.verification_rate:.2f} "
        f"tier1={s.tier1_rate:.2f} unverified={s.unverified_by_section} "
        f"cost=US${s.cost_usd:.4f} seconds={s.seconds:.1f}"
    )
