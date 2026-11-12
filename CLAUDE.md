# CLAUDE.md — Orebody

## What this is
AI-generated, source-linked equity research notes for under-covered copper juniors. Proof of concept for a professor. Read `SPEC.md` §0 and the last §12 entry before doing anything. Then build the next `TODO` feature in §11, and nothing else.

## Session protocol
1. Read SPEC.md §0 "Current state" + last session-log entry.
2. Announce which feature ID you are building.
3. Write the tests first, then the implementation. **The user runs every test, not Claude** (see "User runs the commands" below): Claude gives the exact command, the user runs it and pastes the output, and Claude iterates until it is green.
4. Update the feature's status, §0, and append a §12 entry **in the same commit** as the code.
5. One feature per commit. If a feature grows, split it into F<N>.<M>a/b in SPEC.md and say why.
6. Never mark `DONE` without pasting the passing test output (as reported by the user) in the session-log entry.

## User runs the commands (added 2026-11-11)
The user stays in control of everything that executes. Claude does not run tests, the pipeline, or anything that calls a network service or the Anthropic API.
- **Claude gives the line, the user runs it.** At each point where a check is needed, end the message with the exact command(s) in a code block, from the repo root, in the order to run them, with one line on what a pass looks like. Example:
  ```
  make lint test
  ```
  Pass: `All checks passed!` and `N passed`, no failures.
- **What this covers:** `make lint`, `make test`, `pytest` on single files, `make fetch`, every `orebody` command (`run`, `discover`, `crosscheck`, ...), live tests (`OREBODY_LIVE_EDGAR=1 ...`, `-m live`), and any script that downloads or writes data.
- **Wait for the report.** Do not continue past a check, mark anything `DONE`, or commit until the user has pasted the output. If the output shows a failure, say what failed and why before changing code.
- **Claude may still** read files, search the code, and write or edit code and docs; those change nothing until the user runs them.
- **Commits:** propose the commit (files and message) and make it only after the user says so.
- **Environment:** commands that call EDGAR need `OREBODY_SEC_CONTACT` (set in `.env`); live LLM runs need `ANTHROPIC_API_KEY`. Nothing loads `.env` automatically yet, so prefix such commands with `set -a; source .env; set +a;`.

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
13. **Verification before claiming done.** The user runs the command and pastes the output; read it, then say it passed. No "should work", and no claiming a pass from a run the user has not reported.
14. **Library docs.** Use Context7 MCP for PyMuPDF, FastAPI, Next.js, react-pdf, Anthropic SDK questions before guessing an API.
15. **Scope.** Do not build backlog items (SPEC §11 "Later") or anything not in the current feature's AC. If you think the spec is wrong, say so in the session log and ask; do not silently change the design.

## Layout
See SPEC.md §5.1. Keep it.

## Testing conventions
- `tests/unit/` mirrors `src/orebody/`. `tests/fixtures/pdf/` holds small hand-built PDFs (generate with PyMuPDF in a fixture script, never commit real filings). `tests/fixtures/llm/` holds recorded responses.
- Every numeric engine test states the hand computation in a comment.
- Matcher and units tests are parametrized tables; add a row for every bug found in the real reports.

## Data collection (how a company's drop folder is built)
Same method for every ticker; MARI was the first. The tool's job is to gather the documents, not the user's.
1. **Sources, in order:** the company website (technical reports, financials, MD&A, presentations, news), then EDGAR (S-K 1300 exhibits, 10-K/10-Q, 40-F/6-K; descriptive User-Agent, within rate limits), then SEDAR+ by hand only for what neither has (no scraping SEDAR+). Third-party mirrors (minedocs.com) only as a stopgap; replace with the original.
2. **Set per company:** every technical report ever published (history feeds the study-over-study graph), latest annual FS + MD&A, AIF if filed, latest quarterly FS + MD&A, latest corporate presentation, news releases for the trailing 12 months.
3. **Manifest:** `data/raw/<TICKER>/manifest.yaml` lists each file with `url` and `sha256`; dates not confirmed on SEDAR+ are marked `# approx`. The first `technical_report` listed is the current economic study, which `run` uses. `make fetch T=<TICKER>` rebuilds the folder on a fresh clone.
4. **HTML news pages have no sha256:** they carry session tokens and live quotes. Before any agent reads news, extract the article body only; a page saved today embeds today's share price, which breaks as-of discipline.
5. **News index:** `uv run python scripts/news_index.py` regenerates `docs/news_index.md` from the manifests.
6. **Check corporate changes when collecting:** sales of projects (Highland sold White Pine North), new listings (Gunnison → NYSE American, Lion → Nasdaq/CSE), production starts. A producer is no longer an under-covered junior; flag it for the sample.

## Product vision (future; not in scope until it is a feature in SPEC §11)
The end state is a website with one page per project. Each page has:
- **Project overview:** stage, jurisdiction, ownership, flagship study headline numbers, all source-linked.
- **History graph:** NPV, capex, resource and grade per study (PEA → PFS → FS), each point annotated with the metal price deck it used, so a higher deck is not mistaken for a better project.
- **Grouped by primary commodity:** copper projects are the PoC; any project whose manifest states another primary commodity (Au, Zn, Ni, ...) is kept, not dropped, and gets its own report section on the site (e.g. "Gold projects"). By-products are listed on each project page. `orebody check` records the commodity and by-products for every project (F1.6).
- **Recent news feed:** tagged (Funding, Deal, Study, Permits, Drilling, Production, Listing, People), newest first, with "what changed" in one line each.

What the desk page must show (agreed with the user 2026-11-11; spec each as a feature before building):
1. **One-screen deal sheet on top:** stage, next catalyst and its expected date, cash vs. quarterly burn (months of runway), funding gap to construction, and who is already in the capital stack (strategics, streams, royalties, e.g. Nuton/Rio Tinto at Gunnison and Lion, Wheaton at Northisle, ARM at Surge).
2. **Offtake status:** is concentrate or cathode already committed, to whom, and on what terms? Uncommitted tonnage is the origination opportunity a desk looks for first.
3. **Product quality:** concentrate grade, by-product credits, deleterious elements (As, Bi, Hg, F) and penalty risk, from the technical report's Item 19 (market studies) or metallurgy sections.
4. **Logistics:** port, rail or truck route, distance to smelter or SX-EW plant, from Item 18 (infrastructure).
5. **Re-pricing at the desk's own deck:** NPV/IRR recomputed at spot and at a user-entered price, side by side with the company's deck.
6. **"What changed since last note":** a diff between the current and previous study and between quarterly filings (capex, grade, schedule, cash), surfaced first.
7. **Location:** country, state/province, nearest town, coordinates and a map pin, from Item 4 (property description and location).
8. **Ownership:** who owns the project and in what share (e.g. Highland sold its 34% of White Pine North to Kinterra), the owner's type (public company, private company or fund, state-owned, or mixed/semi-state such as a government agency holding a stake or carried interest), plus royalty and stream holders. Source each line to the technical report (Item 4) or the latest MD&A/AIF.

Every number on the page clicks through to its source page. Stance language and disclaimer rules (ground rule 10) still apply.
