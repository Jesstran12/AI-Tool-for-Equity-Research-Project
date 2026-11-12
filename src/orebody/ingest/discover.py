"""F1.5 discovery: find candidate mining projects with an accessible technical report.

Sources (SPEC §10.2): EDGAR full-text search for S-K 1300 technical report summaries (Ex. 96),
EDGAR company submissions for the SIC code, and a hand-kept candidates file for SEDAR+-only names.
Every candidate is kept in the output; excluded ones carry the reason (SPEC D47).

Network access goes through an injected `fetch(url) -> bytes`, so tests replay recorded responses.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

import yaml
from pydantic import BaseModel

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}"
MINING_SIC = frozenset({"1000", "1040", "1090"})  # metal mining; gold/silver ores; misc metal ores

Fetch = Callable[[str], bytes]


class Hit(BaseModel):
    """One EDGAR full-text search hit for a technical report exhibit."""

    cik: str  # 10-digit, zero-padded
    company: str
    form: str
    file_type: str
    file_date: date
    description: str
    url: str  # full sec.gov Archives URL of the exhibit
    ticker: str = ""
    sic: str = ""  # from the hit's `sics` field when EDGAR returns it


class Candidate(BaseModel):
    company: str
    ticker: str = ""
    exchange: str = ""
    cik: str = ""
    project: str = ""
    source: Literal["edgar", "manual"]
    source_url: str = ""
    report_found: bool
    report_filed: date | None = None
    included: bool
    exclusion_reason: str | None = None


# EDGAR full-text search ignores exhibit-type filters, so search the phrase S-K 1300 requires on
# the cover ("technical report summary"), keep EX-96* hits client-side, and page through results.
SEARCH_PHRASE = "technical report summary"
PAGE_SIZE = 100
MAX_PAGES = 20

_DISPLAY = re.compile(r"^(?P<name>.*?)\s+\((?P<tickers>[^()]*)\)\s+\(CIK \d+\)\s*$")


def _parse_display(display: str) -> tuple[str, str]:
    """'Fixture Copper Corp  (FXC)  (CIK 0000000001)' -> ('Fixture Copper Corp', 'FXC')."""
    m = _DISPLAY.match(display)
    if not m:
        return re.sub(r"\s+\(CIK \d+\)\s*$", "", display).strip(), ""
    return m.group("name").strip(), m.group("tickers").split(",")[0].strip()


class EdgarClient:
    def __init__(self, fetch: Fetch) -> None:
        self.fetch = fetch

    def search_technical_reports(self, query: str = "copper") -> list[Hit]:
        """Full-text search for Ex. 96 technical report summaries mentioning `query`."""
        hits: dict[str, Hit] = {}
        for page in range(MAX_PAGES):
            params = {"q": f'"{query}" "{SEARCH_PHRASE}"'}
            if page:
                params["from"] = str(page * PAGE_SIZE)
            data = json.loads(self.fetch(f"{EFTS_URL}?{urlencode(params)}"))
            batch = data["hits"]["hits"]
            new = 0
            for h in batch:
                src = h["_source"]
                if not src.get("file_type", "").startswith("EX-96") or h["_id"] in hits:
                    continue
                cik = src["ciks"][0]
                name, ticker = _parse_display(src["display_names"][0])
                hits[h["_id"]] = Hit(
                    cik=cik,
                    company=name,
                    form=src["form"],
                    file_type=src["file_type"],
                    file_date=date.fromisoformat(src["file_date"]),
                    description=src.get("file_description") or "",
                    url=exhibit_url(cik, h["_id"]),
                    ticker=ticker,
                    sic=(src.get("sics") or [""])[0],
                )
                new += 1
            total = data["hits"]["total"]["value"]
            if not new or (page + 1) * PAGE_SIZE >= total:
                break
        return list(hits.values())

    def company_hits(self, cik: str) -> list[Hit]:
        """Every filing the company has on EDGAR (main documents, from its submissions record)
        plus its technical report exhibits (EX-96/EX-99, from full-text search by CIK)."""
        sub = json.loads(self.fetch(SUBMISSIONS_URL.format(cik=cik)))
        name = sub.get("name", "")
        ticker = (sub.get("tickers") or [""])[0]
        sic = str(sub.get("sic", ""))
        r = sub.get("filings", {}).get("recent", {})
        hits = [
            Hit(
                cik=cik,
                company=name,
                form=form,
                file_type=form,
                file_date=date.fromisoformat(filed),
                description=desc or form,
                url=exhibit_url(cik, f"{acc}:{doc}"),
                ticker=ticker,
                sic=sic,
            )
            for form, filed, acc, doc, desc in zip(
                r.get("form", []),
                r.get("filingDate", []),
                r.get("accessionNumber", []),
                r.get("primaryDocument", []),
                r.get("primaryDocDescription", []),
                strict=True,
            )
        ]
        # S-K 1300 summaries say "technical report summary"; NI 43-101 reports filed as 40-F/6-K
        # exhibits only say "technical report" (Gunnison, 2026-11-11).
        seen: set[str] = set()
        for phrase in (SEARCH_PHRASE, "technical report"):
            params = {"q": f'"{phrase}"', "ciks": cik}
            data = json.loads(self.fetch(f"{EFTS_URL}?{urlencode(params)}"))
            for h in data["hits"]["hits"]:
                src = h["_source"]
                if h["_id"] in seen or not src.get("file_type", "").startswith(("EX-96", "EX-99")):
                    continue
                seen.add(h["_id"])
                hits.append(
                    Hit(
                        cik=cik,
                        company=name,
                        form=src["form"],
                        file_type=src["file_type"],
                        file_date=date.fromisoformat(src["file_date"]),
                        description=src.get("file_description") or "",
                        url=exhibit_url(cik, h["_id"]),
                        ticker=ticker,
                        sic=sic,
                    )
                )
        return hits

    def company_sic(self, cik: str) -> tuple[str, str]:
        """(SIC code, SIC description) from the company's submissions record."""
        data = json.loads(self.fetch(SUBMISSIONS_URL.format(cik=cik)))
        return str(data.get("sic", "")), data.get("sicDescription", "")


