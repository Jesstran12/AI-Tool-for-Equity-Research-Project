"""F1.5 discovery. Fixtures in tests/fixtures/edgar/ are synthetic, shaped like EDGAR responses:

- CIK 1 Fixture Copper Corp: SIC 1000 (metal mining), two Ex. 96 hits (2025-03-26, 2026-03-30)
- CIK 2 Copper Lane REIT: SIC 6798, an Ex. 96 hit that mentions copper -> not a mining filer
- CIK 3 Late Filer Mining: SIC 1090, only hit filed 2026-12-01 -> after the as-of date
- candidates.yaml: Sedar Only Copper (report found), No Report Resources (no report_url)
"""

import json
import os
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from orebody.ingest.discover import (
    Candidate,
    EdgarClient,
    discover,
    exhibit_url,
    load_manual_candidates,
    write_candidates,
)

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "edgar"
AS_OF = date(2026, 11, 11)


class RecordedFetch:
    """Replays fixture files by URL and records every URL requested."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        parsed = urlparse(url)
        if parsed.netloc == "efts.sec.gov":
            return (FIX / "efts_copper_ex96.json").read_bytes()
        if parsed.netloc == "data.sec.gov":
            cik = parsed.path.rsplit("CIK", 1)[1].removesuffix(".json")
            return (FIX / f"submissions_{cik}.json").read_bytes()
        raise AssertionError(f"unexpected URL in test: {url}")


@pytest.fixture
def fetch() -> RecordedFetch:
    return RecordedFetch()


@pytest.fixture
def client(fetch: RecordedFetch) -> EdgarClient:
    return EdgarClient(fetch)


def _by_company(cands: list[Candidate]) -> dict[str, Candidate]:
    return {c.company: c for c in cands}


# --- EdgarClient -----------------------------------------------------------------------------


def test_search_parses_every_hit(client: EdgarClient) -> None:
    hits = client.search_technical_reports("copper")
    assert len(hits) == 4
    first = hits[0]
    assert first.cik == "0000000001"
    assert first.company == "Fixture Copper Corp"  # ticker/CIK suffix stripped from display name
    assert first.form == "10-K"
    assert first.file_type == "EX-96.1"
    assert first.file_date == date(2026, 3, 30)


def test_search_uses_the_sk1300_phrase_and_keeps_only_ex96(
    client: EdgarClient, fetch: RecordedFetch
) -> None:
    # EDGAR full-text search ignores exhibit-type filters (checked live 2026-11-11:
    # file_type=EX-96.1 returned 6 EX-96 in 100 hits), so the client searches the phrase S-K 1300
    # puts on every
    # summary and drops non-EX-96 hits itself. The fixture has 5 hits, one of them a 10-K body.
    hits = client.search_technical_reports("copper")
    qs = parse_qs(urlparse(fetch.urls[0]).query)
    assert '"copper"' in qs["q"][0] and '"technical report summary"' in qs["q"][0]
    assert len(hits) == 4
    assert all(h.file_type.startswith("EX-96") for h in hits)


def test_company_sic(client: EdgarClient, fetch: RecordedFetch) -> None:
    assert client.company_sic("0000000001") == ("1000", "Metal Mining")
    assert fetch.urls[-1] == "https://data.sec.gov/submissions/CIK0000000001.json"


@pytest.mark.parametrize(
    ("cik", "hit_id", "expected"),
    [
        # CIK loses its leading zeros, accession loses its dashes
        (
            "0000000001",
            "0000000001-26-000010:ex96-1.htm",
            "https://www.sec.gov/Archives/edgar/data/1/000000000126000010/ex96-1.htm",
        ),
        # real Lion Copper exhibit (CIK 1339688), checked by hand on 2026-11-11
        (
            "0001339688",
            "0001062993-25-006322:exhibit96-1.htm",
            "https://www.sec.gov/Archives/edgar/data/1339688/000106299325006322/exhibit96-1.htm",
        ),
    ],
)
def test_exhibit_url(cik: str, hit_id: str, expected: str) -> None:
    assert exhibit_url(cik, hit_id) == expected


# --- discover --------------------------------------------------------------------------------


def test_mining_filer_is_included_with_latest_report(client: EdgarClient) -> None:
    c = _by_company(discover(client, None, AS_OF))["Fixture Copper Corp"]
    assert c.included and c.exclusion_reason is None
    assert c.source == "edgar"
    assert c.cik == "0000000001"
    assert c.ticker == "FXC"
    assert c.report_found
    assert c.report_filed == date(2026, 3, 30)  # latest of 2025-03-26 and 2026-03-30
    assert c.source_url.endswith("/000000000126000010/ex96-1.htm")


def test_one_candidate_per_company(client: EdgarClient) -> None:
    names = [c.company for c in discover(client, None, AS_OF)]
    assert names.count("Fixture Copper Corp") == 1  # two hits, one candidate


def test_non_mining_filer_is_excluded_with_reason(client: EdgarClient) -> None:
    c = _by_company(discover(client, None, AS_OF))["Copper Lane REIT Inc"]
    assert not c.included
    assert "SIC 6798" in c.exclusion_reason


def test_report_after_as_of_is_excluded(client: EdgarClient) -> None:
    c = _by_company(discover(client, None, AS_OF))["Late Filer Mining Ltd"]
    assert not c.included
    assert "as-of" in c.exclusion_reason


def test_report_after_as_of_counts_once_as_of_moves(client: EdgarClient) -> None:
    c = _by_company(discover(client, None, date(2026, 12, 31)))["Late Filer Mining Ltd"]
    assert c.included
    assert c.report_filed == date(2026, 12, 1)


def test_as_of_picks_the_earlier_report(client: EdgarClient) -> None:
    c = _by_company(discover(client, None, date(2025, 12, 31)))["Fixture Copper Corp"]
    assert c.included
    assert c.report_filed == date(2025, 3, 26)  # the 2026-03-30 report is not yet filed


def test_every_excluded_candidate_has_a_reason_and_source(client: EdgarClient) -> None:
    cands = discover(client, FIX / "candidates.yaml", AS_OF)
    assert len(cands) == 5  # 3 EDGAR companies + 2 manual
    for c in cands:
        assert c.included or c.exclusion_reason
        assert c.source in ("edgar", "manual")


# --- manual candidates -----------------------------------------------------------------------


def test_manual_candidate_with_report_is_included() -> None:
    c = _by_company(load_manual_candidates(FIX / "candidates.yaml", AS_OF))[
        "Sedar Only Copper Inc."
    ]
    assert c.included and c.report_found
    assert c.source == "manual"
    assert c.source_url == "https://example.com/north-hill-ni43-101.pdf"
    assert c.report_filed == date(2026, 5, 1)


def test_manual_candidate_without_report_is_excluded() -> None:
    c = _by_company(load_manual_candidates(FIX / "candidates.yaml", AS_OF))[
        "No Report Resources Ltd."
    ]
    assert not c.included and not c.report_found
    assert c.exclusion_reason == "no technical report found"


def test_manual_report_after_as_of_is_excluded() -> None:
    c = _by_company(load_manual_candidates(FIX / "candidates.yaml", date(2026, 4, 30)))[
        "Sedar Only Copper Inc."
    ]
    assert not c.included
    assert "as-of" in c.exclusion_reason


# --- output ----------------------------------------------------------------------------------


def test_write_candidates_round_trips_included_first(client: EdgarClient, tmp_path: Path) -> None:
    out = tmp_path / "universe" / "candidates.json"
    write_candidates(discover(client, FIX / "candidates.yaml", AS_OF), out)
    rows = json.loads(out.read_text())
    assert [r["included"] for r in rows] == sorted((r["included"] for r in rows), reverse=True)
    assert {r["company"] for r in rows} >= {"Fixture Copper Corp", "No Report Resources Ltd."}
    Candidate.model_validate(rows[0])


def test_no_network_outside_injected_fetch(client: EdgarClient, fetch: RecordedFetch) -> None:
    discover(client, FIX / "candidates.yaml", AS_OF)
    hosts = {urlparse(u).netloc for u in fetch.urls}
    assert hosts <= {"efts.sec.gov", "data.sec.gov"}
    # one SIC lookup per company, not per hit
    assert sum("data.sec.gov" in u for u in fetch.urls) == 3


# --- real EDGAR response (recorded 2026-11-11, trimmed; search metadata only) ----------------

REAL = FIX / "efts_real_copper_trs_2026-11-11.json"


class RealFetch(RecordedFetch):
    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        if urlparse(url).netloc == "efts.sec.gov":
            return REAL.read_bytes()
        raise AssertionError("SIC must come from the hit's `sics` field when present")


def test_real_response_parses_ivanhoe_electric() -> None:
    # Ivanhoe Electric is in the frozen Phase 1 sample (PROJECTLOG); its S-K 1300 summary
    # was filed with an 8-K on 2025-06-23 (checked on EDGAR by hand, 2026-11-11).
    hits = EdgarClient(RealFetch()).search_technical_reports("copper")
    ie = next(h for h in hits if h.cik == "0001879016")
    assert ie.company == "Ivanhoe Electric Inc."
    assert (ie.form, ie.file_type, ie.file_date) == ("8-K", "EX-96.1", date(2025, 6, 23))
    assert ie.url == (
        "https://www.sec.gov/Archives/edgar/data/1879016/000110465925061364/tm2518281d1_ex96-1.htm"
    )


def test_real_response_uses_sics_field_without_extra_requests() -> None:
    # All four recorded hits carry `sics` (1000 or 1040), so no submissions lookup is needed.
    fetch = RealFetch()
    cands = discover(EdgarClient(fetch), None, AS_OF)
    assert {c.company for c in cands if c.included} >= {
        "Ivanhoe Electric Inc.",
        "NexMetals Mining Corp.",
    }
    assert all("data.sec.gov" not in u for u in fetch.urls)


@pytest.mark.edgar_live
@pytest.mark.skipif(not os.environ.get("OREBODY_LIVE_EDGAR"), reason="OREBODY_LIVE_EDGAR not set")
def test_live_edgar_search_finds_copper_technical_reports() -> None:
    import urllib.request

    def fetch(url: str) -> bytes:
        req = urllib.request.Request(
            url, headers={"User-Agent": "orebody-research (academic project)"}
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()

    hits = EdgarClient(fetch).search_technical_reports("copper")
    assert len(hits) >= 10
    assert all(h.file_type.startswith("EX-96") for h in hits)


def test_user_agent_requires_a_contact_email(monkeypatch) -> None:
    from orebody.ingest.discover import user_agent

    monkeypatch.delenv("OREBODY_SEC_CONTACT", raising=False)
    with pytest.raises(RuntimeError, match="OREBODY_SEC_CONTACT"):
        user_agent()
    monkeypatch.setenv("OREBODY_SEC_CONTACT", "someone@example.edu")
    assert user_agent() == "orebody-research someone@example.edu"
