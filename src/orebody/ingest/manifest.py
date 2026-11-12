"""Drop-folder manifest: which documents belong to a company and what they are."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ValidationError

DocType = Literal[
    "technical_report",
    "annual_financials",
    "quarterly_financials",
    "mdna",
    "aif",
    "news_release",
    "presentation",
]
Standard = Literal["NI43-101", "SK1300", "JORC", "none"]


class Document(BaseModel):
    file: str
    type: DocType
    standard: Standard = "none"
    effective_date: date | None = None
    filing_date: date
    title: str = ""
    project: str = ""
    url: str = ""  # where the file was downloaded from
    sha256: str = ""


class Manifest(BaseModel):
    ticker: str
    name: str
    exchange: str = ""
    cik: str = ""  # 10-digit EDGAR CIK when the company files with the SEC (F1.8)
    flagship_project: str = ""
    reporting_currency: str = "USD"
    documents: list[Document]

    def technical_report(self) -> Document:
        for doc in self.documents:
            if doc.type == "technical_report":
                return doc
        raise ValueError(f"manifest for {self.ticker} has no technical_report document")


def load_manifest(path: Path) -> Manifest:
    data = yaml.safe_load(Path(path).read_text())
    try:
        return Manifest.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"invalid manifest {path}: {e}") from e
