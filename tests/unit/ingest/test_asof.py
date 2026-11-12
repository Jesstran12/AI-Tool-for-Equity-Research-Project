"""F1.3 as-of filter. Manifest dates chosen by hand around AS_OF = 2026-11-11."""

import json
from datetime import date
from pathlib import Path

import pytest

from orebody.ingest.asof import apply_as_of, select_report, write_exclusion_log
from orebody.ingest.manifest import Manifest

AS_OF = date(2026, 11, 11)


def _std(doc_type: str) -> str:
    return "NI43-101" if doc_type == "technical_report" else "none"


def _m(*docs: tuple[str, str, str]) -> Manifest:
    return Manifest.model_validate(
        {
            "ticker": "FIX",
            "name": "Fixture Copper",
            "documents": [
                {"file": f, "type": t, "filing_date": d, "standard": _std(t)} for f, t, d in docs
            ],
        }
    )


MIXED = _m(
    ("pfs-2026.pdf", "technical_report", "2026-12-01"),  # newer study, after as-of
    ("pea-2023.pdf", "technical_report", "2023-07-28"),  # the study current on as-of
    ("fs-annual.pdf", "annual_financials", "2026-03-31"),
    ("q3.pdf", "quarterly_financials", "2026-11-12"),  # one day after as-of
    ("news-same-day.htm", "news_release", "2026-11-11"),  # filed on as-of: included
    ("news-later.htm", "news_release", "2026-11-20"),
)


def test_split_keeps_manifest_order() -> None:
    r = apply_as_of(MIXED, AS_OF)
    assert [d.file for d in r.included] == ["pea-2023.pdf", "fs-annual.pdf", "news-same-day.htm"]
    assert [e.file for e in r.excluded] == ["pfs-2026.pdf", "q3.pdf", "news-later.htm"]


def test_filed_on_as_of_date_is_included() -> None:
    r = apply_as_of(MIXED, AS_OF)
    assert "news-same-day.htm" in [d.file for d in r.included]


def test_exclusion_reason_names_both_dates() -> None:
    r = apply_as_of(MIXED, AS_OF)
    q3 = next(e for e in r.excluded if e.file == "q3.pdf")
    assert q3.reason == "filed 2026-11-12, after as-of 2026-11-11"
    assert q3.type == "quarterly_financials"


def test_nothing_excluded_when_as_of_is_late() -> None:
    r = apply_as_of(MIXED, date(2027, 1, 1))
    assert r.excluded == [] and len(r.included) == 6


def test_select_report_falls_back_to_the_study_current_on_as_of() -> None:
    # The 2026 PFS is listed first but filed after as-of; the 2023 PEA was current that day.
    assert select_report(apply_as_of(MIXED, AS_OF)).file == "pea-2023.pdf"
    assert select_report(apply_as_of(MIXED, date(2027, 1, 1))).file == "pfs-2026.pdf"


def test_select_report_without_any_lists_the_excluded_ones() -> None:
    r = apply_as_of(MIXED, date(2020, 1, 1))
    with pytest.raises(ValueError) as e:
        select_report(r)
    msg = str(e.value)
    assert "no technical report filed on or before 2020-01-01" in msg
    assert "pfs-2026.pdf (filed 2026-12-01)" in msg and "pea-2023.pdf (filed 2023-07-28)" in msg


def test_select_report_with_no_technical_report_at_all() -> None:
    m = _m(("news.htm", "news_release", "2026-01-01"))
    with pytest.raises(ValueError, match="no technical report in the manifest"):
        select_report(apply_as_of(m, AS_OF))


def test_exclusion_log_is_written(tmp_path: Path) -> None:
    path = write_exclusion_log(apply_as_of(MIXED, AS_OF), tmp_path)
    assert path == tmp_path / "asof.json"
    log = json.loads(path.read_text())
    assert log["as_of"] == "2026-11-11"
    assert log["included"] == ["pea-2023.pdf", "fs-annual.pdf", "news-same-day.htm"]
    assert [x["file"] for x in log["excluded"]] == ["pfs-2026.pdf", "q3.pdf", "news-later.htm"]
    assert log["excluded"][0] == {
        "file": "pfs-2026.pdf",
        "type": "technical_report",
        "filing_date": "2026-12-01",
        "reason": "filed 2026-12-01, after as-of 2026-11-11",
    }


# --- real manifest, skipped on a fresh clone -------------------------------------------------

SURG = Path(__file__).resolve().parents[3] / "data" / "raw" / "SURG" / "manifest.yaml"


@pytest.mark.skipif(not SURG.exists(), reason="SURG manifest missing")
def test_real_surg_before_its_pfs_uses_the_2023_pea() -> None:
    # Berg PFS filed 2026-07-29 (approx); on 2026-06-30 the 2023 PEA was the current study.
    from orebody.ingest.manifest import load_manifest

    r = apply_as_of(load_manifest(SURG), date(2026, 6, 30))
    assert select_report(r).file == "2023-06-12_berg-pea_ni43-101.pdf"
    assert "2026-06-12_berg_ni43-101-pfs.pdf" in [e.file for e in r.excluded]
