"""F1.8 retrieval: match a manifest document to its EDGAR copy. Synthetic hits; dates by hand."""

from datetime import date
from pathlib import Path

import pytest

from orebody.ingest.alternate import document_text, find_edgar_alternate
from orebody.ingest.discover import Hit
from orebody.ingest.manifest import Document

LEO_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "LEO"


def _hit(form: str, file_type: str, filed: str, desc: str, name: str = "ex.htm") -> Hit:
    return Hit(
        cik="0001339688",
        company="Lion Copper & Gold Corp.",
        form=form,
        file_type=file_type,
        file_date=date.fromisoformat(filed),
        description=desc,
        url=f"https://www.sec.gov/Archives/edgar/data/1339688/x/{name}",
    )


HITS = [
    _hit("8-K", "EX-96.1", "2025-03-26", "Yerington Copper Project Initial Assessment", "ia.htm"),
    _hit(
        "8-K", "EX-99.1", "2026-02-18", "Yerington Copper Project Pre-Feasibility Study", "pfs.htm"
    ),
    _hit("10-Q", "EX-96.1", "2026-11-10", "Bear Project Technical Report Summary", "bear.htm"),
    _hit("10-K", "10-K", "2026-03-31", "Annual report", "10k.htm"),
    _hit("10-Q", "10-Q", "2026-11-10", "Quarterly report", "10q.htm"),
]


def _doc(**kw) -> Document:
    base = dict(file="f.pdf", type="technical_report", filing_date=date(2025, 9, 15))
    return Document(**(base | kw))


def test_technical_report_matches_by_project_and_date() -> None:
    # PFS effective 2025-05-31: the 2025-03-26 IA is before it; the 2026-02-18 PFS is the match
    doc = _doc(project="Yerington Copper Project", effective_date=date(2025, 5, 31))
    alt = find_edgar_alternate(doc, HITS)
    assert alt is not None and alt.url.endswith("/pfs.htm")
    assert alt.file_date == date(2026, 2, 18)


def test_technical_report_for_another_project_does_not_match() -> None:
    doc = _doc(project="Bear Project", effective_date=date(2026, 7, 21))
    alt = find_edgar_alternate(doc, HITS)
    assert alt is not None and alt.url.endswith("/bear.htm")


def test_annual_financials_match_10k_within_180_days() -> None:
    # FY end 2025-12-31 -> 10-K filed 2026-03-31 is 90 days later
    doc = _doc(type="annual_financials", effective_date=date(2025, 12, 31))
    alt = find_edgar_alternate(doc, HITS)
    assert alt is not None and alt.form == "10-K"


def test_quarterly_matches_10q_within_90_days() -> None:
    # Q3 end 2026-09-30 -> 10-Q filed 2026-11-10 is 41 days later
    doc = _doc(type="quarterly_financials", effective_date=date(2026, 9, 30))
    alt = find_edgar_alternate(doc, HITS)
    assert alt is not None and alt.form == "10-Q"


def test_quarterly_outside_window_has_no_match() -> None:
    # Q1 end 2026-03-31 -> nearest 10-Q is 2026-11-10, 224 days later
    doc = _doc(type="quarterly_financials", effective_date=date(2026, 3, 31))
    assert find_edgar_alternate(doc, HITS) is None


@pytest.mark.parametrize("doc_type", ["news_release", "presentation"])
def test_news_and_presentations_have_no_alternate(doc_type: str) -> None:
    assert find_edgar_alternate(_doc(type=doc_type, effective_date=date(2026, 1, 1)), HITS) is None


def test_document_text_strips_html(tmp_path: Path) -> None:
    p = tmp_path / "x.htm"
    p.write_text("<html><body><p>NPV&nbsp;(7%)</p>\n<td>$694</td><script>var x=1</script></body>")
    assert document_text(p) == "NPV (7%) $694"


# Real-data check, skipped on a fresh clone (company files are not committed; `make fetch T=LEO`).
# Hand-checked 2026-11-11: Lion PFS Table 1.9 (PDF p.43) and the EDGAR Ex. 99.1 both state
# post-tax NPV7 US$694M, pre-tax US$975M, IRR 14.6% / 16.9%, payback 6.7 years.
@pytest.mark.skipif(
    not (LEO_DIR / "2025-05-31_yerington-pfs_ni43-101.pdf").exists(),
    reason="LEO drop folder not fetched",
)
def test_lion_pfs_company_pdf_and_edgar_exhibit_are_consistent() -> None:
    from orebody.core.crosscheck import compare

    pdf = document_text(LEO_DIR / "2025-05-31_yerington-pfs_ni43-101.pdf")
    htm = document_text(LEO_DIR / "2025-05-31_yerington-pfs_sk1300_ex99-1.htm")
    r = compare(pdf, htm, ["694", "975", "14.6", "16.9", "6.7"])
    assert r.key_missing_in_alternate == [] and r.key_missing_in_primary == []
    assert r.status in ("identical", "consistent")
