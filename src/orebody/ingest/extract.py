"""Extract one text file per PDF page so every later step can cite a page number."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pymupdf

SHA_FILE = "sha256"


@dataclass(frozen=True)
class Extracted:
    doc_id: str
    sha256: str
    n_pages: int
    pages_dir: Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_pages(pdf_path: Path, pages_root: Path) -> Extracted:
    """Write pages_root/<doc_id>/0001.txt ... (1-indexed). Idempotent on the PDF's sha256."""
    pdf_path = Path(pdf_path)
    doc_id = pdf_path.stem
    pages_dir = Path(pages_root) / doc_id
    digest = sha256_of(pdf_path)
    sha_file = pages_dir / SHA_FILE
    if sha_file.exists() and sha_file.read_text().strip() == digest:
        n_pages = len(list(pages_dir.glob("[0-9][0-9][0-9][0-9].txt")))
        return Extracted(doc_id=doc_id, sha256=digest, n_pages=n_pages, pages_dir=pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)
    for old in pages_dir.glob("*.txt"):
        old.unlink()
    with pymupdf.open(pdf_path) as doc:
        n_pages = doc.page_count
        for i, page in enumerate(doc, start=1):
            (pages_dir / f"{i:04d}.txt").write_text(page.get_text("text"))
    sha_file.write_text(digest + "\n")
    return Extracted(doc_id=doc_id, sha256=digest, n_pages=n_pages, pages_dir=pages_dir)


def read_page(pages_dir: Path, n: int) -> str:
    path = Path(pages_dir) / f"{n:04d}.txt"
    if n < 1 or not path.exists():
        raise ValueError(f"page {n} not found under {pages_dir}")
    return path.read_text()
