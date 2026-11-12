"""F1.8 cross-check, retrieval part: find the EDGAR copy of a document collected elsewhere.

Matching rules (on EDGAR full-text search hits for the company's CIK):
- technical_report  -> EX-96* or EX-99* hit whose description names the manifest's project,
                       filed on or after the report's effective date; the earliest such hit wins.
- annual_financials / aif / mdna (annual) -> 10-K, 20-F or 40-F (or their exhibits) filed
                       within 180 days after effective_date.
- quarterly_financials / mdna (interim) -> 10-Q or 6-K filed within 90 days after effective_date.
Anything else (news, presentations) has no alternate.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from orebody.core.crosscheck import MIN_OVERLAP, compare, effective_date_in
from orebody.core.matcher import normalize_ws
from orebody.ingest.discover import EdgarClient, Hit
from orebody.ingest.manifest import Document, load_manifest


class AltSource(BaseModel):
    url: str
    form: str
    file_type: str
    file_date: date


ANNUAL_FORMS = frozenset({"10-K", "20-F", "40-F"})
INTERIM_FORMS = frozenset({"10-Q", "6-K"})
ANNUAL_WINDOW_DAYS = 180
INTERIM_WINDOW_DAYS = 90


def _within(h: Hit, start: date, days: int) -> bool:
    return 0 <= (h.file_date - start).days <= days


def _first(hits: list[Hit]) -> AltSource | None:
    if not hits:
        return None
    h = min(hits, key=lambda h: h.file_date)
    return AltSource(url=h.url, form=h.form, file_type=h.file_type, file_date=h.file_date)


def find_edgar_alternate(doc: Document, hits: list[Hit]) -> AltSource | None:
    eff = doc.effective_date
    if eff is None:
        return None
    if doc.type == "technical_report":
        project = doc.project.lower().strip()
        if not project:
            return None
        return _first(
            [
                h
                for h in hits
                if h.file_type.startswith(("EX-96", "EX-99"))
                and project in h.description.lower()
                and h.file_date >= eff
            ]
        )
    annual = [h for h in hits if h.form in ANNUAL_FORMS and _within(h, eff, ANNUAL_WINDOW_DAYS)]
    interim = [h for h in hits if h.form in INTERIM_FORMS and _within(h, eff, INTERIM_WINDOW_DAYS)]
    if doc.type in ("annual_financials", "aif"):
        return _first(annual)
    if doc.type == "quarterly_financials":
        return _first(interim)
    if doc.type == "mdna":
        return _first(annual) or _first(interim)
    return None


_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def document_text(path: Path) -> str:
    """Plain text of a PDF (PyMuPDF, all pages) or an HTML exhibit (tags stripped, entities
    unescaped, whitespace collapsed)."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        import pymupdf

        with pymupdf.open(path) as pdf:
            return "\n".join(page.get_text() for page in pdf)
    raw = path.read_text(errors="ignore")
    text = html.unescape(_TAG.sub(" ", _SCRIPT.sub(" ", raw)))
    return normalize_ws(text)


MAX_CONTENT_CANDIDATES = 6
CONTENT_WINDOW_DAYS = 730


def technical_report_candidates(doc: Document, hits: list[Hit]) -> list[Hit]:
    """EX-96/EX-99 exhibits filed within two years after the report's effective date, oldest
    first. Used when EDGAR's exhibit description is generic ('EXHIBIT 99.1') and names no
    project."""
    if doc.effective_date is None:
        return []
    found = [
        h
        for h in hits
        if h.file_type.startswith(("EX-96", "EX-99"))
        and _within(h, doc.effective_date, CONTENT_WINDOW_DAYS)
    ]
    return sorted(found, key=lambda h: h.file_date)[:MAX_CONTENT_CANDIDATES]


def _alt_path(folder: Path, url: str, client: EdgarClient) -> Path:
    path = folder / "alt" / url.rstrip("/").rsplit("/", 1)[1]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(client.fetch(url))
    return path


def crosscheck_folder(folder: Path, client: EdgarClient) -> list[dict]:
    """Cross-check every document in a drop folder against its EDGAR copy.

    Alternates are cached under `<folder>/alt/`; results go to `<folder>/crosscheck.json`
    (a sidecar, so the hand-commented manifest is never rewritten). Status per document:
    identical | consistent | differs | same_source | no_alternate. Technical reports are matched
    by project name when EDGAR describes the exhibit, otherwise by content (best numeric overlap,
    accepted only at >= MIN_OVERLAP, so a content match cannot report `differs`; key figures
    from the claims ledger (F5.x) do the fine check). No key figures yet.
    """
    folder = Path(folder)
    manifest = load_manifest(folder / "manifest.yaml")
    hits = client.company_hits(manifest.cik) if manifest.cik else []
    rows: list[dict] = []
    for doc in manifest.documents:
        row: dict = {"file": doc.file, "type": doc.type, "status": "no_alternate"}
        rows.append(row)
        if not manifest.cik:
            row["note"] = "no CIK in manifest"
            continue
        if "sec.gov/Archives/" in doc.url:
            row |= {
                "status": "same_source",
                "alt_url": doc.url,
                "note": "the collected file was downloaded from EDGAR; no independent copy",
            }
            continue
        alt = find_edgar_alternate(doc, hits)
        matched_by = "metadata"
        primary = document_text(folder / doc.file) if doc.type != "news_release" else ""
        if alt is None and doc.type == "technical_report":
            best = None
            other_versions = []
            for h in technical_report_candidates(doc, hits):
                alt_text = document_text(_alt_path(folder, h.url, client))
                stated = effective_date_in(alt_text)
                if stated is not None and stated != doc.effective_date:
                    other_versions.append(f"{h.url.rsplit('/', 1)[1]} ({stated})")
                    continue
                r = compare(primary, alt_text, [])
                if best is None or r.number_overlap > best[1].number_overlap:
                    best = (h, r)
            if best is None and other_versions:
                row["note"] = (
                    f"EDGAR exhibits state a different effective date than {doc.effective_date}: "
                    + ", ".join(other_versions)
                )
                continue
            if best and best[1].number_overlap >= MIN_OVERLAP:
                h = best[0]
                alt = AltSource(
                    url=h.url, form=h.form, file_type=h.file_type, file_date=h.file_date
                )
                matched_by = "content"
            elif best:
                row["note"] = (
                    "no EDGAR exhibit matched by content "
                    f"(best overlap {best[1].number_overlap:.2f})"
                )
                continue
        if alt is None:
            row.setdefault("note", "no matching EDGAR filing")
            continue
        if doc.url and doc.url == alt.url:
            row |= {
                "status": "same_source",
                "alt_url": alt.url,
                "note": "the collected file was downloaded from EDGAR; no independent copy",
            }
            continue
        alt_path = _alt_path(folder, alt.url, client)
        result = compare(primary, document_text(alt_path), [])
        row |= {
            "alt_url": alt.url,
            "alt_form": alt.form,
            "alt_file_date": alt.file_date.isoformat(),
            "alt_sha256": hashlib.sha256(alt_path.read_bytes()).hexdigest(),
            "matched_by": matched_by,
        } | result.model_dump()
    (folder / "crosscheck.json").write_text(json.dumps(rows, indent=2) + "\n")
    return rows
