# CLAUDE.md — Orebody

## What this is
AI-generated, source-linked equity research notes for under-covered copper juniors. Proof of concept for a professor. Read `SPEC.md` §0 and the last §12 entry before doing anything. Then build the next `TODO` feature in §11, and nothing else.

## Session protocol
1. Read SPEC.md §0 "Current state" + last session-log entry.
2. Announce which feature ID you are building.
3. Write the tests first, then the implementation, until `make lint test` is green.
4. Update the feature's status, §0, and append a §12 entry **in the same commit** as the code.
5. One feature per commit. If a feature grows, split it into F<N>.<M>a/b in SPEC.md and say why.
6. Never mark `DONE` without pasting the passing test output in the session-log entry.

## Stack
- Python 3.12, `uv`, `ruff`, `pytest`, Pydantic v2, PyMuPDF, FastAPI, SQLite (stdlib `sqlite3`, SQL migration files), yfinance, Anthropic SDK (official `anthropic` package only; never raw HTTP; never OpenAI-compatible shims).
- Web: Next.js (App Router, TypeScript), pdf.js via `react-pdf`, plain CSS modules or Tailwind. Web lives in `web/`.
- Ports: API **8114**, web **3014**. Never use other ports without asking.
- No Docker. No Postgres. No background services beyond the two dev servers.

## Commands
```
make lint          # ruff check + ruff format --check
make test          # pytest -q
make api           # uvicorn orebody.api:app --port 8114 --reload
make web           # cd web && npm run dev -- -p 3014
orebody db init | ingest <TICKER> | run <TICKER> --as-of YYYY-MM-DD | export <note_id> --pdf | judge <note_id> | summary | diff-runs A B
```

## Ground rules (non-negotiable)
1. **Pure core.** `src/orebody/core/*` and `index/*` contain no LLM calls and no network except `prices.py`. They are unit-tested with hand-computed fixtures in `tests/fixtures/`.
2. **LLM behind an interface.** All model calls go through `llm/provider.py`. Tests use `FakeProvider` replaying `tests/fixtures/llm/*.json`. Live tests are marked `@pytest.mark.live` and skipped without `ANTHROPIC_API_KEY`.
3. **No number without a source.** Agents emit structured JSON with a claims array; Markdown is rendered by code. The renderer fails if prose contains a number that is not a ledgered claim. Computed numbers carry a derivation listing input claim ids.
4. **No invented economics.** If a company has no economic study, Section 3 is the "no economic study" block. Never estimate capex/NPV from comparables.
5. **As-of discipline.** Every run has `--as-of`; documents with `filing_date` after it are excluded and logged. Prices are as-of.
6. **Reproducibility.** Pinned model ids from `config/models.yaml`, fixed `effort`, prompts in `prompts/*.md` with a `version:` header, document sha256s, full request/response logs under `data/runs/<run_id>/`. Do not pass `temperature` (current models reject it). Compare reruns with `orebody diff-runs`; never assume identical output.
7. **Budget.** Target ≤ US$2 and ≤ 10 min per note; project ceiling ≈ US$50 (SPEC D43). Agents receive section-targeted page text (SPEC D37), never whole reports. Log cost per agent call. Record every live response as a `FakeProvider` fixture; iterate on prompts and parsers offline, re-run live only when the fixture cannot answer the question.
8. **Models.** Default per SPEC D31: `claude-sonnet-5-5` for Project Analyst, Advisor, vision fallback; `claude-opus-5-5` for Financial Analyst and tier-2 Verifier. Use `output_config.format` for structured output, adaptive thinking (omit the `thinking` param), server-side fallbacks on, streaming for long outputs. No assistant prefill. No forced `tool_choice`.
9. **No web search in agents.** The drop folder is the universe (SPEC D23).
10. **Stance language.** Only `Favourable / Neutral / Unfavourable on disclosed fundamentals`. No price targets, no return language, disclaimer verbatim from SPEC §4.2.
11. **Data hygiene.** `data/`, `*.sqlite`, `.env`, `web/node_modules`, `reports/*.pdf` are gitignored. Never commit a company PDF. Never commit API keys.
12. **Commits.** Small, one feature each, imperative subject (`F3.3: NPV engine with IRR and payback`). No `Co-Authored-By`, no AI credit lines, ever.
13. **Verification before claiming done.** Run the command, read the output, then say it passed. No "should work".
14. **Library docs.** Use Context7 MCP for PyMuPDF, FastAPI, Next.js, react-pdf, Anthropic SDK questions before guessing an API.
15. **Scope.** Do not build backlog items (SPEC §11 "Later") or anything not in the current feature's AC. If you think the spec is wrong, say so in the session log and ask; do not silently change the design.

## Layout
See SPEC.md §5.1. Keep it.

## Testing conventions
- `tests/unit/` mirrors `src/orebody/`. `tests/fixtures/pdf/` holds small hand-built PDFs (generate with PyMuPDF in a fixture script, never commit real filings). `tests/fixtures/llm/` holds recorded responses.
- Every numeric engine test states the hand computation in a comment.
- Matcher and units tests are parametrized tables; add a row for every bug found in the real reports.
