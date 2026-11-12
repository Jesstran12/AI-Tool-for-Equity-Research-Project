"""F1.6 eligibility: one passing fixture folder, and one failing folder per rule.

The passing folder uses the synthetic 6-page fixture report (tests/fixtures/make_pdf.py): Items 1,
14, 21, 22 on pages 3-6, every page has text; filed 2025-10-09; manifest says Cu, TSXV.
"""

import shutil
from datetime import date
from pathlib import Path

import pymupdf
import pytest

from orebody.ingest.eligibility import RULES, check_folder, contents_note

ROOT = Path(__file__).resolve().parents[3]
SECTIONS = ROOT / "config" / "sections.yaml"
AS_OF = date(2026, 11, 11)

MANIFEST = """
ticker: FIX
name: Fixture Copper Corp
exchange: TSXV
primary_commodity: Cu
documents:
  - file: report.pdf
    type: technical_report
    standard: NI43-101
    effective_date: 2025-08-25
    filing_date: 2025-10-09
"""


def _folder(tmp_path: Path, fixture_pdf: Path, manifest: str = MANIFEST) -> Path:
    d = tmp_path / "FIX"
    d.mkdir()
    shutil.copy(fixture_pdf, d / "report.pdf")
    (d / "manifest.yaml").write_text(manifest)
    return d


def _rule(result, name: str):
    return next(r for r in result.rules if r.rule == name)


def test_fixture_folder_passes_every_rule(tmp_path: Path, fixture_pdf: Path) -> None:
    r = check_folder(_folder(tmp_path, fixture_pdf), AS_OF, SECTIONS)
    assert r.passed
    assert [x.rule for x in r.rules] == list(RULES)
    assert all(x.passed for x in r.rules)
    assert r.report_file == "report.pdf"
    assert r.section3_path == "economics"  # Items 21 and 22 are on pages 5 and 6


@pytest.mark.parametrize(
    ("rule", "old", "new"),
    [
        ("listed_owner", "exchange: TSXV\n", ""),
        ("primary_commodity", "primary_commodity: Cu\n", "primary_commodity: Au\n"),
        ("primary_commodity", "primary_commodity: Cu\n", ""),  # missing is a failure, not a guess
        ("report_filed", "filing_date: 2025-10-09", "filing_date: 2026-12-01"),  # after as-of
    ],
)
def test_each_manifest_rule_fails_alone(
    tmp_path: Path, fixture_pdf: Path, rule: str, old: str, new: str
) -> None:
    r = check_folder(_folder(tmp_path, fixture_pdf, MANIFEST.replace(old, new)), AS_OF, SECTIONS)
    assert not r.passed
    failed = [x for x in r.rules if not x.passed]
    assert [x.rule for x in failed] == [rule]
    assert failed[0].message.startswith(rule)


def test_report_filed_lists_the_dates(tmp_path: Path, fixture_pdf: Path) -> None:
    m = MANIFEST.replace("filing_date: 2025-10-09", "filing_date: 2026-12-01")
    msg = _rule(check_folder(_folder(tmp_path, fixture_pdf, m), AS_OF, SECTIONS), "report_filed")
    assert "2026-12-01" in msg.message and "2026-11-11" in msg.message


def test_no_technical_report_fails_report_filed_and_skips_file_rules(
    tmp_path: Path, fixture_pdf: Path
) -> None:
    m = MANIFEST.replace("type: technical_report", "type: presentation")
    r = check_folder(_folder(tmp_path, fixture_pdf, m), AS_OF, SECTIONS)
    assert r.report_file is None and r.section3_path is None
    assert not _rule(r, "report_filed").passed
    # rules 4-5 have nothing to check: they fail with a message that says so
    assert "no technical report" in _rule(r, "text_layer").message
    assert "no technical report" in _rule(r, "items_found").message


def test_earlier_report_is_used_when_the_first_is_after_as_of(
    tmp_path: Path, fixture_pdf: Path
) -> None:
    # The first technical report listed (the current study) is filed after as-of, so the check
    # falls back to the earlier one, as `run --as-of` must.
    m = MANIFEST.replace(
        "documents:\n",
        "documents:\n  - file: newer.pdf\n    type: technical_report\n"
        "    standard: NI43-101\n    filing_date: 2026-12-01\n",
    )
    r = check_folder(_folder(tmp_path, fixture_pdf, m), AS_OF, SECTIONS)
    assert r.report_file == "report.pdf"
    assert r.passed


