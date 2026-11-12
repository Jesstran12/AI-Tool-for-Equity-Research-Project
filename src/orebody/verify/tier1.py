"""Tier-1 verification: deterministic quote and number matching against the cited page."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from orebody.agents.schemas import Claim
from orebody.core.matcher import entity_on_page, number_match, quote_on_page


class VerifiedClaim(Claim):
    tier1_status: Literal["pass", "fail"]
    tier1_reason: str
    final_status: Literal["verified", "unverified"]


def verify_tier1(claims: list[Claim], read_page: Callable[[int], str]) -> list[VerifiedClaim]:
    """Pass iff the quote is on the page and the value is too: numbers exactly, rounded to their
    printed precision, or rescaled (F3.6, D39); entities by name (case, accents, punctuation)."""
    out: list[VerifiedClaim] = []
    for claim in claims:
        page_text = read_page(claim.page)
        failures: list[str] = []
        if not quote_on_page(page_text, claim.quote):
            failures.append(f"quote not found on page {claim.page}")
        if claim.claim_type == "number" and number_match(page_text, claim.value_orig) is None:
            failures.append(f"number {claim.value_orig!r} not found on page {claim.page}")
        if claim.claim_type == "entity" and not entity_on_page(page_text, claim.value_orig):
            failures.append(f"entity {claim.value_orig!r} not found on page {claim.page}")
        status: Literal["pass", "fail"] = "fail" if failures else "pass"
        out.append(
            VerifiedClaim(
                **claim.model_dump(),
                tier1_status=status,
                tier1_reason="; ".join(failures) if failures else "quote and number on page",
                final_status="verified" if status == "pass" else "unverified",
            )
        )
    return out


def verification_rate(vc: list[VerifiedClaim]) -> float:
    if not vc:
        return 0.0
    return sum(1 for c in vc if c.final_status == "verified") / len(vc)
