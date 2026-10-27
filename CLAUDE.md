# CLAUDE.md

Instructions for Claude Code in this repo. Read this, then `PROJECTLOG.md` (where the project stands) and the latest entry in `WORKLOG.md` (where the last session stopped) before doing anything. Both logs are local only: gitignored, never committed or pushed, so keep a backup outside the repo.

## Project

**Coverage for the Uncovered (working name: Orebody).** A multi-agent system that writes sourced research notes on under-covered junior mining companies, validated with a blinded expert evaluation that extends Francis and Zhang (2026). Full design is in `README.md`.

- **Owner:** Jess Tran (Purdue Finance + SCOM, accelerated BS/MSF). Solo project.
- **Audience:** a finance professor (an author of the paper this builds on) who will judge the work's rigor. Every claim, number and design choice should hold up to his reading.
- **Stance:** the system sells coverage and synthesis, not stock picks. No Buy/Hold/Sell ratings, no return claims, anywhere.

## How I work

1. **Remote Control check.** At the start of every session, call `ListAgents`. If no Remote Control sessions appear, say plainly: "Remote Control is disconnected."
2. **One phase at a time.** Work only on the current phase in `PROJECTLOG.md`. When it's done, stop and summarize. Don't start the next phase until I say so.
3. **Plan, then tests, then code.** For a new module: propose the plan in a few lines, write the tests and stubs, wait for my OK, then implement until the tests pass. Don't write implementation ahead of the agreed tests.
4. **Commit after every passing milestone.** Small commits with clear messages. Never commit with failing tests.
5. **Ask instead of guessing** when a choice affects results (a data source, an assumption, a threshold, a sample rule). Make the call yourself on routine engineering choices and say what you chose.
6. **Take a stance.** When I ask "A or B?", recommend one and give the reason. No menus without a pick.
7. **Number first, then the rule.** Explain with a concrete example ("NPV at $4.10/lb drops from $620M to $310M") before the general formula. Why before how.
8. **Short.** If I say something is too long, cut hard, not lightly.
9. **Don't edit tests to make them pass.** Tests are the agreed acceptance criteria. If one looks wrong, say so and stop.
10. **Don't tidy what you weren't asked to change.** If existing text or code looks wrong, flag it and leave it.

## Research integrity (non-negotiable)

- **Every figure is traceable.** Any number extracted from a filing is stored with its source document, page, and the raw text it came from. No figure enters a note without that record.
- **No hand-typed numbers in docs.** Every number in `README.md` or a write-up comes from a script output in `results/`. If a doc number doesn't match the code, flag it. Don't silently "fix" either one.
- **No look-ahead.** When a note is matched to a comparator, agents see only filings and prices dated on or before the comparator's publication date. Enforce this in code with an `as_of` date, and test it.
- **Pass conditions are frozen.** Stage pass conditions are recorded in `PROJECTLOG.md`. Don't change a threshold, test, or sample rule after seeing the data it applies to. If a change is needed, log it with the date and the reason *before* rerunning.
- **Report what failed.** Negative or null results go into the logs and the write-up just like positive ones.
- **Don't overclaim.** Say "evaluators perceived as comparable," not "as good as." Say "in this sample," not "in general." Underpowered results are labelled as underpowered.
- **No outside facts slipped in.** If a note or doc needs a fact that isn't in the source documents, flag it and ask. Don't fill it from general knowledge.

## Writing

- `README.md` and any write-up for the professor are **my writing.** Flag gaps, errors and structural problems, and suggest specific fixes, but don't rewrite my prose in your voice.
- Code comments, docstrings and generated notes are yours to write. Keep them plain and specific.
- Style for anything I'll read: spare, concrete, no filler, no hype words.

## Code conventions

- Python 3.12, managed with `uv`; tests with `pytest`; lint and format with `ruff` (config in `pyproject.toml`).
- Everything runs through `uv run`. Never activate the venv by hand, never `pip install`; add packages with `uv add`.
- Tests run offline. Network calls (EDGAR, prices, LLM) are mocked or read from fixtures.
- Type hints on public functions. Small, testable functions over large ones.
- Valuation math (DCF, breakeven, price-sensitivity interpolation) lives in pure functions with unit tests against hand-checked cases.
- LLM calls go through one wrapper that logs model, prompt version, temperature, token cost, and caches responses. That keeps runs reproducible and cheap.
- Prompts live in versioned files, not inline strings.

## Data and access

- **EDGAR:** use the official API with a descriptive User-Agent, and respect SEC rate limits. S-K 1300 technical report summaries are Exhibit 96.
- **SEDAR+:** no scraping. Documents are pulled manually into `data/raw/` and logged.
- **Prices:** settlement or delayed data only. Record the source and licence in `data/README.md`.
- `data/raw/` is gitignored. Never commit API keys; use `.env`.
- **Evaluator data (Stage 2):** anonymized IDs only. No names, emails or firms in the repo. IRB rules apply.

## Commands

```bash
uv sync                 # install
uv run ruff check . && uv run ruff format --check .   # lint (must pass before any commit)
uv run pytest           # run tests (must pass before any commit)
uv run pytest -k name   # run one test
```

Update this section as scripts are added.

## Repo layout (folders are created when their first module starts)

```
src/orebody/
  ingest/       # EDGAR client, manual SEDAR+ loader, technical-report section extractor
  agents/       # manager, project analyst, financial analyst, synthesis, verifier
  valuation/    # dcf, breakeven price, sensitivity interpolation
  verify/       # citation index, figure-vs-source checks
evaluation/     # pairing, blinding/format normalization, analysis (clustered SEs)
prompts/        # versioned prompt files
data/           # raw/ (gitignored), processed/
notes/          # generated research notes
results/        # every number used in docs comes from here
tests/
PROJECTLOG.md, WORKLOG.md   # local only, gitignored
```

## End of every session

1. Add an entry to `WORKLOG.md`: what was done, decisions made, open questions, and the next step.
2. If a phase finished, a decision changed the design, or a pass condition was tested, update `PROJECTLOG.md`.
3. Don't commit the logs. Commit only code and tracked docs.
