"""Build the synthetic 6-page NI 43-101 fixture report with PyMuPDF (never a real filing)."""

from __future__ import annotations

from pathlib import Path

import pymupdf

PAGES: list[str] = [
    "\n".join(
        [
            "Fixture Copper Project NI 43-101 Technical Report",
            "Effective date: 2025-08-25",
        ]
    ),
    "\n".join(
        [
            "TABLE OF CONTENTS",
            "1 Summary ........ 3",
            "2 Introduction ........ 3",
            "14 Mineral Resource Estimates ........ 4",
            "21 Capital and Operating Costs ........ 5",
            "22 Economic Analysis ........ 6",
        ]
    ),
    "\n".join(
        [
            "1 Summary",
            "The Project has a mine life of 18 years and produces an average of",
            "50,000 tonnes of payable copper per year.",
        ]
    ),
    "\n".join(
        [
            "14 Mineral Resource Estimates",
            "The resource estimate was prepared using industry-standard methods.",
            "Block model dimensions and density assumptions are described below.",
        ]
    ),
    "\n".join(
        [
            "21 Capital and Operating Costs",
            "Initial capital cost is estimated at US$1,240 million.",
            "Sustaining capital totals US$310 million over the life of mine.",
            "C1 cash cost is US$1.85/lb.",
        ]
    ),
    "\n".join(
        [
            "22 Economic Analysis",
            "At a base case copper price of US$4.00/lb the post-tax NPV at an 8%",
            "discount rate is US$2,100 million with an IRR of 22.8%.",
            "The effective tax rate is 27%.",
        ]
    ),
]


def make_report(path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    for text in PAGES:
        page = doc.new_page()
        page.insert_text(pymupdf.Point(50, 72), text, fontsize=11)
    doc.save(path)
    doc.close()
    return path


if __name__ == "__main__":
    import sys

    print(make_report(Path(sys.argv[1])))
