"""F3.2 FX resolution (D14): which rate converts a report's local-currency figures to USD.

Precedence:
  1. USD figures need no rate (identity).
  2. The rate the technical report states (a claim from the Financial Analyst,
     EconInputs.fx_stated_local_per_usd, e.g. Berg PFS "C$1.37 = US$1.00").
  3. config/fx.yaml fallback (usd_per_unit, as_of, source), only if its as_of is on or before
     the run's as-of date (ground rule 5: no rate from the future).
  4. Otherwise an error naming the currency and both remedies. Never a guessed rate.
Every resolution carries its source, so a converted number can show its derivation (ground rule 3).
Pure: no network, no config loading (the caller passes the fallback table in).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

from orebody.config import FxRate


class FxResolution(BaseModel):
    currency: str
    local_per_usd: float
    source: Literal["identity", "report", "config"]
    # e.g. "stated in report (claim c12)" or "config/fx.yaml: Bank of Canada, 2026-11-10"
    detail: str


def resolve_fx(
    currency: str,
    as_of: date,
    stated_local_per_usd: float | None = None,
    stated_claim_id: str | None = None,
    fallback: dict[str, FxRate] | None = None,
) -> FxResolution:
    code = currency.strip().upper()
    if code == "USD":
        return FxResolution(currency=code, local_per_usd=1.0, source="identity", detail="USD")
    if stated_local_per_usd is not None:
        if stated_local_per_usd <= 0:
            raise ValueError(
                f"{code} rate stated in the report must be positive, got {stated_local_per_usd}"
            )
        claim = f" (claim {stated_claim_id})" if stated_claim_id else ""
        return FxResolution(
            currency=code,
            local_per_usd=stated_local_per_usd,
            source="report",
            detail=f"stated in report{claim}",
        )
    rate = (fallback or {}).get(code)
    if rate is not None:
        if rate.as_of > as_of:
            raise ValueError(
                f"{code} rate in config/fx.yaml is dated {rate.as_of}, after as-of {as_of}"
            )
        if rate.usd_per_unit <= 0:
            raise ValueError(f"{code} rate in config/fx.yaml must be positive")
        return FxResolution(
            currency=code,
            local_per_usd=1.0 / rate.usd_per_unit,
            source="config",
            detail=f"config/fx.yaml: {rate.source}, {rate.as_of}",
        )
    raise ValueError(
        f"no {code} rate: the report states none and config/fx.yaml has no {code} entry "
        f"dated on or before {as_of}"
    )


def to_usd(value_local: float, fx: FxResolution) -> float:
    """value_local / local_per_usd."""
    return value_local / fx.local_per_usd
