"""F1.8 end to end on a tmp drop folder: company PDF-like text vs a fake EDGAR exhibit."""

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from orebody.ingest.alternate import crosscheck_folder
from orebody.ingest.discover import EdgarClient

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "edgar"

MANIFEST = """
ticker: FXC
name: Fixture Copper Corp
cik: "0000000009"
documents:
  - file: 2025-05-31_fixture-pfs.htm
    type: technical_report
    standard: NI43-101
    effective_date: 2025-05-31
    filing_date: 2025-09-15
    project: Fixture Copper Project
  - file: 2025-12-31_10-K.htm
    type: annual_financials
    effective_date: 2025-12-31
    filing_date: 2026-03-31
  - file: 2026-10-01_news.htm
    type: news_release
    effective_date: 2026-10-01
    filing_date: 2026-10-01
"""
# Company copy and EDGAR copy of the PFS: same figures, different wording -> consistent.
PRIMARY_PFS = "<p>Post-tax NPV (7%) US$694 M; IRR 14.6%; payback 6.7 years; capex 724.</p>"
EDGAR_PFS = "<td>NPV7 after tax</td><td>694</td><td>IRR</td><td>14.6%</td><td>6.7</td><td>724</td>"
# Annual: the EDGAR 10-K states cash 12.5 where the company copy says 21.5 -> differs.
PRIMARY_10K = "<p>Cash 21.5 million at 31 December 2025.</p>"
EDGAR_10K = "<p>Cash 12.5 million at 31 December 2025.</p>"


class Fetch:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        u = urlparse(url)
        if u.netloc == "efts.sec.gov":
            assert parse_qs(u.query)["ciks"] == ["0000000009"]
            return (FIX / "efts_cik9_trs.json").read_bytes()
        if u.netloc == "data.sec.gov":
            return (FIX / "submissions_0000000009.json").read_bytes()
        if url.endswith("/ex99-1.htm"):
            return EDGAR_PFS.encode()
        if url.endswith("/fxc-10k.htm"):
            return EDGAR_10K.encode()
        raise AssertionError(f"unexpected URL {url}")


def _folder(tmp_path: Path) -> Path:
    d = tmp_path / "FXC"
    d.mkdir()
    (d / "manifest.yaml").write_text(MANIFEST)
    (d / "2025-05-31_fixture-pfs.htm").write_text(PRIMARY_PFS)
    (d / "2025-12-31_10-K.htm").write_text(PRIMARY_10K)
    (d / "2026-10-01_news.htm").write_text("<p>news</p>")
    return d


def test_company_hits_merge_submissions_and_exhibits() -> None:
    hits = EdgarClient(Fetch()).company_hits("0000000009")
    forms = {(h.form, h.file_type) for h in hits}
    # 3 main documents from submissions + the EX-99.1 found by full-text search
    assert forms == {("10-Q", "10-Q"), ("10-K", "10-K"), ("8-K", "8-K"), ("8-K", "EX-99.1")}
    tenk = next(h for h in hits if h.form == "10-K")
    assert tenk.url == "https://www.sec.gov/Archives/edgar/data/9/000000000926000200/fxc-10k.htm"
    assert tenk.file_date == date(2026, 3, 31)


def test_crosscheck_folder_writes_results(tmp_path: Path) -> None:
    d = _folder(tmp_path)
    rows = crosscheck_folder(d, EdgarClient(Fetch()))
    by_file = {r["file"]: r for r in rows}
    # PFS: every number in the company copy (7, 694, 14.6, 6.7, 724) is in the EDGAR copy
    assert by_file["2025-05-31_fixture-pfs.htm"]["status"] == "consistent"
    assert by_file["2025-05-31_fixture-pfs.htm"]["alt_url"].endswith("/ex99-1.htm")
    # 10-K: 21.5 vs 12.5 -> overlap 2/3 (31, 2025 shared) < 0.90
    assert by_file["2025-12-31_10-K.htm"]["status"] == "differs"
    assert "21.5" in by_file["2025-12-31_10-K.htm"]["only_in_primary"]
    # news has no EDGAR alternate
    assert by_file["2026-10-01_news.htm"]["status"] == "no_alternate"
    # alternates are saved next to the folder with their sha256, results to crosscheck.json
    assert (d / "alt" / "ex99-1.htm").read_text() == EDGAR_PFS
    assert len(by_file["2025-05-31_fixture-pfs.htm"]["alt_sha256"]) == 64
    assert json.loads((d / "crosscheck.json").read_text()) == rows


