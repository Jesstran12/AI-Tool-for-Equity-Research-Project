import json
import os
from pathlib import Path

import pytest
from pydantic import BaseModel

from orebody.llm.anthropic_provider import AnthropicProvider
from orebody.llm.cost import load_prices
from orebody.llm.fake import FakeProvider

MODELS_YAML = Path(__file__).resolve().parents[3] / "config" / "models.yaml"
FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "llm"


class Answer(BaseModel):
    answer: str


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
def test_live_parse_records_fixture(tmp_path: Path) -> None:
    provider = AnthropicProvider(
        record_dirs=[FIXTURE_DIR, tmp_path], prices=load_prices(MODELS_YAML)
    )
    c = provider.complete(
        system="Answer with one word.",
        user="What colour is the sky on a clear day?",
        schema=Answer,
        model="claude-sonnet-5-5",
        effort="low",
    )
    assert c.cost_usd > 0
    assert "blue" in c.parsed["answer"].lower()
    recorded = tmp_path / f"{c.request_key}.json"
    assert recorded.exists() and (FIXTURE_DIR / recorded.name).exists()
    data = json.loads(recorded.read_text())
    assert data["parsed"] == c.parsed and data["model"] == c.model
    # The recording replays through FakeProvider with the same key.
    replay = FakeProvider(tmp_path).complete(
        system="Answer with one word.",
        user="What colour is the sky on a clear day?",
        schema=Answer,
        model="claude-sonnet-5-5",
        effort="low",
    )
    assert replay.parsed == c.parsed
