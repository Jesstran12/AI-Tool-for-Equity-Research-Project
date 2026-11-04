"""Section-targeted page text for agents: Items 1, 21, 22 only, never the whole report."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orebody.index.ni43101 import ItemSpan
from orebody.ingest.extract import read_page


@dataclass(frozen=True)
class ContextBundle:
    text: str
    pages: set[int]
    items_found: list[int]
    items_missing: list[int]


def build_context(
    pages_dir: Path,
    index: dict[int, ItemSpan],
    items: tuple[int, ...] = (1, 21, 22),
    max_pages_per_item: int = 40,
) -> ContextBundle:
    parts: list[str] = []
    pages: set[int] = set()
    found: list[int] = []
    missing: list[int] = []
    for item in items:
        span = index.get(item)
        if span is None:
            missing.append(item)
            continue
        found.append(item)
        end = min(span.end, span.start + max_pages_per_item - 1)
        parts.append(f"=== Item {item}: pages {span.start}-{end} ===")
        for p in range(span.start, end + 1):
            parts.append(f"--- page {p} ---\n{read_page(pages_dir, p)}")
            pages.add(p)
    return ContextBundle(
        text="\n".join(parts), pages=pages, items_found=found, items_missing=missing
    )
