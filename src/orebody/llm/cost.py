"""Per-call cost accounting from config/models.yaml prices (USD per MTok)."""

from __future__ import annotations

from pathlib import Path

import yaml

from orebody.llm.provider import Usage


def load_prices(path: Path = Path("config/models.yaml")) -> dict:
    return yaml.safe_load(Path(path).read_text())["prices_usd_per_mtok"]


def cost_usd(model: str, usage: Usage, prices: dict) -> float:
    p = prices[model]
    return (
        usage.input_tokens * p["input"]
        + usage.output_tokens * p["output"]
        + usage.cache_read_input_tokens * p.get("cache_read", 0.0)
    ) / 1_000_000
