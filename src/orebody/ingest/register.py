"""F1.4 `orebody ingest <TICKER>`: register a drop folder's company and documents in SQLite.

For each manifest document whose file is present: sha256, page count (PDF; None for HTML), path
relative to the data root, url. doc_id in the database is "<TICKER>/<file stem>": file stems
repeat across companies (NCX and USCU both have 2025-12-31_FS_annual-2025), and documents.doc_id
is the primary key. (ingest/extract keeps the bare stem for page folders; mapping claims to the
DB id is F5.5's job.)

Outcomes per document:
  added      new row
  unchanged  row exists with the same sha256
  changed    row exists, file on disk now has a different sha256 -> row updated, reported
  missing    file not on disk -> not registered (run `make fetch T=<TICKER>`)
  mismatch   manifest states a sha256 and the file differs -> not registered (wrong or edited file)
Idempotent: a second ingest of an unchanged folder reports everything `unchanged`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pymupdf
from pydantic import BaseModel

from orebody.ingest.extract import sha256_of
from orebody.ingest.manifest import load_manifest


class IngestReport(BaseModel):
    ticker: str
    added: list[str] = []
    unchanged: list[str] = []
    changed: list[str] = []
    missing: list[str] = []
    mismatch: list[str] = []

    @property
    def ok(self) -> bool:
        """False when any document could not be registered (missing or mismatch)."""
        return not self.missing and not self.mismatch


def doc_id_for(ticker: str, file: str) -> str:
    """'NCX', '2025-12-31_FS_annual-2025.pdf' -> 'NCX/2025-12-31_FS_annual-2025'."""
    return f"{ticker.upper()}/{Path(file).stem}"


def _pages(path: Path) -> int | None:
    if path.suffix.lower() != ".pdf":
        return None
    with pymupdf.open(path) as pdf:
        return pdf.page_count


def ingest_folder(conn: sqlite3.Connection, folder: Path, data_root: Path) -> IngestReport:
    """Upsert the company from the manifest, then register each document (see module doc).
    `conn` must already be migrated. Paths are stored relative to `data_root`."""
    folder = Path(folder)
    m = load_manifest(folder / "manifest.yaml")
    ticker = m.ticker.upper()
    report = IngestReport(ticker=ticker)
    rel_folder = folder.resolve().relative_to(Path(data_root).resolve())

    conn.execute("BEGIN")
    try:
        conn.execute(
            """INSERT INTO companies (ticker, name, exchange, cik, flagship_project,
                   primary_commodity, by_products, reporting_currency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET name = excluded.name,
                   exchange = excluded.exchange, cik = excluded.cik,
                   flagship_project = excluded.flagship_project,
                   primary_commodity = excluded.primary_commodity,
                   by_products = excluded.by_products,
                   reporting_currency = excluded.reporting_currency""",
            (
                ticker,
                m.name,
                m.exchange,
                m.cik,
                m.flagship_project,
                m.primary_commodity,
                json.dumps(m.by_products),
                m.reporting_currency,
            ),
        )
        for doc in m.documents:
            path = folder / doc.file
            if not path.exists():
                report.missing.append(doc.file)
                continue
            sha = sha256_of(path)
            if doc.sha256 and doc.sha256 != sha:
                report.mismatch.append(doc.file)
                continue
            doc_id = doc_id_for(ticker, doc.file)
            prior = conn.execute(
                "SELECT sha256 FROM documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
            conn.execute(
                """INSERT INTO documents (doc_id, ticker, type, standard, effective_date,
                       filing_date, path, url, sha256, pages)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(doc_id) DO UPDATE SET type = excluded.type,
                       standard = excluded.standard, effective_date = excluded.effective_date,
                       filing_date = excluded.filing_date, path = excluded.path,
                       url = excluded.url, sha256 = excluded.sha256, pages = excluded.pages""",
                (
                    doc_id,
                    ticker,
                    doc.type,
                    doc.standard,
                    doc.effective_date.isoformat() if doc.effective_date else None,
                    doc.filing_date.isoformat(),
                    (rel_folder / doc.file).as_posix(),
                    doc.url,
                    sha,
                    _pages(path),
                ),
            )
            if prior is None:
                report.added.append(doc.file)
            elif prior[0] == sha:
                report.unchanged.append(doc.file)
            else:
                report.changed.append(doc.file)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return report
