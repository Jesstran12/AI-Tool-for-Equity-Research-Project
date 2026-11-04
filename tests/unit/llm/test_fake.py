import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from orebody.llm.fake import FakeProvider
from orebody.llm.provider import MissingFixture, request_key


class Answer(BaseModel):
    answer: str


def test_request_key_is_16_hex_and_stable() -> None:
    k1 = request_key("sys", "user", "Answer", "claude-opus-5-5")
    k2 = request_key("sys", "user", "Answer", "claude-opus-5-5")
    assert k1 == k2 and len(k1) == 16 and int(k1, 16) >= 0
    assert request_key("sys", "user2", "Answer", "claude-opus-5-5") != k1


def test_fake_replays_fixture(tmp_path: Path) -> None:
    key = request_key("sys", "What is 2+2?", "Answer", "claude-opus-5-5")
    (tmp_path / f"{key}.json").write_text(
        json.dumps(
            {
                "parsed": {"answer": "4"},
                "raw_text": '{"answer": "4"}',
                "usage": {"input_tokens": 12, "output_tokens": 5},
                "model": "claude-opus-5-5",
            }
        )
    )
    c = FakeProvider(tmp_path).complete(
        system="sys", user="What is 2+2?", schema=Answer, model="claude-opus-5-5", effort="medium"
    )
    assert c.parsed == {"answer": "4"}
    assert Answer.model_validate(c.parsed).answer == "4"
    assert c.usage.input_tokens == 12 and c.usage.cache_read_input_tokens == 0
    assert c.model == "claude-opus-5-5"
    assert c.cost_usd == 0.0
    assert c.request_key == key


def test_fake_missing_raises_with_key(tmp_path: Path) -> None:
    key = request_key("sys", "nope", "Answer", "claude-opus-5-5")
    with pytest.raises(MissingFixture, match=key):
        FakeProvider(tmp_path).complete(
            system="sys", user="nope", schema=Answer, model="claude-opus-5-5", effort="medium"
        )
