"""Live provider: official Anthropic SDK, structured output; every response is recorded."""

from __future__ import annotations

import json
from pathlib import Path

import anthropic
from pydantic import BaseModel

from orebody.llm.cost import cost_usd
from orebody.llm.provider import Completion, Usage, request_key

MAX_TOKENS = 16000


class AnthropicProvider:
    def __init__(
        self, record_dirs: list[Path], prices: dict, client: anthropic.Anthropic | None = None
    ):
        self.record_dirs = [Path(d) for d in record_dirs]
        self.prices = prices
        self.client = client or anthropic.Anthropic()

    def complete(
        self, *, system: str, user: str, schema: type[BaseModel], model: str, effort: str
    ) -> Completion:
        key = request_key(system, user, schema.__name__, model)
        response = self.client.messages.parse(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            output_config={"effort": effort},
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"model refused request {key}: {response.stop_details}")
        if response.parsed_output is None:
            raise RuntimeError(f"no structured output for request {key} ({response.stop_reason})")
        raw_text = "".join(b.text for b in response.content if b.type == "text")
        usage = Usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_input_tokens=response.usage.cache_read_input_tokens or 0,
        )
        completion = Completion(
            parsed=response.parsed_output.model_dump(mode="json"),
            raw_text=raw_text,
            usage=usage,
            model=response.model,
            cost_usd=cost_usd(model, usage, self.prices),
            request_key=key,
        )
        record = {
            "parsed": completion.parsed,
            "raw_text": raw_text,
            "usage": usage.model_dump(),
            "model": response.model,
            "request": {
                "system": system,
                "user": user,
                "schema": schema.__name__,
                "effort": effort,
            },
            "cost_usd": completion.cost_usd,
        }
        for d in self.record_dirs:
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{key}.json").write_text(json.dumps(record, indent=2))
        return completion
