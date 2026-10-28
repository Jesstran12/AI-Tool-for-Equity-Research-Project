"""Manifest of source documents (data/manifest.json).

Every filing or technical report the pipeline reads is registered here with where it came from,
when it became public, and its sha256 fingerprint. The PDFs live in data/raw/ (gitignored); the
manifest is committed so anyone can check they hold the same files.

Look-ahead is enforced on ``filed_date`` (when the document became public), not on
``effective_date`` (the date the report's data refer to), because a report effective on
1 May may not be filed until 12 June.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

SOURCES = ("SEDAR+", "EDGAR")


class ManifestError(Exception):
    """A manifest entry conflicts with what is on disk or already registered."""


@dataclass(frozen=True)
class SourceDocument:
    path: str  # relative to the repo root, e.g. "data/raw/red-canyon/2023-05-01_peak_ni43-101.pdf"
    company: str
    project: str
    doc_type: str  # e.g. "NI 43-101 technical report", "S-K 1300 TRS", "MD&A"
    effective_date: date
    filed_date: date
    source: str  # one of SOURCES
    sha256: str
    url: str | None = None


def sha256_file(path: Path) -> str:
    """Hex sha256 of the file's bytes."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(manifest_path: Path) -> list[SourceDocument]:
    """Read the manifest; a missing file means an empty manifest."""
    if not manifest_path.exists():
        return []
    entries = json.loads(manifest_path.read_text())
    return [
        SourceDocument(
            **{
                **e,
                "effective_date": date.fromisoformat(e["effective_date"]),
                "filed_date": date.fromisoformat(e["filed_date"]),
            }
        )
        for e in entries
    ]


def _save(manifest_path: Path, docs: list[SourceDocument]) -> None:
    entries = [
        {
            **asdict(d),
            "effective_date": d.effective_date.isoformat(),
            "filed_date": d.filed_date.isoformat(),
        }
        for d in sorted(docs, key=lambda d: d.path)
    ]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(entries, indent=2) + "\n")


def register(
    manifest_path: Path,
    root: Path,
    path: str,
    *,
    company: str,
    project: str,
    doc_type: str,
    effective_date: date,
    filed_date: date,
    source: str,
    url: str | None = None,
) -> SourceDocument:
    """Fingerprint the file at ``root / path`` and add it to the manifest.

    Registering the same path with the same bytes again is a no-op. Raises ManifestError if the
    path is already registered with a different hash, the file is missing, the source is not in
    SOURCES, or filed_date is before effective_date.
    """
    if source not in SOURCES:
        raise ManifestError(f"unknown source {source!r}; expected one of {SOURCES}")
    if filed_date < effective_date:
        raise ManifestError(f"{path}: filed {filed_date} before effective {effective_date}")
    file = root / path
    if not file.is_file():
        raise ManifestError(f"{path}: file not found")

    doc = SourceDocument(
        path=path,
        company=company,
        project=project,
        doc_type=doc_type,
        effective_date=effective_date,
        filed_date=filed_date,
        source=source,
        sha256=sha256_file(file),
        url=url,
    )
    docs = load_manifest(manifest_path)
    existing = next((d for d in docs if d.path == path), None)
    if existing is not None:
        if existing.sha256 != doc.sha256:
            raise ManifestError(f"{path}: already registered with a different sha256")
        return existing
    _save(manifest_path, [*docs, doc])
    return doc


def verify(manifest_path: Path, root: Path) -> list[str]:
    """Return one message per registered file that is missing or whose hash has changed."""
    problems = []
    for d in load_manifest(manifest_path):
        file = root / d.path
        if not file.is_file():
            problems.append(f"{d.path}: missing")
        elif sha256_file(file) != d.sha256:
            problems.append(f"{d.path}: sha256 changed since registration")
    return problems


def documents_as_of(docs: list[SourceDocument], as_of: date) -> list[SourceDocument]:
    """Documents filed on or before ``as_of``: the only ones an agent may see."""
    return [d for d in docs if d.filed_date <= as_of]
