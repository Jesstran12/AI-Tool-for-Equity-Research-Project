"""Financial Analyst agent: one structured call, page-bounded claims."""

from __future__ import annotations

from pathlib import Path

from orebody.agents.context import ContextBundle
from orebody.agents.schemas import FinancialAnalystOutput
from orebody.llm.provider import Completion, LLMProvider


def load_prompt(path: Path) -> tuple[str, str]:
    """Return (version, body) from a prompt file whose first line is `version: N`."""
    text = Path(path).read_text()
    first, _, body = text.partition("\n")
    if not first.startswith("version:"):
        raise ValueError(f"{path}: first line must be 'version: N', got {first!r}")
    return first.split(":", 1)[1].strip(), body.strip() + "\n"


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
        if claim.doc_id != doc_id:
            raise ValueError(
                f"claim {claim.field!r} cites doc {claim.doc_id!r}, expected {doc_id!r}"
            )
        if claim.page not in bundle.pages:
            raise ValueError(
                f"claim {claim.field!r} cites page {claim.page}, which was not in the context"
            )
    return output, completion
