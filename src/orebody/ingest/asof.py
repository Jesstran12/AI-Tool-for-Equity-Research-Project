"""F1.3 as-of filter (D15, ground rule 5): a run sees only documents filed on or before its as-of
date. Everything else is excluded and logged with the reason, so a note can be audited for
look-ahead. Pure: no network, no LLM, no clock (the as-of date is passed in).

Rule: include when filing_date <= as_of (a document filed on the as-of date is public that day).
The technical report a run uses is the first one in manifest order that survives the filter
(manifest order lists the current study first), so a newer study filed after as-of makes the run
fall back to the study that was current on the as-of date.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from orebody.ingest.manifest import Document, Manifest


class Exclusion(BaseModel):
    file: str
    type: str
    filing_date: date
    reason: str  # "filed 2026-12-01, after as-of 2026-11-11"


class AsOfResult(BaseModel):
    as_of: date
    included: list[Document]
    excluded: list[Exclusion]


def apply_as_of(manifest: Manifest, as_of: date) -> AsOfResult:
    """Split the manifest's documents; both lists keep manifest order."""
    included = [d for d in manifest.documents if d.filing_date <= as_of]
    excluded = [
        Exclusion(
            file=d.file,
            type=d.type,
            filing_date=d.filing_date,
            reason=f"filed {d.filing_date}, after as-of {as_of}",
        )
        for d in manifest.documents
        if d.filing_date > as_of
    ]
    return AsOfResult(as_of=as_of, included=included, excluded=excluded)


def select_report(result: AsOfResult) -> Document:
    """First technical report among the included documents. ValueError when there is none; the
    message lists any technical reports that were excluded, with their filing dates."""
    for d in result.included:
        if d.type == "technical_report":
            return d
    late = [e for e in result.excluded if e.type == "technical_report"]
    if not late:
        raise ValueError("no technical report in the manifest")
    listed = ", ".join(f"{e.file} (filed {e.filing_date})" for e in late)
    raise ValueError(f"no technical report filed on or before {result.as_of}; excluded: {listed}")


def write_exclusion_log(result: AsOfResult, run_dir: Path) -> Path:
    """Write `<run_dir>/asof.json`: {as_of, included: [file...], excluded: [Exclusion...]}."""
    path = Path(run_dir) / "asof.json"
    path.write_text(json.dumps(_dump(result), indent=2) + "\n")
    return path


def _dump(result: AsOfResult) -> dict:  # used by write_exclusion_log
    return {
        "as_of": result.as_of.isoformat(),
        "included": [d.file for d in result.included],
        "excluded": [json.loads(e.model_dump_json()) for e in result.excluded],
    }
