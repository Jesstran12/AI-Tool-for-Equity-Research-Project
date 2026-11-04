"""Locate NI 43-101 items by page so agents receive section-targeted text (SPEC D37)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

MAX_TOC_PAGE = 15
MIN_TOC_LINES = 5


def load_patterns(path: Path = Path("config/sections.yaml")) -> dict[int, str]:
    data = yaml.safe_load(Path(path).read_text())
    return {int(k): str(v) for k, v in data["items"].items()}


@dataclass(frozen=True)
class ItemSpan:
    item: int
    start: int  # 1-indexed, inclusive
    end: int  # 1-indexed, inclusive


def heading_regex(item: int, title: str) -> re.Pattern[str]:
    return re.compile(
        rf"^\s*(?:ITEM\s+)?{item}(?:\.0)?[\s.:\-–]+{re.escape(title)}",
        re.I | re.M,
    )


def _looks_like_toc(text: str) -> bool:
    return sum(1 for line in text.splitlines() if re.search(r"\d\s*$", line)) >= MIN_TOC_LINES


def toc_end(pages: list[str]) -> int:
    """Largest page number ≤ MAX_TOC_PAGE whose text looks like a table of contents; 0 if none."""
    last = 0
    for n, text in enumerate(pages[:MAX_TOC_PAGE], start=1):
        if _looks_like_toc(text):
            last = n
    return last


def build_index(pages: list[str], patterns: dict[int, str]) -> dict[int, ItemSpan]:
    """Map item number → page span. Items whose heading is not found are omitted."""
    first_body = toc_end(pages) + 1
    starts: dict[int, int] = {}
    for item, title in patterns.items():
        rx = heading_regex(item, title)
        for n in range(first_body, len(pages) + 1):
            if rx.search(pages[n - 1]):
                starts[item] = n
                break
    ordered = sorted(starts.items(), key=lambda kv: (kv[1], kv[0]))
    result: dict[int, ItemSpan] = {}
    for i, (item, start) in enumerate(ordered):
        end = ordered[i + 1][1] - 1 if i + 1 < len(ordered) else len(pages)
        result[item] = ItemSpan(item=item, start=start, end=max(start, end))
    return dict(sorted(result.items()))
