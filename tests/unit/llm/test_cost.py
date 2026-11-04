from pathlib import Path

import pytest
import yaml

from orebody.llm.cost import cost_usd, load_prices
from orebody.llm.provider import Usage

MODELS_YAML = Path(__file__).resolve().parents[3] / "config" / "models.yaml"

PRICES = {
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.20},
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.20},
}


def test_cost_usd() -> None:
    # opus: 100k in × $4/MTok = 0.40; 10k out × $20/MTok = 0.20 → 0.60
    usage = Usage(input_tokens=100_000, output_tokens=10_000)
    assert cost_usd("claude-opus-5-5", usage, PRICES) == pytest.approx(0.60)


def test_cost_usd_counts_cache_reads() -> None:
    # 50k cache-read × $0.20/MTok = 0.01, plus 1k in (0.004) and 1k out (0.02) → 0.034
    usage = Usage(input_tokens=1_000, output_tokens=1_000, cache_read_input_tokens=50_000)
    assert cost_usd("claude-opus-5-5", usage, PRICES) == pytest.approx(0.034)


def test_cost_usd_unknown_model_raises() -> None:
    with pytest.raises(KeyError):
        cost_usd("claude-unknown", Usage(input_tokens=1, output_tokens=1), PRICES)


def test_models_yaml_pins_financial_analyst() -> None:
    cfg = yaml.safe_load(MODELS_YAML.read_text())
    assert cfg["financial_analyst"] == {"model": "claude-opus-5-5", "effort": "medium"}
    assert load_prices(MODELS_YAML)["claude-opus-5-5"]["input"] == 4.0
