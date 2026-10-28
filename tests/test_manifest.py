import hashlib
import json
from datetime import date

import pytest

from orebody.ingest.manifest import (
    ManifestError,
    documents_as_of,
    load_manifest,
    register,
    sha256_file,
    verify,
)

META = dict(
    company="Red Canyon Resources Ltd.",
    project="Peak",
    doc_type="NI 43-101 technical report",
    effective_date=date(2023, 5, 1),
    filed_date=date(2023, 9, 1),
    source="SEDAR+",
)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "data/raw/red-canyon").mkdir(parents=True)
    pdf = tmp_path / "data/raw/red-canyon/peak.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake report")
    return tmp_path


def reg(repo, path="data/raw/red-canyon/peak.pdf", **overrides):
    return register(repo / "data/manifest.json", repo, path, **{**META, **overrides})


def test_sha256_matches_hashlib(repo):
    pdf = repo / "data/raw/red-canyon/peak.pdf"
    assert sha256_file(pdf) == hashlib.sha256(b"%PDF-1.4 fake report").hexdigest()


def test_missing_manifest_is_empty(tmp_path):
    assert load_manifest(tmp_path / "manifest.json") == []


def test_register_round_trip(repo):
    doc = reg(repo)
    assert doc.sha256 == hashlib.sha256(b"%PDF-1.4 fake report").hexdigest()
    assert load_manifest(repo / "data/manifest.json") == [doc]


def test_manifest_is_readable_json_with_iso_dates(repo):
    reg(repo)
    raw = json.loads((repo / "data/manifest.json").read_text())
    entry = raw[0] if isinstance(raw, list) else next(iter(raw.values()))
    assert entry["filed_date"] == "2023-09-01"
    assert entry["sha256"]


def test_register_same_file_twice_is_noop(repo):
    reg(repo)
    reg(repo)
    assert len(load_manifest(repo / "data/manifest.json")) == 1


def test_register_changed_file_raises(repo):
    reg(repo)
    (repo / "data/raw/red-canyon/peak.pdf").write_bytes(b"%PDF-1.4 swapped")
    with pytest.raises(ManifestError):
        reg(repo)


def test_register_missing_file_raises(repo):
    with pytest.raises(ManifestError):
        reg(repo, path="data/raw/red-canyon/nope.pdf")


def test_register_unknown_source_raises(repo):
    with pytest.raises(ManifestError):
        reg(repo, source="Google")


def test_register_filed_before_effective_raises(repo):
    with pytest.raises(ManifestError):
        reg(repo, filed_date=date(2023, 4, 1))


def test_verify_clean(repo):
    reg(repo)
    assert verify(repo / "data/manifest.json", repo) == []


def test_verify_flags_changed_and_missing(repo):
    (repo / "data/raw/red-canyon/scraper.pdf").write_bytes(b"other")
    reg(repo)
    reg(repo, path="data/raw/red-canyon/scraper.pdf", project="Scraper Springs")
    (repo / "data/raw/red-canyon/peak.pdf").write_bytes(b"edited")
    (repo / "data/raw/red-canyon/scraper.pdf").unlink()
    problems = verify(repo / "data/manifest.json", repo)
    assert len(problems) == 2
    assert any("peak.pdf" in p for p in problems)
    assert any("scraper.pdf" in p for p in problems)


def test_as_of_uses_filed_date_not_effective_date(repo):
    doc = reg(repo)  # effective 2023-05-01, filed 2023-09-01
    docs = [doc]
    assert documents_as_of(docs, date(2023, 6, 1)) == []  # effective, but not yet public
    assert documents_as_of(docs, date(2023, 9, 1)) == [doc]  # filed that day: visible
    assert documents_as_of(docs, date(2024, 1, 1)) == [doc]
