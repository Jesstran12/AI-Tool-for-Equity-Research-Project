# Orebody

AI-generated, source-linked equity research notes for under-covered copper juniors.
Demo slice: Section 3 (Economics) for one company, every figure footnoted to a report page.

## Install

```
uv sync
cp .env.example .env   # add ANTHROPIC_API_KEY for live runs
```

## Run

```
uv run orebody run MARI --as-of 2026-11-05 --spot 4.50 --deck-a 3.50 --deck-b 5.00
uv run orebody run MARI --as-of 2026-11-05 --spot 4.50 --provider fake   # replay the recording
```

Inputs: `data/raw/<TICKER>/manifest.yaml` plus the technical report PDF it names.
Outputs: `data/runs/<run_id>/` holds `context.txt` (pages shown to the model), `request.json`,
`output.json` (raw structured response, usage, cost), `claims.json` (tier-1 results), `note.md`,
and `stats.json`. Live responses are also recorded under `tests/fixtures/llm/` for replay.

`make lint test` runs ruff and pytest; `uv run pytest -m live` runs the one live API test.
