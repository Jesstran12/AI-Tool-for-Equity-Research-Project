"""The one interface every model call goes through (CLAUDE.md rule 2)."""

from __future__ import annotations

import hashlib
from typing import Protocol

from pydantic import BaseModel


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0


class Completion(BaseModel):
    parsed: dict
    raw_text: str
    usage: Usage
    model: str
    cost_usd: float
    request_key: str


class MissingFixture(Exception):
    """FakeProvider has no recording for this request key."""


class LLMProvider(Protocol):
    def complete(
        self, *, system: str, user: str, schema: type[BaseModel], model: str, effort: str
    ) -> Completion: ...


def request_key(system: str, user: str, schema_name: str, model: str) -> str:
    """Stable 16-hex id for a request: the fixture file name under tests/fixtures/llm/."""
    h = hashlib.sha256()
    for part in (system, user, schema_name, model):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]