def test_scanned_pdf_fails_text_layer(tmp_path: Path, fixture_pdf: Path) -> None:
    d = _folder(tmp_path, fixture_pdf)
    blank = pymupdf.open()
    for _ in range(6):
        blank.new_page()  # pages with no text, like an unOCRed scan
    blank.save(d / "report.pdf")
    r = check_folder(d, AS_OF, SECTIONS)
    assert not _rule(r, "text_layer").passed
    assert "0/6" in _rule(r, "text_layer").message  # pages with text / total pages


def test_unnumbered_headings_fail_items_found(tmp_path: Path, fixture_pdf: Path) -> None:
    # Real-data lesson (Lion Yerington PFS, Highland Copperwood FS): headings without item numbers.
    d = _folder(tmp_path, fixture_pdf)
    pdf = pymupdf.open()
    for title in ["SUMMARY", "INTRODUCTION", "CAPITAL AND OPERATING COSTS", "ECONOMIC ANALYSIS"]:
        page = pdf.new_page()
        page.insert_text((50, 72), title + "\n" + "Body text of the section. " * 8, fontsize=11)
    pdf.save(d / "report.pdf")
    r = check_folder(d, AS_OF, SECTIONS)
    assert not _rule(r, "items_found").passed
    assert "0 items" in _rule(r, "items_found").message


def test_sk1300_html_report_is_eligible(tmp_path: Path) -> None:
    # Was test_sk1300_report_fails_items_found_until_f22 (a placeholder until F2.2); replaced with
    # the user's approval when F2.2 added the S-K 1300 index (2026-11-11).
    d = tmp_path / "FIX"
    d.mkdir()
    body = "Body text of the section. " * 8
    pages = [
        f"<p>{n}.0</p><p>{title}</p><p>{body}</p>"
        for n, title in [
            (1, "EXECUTIVE SUMMARY"),
            (2, "INTRODUCTION"),
            (11, "MINERAL RESOURCE ESTIMATES"),
            (18, "CAPITAL AND OPERATING COSTS"),
            (19, "ECONOMIC ANALYSIS"),
        ]
    ]
    brk = '<div style="page-break-before: always"></div>'
    (d / "report.htm").write_text("<html><body>" + brk.join(pages) + "</body></html>")
    (d / "manifest.yaml").write_text(
        MANIFEST.replace("report.pdf", "report.htm").replace("NI43-101", "SK1300")
    )
    r = check_folder(d, AS_OF, SECTIONS)
    assert r.passed, [x.message for x in r.rules if not x.passed]
    assert "5 items found via S-K 1300 headings" in _rule(r, "items_found").message
    assert r.section3_path == "economics"  # Items 18 and 19, not 21 and 22


def test_no_study_path_when_items_21_22_absent(tmp_path: Path, fixture_pdf: Path) -> None:
    # Exploration-stage report: Items 1, 2, 14 found, no 21/22 -> eligible, Section 3 no-study block
    d = _folder(tmp_path, fixture_pdf)
    pdf = pymupdf.open()
    for title in [
        "1 Summary",
        "2 Introduction",
        "14 Mineral Resource Estimates",
        "26 Recommendations",
    ]:
        page = pdf.new_page()
        page.insert_text((50, 72), title + "\n" + "Body text of the section. " * 8, fontsize=11)
    pdf.save(d / "report.pdf")
    r = check_folder(d, AS_OF, SECTIONS)
    assert r.passed
    assert r.section3_path == "no_study"


# Real drop folders, skipped on a fresh clone. Expected outcomes checked by hand 2026-11-11:
# SURG Berg PFS indexes 26 items incl. 21/22; LEO Yerington PFS has un-numbered headings.
RAW = ROOT / "data" / "raw"


@pytest.mark.skipif(
    not (RAW / "SURG" / "2026-06-12_berg_ni43-101-pfs.pdf").exists(), reason="SURG not fetched"
)
def test_real_surg_is_eligible_with_economics() -> None:
    r = check_folder(RAW / "SURG", AS_OF, SECTIONS)
    assert r.passed
    assert r.section3_path == "economics"


