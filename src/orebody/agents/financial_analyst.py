"""Financial Analyst agent: one structured call, page-bounded claims."""

from __future__ import annotations

from pathlib import Path

from orebody.agents.context import ContextBundle
from orebody.agents.schemas import FinancialAnalystOutput
from orebody.llm.prompts import load_prompt as load_prompt_file
from orebody.llm.provider import Completion, LLMProvider


def load_prompt(path: Path) -> tuple[str, str]:
    """Return (version, body) from a prompt file whose first line is `version: N` (F4.3 loader)."""
    p = load_prompt_file(path)
    return p.version, p.body


def run_financial_analyst(
    provider: LLMProvider,
    bundle: ContextBundle,
    doc_id: str,
    model: str,
    effort: str,
    prompt_path: Path,
) -> tuple[FinancialAnalystOutput, Completion]:
    _, system = load_prompt(prompt_path)
    completion = provider.complete(
        system=system,
        user=bundle.text,
        schema=FinancialAnalystOutput,
        model=model,
        effort=effort,
    )
    output = FinancialAnalystOutput.model_validate(completion.parsed)
    for claim in output.claims:
        # The model saw exactly one document and cannot know its id: the pipeline stamps it.
        claim.doc_id = doc_id
        if claim.page not in bundle.pages:
            raise ValueError(
                f"claim {claim.field!r} cites page {claim.page}, which was not in the context"
            )
    return output, completion
