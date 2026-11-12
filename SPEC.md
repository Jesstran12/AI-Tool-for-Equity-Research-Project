# Orebody — Specification and Feature Log

> **Session protocol.** Every session: (1) read §0 "Current state" and the last §12 session-log entry; (2) pick the first `TODO` feature in §11 unless Current state says otherwise; (3) build it per CLAUDE.md; (4) set its status, update §0, append a §12 entry, commit with the code. Status values: `TODO` · `IN PROGRESS` · `DONE` · `BLOCKED(reason)` · `DEFERRED`. Never delete a feature; mark it `DEFERRED` and say why.

## 0. Current state

- **Phase:** 1–2 (ingestion and indexing). Phase D demo slice done 2026-11-04; F0.2, F0.3, F1.3–F1.6, F1.8a, F2.1a/b, F2.2 done 2026-11-11.
- **Last completed feature:** F4.3 (prompt versions + lock), 2026-11-12.
- **Next feature:** F5.1 (schemas for Sections 1–5); the first live SURG note once `ANTHROPIC_API_KEY` is set. F2.3 waits for 20 hand-labelled pages from the user. F0.1, F1.1, F1.2, F3.3, F4.1, F4.2, F6.1 are DONE via Phase D; F2.1, F3.1, F3.6, F5.3, F5.6, F7.1 are IN PROGRESS with the demo-slice subset built.
- **Blockers:** none. Demo fallback: `uv run orebody run MARI --as-of 2026-11-05 --spot 6.71 --deck-a 3.50 --deck-b 5.00 --provider fake` replays the recorded response.
- **Universe status:** rule-based (§10, D47). Drop folders: MARI, SURG, GCU, NCX, USCU, LEO, HI. Eligible by `orebody check` (2026-11-11): MARI, SURG, LEO, HI. MARI is missing 7 hand-collected files (no url in its manifest).
- **Repository:** github.com/Jesstran12/AI-Tool-for-Equity-Research-Project (commit authorship unified to Jess Tran 2026-11-11).
- **Spend to date:** US$0.34 of ≈ US$50 (D43) — one Opus 5.5 call on the MARI FS (US$0.3391) plus the D8 smoke test (US$0.0006)

## 1. Intent

Build the proof of concept named in the proposal's "Proposed next steps": a technical-report parser plus a five-agent pipeline that writes a five-section, fully source-linked research note for ~10 listed copper companies, with every number traceable to a page in a company filing, and the NPV rebuilt and re-priced rather than quoted. The audience for the PoC is a professor deciding whether this becomes a supervised project (independent study or thesis, spring 2027). The audience for the notes is a trading desk or resource investor who will throw the note away on the first wrong capex figure.

The evidence base is Francis & Zhang (2026): a four-agent GPT-4o/CrewAI system produced reports that general-population evaluators rated above Value Line (8.13 vs 6.64, 77% preference, n=194 pairs), finance grad students were split (51%, underpowered), LLM judges were unstable (48–96% by model), and no strategy generated alpha. The product therefore sells synthesis, speed, and coverage, never returns. What the paper did not measure, and what this PoC adds, is **factual accuracy**, via a Verifier agent and a claims ledger.

## 2. Goals, non-goals, anti-goals

**Goals (PoC, ~4 weeks of sessions)**
- G1. Generate a five-section note for each company in the universe from hand-collected filings, with every number and named fact in a claims ledger linked to document + page + quoted snippet.
- G2. Rebuild NPV parametrically from disclosed inputs; re-price at spot and user decks; print the gap vs the company's stated NPV.
- G3. Two-tier verification (deterministic matcher, then LLM) with an honest, measured flag rate. Stage 1 pass condition from the proposal: Verifier flags under 5% of figures; manual audit of notes finds no unsupported capex, NPV, or resource figure.
- G4. A local dashboard: company list, run trigger, split-view note + PDF page viewer with snippet highlight, ledger table, run trace, blinded compare, live re-pricing.
- G5. Full reproducibility and cost accounting per run, so the pipeline can later be the subject of the Stage 2 expert evaluation.
- G6. Deliverable for the professor: live dashboard demo, one exported PDF per company, and an auto-generated results summary (verification rate, cost, time per note, judge scores).

**Non-goals (PoC)**
- Automated fetching from SEDAR+/EDGAR (manual drop folder only).
- Web search by agents.
- Refresh-on-filing automation, subscriptions, auth, multi-user, hosting.
- Full annual cash-flow DCF, NSR/TC-RC modelling, multi-metal NPV.
- Commodities beyond copper (zinc/nickel by-products are handled only as disclosed credits).
- The Stage 2 evaluator-recruitment interface and statistics (the blinded compare view is a seed for it, not the thing).

**Anti-goals (would make this a failure even if it "works")**
- A number in a note that cannot be traced to a page.
- An invented economic estimate for a company that has not published one.
- A note that reads as an investment recommendation or carries a return claim.
- A pipeline whose output cannot be re-run and compared because prompts, model, or inputs were not recorded.
- LLM-judge scores presented as evidence of quality.

## 3. Decisions log