def exhibit_url(cik: str, hit_id: str) -> str:
    """Build the Archives URL from a 10-digit CIK and an efts `_id` ("accession:filename")."""
    accession, filename = hit_id.split(":", 1)
    return ARCHIVE_URL.format(cik=int(cik), accession=accession.replace("-", ""), filename=filename)


def load_manual_candidates(path: Path, as_of: date) -> list[Candidate]:
    """Read config/candidates.yaml; a candidate without a report_url is excluded."""
    rows = (yaml.safe_load(Path(path).read_text()) or {}).get("candidates") or []
    out = []
    for r in rows:
        url = r.get("report_url") or ""
        filed = r.get("report_filed")
        reason = None
        if not url:
            reason = "no technical report found"
        elif filed and filed > as_of:
            reason = f"technical report filed {filed} is after as-of {as_of}"
        out.append(
            Candidate(
                company=r["company"],
                ticker=r.get("ticker", ""),
                exchange=r.get("exchange", ""),
                project=r.get("project", ""),
                source="manual",
                source_url=url,
                report_found=bool(url),
                report_filed=filed,
                included=reason is None,
                exclusion_reason=reason,
            )
        )
    return out


def discover(client: EdgarClient, manual_path: Path | None, as_of: date) -> list[Candidate]:
    """EDGAR hits grouped to one candidate per company (latest report on or before as_of),
    plus manual candidates. Exclusion reasons: not a mining filer (SIC), no report filed on or
    before as-of, no report found."""
    by_cik: dict[str, list[Hit]] = {}
    for h in client.search_technical_reports():
        by_cik.setdefault(h.cik, []).append(h)
    out = []
    for cik, hits in by_cik.items():
        first = hits[0]
        sic, sic_desc = (first.sic, "") if first.sic else client.company_sic(cik)
        filed = [h for h in hits if h.file_date <= as_of]
        latest = max(filed, key=lambda h: h.file_date) if filed else None
        reason = None
        if sic not in MINING_SIC:
            reason = f"not a mining filer (SIC {sic}{' ' + sic_desc if sic_desc else ''})"
        elif latest is None:
            reason = f"no technical report filed on or before as-of {as_of}"
        out.append(
            Candidate(
                company=first.company,
                ticker=first.ticker,
                cik=cik,
                project=latest.description if latest else "",
                source="edgar",
                source_url=latest.url if latest else "",
                report_found=latest is not None,
                report_filed=latest.file_date if latest else None,
                included=reason is None,
                exclusion_reason=reason,
            )
        )
    if manual_path is not None:
        out += load_manual_candidates(manual_path, as_of)
    return out


def write_candidates(candidates: list[Candidate], path: Path) -> None:
    """Write candidates as JSON (sorted: included first, then by company)."""
    rows = sorted(candidates, key=lambda c: (not c.included, c.company.lower()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([c.model_dump(mode="json") for c in rows], indent=2) + "\n")


MIN_INTERVAL_S = 0.15  # stays under the SEC's 10 requests/second
RETRIES = 3


def user_agent() -> str:
    """SEC fair-access policy: the User-Agent must name the requester and give a contact email.
    www.sec.gov/Archives returns 403 without one (checked 2026-11-11)."""
    import os

    contact = os.environ.get("OREBODY_SEC_CONTACT", "").strip()
    if "@" not in contact:
        raise RuntimeError(
            "Set OREBODY_SEC_CONTACT in .env to a contact email for SEC requests "
            "(SEC fair-access policy; www.sec.gov rejects requests without one)."
        )
    return f"orebody-research {contact}"


def http_fetch(url: str) -> bytes:  # pragma: no cover - network
    """Live fetch for the CLI: SEC-compliant User-Agent, rate-limited, retried."""
    import time
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    for attempt in range(RETRIES):
        elapsed = time.monotonic() - _last_call[0]
        if elapsed < MIN_INTERVAL_S:
            time.sleep(MIN_INTERVAL_S - elapsed)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except (urllib.error.URLError, ConnectionError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code in (403, 404):
                raise
            if attempt == RETRIES - 1:
                raise
            time.sleep(2**attempt)
        finally:
            _last_call[0] = time.monotonic()
    raise AssertionError("unreachable")


_last_call = [0.0]
