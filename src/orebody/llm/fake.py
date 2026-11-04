"""Replay recorded responses so prompts and parsers iterate offline (CLAUDE.md rule 7)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from orebody.llm.provider import Completion, MissingFixture, Usage, request_key


class FakeProvider:
    def __init__(self, fixture_dir: Path):
        self.fixture_dir = Path(fixture_dir)

    def complete(
        self, *, system: str, user: str, schema: type[BaseModel], model: str, effort: str
    ) -> Completion:
        key = request_key(system, user, schema.__name__, model)
        path = self.fixture_dir / f"{key}.json"
        if not path.exists():
            raise MissingFixture(f"{key} (expected {path})")
        data = json.loads(path.read_text())
        return Completion(
            parsed=data["parsed"],
            raw_text=data.get("raw_text", ""),
            usage=Usage.model_validate(data.get("usage", {"input_tokens": 0, "output_tokens": 0})),
            model=data.get("model", model),
            cost_usd=0.0,
            request_key=key,
        )