def test_crosscheck_folder_without_cik_skips_everything(tmp_path: Path) -> None:
    d = _folder(tmp_path)
    (d / "manifest.yaml").write_text(MANIFEST.replace('cik: "0000000009"\n', ""))
    rows = crosscheck_folder(d, EdgarClient(Fetch()))
    assert {r["status"] for r in rows} == {"no_alternate"}
    assert all(r["note"] == "no CIK in manifest" for r in rows)


# --- real-data lessons (2026-11-11): generic exhibit descriptions, files pulled from EDGAR -------


class GenericFetch(Fetch):
    """EDGAR describes the exhibit only as 'EXHIBIT 99.1' (as it does for Lion's PFS)."""

    def __call__(self, url: str) -> bytes:
        if urlparse(url).netloc == "efts.sec.gov":
            self.urls.append(url)
            return (FIX / "efts_cik9_generic.json").read_bytes()
        return super().__call__(url)


def test_technical_report_matched_by_content_when_description_is_generic(tmp_path: Path) -> None:
    d = _folder(tmp_path)
    rows = crosscheck_folder(d, EdgarClient(GenericFetch()))
    pfs = next(r for r in rows if r["file"] == "2025-05-31_fixture-pfs.htm")
    assert pfs["status"] == "consistent"
    assert pfs["matched_by"] == "content"
    assert pfs["alt_url"].endswith("/ex99-1.htm")


def test_content_match_below_threshold_is_not_an_alternate(tmp_path: Path) -> None:
    d = _folder(tmp_path)
    (d / "2025-05-31_fixture-pfs.htm").write_text("<p>Resource 812 Mt at 0.31% Cu, 2019.</p>")
    rows = crosscheck_folder(d, EdgarClient(GenericFetch()))
    pfs = next(r for r in rows if r["file"] == "2025-05-31_fixture-pfs.htm")
    assert pfs["status"] == "no_alternate"
    assert "best overlap" in pfs["note"]


def test_document_downloaded_from_edgar_is_same_source(tmp_path: Path) -> None:
    # The 10-K in the manifest was itself pulled from EDGAR: comparing it with EDGAR proves nothing.
    d = _folder(tmp_path)
    url = "https://www.sec.gov/Archives/edgar/data/9/000000000926000200/fxc-10k.htm"
    m = (
        (d / "manifest.yaml")
        .read_text()
        .replace("    filing_date: 2026-03-31\n", f"    filing_date: 2026-03-31\n    url: {url}\n")
    )
    (d / "manifest.yaml").write_text(m)
    rows = crosscheck_folder(d, EdgarClient(Fetch()))
    tenk = next(r for r in rows if r["file"] == "2025-12-31_10-K.htm")
    assert tenk["status"] == "same_source"


def test_company_hits_searches_both_report_phrases() -> None:
    f = Fetch()
    EdgarClient(f).company_hits("0000000009")
    qs = [parse_qs(urlparse(u).query)["q"][0] for u in f.urls if "efts" in u]
    assert '"technical report summary"' in qs and '"technical report"' in qs


def test_content_match_rejects_a_different_report_version(tmp_path: Path) -> None:
    # Same numbers, but EDGAR's exhibit states a later effective date: a newer version, not a copy.
    d = _folder(tmp_path)
    newer = EDGAR_PFS + "<p>The effective date of this technical report is March 18, 2026.</p>"

    class NewerFetch(GenericFetch):
        def __call__(self, url: str) -> bytes:
            if url.endswith("/ex99-1.htm"):
                self.urls.append(url)
                return newer.encode()
            return super().__call__(url)

    rows = crosscheck_folder(d, EdgarClient(NewerFetch()))
    pfs = next(r for r in rows if r["file"] == "2025-05-31_fixture-pfs.htm")
    assert pfs["status"] == "no_alternate"
    assert "effective date" in pfs["note"]


def test_any_edgar_url_is_same_source_without_searching(tmp_path: Path) -> None:
    # An S-K 1300 exhibit pulled from EDGAR has no independent copy there, whatever matching finds.
    d = _folder(tmp_path)
    url = "https://www.sec.gov/Archives/edgar/data/9/000000000926000100/ex99-1.htm"
    m = (
        (d / "manifest.yaml")
        .read_text()
        .replace(
            "    project: Fixture Copper Project\n",
            f"    project: Fixture Copper Project\n    url: {url}\n",
        )
    )
    (d / "manifest.yaml").write_text(m)
    rows = crosscheck_folder(d, EdgarClient(GenericFetch()))
    pfs = next(r for r in rows if r["file"] == "2025-05-31_fixture-pfs.htm")
    assert pfs["status"] == "same_source"