@pytest.mark.skipif(
    not (RAW / "LEO" / "2025-05-31_yerington-pfs_ni43-101.pdf").exists(), reason="LEO not fetched"
)
def test_real_leo_is_eligible_after_f21() -> None:
    # Was test_real_leo_fails_items_found (recorded the un-numbered-heading bug); changed with the
    # user's approval when F2.1 added the subsection fallback (2026-11-11).
    r = check_folder(RAW / "LEO", AS_OF, SECTIONS)
    assert _rule(r, "text_layer").passed
    assert _rule(r, "items_found").passed
    assert "via subsection" in _rule(r, "items_found").message
    assert r.passed and r.section3_path == "economics"


# --- F2.1b contents check surfaced in `check` (a note, never a rule) ---------------------------


def _report_with_contents(path: Path, printed_21: int) -> None:
    """Pages: 1 cover, 2 contents, 3-6 Items 1/14/21/22. The contents prints Item 21 on
    `printed_21`; the true page is 5."""
    pdf = pymupdf.open()
    body = "Body text of the section. " * 8
    toc = "\n".join(
        [
            "TABLE OF CONTENTS",
            "1 Summary ........ 3",
            "14 Mineral Resource Estimates ........ 4",
            f"21 Capital and Operating Costs ........ {printed_21}",
            "22 Economic Analysis ........ 6",
            "26 Recommendations ........ 7",
        ]
    )
    pages = ["Fixture cover page " * 6, toc]
    titles = [
        "1 Summary",
        "14 Mineral Resource Estimates",
        "21 Capital and Operating Costs",
        "22 Economic Analysis",
    ]
    pages += [t + "\n" + body for t in titles]
    for text in pages:
        pdf.new_page().insert_text((50, 72), text, fontsize=9)
    pdf.save(path)


def test_contents_check_agrees(tmp_path: Path, fixture_pdf: Path) -> None:
    d = _folder(tmp_path, fixture_pdf)
    _report_with_contents(d / "report.pdf", printed_21=5)
    r = check_folder(d, AS_OF, SECTIONS)
    assert r.passed
    assert (r.contents.offset, r.contents.checked, r.contents.flagged) == (0, 4, [])
    assert contents_note(r.contents) == "contents check: offset +0 over 4 items, no disagreement"


def test_contents_disagreement_is_a_note_not_a_failure(tmp_path: Path, fixture_pdf: Path) -> None:
    d = _folder(tmp_path, fixture_pdf)
    _report_with_contents(d / "report.pdf", printed_21=9)  # contents is wrong about Item 21
    r = check_folder(d, AS_OF, SECTIONS)
    assert r.passed  # eligibility unchanged
    assert [f.item for f in r.contents.flagged] == [21]
    assert contents_note(r.contents) == (
        "contents check: offset +0 over 4 items; item 21 found p.5, contents says p.9 "
        "(expected p.9)"
    )


def test_contents_note_when_check_is_impossible() -> None:
    from orebody.index.toc import TocCheck

    reason = "too few items agree on an offset (2 < 3)"
    c = TocCheck(offset=None, checked=2, flagged=[], note=reason)
    assert contents_note(c) == f"contents check: not possible ({reason})"
    assert contents_note(None) == ""


def test_check_cli_prints_the_contents_note(tmp_path: Path, fixture_pdf: Path) -> None:
    from typer.testing import CliRunner

    from orebody.cli import app

    data = tmp_path / "data" / "raw"
    data.mkdir(parents=True)
    d = _folder(data, fixture_pdf)
    _report_with_contents(d / "report.pdf", printed_21=5)
    args = ["check", "FIX", "--as-of", "2026-11-11", "--data-dir", str(tmp_path / "data")]
    out = CliRunner().invoke(app, args).output
    assert "NOTE  contents check: offset +0 over 4 items, no disagreement" in out


@pytest.mark.skipif(
    not (RAW / "SURG" / "2026-06-12_berg_ni43-101-pfs.pdf").exists(), reason="SURG not fetched"
)
def test_real_surg_contents_check() -> None:
    r = check_folder(RAW / "SURG", AS_OF, SECTIONS)
    assert r.contents.offset == 25 and r.contents.flagged == []