| ID | Decision | Source |
|----|----------|--------|
| D1 | Repo's first life is the PoC for the professor; research artifact, not a product. | user |
| D2 | Documents arrive via a manual drop folder `data/raw/<TICKER>/` with a `manifest.yaml`; no scraping. | user |
| D3 | NPV is rebuilt parametrically; reconciliation line vs company NPV is mandatory; company sensitivity table is a cross-check; annual-schedule DCF is a backlog feature. | user (on my recommendation) |
| D4 | Hand-rolled Python orchestrator on the Anthropic SDK; thin provider interface so another vendor's model can be plugged in (for self-preference checks). | user |
| D5 | Dashboard = FastAPI backend + Next.js frontend. | user |
| D6 | PDF parsing = PyMuPDF text per page + section index keyed to NI 43-101 items / S-K 1300 sections; vision-model fallback only for pages whose tables extract as garbage. | user |
| D7 | Verifier failure after max revision rounds → note is still released with failed claims visibly flagged; flag rate is a first-class metric. | user |
| D8 | Verifier is two-tier: deterministic number/entity matcher on the cited page first, LLM second. | user |
| D9 | Claim scope = every number and every named fact (entities, jurisdictions, permits, stage, dates). Section 5 analytical sentences are tagged `synthesis` and exempt. | user |
| D10 | Citation = document id + page + exact quoted snippet; viewer opens the PDF at the page and highlights the snippet by text search. | user |
| D11 | One note per company; flagship project named in the manifest; other projects get one line in the snapshot. | user |
| D12 | No economic study → Section 3 is an explicit "no economics disclosed" block with in-situ metal value at spot (labelled not a valuation) plus runway. | user |
| D13 | Prices: free delayed proxies via yfinance (COMEX HG=F for copper, plus configured proxies for Zn/Ni/Au/Ag) with `config/prices.yaml` manual override; every note records price, source, timestamp. | user |
| D14 | Normalize all figures to USD and metric at the FX rate stated in the source report (fallback: `config/fx.yaml`); keep original value/unit in the ledger; flag technical reports older than 24 months. | user |
| D15 | Every run has a hard `as_of` date; documents dated after it are excluded and the exclusion logged; price deck is as of that date. | user |
| D16 | Notes are author-agnostic (`author: agent | human`); hand-written comparator notes use the same schema, ledger, and viewer. | user |
| D17 | LLM-judge harness exists as a regression tool using the paper's rubric + accuracy; never used for product claims. | user |
| D18 | Budget envelope ≈ US$2 and ≈10 minutes per note. | user |
| D19 | Split-view note page: note left, PDF right, click-to-jump with highlight. | user |
| D20 | Live re-pricing in the dashboard via a pure-Python NPV endpoint; released note freezes base/spot/two default decks. | user |
| D21 | Dashboard views: company list + run trigger; claims ledger with filters; run trace; blinded compare. | user |
| D22 | Deliverable: dashboard demo + exported PDF notes + results summary. | user |
| D23 | No web search; the drop folder is the universe of truth. | user |
| D24 | Agents emit structured JSON (fields + claims array); Markdown is rendered by code, never by the model. | user |
| D25 | Stance = `Favourable / Neutral / Unfavourable on disclosed fundamentals`, no price target, no return forecast, fixed disclaimer in every note. | user |
| D26 | Storage = SQLite + files under `data/`; no Docker. | user |
| D27 | Ports: API **8114**, web **3014**. | user |
| D28 | Solo repo; SPEC.md and CLAUDE.md committed. | user |
| D29 | Ground rules: uv + ruff + pytest, TDD; pure-function core without LLM calls; reproducible runs with versioned prompts; small per-feature commits, no credit lines, SPEC.md updated in the same commit. | user |
| D30 | Universe proposed by Claude (§10), to be confirmed/edited by Jess Tran. | user |
| D31 | Models tiered: Project Analyst, Advisor, vision fallback, renderer-free = `claude-sonnet-5-5`; Financial Analyst and tier-2 Verifier = `claude-opus-5-5`. Per-agent model is config; a single-model run is one flag. | user |
| D32 | Section 4 = disclosed offtake/stream/royalty terms + computed uncommitted share of planned production; no NSR modelling. | user |
| D33 | Human overrides (mark claim verified, fix value, override stage/flagship) stored separately from agent output, in a later phase. | user |
| D34 | Max revision rounds = 3. | my call |
| D35 | Staleness flag threshold = 24 months from technical report effective date. | my call |
| D36 | "Deterministic" means: pinned model ids, fixed `effort`, versioned prompts, hashed inputs, full logs. Current Claude models reject `temperature`; reruns are *compared*, never assumed byte-identical. | my call (corrects the "temperature 0" ground rule) |
| D37 | Agent context is section-targeted, never the whole report: the Financial Analyst sees Items 1, 21, 22 (+19 for offtake, +4 for royalties); the Project Analyst sees Items 1, 4, 14, 15, 16, 20, 24, 25, 26 plus MD&A/news. This is how the $2 budget is met. | my call |
| D38 | Structured outputs via `output_config.format` with a JSON schema per agent; no prefill. | my call |
| D39 | Tier-1 matcher normalizes scale (M/B/k, Mlb/kt), thousands separators, currency symbols, and tolerates rounding to the precision printed in the source. | my call |
| D40 | Vision fallback model = `claude-sonnet-5-5` on a rendered page image at 150 dpi; triggered when a page's table-density heuristic says "table" but text extraction yields < N numeric tokens or broken row alignment. | my call |
| D41 | Pilot companies = Marimaca (MARI, demo company) and Solaris (SLS); documents collected by hand (F1.0) so real filings exist for Phase 2 fixtures and the first live run. Third pilot = Faraday (FDY), for the staleness-flag path. Foran was dropped on 2026-11-04: acquired by Eldorado Gold (closed 2026-04-14), shares delisted. | user; revised after web check |
| D42 | Cut line: after the CLI phase, run the three pilots end-to-end and keep them demo-ready (F7.5). If time runs short, cut in this order: judges (Phase 10) → secondary dashboard pages (ledger, trace, compare) → company count. Company count is cut last. | user |
| D43 | Total API spend ceiling ≈ US$50. Pilots may be run several times; the remaining companies get one pass each; judges on a subset (pilots + up to 2 more). Every live response is recorded as a `FakeProvider` fixture so fixes replay offline. Cumulative spend is printed by `orebody summary`. | user |
| D44 | Jess Tran hand-writes comparator notes (same template, same claims format) for MARI and SLS; the compare page shows agent vs human, blinded. | user |
| D45 | S-K 1300 section index (F2.2) is DEFERRED: no company in the universe files under S-K 1300. Revived if a US filer is added. | my call (reviewer finding) |
| D49 | Projects whose primary commodity is not copper are recorded, not dropped: `orebody check` keeps primary commodity and by-products, and the site will give each commodity its own report section. The PoC note pipeline stays copper-only (§10.1 rule 3). | user, 2026-11-11 |
| D48 | Every number gets a second source where one exists: primary copy from the company website, alternate from EDGAR (SEDAR+ by hand otherwise); the copies are compared on normalized numbers, not bytes (PDF vs HTML exhibit). A `differs` result blocks the claim from `verified` until a human resolves it. | user, 2026-11-11 |
| D47 | §10 universe is a rule plus a discovery step (10.1, 10.2), not a hand list. The evaluation sample is the PROJECTLOG Phase 1 sample (frozen 2026-10-27); the old §10 proposed list is superseded. | user, 2026-11-11 |
| D46 | Desk view (Phase 12): eight per-project features chosen for a trading-desk reader (deal sheet, offtake, product quality, logistics, re-pricing at the desk's deck, what changed, location, ownership). Volumes, peer table and alerts were considered and left out. Scheduled after Phase 11. | user, 2026-11-11 |

## 4. The note

### 4.1 Template (fixed, five sections)

| # | Section | Required fields (each a ledgered claim unless marked) | Owner agent |
|---|---------|------------------------------------------------------|-------------|
| 1 | Project snapshot | commodity(ies); jurisdiction (country, region); stage ∈ {exploration, PEA, PFS, FS, construction, production}; flagship project name; resource tonnage/grade/contained metal by category (M&I, Inferred); reserves (P&P) if any; mine life; other projects (one line each) | Project Analyst |
| 2 | Capital structure & funding | cash; debt; quarterly burn (computed from two balance dates, derivation shown); runway in quarters (computed); recent raises (date, amount, instrument); major shareholders (>5% if disclosed); streams/royalties (counterparty, %/rate, scope) | Financial Analyst |
| 3 | Economics | initial capex; sustaining capex; C1 and/or AISC; company base-case price; company NPV (rate) and IRR; **rebuilt NPV at base, spot, deck A, deck B** (computed); **reconciliation gap %** (computed); payback; sensitivity-table cross-check if present. If stage = exploration with no study: "No economic study disclosed" block + in-situ value at spot (computed, labelled) | Financial Analyst |
| 4 | Offtake & commercial terms | offtake agreements (counterparty, product, tonnage or %, term, pricing basis if disclosed); TC/RC exposure statement for concentrate producers (disclosed terms only); streams/royalties cross-referenced; **uncommitted share of planned production** (computed) | Financial Analyst |
| 5 | Catalysts, risks, view | catalysts (dated where disclosed); risks; stance ∈ {Favourable, Neutral, Unfavourable} "on disclosed fundamentals"; one-paragraph thesis citing only ledgered facts; fixed disclaimer | Investment Advisor |

Header on every note: company, ticker, exchange, as-of date, author (hidden in blinded views), verification rate, flagged count, price deck used, pipeline version, report-age flag.

### 4.2 Fixed disclaimer (verbatim in every note and PDF)

> This note is an automated synthesis of the company's public disclosures as of the stated date. It is not investment advice, contains no forecast of returns, and the stance expressed describes disclosed fundamentals only. Every figure links to its source page; figures marked "unverified" could not be matched to a source and should not be relied on.

### 4.3 Claim schema

```
claim_id        uuid
note_id         fk
section         1..5
field           e.g. "initial_capex"
claim_type      number | entity | date | synthesis
value_norm      float|str      (USD, metric)
unit_norm       str            (USD_M, t, kt, Mlb, pct, g_t, years, ...)
value_orig      str            (as printed)
unit_orig       str
currency_orig   str|null
fx_rate_used    float|null
doc_id          fk|null        (null only for synthesis)
page            int|null       (1-indexed)
quote           str|null       (exact snippet, ≤ 300 chars)
tier1_status    pass | fail | na
tier2_status    pass | fail | skipped
final_status    verified | unverified | synthesis
revision_round  int
override_id     fk|null        (Phase L1)
```

### 4.4 Verification statuses
- `verified`: tier-1 pass, or tier-1 fail + tier-2 pass.
- `unverified`: both tiers fail after the final revision round. Rendered with a visible tag.
- `synthesis`: exempt; must not contain a number that is not also a verified claim elsewhere in the note (renderer check).

## 5. Architecture

### 5.1 Components

```
data/raw/<TICKER>/            PDFs + manifest.yaml        (gitignored)
data/pages/<doc_id>/NNN.txt   extracted text per page     (gitignored, derived)
data/runs/<run_id>/           every prompt/response, timings, cost (gitignored)
orebody.sqlite                companies, documents, runs, notes, claims, judge_scores, overrides
src/orebody/
  ingest/      manifest loader, PyMuPDF extraction, hashing, as-of filter
  index/       NI 43-101 / S-K 1300 section index, table-garble detector, vision fallback
  core/        units.py, fx.py, npv.py, insitu.py, prices.py, matcher.py   (pure, no LLM)
  llm/         provider.py (interface), anthropic_provider.py, fake_provider.py, logging, cost
  agents/      manager.py, project_analyst.py, financial_analyst.py, advisor.py, verifier.py, schemas.py
  render/      markdown.py, pdf.py
  judge/       rubric.py, runner.py
  api/         FastAPI app
  cli.py
prompts/       one .md per agent, with a version header
config/        models.yaml, prices.yaml, fx.yaml, sections.yaml
web/           Next.js app
tests/         pytest; fixtures/ holds small hand-built PDFs and recorded LLM responses
```

### 5.2 Data flow (one run)

1. `orebody run <TICKER> --as-of YYYY-MM-DD [--deck-a X --deck-b Y]`
2. Load manifest; exclude documents dated after as-of (log them); hash included documents.
3. Ensure pages are extracted and the section index exists for each technical report.
4. Resolve price deck: spot from `core/prices.py` (yfinance, as-of close, or override), deck A/B from CLI or config defaults.
5. Manager builds task contexts (section-targeted page text) and calls, in order: Project Analyst → Financial Analyst → Investment Advisor. Each returns a structured object validated against its schema.
6. Financial Analyst's numeric outputs go through `core/npv.py`; computed claims are ledgered with `doc_id = null`, `claim_type = number`, and a `derivation` string listing the input claim ids.
7. Verifier tier 1 runs on every non-synthesis claim; tier 2 (LLM) runs on tier-1 failures and on all entity/date claims.
8. If any claim fails and `round < 3`: Manager re-calls the owning agent with the failed claims and the Verifier's reason; go to 7.
9. Renderer produces Markdown from the structured note; renderer check ensures no unledgered number appears in prose.
10. Persist note, claims, stats; write run trace and cost.

### 5.3 Agents

| Agent | Model (config) | Input | Output schema | Notes |
|-------|----------------|-------|---------------|-------|
| Strategy Manager | none (code) | manifest, index, config | — | Pure orchestration; builds contexts, enforces template, runs the revision loop. Not an LLM. |
| Project Analyst | sonnet-5-5 | Items 1, 4, 14, 15, 16, 20, 24–26 text; MD&A; news releases | `Section1`, `CatalystsRisks` (feeds §5) | Stage classification must cite the sentence that justifies it. |
| Financial Analyst | opus-5-5 | Items 1, 19, 21, 22 (+4 for royalties); financial statements; MD&A | `Section2`, `EconInputs`, `Section4` | Emits NPV *inputs* only; NPV itself is computed in code. |
| Investment Advisor | sonnet-5-5 | Sections 1–4 structured objects only | `Section5` | May not introduce new facts; may only reference claim ids. |
| Verifier (tier 2) | opus-5-5 | one claim + the cited page text (±1 page) | `{status, reason, suggested_quote?}` | Prompt forbids using outside knowledge. |
| Vision fallback | sonnet-5-5 | page image | page text (Markdown table) | Only on flagged pages; output cached to `data/pages`. |

Prompts live in `prompts/<agent>.md` with a `version:` header. A run records every prompt version.

### 5.4 Provider interface

`LLMProvider.complete(messages, schema, model, effort) -> (parsed, raw, usage)`. `AnthropicProvider` uses the official SDK with `output_config.format`, adaptive thinking default, server-side fallbacks enabled, streaming for long outputs. `FakeProvider` replays recorded JSON from `tests/fixtures/llm/` keyed by a hash of the request, so the whole pipeline runs in tests without a key. Adding a second vendor = one new class.

### 5.5 Reproducibility & cost
Each run stores: pipeline git SHA, model ids, effort levels, prompt versions, document hashes, as-of, price deck + source + timestamp, FX, every request/response, token usage, USD cost (from a `config/models.yaml` price table), wall time per agent. `orebody diff-runs A B` compares two runs' claims.

### 5.6 Database (SQLite)

`companies`, `documents` (doc_id, ticker, type, date, standard, path, sha256, pages), `runs`, `notes`, `claims`, `judge_scores`, `overrides`, `prices` (as-of cache). Schema managed by plain SQL migration files under `src/orebody/db/migrations/`.

## 6. Data inputs

### 6.1 Drop folder & manifest

```
data/raw/FOM/
  manifest.yaml
  2022-02-28_McIlvennaBay_FS_NI43-101.pdf
  2026-02-19_news_operations_update.pdf
  2025-12-31_FS_annual.pdf
  2026-03-31_MDA_Q1.pdf
```

```yaml
ticker: FOM
exchange: TSX
name: Foran Mining Corporation
flagship_project: McIlvenna Bay
primary_commodity: Cu
by_products: [Zn, Au, Ag]
jurisdiction: {country: Canada, region: Saskatchewan}
reporting_currency: CAD
documents:
  - file: 2022-02-28_McIlvennaBay_FS_NI43-101.pdf
    type: technical_report        # technical_report | annual_financials | quarterly_financials | mdna | aif | news_release | presentation
    standard: NI43-101            # NI43-101 | SK1300 | JORC | none
    effective_date: 2022-02-28
    filing_date: 2022-03-15
    title: "McIlvenna Bay Feasibility Study"
    project: McIlvenna Bay
```

`filing_date` is what the as-of filter uses; `effective_date` drives the staleness flag.

### 6.2 Section index

`config/sections.yaml` maps NI 43-101 Items 1–27 and S-K 1300 §229.601(b)(96) sections to regex heading patterns. The indexer finds each item's start page by heading match + table-of-contents cross-check and stores `(doc_id, item, start_page, end_page)`. Items not found are logged; agents receive what was found plus the TOC pages.

### 6.3 Prices & FX
`core/prices.py`: `spot(commodity, as_of) -> Price(value, unit, source, timestamp)`. Order: `config/prices.yaml` override → yfinance proxy (HG=F copper; others configured) → error. FX: report-stated rate from the Financial Analyst's `EconInputs.fx_stated` claim → `config/fx.yaml` → error. Units: copper always shown in USD/lb and USD/t.

## 7. NPV engine (`core/npv.py`, pure)

Inputs (all from ledgered claims or explicit defaults recorded in the note):
`mine_life_years`, `annual_payable_metal` (t), `price` (USD/t), `unit_cost` (USD/t, C1 net of by-products if disclosed, else AISC), `initial_capex` (USD M), `sustaining_capex_total` (USD M, spread evenly over production years), `construction_years` (default 2, capex spread evenly), `ramp_up_year1_fraction` (default 0.7), `tax_rate` (effective; from report, default 0.30 flagged), `discount_rate` (from report, usually 0.08).

Outputs: `npv`, `irr`, `payback_years`, annual cash-flow table (for the trace). Run at base, spot, deck A, deck B. `reconciliation_gap = (npv_rebuilt_base - npv_company) / npv_company`. If a sensitivity table exists, compare rebuilt-at-each-price to the table's values and report max deviation.

Explorers: `core/insitu.py`: Σ(tonnes × grade × price) by category, labelled "in-situ value, not a valuation".

Tests: hand-computed fixtures (3 synthetic projects), IRR bracket test, zero-mine-life edge, negative NPV, sustaining-capex spreading.

## 8. Dashboard

### 8.1 API (FastAPI, port 8114)
`GET /companies` · `GET /companies/{ticker}` · `POST /runs` {ticker, as_of, deck_a, deck_b} (background task, returns run_id) · `GET /runs/{id}` (status, stats) · `GET /runs/{id}/trace` · `GET /notes/{id}` (structured + markdown) · `GET /notes/{id}/claims?status=&section=&tier=` · `GET /documents/{id}/file` (PDF) · `GET /documents/{id}/pages/{n}` (text) · `POST /npv` (inputs → outputs, no LLM) · `POST /judge/{note_id}` · `GET /judge/{note_id}` · `GET /compare?a=&b=` (labels stripped) · `GET /notes/{id}/export.pdf`.

### 8.2 Pages (Next.js, port 3014)
- `/` companies: ticker, name, stage, docs count, last run, verification rate, [Run] button with as-of + decks.
- `/notes/[id]` split view (D19): left = rendered note with clickable claims (verified = underline, unverified = red tag, synthesis = plain); right = pdf.js viewer at the cited page with text-layer highlight of `quote`; bottom-right = claim card (status, tiers, original value/unit, derivation for computed claims). Price-deck panel (D20) with inputs for spot/deck A/deck B recomputes Section 3 numbers live.
- `/notes/[id]/ledger` table with filters and CSV export.
- `/runs/[id]` trace: timeline of agent calls, each expandable to prompt/response/usage/cost; revision rounds shown as groups.
- `/compare` two notes side by side, author hidden, with a reveal toggle and judge scores below.

## 9. Evaluation harness

`orebody judge <note_id> --models m1,m2`: each judge model receives the anonymized note Markdown and scores 1–10 on clarity/structure, depth, data relevance, logical consistency, actionable insight (the paper's five) plus **factual accuracy** (judge is given the ledger with statuses), and returns a short justification. Scores stored per (note, model, rubric_version). `orebody summary` writes `reports/summary.md`: per-company verification rate, tier-1 pass rate, unverified count by section, cost, wall time, judge scores, reconciliation gap.

## 10. Universe (rule-based, not a fixed list)

Revised 2026-11-11 (D47). The tool is meant to cover every mining project whose documents it can get, so the universe is defined by a rule and found by a discovery step, not typed in by hand.

### 10.1 Eligibility rule
A project is in the universe when all of these hold on the as-of date:
1. **Listed owner:** the project (or a majority/operated interest) belongs to a listed company, so disclosure obligations apply.
2. **Technical report accessible:** at least one NI 43-101 technical report or S-K 1300 technical report summary is downloadable from the company website, EDGAR, or SEDAR+ (by hand), and is filed on or before the as-of date.
3. **Primary commodity in scope:** copper for the PoC (copper/zinc for Stage 1, PROJECTLOG); other commodities after L10.
4. **Readable:** the report has a text layer or passes the vision fallback (F2.4), and the section index (F2.1, or F2.2 for S-K 1300) finds its items.

Stage decides the Section 3 path, not eligibility: a project with a PEA/PFS/FS gets the economics path; an exploration-stage report gets the "No economic study disclosed" block (ground rule 4).

### 10.2 Discovery (how projects enter)
Discovery finds candidates and records why each one is in or out (see F1.5, F1.6). Sources, in order: EDGAR full-text search for S-K 1300 technical report summaries (Ex. 96) and 40-F/6-K filers; company websites; SEDAR+ by hand. A candidate becomes a drop folder only when the rule in 10.1 passes. Every exclusion is logged with its reason (acquired, no report, not copper-primary, unreadable).

### 10.3 Evaluation sample (frozen)
The Phase 1 sample in `PROJECTLOG.md` ("Phase 1 sample", locked 2026-10-27) is the sample the pass conditions are measured on. It is a fixed subset drawn from the universe and is not edited without a dated Decisions entry there. The earlier proposed list in this section (Kodiak, Hot Chili, Los Andes, Solaris, Western, NGEx, Taseko, ...) is superseded; MARI stays as the demo company.

### 10.4 Collected so far
Generated from `data/raw/*/manifest.yaml`, not maintained by hand: as of 2026-11-11 the drop folders are MARI, SURG, GCU, NCX, USCU, LEO, HI. Of the frozen sample, SURG, GCU and LEO are collected; Ivanhoe Electric, Sandfire Black Butte, Faraday (Copper Creek PEA), Edge Copper, IDEX, Oreterra and Star Copper are not yet (Oreterra and Star Copper reports exist in the old workspace and are exploration-stage).

## 11. Feature log

Each feature: acceptance criteria (AC) are the definition of done. Status column is updated by the session that completes it.

### Phase D — Demo slice (2026-11-05), detailed in `DEMO_PLAN.md`
Built out of order so a professor demo exists on 2026-11-05. Each row maps to a later feature (right column); trimmed ones stay `IN PROGRESS` there after the demo.
| ID | Feature | AC | Maps to | Status |
|----|---------|----|---------|--------|
| D0 | Demo company = MARI: report + manifest in `data/raw/MARI/`; API key available | files present; key in `.env` worked for the live run | F1.0 | DONE |
| D1 | Scaffold (uv, ruff, pytest, Makefile, gitignore) | `make lint test` green | F0.1 | DONE |
| D2 | Manifest loader | tests | F1.1 | DONE |
| D3 | PDF page extraction + synthetic fixture report | tests | F1.2 | DONE |
| D4 | NI 43-101 item index | tests on fixture; Items 1/21/22 found on the real report | F2.1 (trimmed) | DONE |
| D5 | Units parser | 12 parametrized rows + FX/lb conversions | F3.1 (trimmed) | DONE |
| D6 | NPV engine | two hand-computed fixtures | F3.3 | DONE |
| D7 | Tier-1 matcher | tests | F3.6 (trimmed) | DONE |
| D8 | Provider interface, FakeProvider, AnthropicProvider, cost | fake tests + one live fixture | F4.1, F4.2 | DONE |
| D9 | Financial Analyst agent, schemas, page-bounded context, prompt v1 | tests with fake fixtures | F5.3 (trimmed, Section 3 only) | DONE |
| D10 | Tier-1 verification pass | tests | F6.1 | DONE |
| D11 | Section 3 Markdown renderer with footnotes, reconciliation, disclaimer | tests | F5.6 (trimmed) | DONE |
| D12 | `orebody run` CLI, fake end-to-end, first live note, `reports/audit.md` | live note with rate ≥ 0.8, cost ≤ US$2 | F7.1 (trimmed) | DONE |
| D13 | SPEC.md log updated after the demo; §0 points back to F0.2 | this file | — | DONE |

### Phase 0 — Scaffold
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F0.1 | Repo scaffold: `uv` project, `src/orebody`, `tests/`, `Makefile` (`make lint test`), `.gitignore` (data/, *.sqlite, .env, web/node_modules), `.env.example` | `make lint test` passes with one placeholder test | DONE (D1) |
| F0.2 | Config loader (`orebody.config.load_config`) + `config/models.yaml` (per-agent model + effort + USD prices; agents missing from the file get D31 defaults; sampling/thinking keys rejected), `config/sections.yaml`, `config/prices.yaml` (proxies, overrides with source, default decks), `config/fx.yaml` (rates with source); `single_model` override (D31) | typed config object, tests for defaults and override | DONE (2026-11-11; `run` reads agent + prices from it. Default decks in prices.yaml are not yet used by `run`: wiring them changes notes run without --deck-a/b, so it waits for the user's OK) |
| F0.3 | SQLite schema + migration runner (§5.6): `orebody.db` (connect with foreign keys on, `NNNN_name.sql` files applied once each in a transaction, recorded in `schema_migrations`), `0001_initial.sql` with the eight tables; claims per §4.3 with CHECKs for ground rules 3 and 10 | `orebody db init` creates all tables; tests | DONE (2026-11-11; `data/orebody.sqlite` created at version 1) |

### Phase 1 — Ingestion
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F1.0 | **Pilot documents (by hand):** technical report, latest annual + quarterly financials, MD&A, and recent news for MARI and SLS into `data/raw/<TICKER>/` with a draft `manifest.yaml` (D41) | both folders exist; manifests list every file with dates | IN PROGRESS (MARI done 2026-11-04; SLS pending) |
| F1.1 | Manifest loader + validation (§6.1) | bad manifest fails with a clear message; tests | DONE (D2) |
| F1.2 | PyMuPDF page extraction → `data/pages/<doc_id>/NNN.txt`, sha256, page count, idempotent | fixture PDF extracts; re-run is a no-op | DONE (D3) |
| F1.3 | As-of filter with exclusion log (`ingest/asof.py`): every manifest document filed after as-of is excluded with its reason; `run` uses the first technical report filed by as-of (falls back to the study current that day) and writes `asof.json` in the run dir | docs after as-of excluded; log lists them; tests | DONE (2026-11-11; SURG at as-of 2026-06-30 uses the 2023 Berg PEA, 11 later documents excluded) |
| F1.4 | `orebody ingest <TICKER>` CLI (`ingest/register.py`): upserts the company and each present document (sha256, pages, relative path, url); doc_id = `TICKER/<file stem>`; outcomes added / unchanged / changed / missing / mismatch (manifest sha256 differs: not registered) | registers documents in DB | DONE (2026-11-11; MARI 20 registered + 7 missing (hand-collected files with no url), SURG 20 registered) |
| F1.5 | **Discovery** (`orebody discover`, D47): EDGAR full-text search for S-K 1300 Ex. 96 summaries and 40-F/6-K mining filers (official API, descriptive User-Agent, rate-limited), plus a hand-kept `config/candidates.yaml` for SEDAR+-only names; writes `data/universe/candidates.json` with company, project, source, report found (y/n), and exclusion reason. Absorbs L4. | offline test on recorded EDGAR responses finds the planted Ex. 96 filer and skips a non-mining filer; each candidate has a source URL and a reason when excluded | DONE (2026-11-11; live: 66 included, 27 excluded. Primary-commodity filter not applied yet, so gold/uranium/lithium filers and majors are included: that is F1.6) |
| F1.6 | **Eligibility check** (`orebody check <TICKER> --as-of`): applies §10.1 to a drop folder: listed owner, technical report filed ≤ as-of, primary commodity (from the manifest, never inferred), text layer (≥ 90% of pages with ≥ 20 chars; a scan has 0), items found (Item 1 + ≥ 4 items; S-K 1300 fails until F2.2). Reports the Section 3 path (economics if Items 21/22, else no-study) and records primary commodity + by-products for every project (D49). | fixture folders: one passes, one fails per rule, each with the rule named in the message; a non-Cu project is recorded with a note for a separate commodity section | DONE (2026-11-11; live: SURG and MARI eligible on the economics path, LEO not eligible: 0 items, un-numbered headings) |
| F1.7 | **Collection** (`orebody collect <TICKER>`): turns a passing candidate into a drop folder by the CLAUDE.md "Data collection" method and writes the manifest with url + sha256 (generalizes `scripts/fetch.py` and the 2026-11-11 hand collection). | fixture site + recorded EDGAR index produce a valid manifest; re-run is a no-op; HTML news stored without sha256 | TODO |
| F1.8a | **Source cross-check, retrieval and comparison** (D48): `ingest/alternate.py` finds the EDGAR copy of each collected document (technical report by project name, else by content: EX-96/EX-99 within two years, stated effective date must equal the manifest's, numeric overlap ≥ 0.90; annual within 180 days; interim within 90 days); `core/crosscheck.py` compares (`identical`/`consistent`/`differs`); files whose own URL is on sec.gov are `same_source`. Results go to a sidecar `data/raw/<T>/crosscheck.json` (not the manifest: rewriting YAML would drop its hand comments); alternates cached in `alt/`. `orebody crosscheck <TICKER>`. | unit tests on hand-built texts and synthetic hits; Lion Yerington PFS company PDF vs EDGAR Ex. 99.1 agree on NPV 694/975, IRR 14.6/16.9, payback 6.7 | DONE (2026-11-11; live LEO: PFS consistent 0.95; GCU: 2026 PEA best overlap 0.87, unresolved because the EDGAR copy holds tables as images) |
| F1.8b | **Cross-check on claims:** each claim shows its document's cross-check status; a `differs` result blocks `verified` until a human resolves it (D48). Split from F1.8 because claims are persisted only from F5.x/F0.3. | fixture claim from a `differs` document cannot reach `verified` | TODO |

### Phase 2 — Technical report index
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F2.1a | NI 43-101 item index: numbered headings, plus fallbacks for un-numbered layouts (`page_marker`: "Page N-1"; `subsection`: un-numbered capitals heading + "N.1" + upper-case title, longest increasing chain); `detect_index` keeps the method with the most items and reports it | fixture items with correct pages; un-numbered layouts on hand-built pages; real reports: MARI 27 items (numbered), Copperwood FS 27 (page_marker; Items 1/21/22 on pp. 29/413/441), Lion Yerington PFS 25 (subsection; pp. 24/336/361) | DONE (D4 slice + 2026-11-11 fallbacks) |
| F2.1b | TOC cross-check: compare index start pages with the TOC's printed page numbers (offset-corrected) and flag disagreements | flags a planted wrong start page on a fixture; no false flags on MARI | DONE (2026-11-11 in `index/toc.py`; real offsets MARI +25 (27 items), SURG +25, Lion S-K 1300 +20, no flags; shown as a NOTE in `orebody check` since 2026-11-12. Known limit: un-numbered contents lines (Lion PDF "INTRODUCTION ..... 1") cannot be tied to an item, so the check reports "not possible") |
| F2.2 | S-K 1300 section index (`index/sk1300.py`, `config/sections_sk1300.yaml`): HTML exhibits split at CSS page breaks (`html_pages`), numbered `N.0` + title headings, contents pages = ≥ 5 titled headings; costs/economics are Items 18/19 (`ECONOMICS_ITEMS`); eligibility uses it for SK1300 reports and `html_pages` for any HTML report | same on an S-K 1300 fixture; items found on the Lion Yerington Ex. 99.1 | DONE (2026-11-11; Lion Ex. 99.1: 412 pages, Items 1/18/19/25 on pp. 21/345/372/406) |
| F2.3 | Table-garble detector | precision/recall measured on 20 hand-labelled pages from the pilot reports, logged in tests | TODO |
| F2.4 | Vision fallback (sonnet-5-5, page image → Markdown table), cached | flagged page re-extracts; cost logged | TODO |

### Phase 3 — Deterministic core
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F3.1 | `core/units.py`: scale/unit/currency parsing and normalization (D39) | 40+ parametrized cases incl. "US$1,240 M", "C$1.2 billion", "412 Mt @ 0.48% Cu", "2.1 Blb", "g/t", "short tons" | DONE (2026-11-12: 62 rows (12 Phase D + 50), `parse_tonnage_grade`, exact short-ton factor) |
| F3.2 | `core/fx.py`: USD identity → report-stated rate → config/fx.yaml (dated ≤ as-of) → error; every resolution carries its source | stated-rate precedence, fallback, error | DONE (2026-11-12; not yet wired into `run`: that comes with F5.3, where the stated rate arrives as a claim) |
| F3.3 | `core/npv.py` (§7) | hand-computed fixtures match to 0.1%; IRR, payback | DONE (D6; audit.md asks for expansion capex + production profile later) |
| F3.4 | `core/insitu.py` | fixture match | TODO |
| F3.5 | `core/prices.py` with yfinance + override + as-of | override wins; as-of close used; offline test via recorded data | TODO |
| F3.6 | `core/matcher.py` tier-1 verifier | finds normalized numbers and entity strings on page text; rounding tolerance; 30+ cases | DONE (2026-11-12: `number_match` exact/rounded/rescaled, `entity_on_page`, 50 cases; `verify/tier1.py` uses both; exact-match decimal-prefix bug fixed) |

### Phase 4 — LLM layer
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F4.1 | `LLMProvider` interface + `FakeProvider` replay | pipeline unit tests run without API key | DONE (D8) |
| F4.2 | `AnthropicProvider` with structured output, logging to `data/runs/`, usage + cost accounting | one live smoke test (skipped without key) records request/response files and cost | DONE (D8; logs to data/runs/<run_id>/ and tests/fixtures/llm/) |
| F4.3 | Prompt files with version headers + loader (`llm/prompts.py`), `prompts/versions.lock` (version + text sha256), `orebody prompts check|lock` | run records prompt versions | DONE (2026-11-12; run row stores {name: {version, sha256}}) |

### Phase 5 — Agents and note
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F5.1 | Pydantic schemas for Sections 1–5, EconInputs, Claim (§4.3) | schema round-trip tests | TODO |
| F5.2 | Project Analyst (context assembly per D37, prompt, parse) | on fixture company with FakeProvider produces valid Section1 with claims | TODO |
| F5.3 | Financial Analyst → EconInputs → `core/npv.py` → Section 3 with computed claims + reconciliation + sensitivity cross-check; Section 2 runway; Section 4 uncommitted share | fixture run yields all computed fields with derivations | IN PROGRESS (D9: Section 3 only; remaining AC: derivations on computed claims, sensitivity cross-check, Section 2 runway, Section 4) |
| F5.4 | Investment Advisor constrained to claim ids; stance + disclaimer | advisor output referencing an unknown claim id fails validation | TODO |
| F5.5 | Manager orchestration (sequential, state passing, run record) | end-to-end fixture run produces a note row | TODO |
| F5.6 | Markdown renderer + unledgered-number check | renderer raises on a prose number not in ledger | IN PROGRESS (D11: Section 3 renderer; remaining AC: unledgered-number check on prose) |

### Phase 6 — Verification
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F6.1 | Tier-1 pass over all claims, statuses persisted | fixture: known-good claims pass, planted bad claim fails | DONE (D10; statuses persisted in run_dir/claims.json until F0.3 adds the DB) |
| F6.2 | Tier-2 LLM verifier (opus-5-5) with page ±1 context, outside knowledge forbidden | FakeProvider tests; prompt reviewed | TODO |
| F6.3 | Revision loop (max 3) re-calling the owning agent with failures | fixture: planted failure corrected in round 2; unresolved failure released as `unverified` | TODO |
| F6.4 | Run stats: verification rate, tier-1 rate, unverified by section, cost, time | stored on run; `orebody run` prints them | DONE (2026-11-12: `verify/stats.py`, `db/runs.py`, migration 0002 `runs.stats`; `run` writes running → done/failed with git SHA, documents used/excluded, price deck, models, prompt version) |

### Phase 7 — CLI completeness
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F7.1 | `orebody run <TICKER> --as-of --deck-a --deck-b` | full live run on one real company | IN PROGRESS (D12: live run on MARI done; remaining AC: as-of document filtering beyond the technical report, DB registration, `orebody summary`) |
| F7.2 | `orebody export <note_id> --pdf` (citations as footnotes, disclaimer, unverified tags) | PDF opens; footnotes correct | TODO |
| F7.3 | `orebody diff-runs A B` | claim-level diff output | TODO |
| F7.4 | `orebody note import <markdown+claims.yaml> --author human` (D16) | human note stored and rendered identically | TODO |
| F7.5 | **Pilot notes, demo-ready (D42):** collect SLS and FDY documents; run MARI, SLS, FDY live end-to-end; fix what breaks; record all live responses as fixtures; export PDFs | three released notes with stats; cumulative spend logged | TODO |

### Phase 8 — API
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F8.1 | FastAPI app on 8114 with endpoints in §8.1, background run task | OpenAPI docs render; tests with TestClient | TODO |
| F8.2 | PDF + page text serving, `/npv` pure endpoint | tests | TODO |

### Phase 9 — Dashboard
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F9.1 | Next.js scaffold on 3014, API client, companies page with run trigger | lists companies, starts a run, shows status | TODO |
| F9.2 | Note split view with pdf.js, click-to-jump, snippet highlight, claim card | clicking a claim lands on the right page with highlight for ≥ 90% of verified claims on a real note | TODO |
| F9.3 | Ledger page with filters + CSV | works | TODO |
| F9.4 | Run trace page | works | TODO |
| F9.5 | Live re-pricing panel (D20) | NPV updates without an LLM call | TODO |
| F9.6 | Blinded compare page with reveal toggle | works | TODO |

### Phase 10 — Judges and summary
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F10.1 | Judge rubric + runner (§9), ≥ 2 models configurable | scores stored | TODO |
| F10.2 | `orebody summary` → `reports/summary.md` | table generated from DB | TODO |

### Phase 11 — The ten notes (the deliverable)
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F11.1 | Confirm universe; collect documents + manifests for the remaining 7 | all manifests validate | TODO |
| F11.2 | Run the remaining 7 once each (D43); fix parser/prompt issues offline via fixtures; selective re-runs only | 10 notes released | TODO |
| F11.3 | Manual audit of capex, NPV, resource figures on every note (recorded in `reports/audit.md`) | no unsupported capex/NPV/resource figure, or each exception documented | TODO |
| F11.4 | **Human comparator notes (Jess Tran, by hand, D44):** MARI and SLS in the note template with a claims file; import via F7.4 | two human notes in the DB, blinded compare works | TODO |
| F11.5 | Judge pilots + up to 2 more (D43); export PDFs; `orebody summary`; demo script in `reports/demo.md` | deliverable complete | TODO |

### Phase 12 — Desk view (D46)
A per-project page for a trader or concentrate buyer, built on the ledgered claims of the note. Scheduled after Phase 11 (the deliverable comes first). Every field is a ledgered claim or a computed claim with a derivation; a field the documents do not disclose shows "Not disclosed", never an estimate (ground rule 4).
| ID | Feature | AC | Status |
|----|---------|----|--------|
| F12.1 | **Deal sheet** (top of page): stage, next catalyst + expected date, cash, quarterly burn, runway, funding gap to construction, capital stack (strategic holders, streams, royalties). Reuses Section 2 and Section 5 claims (F5.3, F5.4). | funding gap = initial capex − cash − committed funding, computed with derivation listing input claim ids; fixture with two funders and one stream renders all fields; a missing catalyst date renders "Not disclosed" | TODO |
| F12.2 | **Offtake status:** per agreement counterparty, product, tonnage or %, term, pricing basis; uncommitted share of planned production. Extends Section 4 (F5.3). | fixture with one partial offtake shows committed and uncommitted shares summing to 100%; no-offtake fixture shows "No offtake disclosed" | TODO |
| F12.3 | **Product quality:** concentrate or cathode grade, by-product credits, deleterious elements (As, Bi, Hg, F, others disclosed) and any disclosed penalty terms, from Items 13 and 19. | each element value ledgered to its page; penalty risk stated only where the report states a threshold or penalty (no thresholds supplied by the tool); fixture report covers both cases | TODO |
| F12.4 | **Logistics:** port, route (rail/truck/pipeline), distance to port and to smelter or SX-EW plant, power and water source, from Item 18. | fixture Item 18 yields all fields with pages; distances normalized to km by `core/units.py` with a parametrized test row per unit seen | TODO |
| F12.5 | **Re-pricing at the desk's deck:** user-entered Cu price (and by-product prices where L7 exists) next to company deck, spot, deck A, deck B. Extends F9.5 (D20). | NPV/IRR update without an LLM call; company-deck column reproduces the Section 3 rebuilt NPV exactly | TODO |
| F12.6 | **What changed since last note:** diff of the current vs previous technical report (capex, opex, NPV, IRR, grade, resource, mine life, start year, price deck) and of the latest two quarterly filings (cash, burn, debt, shares out). Shown first on the page. Uses the full study history in the manifest. | fixture pair of studies lists every changed field with old value, new value, both sources, and % change; price-deck change is listed beside NPV change; unchanged fields omitted | TODO |
| F12.7 | **Location:** country, state/province, nearest town, coordinates, map pin, from Item 4. | `core/geo.py` (pure) converts degrees-minutes-seconds and UTM to decimal lat/long, parametrized tests incl. the Trek "57˚ 01' 34" N / UTM Zone 9" format; map renders the pin | TODO |
| F12.8 | **Ownership:** project owner(s) and % interest, owner type ∈ {public company, private company or fund, state-owned, mixed (state agency stake or carried interest)}, royalty and stream holders, recent ownership changes. From Item 4, latest MD&A/AIF, and news. | fixture with a JV + royalty renders shares summing to 100%; owner type is set only from a disclosed fact (cited), otherwise "Not disclosed"; a sale in the news (e.g. Highland → Kinterra, White Pine North) appears as an ownership change with date | TODO |

### Later (backlog, not scheduled)
| ID | Feature | Why deferred |
|----|---------|--------------|
| L1 | Human overrides in dashboard (D33) | after core pipeline |
| L2 | Annual cash-flow schedule DCF when disclosed | D3 |
| L3 | Web fetch with URL + snapshot citations | D23 |
| L4 | EDGAR API ingestion for S-K 1300 filers | moved into F1.5 (D47) |
| L5 | Postgres migration + hosted evaluator interface for Stage 2 | multi-user only |
| L6 | NSR / TC-RC payability model | D32 |
| L7 | Multi-metal NPV, by-product revenue lines | §7 single-metal |
| L8 | Refresh-on-filing watcher | product feature |
| L9 | Cross-vendor Verifier (self-preference check) | needs second API account; provider interface already allows it |
| L10 | Other-commodity universes (zinc, nickel, gold, ...), each as its own report section on the site (D49) | after copper proves out |
| L11 | S-K 1300 section index (was F2.2) | back in Phase 2 as F2.2 (D47) |

## 12. Session log

- **2026-11-04** — Interview completed; SPEC.md and CLAUDE.md written. No code. Next: F0.1.
- **2026-11-04 (later)** — Professor demo moved to 2026-11-05. Wrote `DEMO_PLAN.md` (Phase D, 13 tasks, Section-3-only vertical slice for one company). §0 now points at D1; after the demo, resume at F0.2. No code yet.
- **2026-11-04 (later still)** — Web check found Foran acquired by Eldorado Gold (closed 2026-04-14); removed from universe and pilots, NGEx added. Collected the MARI drop folder from marimaca.com (8 documents incl. the 361-page FS technical report, effective 2025-08-25, filed 2025-10-09) and wrote `data/raw/MARI/manifest.yaml`. Q3 2026 financials not yet posted. Demo company = MARI.

- **2026-11-04 (Phase D)** — Built DEMO_PLAN.md Tasks 1–12 (commits D1…D12b, one per task, TDD throughout). Live run on the MARI FS: `uv run orebody run MARI --as-of 2026-11-05 --spot 6.71 --deck-a 3.50 --deck-b 5.00` → stats line `MARI-2026-11-05-104923: verified 10/10 rate=1.00 cost=US$0.3391 seconds=0.1 items_missing=[]` (the first live call, run 104632, recorded fixture `1bc990a873026319.json` then aborted because the model invented a doc id; the pipeline now stamps `doc_id`, and later runs replay the recording). Hand audit in `reports/audit.md`: all ten figures correct; rebuilt base-case NPV US$570 M vs stated US$709 M (−19.6%), explained by the parametric model shape, nameplate vs LOM-average production, and the omitted US$77 M expansion capital. Plan deviations (all ledgered): TOC detection changed to a contiguous run of dot-leader pages (the plan's 'largest page ≤ 15' rule put Items 21–27 on their TOC entries); renderer escapes Markdown control characters in model text (security review); FakeProvider replays recorded cost; CLI refuses a technical report filed after `--as-of`. Spot price US$6.71/lb was a 2026-10-13 quote (no live feed yet). `make lint test`: `................                                                         [100%] 87 passed, 1 skipped in 1.07s`. Next: F0.2.

- **2026-11-11** — Spec-only session, no pipeline code. Added Phase 12 "Desk view" (F12.1–F12.8, D46) at the user's request; scheduled after Phase 11. Also this session (separate commits): merged the AI-Tool-for-Equity-Research-Project workspace (logs and CLAUDE.local.md moved; its companies reviewed), collected drop folders with url + sha256 manifests for SURG, GCU, NCX, USCU, LEO, HI and news for all of them plus MARI, added `make fetch T=<TICKER>` and `docs/news_index.md`. These tickers differ from the §10 universe (SLS, FDY pilots); reconciling them is OQ5. Matcher gaps found: Lion Yerington PFS and Highland Copperwood FS use un-numbered item headings, so F2.1 finds no items (needs a parametrized row under F2.1). No `make lint test` change to report beyond: `89 passed, 1 skipped`.
- **2026-11-11 (later)** — Rewrote §10 as a rule-based universe with discovery (D47): eligibility rule 10.1, discovery 10.2, evaluation sample = PROJECTLOG Phase 1 sample (frozen 2026-10-27), collected list 10.4. Added F1.5 discover, F1.6 eligibility check, F1.7 collect; F2.2 S-K 1300 index back to TODO (reverses D45); L4 folded into F1.5. OQ1 and OQ5 answered. No code. `make lint test`: `89 passed, 1 skipped`.
- **2026-11-11 (F1.5, F1.8a)** — Built discovery and the source cross-check, tests first. Real-data lessons, each now a test: EDGAR full-text search ignores exhibit-type filters (search the S-K 1300 phrase, filter EX-96 client-side, page through); exhibit descriptions are generic ("EXHIBIT 99.1"), so technical reports are matched by content; successive report versions share ~92% of numbers (Gunnison JCM 2025 vs 2026), so the stated effective date must match; files pulled from EDGAR are `same_source`, not a check; www.sec.gov/Archives needs a contact email in the User-Agent (new `OREBODY_SEC_CONTACT`). One test was corrected, not loosened: it assumed EDGAR could filter by exhibit type. Live: `orebody discover --as-of 2026-11-11` → 66 included, 27 excluded; `orebody crosscheck LEO` → consistent=1 no_alternate=19 same_source=5; GCU → no_alternate=28 same_source=6. F1.5 and F1.8a share one commit because `EdgarClient` and the CLI carry both. `make lint test`: `145 passed, 2 skipped in 2.53s`.
- **2026-11-11 (F1.6)** — Eligibility check, tests first; from this feature on the user runs every command (CLAUDE.md). Rules 1-5 of §10.1 plus the Section 3 path; other primary commodities are recorded with a note for their own report section (D49); `primary_commodity: Cu` added to all manifests, by-products only where the company states them (SURG Mo/Ag, NCX Au). The user's first run failed 8 tests on one threshold: a page "has text" at 100 chars counted the fixture's 75-char cover page as a scan; lowered to 20 (a scan has 0), no test changed. User-run results: `orebody check SURG` ELIGIBLE (26 items, economics), `MARI` ELIGIBLE (27 items), `LEO` NOT ELIGIBLE (items_found: 0 items). `make lint test` (run by the user): `All checks passed!` / `65 files already formatted` / `162 passed, 2 skipped in 5.62s`.
- **2026-11-11 (F2.1a)** — Index fallbacks for un-numbered headings, tests first. Two real layouts: Copperwood marks every page "Section N / Page N-k" (page_marker); Lion puts an un-numbered capitals heading before its first subsection "N.1" (subsection). Lion lessons: a bare "22.1" table cell on p.342 (rule: the next line must be an upper-case title); a stray "14.1" after Item 22 (rule: longest chain with increasing pages, not first-match greedy); "INTRODUCTION" alone on p.24 with "1.1" overleaf (rule: step back one page). `build_index` now calls `detect_index`, so `run` and `check` use the fallbacks. With the user's approval, F1.6's `test_real_leo_fails_items_found` (which recorded this bug) became `test_real_leo_is_eligible_after_f21`. F2.1 split: TOC cross-check is F2.1b. User-run results: `orebody check LEO` ELIGIBLE (25 items via subsection), `HI` ELIGIBLE (27 via page_marker), `MARI` ELIGIBLE (27 via numbered). `make lint test` (run by the user): `All checks passed!` / `66 files already formatted` / `170 passed, 2 skipped in 8.69s`.
- **2026-11-11 (F0.2)** — Typed config, tests first. `load_config` reads models.yaml (agents + prices; D31 defaults fill missing agents; effort pinned to low|medium|high|xhigh|max, checked against the claude-api reference; temperature/top_p/thinking/budget_tokens rejected), sections.yaml, optional prices.yaml (Cu proxy HG=F, overrides need a source, default decks 3.50/5.00 from the MARI demo) and fx.yaml (empty: no rate without a source). `single_model` override per D31. `orebody run` now takes its model, effort and price table from the config. User-run results: MARI fake replay unchanged (`verified 10/10 rate=1.00 cost=US$0.3391`); one ruff format fix applied from the user's lint output. `make lint test` (run by the user): `All checks passed!` / `68 files already formatted` / `191 passed, 2 skipped in 8.95s`.
- **2026-11-11 (F0.3)** — SQLite store, tests first. `0001_initial.sql`: companies, documents, runs (§5.5 record), notes, claims (§4.3 field for field), judge_scores, overrides (empty, Phase L1), prices (as-of cache). The database itself enforces ground rule 3 (only synthesis claims may lack doc_id + page), ground rule 10 (stance values), synthesis status only on synthesis claims, quote ≤ 300 chars, sections 1-5. Runner applies each `NNNN_name.sql` with its `schema_migrations` row in one transaction; a failing migration rolls back. `orebody db init`. Nothing writes to the DB yet (F1.4 ingest, F5.5 orchestration). User-run results: `db init` → `applied 0001_initial`, rerun → `up to date (version 1)`. `make lint test` (run by the user): `All checks passed!` / `70 files already formatted` / `218 passed, 2 skipped in 9.38s`.
- **2026-11-11 (F1.3)** — As-of filter, tests first. Every manifest document filed after as-of is excluded with a reason and logged to `asof.json`; `run` uses the first technical report filed by as-of, which also fixes `run` refusing when the newest study post-dates as-of (it now falls back, as `check` does). Limitation: `# approx` filing dates are YAML comments, invisible to code. Found on real data: SURG at 2026-06-30 includes the 2026-06-15 PFS results release but excludes the PFS report (filed 2026-07-29), see OQ6. User-run results: MARI fake replay unchanged (`verified 10/10 rate=1.00 cost=US$0.3391`); SURG `--as-of 2026-06-30` → `excluded 11 document(s)`, asof.json includes `2023-06-12_berg-pea_ni43-101.pdf` and excludes the PFS, then `MissingFixture` at the model step as expected (no Berg recording). `make lint test` (run by the user): `All checks passed!` / `72 files already formatted` / `228 passed, 2 skipped in 8.92s`.
- **2026-11-11 (F1.4)** — `orebody ingest`, tests first. Company upsert + one row per present document (sha256, pages, path relative to data/, url); doc_id `TICKER/<stem>` because stems repeat across companies. With the user's agreement the test fixture dropped its second copy of the same PDF (the schema rejects identical contents twice per company). Bug found by the user's run: YAML read an unquoted all-digit sha256 as an int (and a 0-7 one starting with 0 would be octal); manifests are now loaded with `yaml.BaseLoader` (all text, dates still parsed by Pydantic), with 5 test rows. Data gap: MARI's 7 hand-collected files (FS, MD&A, AIF, Q2, Oct news, presentation) have no url, so `make fetch` cannot restore them. User-run results: `ingest MARI` → added 20, missing 7; rerun → unchanged 20; `ingest SURG` → added 20, rerun after the loader change → unchanged 20. `make lint test` (run by the user): `All checks passed!` / `74 files already formatted` / `246 passed, 2 skipped in 9.18s`.
- **2026-11-11 (F2.2)** — S-K 1300 index, tests first. EDGAR HTML exhibits are split at CSS page breaks (`html_pages`) so claims keep page numbers; S-K 1300 titles in `config/sections_sk1300.yaml`; costs/economics are Items 18/19 (`ECONOMICS_ITEMS`). Eligibility now indexes any HTML report and uses S-K 1300 titles for SK1300 reports. With the user's approval F1.6's placeholder `test_sk1300_report_fails_items_found_until_f22` became `test_sk1300_html_report_is_eligible`. Real-data lesson from the user's run: Lion's contents page 6 lists only Items 18-19 plus sub-sections, so "≥ 5 item headings" missed it and Items 18/19 landed on p.6; added a second contents signal, ≥ 10 "N.M / title / page" entries (contents pages hold 34-39, body pages ≤ 4), with a test. `make lint test` (run by the user): `All checks passed!` / `76 files already formatted` / `253 passed, 2 skipped in 9.16s`.
- **2026-11-11 (F2.1b)** — Contents cross-check, tests first. `printed_pages` reads dot-leader and three-line contents (title prefix must match the configured title); `cross_check` takes the most common (index start − printed page) as the offset, needs ≥ 3 agreeing items, flags items more than 1 page off. Offsets measured by hand and asserted on real reports: MARI +25 (27 items, no false flags: the AC), SURG +25, Lion S-K 1300 exhibit +20. Not yet called by `check` or `run`. `make lint test` (run by the user): `All checks passed!` / `78 files already formatted` / `266 passed, 2 skipped in 12.59s`.
- **2026-11-12 (F3.2)** — FX resolution, tests first, every expected number hand-computed in the test. Precedence per D14: USD identity → rate stated in the report (with its claim id) → config/fx.yaml only if dated on or before as-of (ground rule 5) → error naming both remedies; never a guessed rate. config/fx.yaml stays empty (no rate without a source), so a CAD note needs the report's stated rate. Not wired into `run` yet (F5.3). SPEC §0 refreshed (it still described the 2026-11-04 demo). `make lint test` (run by the user): `All checks passed!` / `81 files already formatted` / `275 passed, 2 skipped in 12.64s`.
- **2026-11-12 (F2.1b follow-up)** — Contents cross-check shown in `orebody check` as a NOTE (never a rule): `Eligibility.contents` + `contents_note`, tests first (5 tests: agreement, a wrong contents entry that leaves the company eligible, "not possible", the CLI line, real SURG). User-run results: SURG `NOTE  contents check: offset +25 over 26 items, no disagreement`; LEO `not possible (no item in both index and contents)` because Lion's PDF contents are un-numbered like its headings (known limit, recorded on F2.1b). `make lint test` (run by the user): `All checks passed!` / `81 files already formatted` / `280 passed, 2 skipped in 16.62s`.
- **2026-11-12 (F3.1)** — Units finished, tests first: 50 new rows (62 total) and `parse_tonnage_grade` ("412 Mt @ 0.48% Cu", "at", "grading", element symbol or name). Fixed a wrong-number case confirmed by the user's stub run: "89 million pounds" parsed as US$89 M and "4.9 billion pounds" as 4,900 (money), now metal in lb; specific tails are now tried before money scale words. US "tons"/"short tons"/"st" convert at the exact 0.90718474 t (Lion PFS "721,352 tons" → 654,399.53 t; previously not parsed at all). Negatives: leading minus or accounting parentheses. MARI manifest: urls for all 27 documents (7 from marimaca.com/reports-and-filings, FS url + sha256 from the Makefile); download pending (`make fetch T=MARI`). `make lint test` (run by the user): `All checks passed!` / `82 files already formatted` / `330 passed, 2 skipped in 15.81s`.
- **2026-11-12 (F3.6)** — Tier-1 matcher finished, tests first: `number_match` (exact → rounded half-up to the claim's printed decimals, claim never more precise than the page → rescaled via core/units at the claim's precision; bare table numbers never rescale) and `entity_on_page` (case, accents, punctuation, whole words; space-free fallback for multi-word names split by the PDF). `verify/tier1.py` now uses both. Bug found by the new tests in the Phase D exact matcher: a number matched as the integer part of a decimal ("US$708 million" verified against "708.6", "2" inside "2.5"); fixed with a decimal-part lookahead and a 4-row regression table. One test-page fix before the run ("Table 1.9" would round to 2). User-run results: MARI fake replay unchanged after both changes (`verified 10/10 rate=1.00 cost=US$0.3391`). `make lint test` (run by the user): `All checks passed!` / `83 files already formatted` / `365 passed, 2 skipped in 14.35s`.
- **2026-11-12 (F6.4)** — Run stats, tests first. `run_stats`/`stats_line` (verification rate, tier-1 rate kept separate for F6.2, unverified by section, cost, time); migration `0002_run_stats.sql` adds `runs.stats` (JSON); `record_run` upserts the §5.5 run row (creates a minimal company row if missing). `orebody run` records 'running' after the run dir exists, then 'done' with stats or 'failed' on any error, in `<data_dir>/orebody.sqlite`. With the user's approval four F0.3 tests now expect migrations 0001+0002 / version 2. A first draft split `run` in two; restored `cli.py` from HEAD and wrapped the body instead; one blank-line format fix from the user's lint output. User-run results: MARI fake replay `verified 10/10 rate=1.00 tier1=1.00 unverified={} cost=US$0.3391`; DB row `MARI-2026-11-05-171724 done 10 10 46ab5c0`. `make lint test` (run by the user): `All checks passed!` / `87 files already formatted` / `377 passed, 2 skipped in 16.89s`.
- **2026-11-12 (F4.3)** — Prompt versions, tests first. `llm/prompts.py` (load with strict `version: N`/`N.M` header, text sha256, lock check/write, run record); `prompts/versions.lock` pins financial_analyst v1 + sha256; `orebody prompts check|lock`; `financial_analyst.load_prompt` now delegates to the shared loader (identical text, so the MARI recording still replays); the run row stores {name: {version, sha256}}. A test fails whenever a prompt's text changes without a version bump (ground rule 6). User-run results: `prompts check` → `1 prompt(s) match the lock`; MARI fake replay `verified 10/10 … cost=US$0.3391`. `make lint test` (run by the user): `All checks passed!` / `89 files already formatted` / `397 passed, 2 skipped in 15.79s`.

## 13. Open questions

- OQ1. ~~Confirm the universe in §10.~~ Answered 2026-11-11 by D47: rule-based universe, frozen evaluation sample in PROJECTLOG.
- OQ2. Whether any ASX-only filer (JORC) should be included; JORC reports have a different structure and the indexer in F2 covers only NI 43-101 and S-K 1300.
- OQ3. Whether a non-Anthropic judge model/API account will be available for F10.1 (otherwise two Anthropic tiers are used and the limitation is noted in the summary).
- OQ4. Demo date with the professor (not yet set; D42 cut order applies whenever it is).
- OQ6. A news release can announce a newer study before its technical report is filed (SURG: PFS results 2026-06-15, report 2026-07-29). A note in that window rests on the older study while newer headline numbers are public. Should the note flag "newer study announced, report not yet filed" (once news feeds the note)?
- OQ5. ~~Which list is the PoC universe?~~ Answered by D47. Original question: the drop folders collected on 2026-11-11 (SURG, GCU, NCX, USCU, LEO, HI) are not the §10 universe. Which list is the PoC universe? GCU is now a producer listed on NYSE American, and LEO and HI have S-K 1300 or un-numbered reports, which affects D45 and F2.1.

## 14. Risks (PoC-specific)

| Risk | Mitigation in this spec |
|------|-------------------------|
| Section index misses items in oddly formatted reports | F2.1 AC measured on fixtures; agents also get TOC pages; log misses per document |
| Tier-1 matcher false negatives from rounding/units | D39 tolerance; tier-2 catches the rest; stats separate the tiers |
| Cost blows past $2 | D37 section targeting; cost logged per agent; `config/models.yaml` can drop tiers |
| pdf.js text-layer highlight fails on scanned/odd PDFs | fallback: page jump only, claim card shows the quote |
| Model nondeterminism undermines "reproducible" | D36: compare runs via `diff-runs`, report claim-level agreement |
