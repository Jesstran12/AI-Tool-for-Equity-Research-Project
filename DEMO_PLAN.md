# Demo Slice Implementation Plan (for 2026-11-05)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command, `orebody run MARI --as-of <date> --spot <USD/lb>`, turns one company's technical report into a Section 3 (Economics) note where every figure is footnoted to a page, tier-1 verified, and the NPV is rebuilt and re-priced, with a run folder holding every prompt, response, and cost.

**Architecture:** A pure-Python core (PDF page extraction, NI 43-101 item index, units parser, NPV engine, number matcher) with one LLM agent (Financial Analyst) behind a provider interface that records every live response as a replayable fixture. Markdown is rendered by code from structured output. No database, no web UI, no web search.

**Tech Stack:** Python 3.12, uv, ruff, pytest, Pydantic v2, PyMuPDF (`pymupdf`), PyYAML, Typer (CLI), Anthropic Python SDK (`anthropic`).

**Spec:** `SPEC.md` (this plan implements Phase D in §11; decisions D2, D3, D8, D9, D10, D14, D18, D23, D24, D25, D31, D36, D37, D38, D39, D43 apply). After the demo, work resumes at F0.2 per SPEC §0.

## Global Constraints

- Python ≥ 3.12; `uv` manages the environment; `make lint test` must pass before every commit.
- Models: Financial Analyst = `claude-opus-5-5`, effort `medium`. Never pass `temperature`. No assistant prefill. Omit `thinking`.
- Budget: ≤ US$2 per run, project ceiling ≈ US$50 (SPEC D43). Every live response is recorded under `tests/fixtures/llm/` and `data/runs/<run_id>/`.
- Agents see section-targeted page text only: Items 1, 21, 22 (SPEC D37). No web search (D23).
- Every number in the note is a claim with `doc_id`, `page`, `quote` (D9, D10). No invented economics (CLAUDE.md rule 4).
- Stance language and the disclaimer are verbatim from SPEC §4.2 (D25); the demo note has no stance (Section 3 only) but carries the disclaimer.
- Commits: one per task, imperative subject prefixed with the task ID, no credit lines (CLAUDE.md rule 12).
- `data/`, `*.sqlite`, `.env` are gitignored; never commit a company PDF.
- Ports are not used in this slice.

## Review Focus

1. A page cited by the model that lies outside the pages it was shown: `FinancialAnalystOutput` validation must reject it (Task 9 test `test_claim_page_outside_context_rejected`).
2. A quote the model paraphrased instead of copying: tier-1 must mark it `fail`, not crash (Task 10 test `test_quote_not_on_page_fails`).
3. A field the report does not disclose (e.g. sustaining capex): the agent returns `null`, NPV is reported as "not computable" listing the missing fields, the run still writes a note (Task 11 test `test_render_missing_inputs`).
4. Currency not USD (e.g. C$ capex): `value_norm` must be converted at `fx_stated`, and the footnote must show the original (Task 5 test `test_to_usd_m_with_fx`, Task 11 test `test_footnote_shows_original_value`).
5. Prices quoted per pound while the engine works per tonne: `to_usd_per_t` must apply 2204.62 lb/t (Task 5 test `test_usd_per_lb_to_per_t`).

---

## File Structure

```
pyproject.toml, Makefile, .gitignore, .env.example, README.md
config/sections.yaml                 NI 43-101 item numbers → title regex
config/models.yaml                   model ids, effort, USD per MTok
prompts/financial_analyst.md         version: 1
src/orebody/__init__.py
src/orebody/ingest/manifest.py       Manifest, Document, load_manifest
src/orebody/ingest/extract.py        extract_pages, read_page
src/orebody/index/ni43101.py         load_patterns, build_index
src/orebody/core/units.py            Quantity, parse_quantity, to_usd_m, to_usd_per_t
src/orebody/core/npv.py              NpvInputs, NpvResult, npv
src/orebody/core/matcher.py          normalize_ws, quote_on_page, number_on_page
src/orebody/llm/provider.py          Usage, Completion, LLMProvider (Protocol), MissingFixture
src/orebody/llm/fake.py              FakeProvider
src/orebody/llm/anthropic_provider.py AnthropicProvider
src/orebody/llm/cost.py              cost_usd
src/orebody/agents/schemas.py        Claim, EconInputs, FinancialAnalystOutput
src/orebody/agents/context.py        build_context, ContextBundle
src/orebody/agents/financial_analyst.py run_financial_analyst
src/orebody/verify/tier1.py          VerifiedClaim, verify_tier1
src/orebody/render/markdown.py       render_section3, DISCLAIMER
src/orebody/cli.py                   Typer app: `orebody run`
tests/unit/...                       mirrors src
tests/fixtures/make_pdf.py           builds the synthetic 6-page report into a tmp dir
tests/fixtures/llm/                  recorded live responses (committed)
```

---

### Task 0: Prerequisites (Jess Tran, before any coding)

- [x] Demo company = **MARI** (Marimaca Copper). `data/raw/MARI/` holds the NI 43-101 FS technical report (361 pages, effective 2025-08-25) plus financials, MD&A, AIF, news, presentation, and `manifest.yaml` (done 2026-11-04). Base-case figures to check against from the company's summary: ~50,000 t/yr cathode, 13-year reserve life, pre-production capex ~US$587 M, post-tax NPV8 ~US$709 M at US$4.30/lb, IRR ~31%.
- [ ] Confirm credentials: run `ant auth status` or check `echo ${ANTHROPIC_API_KEY:+set}` prints `set`.
- [x] Base-case price and NPV noted above (from the company's FS press release; confirm on the report's Item 1 during Task 12 Step 7).

---

### Task 1: Scaffold

**Files:**
- Create: `pyproject.toml`, `Makefile`, `.gitignore`, `.env.example`, `src/orebody/__init__.py`, `tests/unit/test_smoke.py`

**Interfaces:**
- Produces: a `uv` project named `orebody` with dependencies `pydantic>=2`, `pymupdf`, `pyyaml`, `typer`, `anthropic`; dev deps `pytest`, `ruff`; console script `orebody = "orebody.cli:app"`; `make lint` = `uv run ruff check . && uv run ruff format --check .`; `make test` = `uv run pytest -q`.

- [ ] **Step 0: Fix the git root.** `git rev-parse --show-toplevel` must print the repo root (e.g. `/Users/jesstran/orebody`). If it prints the home directory, run `git init` inside `project-4` so commits never sweep in home-folder files. Then confirm `git status --short` shows only project files.
- [ ] **Step 1: Write `tests/unit/test_smoke.py`** asserting `import orebody` works and `orebody.__version__ == "0.0.1"`.
- [ ] **Step 2: Run `uv run pytest -q`** → FAIL (no package).
- [ ] **Step 3: Create `pyproject.toml`** (hatchling build, `[tool.ruff] line-length = 100`, `[tool.pytest.ini_options] testpaths = ["tests"]`, marker `live`), `src/orebody/__init__.py` with `__version__`, `Makefile`, `.gitignore` (`data/`, `*.sqlite`, `.env`, `.venv/`, `__pycache__/`, `reports/*.pdf`), `.env.example` with `ANTHROPIC_API_KEY=`.
- [ ] **Step 4: Run `uv sync && make lint test`** → PASS, 1 test.
- [ ] **Step 5: Commit** `D1: scaffold uv project, lint, test`.

---

### Task 2: Manifest loader

**Files:**
- Create: `src/orebody/ingest/manifest.py`, `tests/unit/ingest/test_manifest.py`

**Interfaces:**
- Produces:
  ```python
  class Document(BaseModel):
      file: str; type: Literal["technical_report","annual_financials","quarterly_financials","mdna","aif","news_release","presentation"]
      standard: Literal["NI43-101","SK1300","JORC","none"] = "none"
      effective_date: date | None = None; filing_date: date; title: str = ""; project: str = ""
  class Manifest(BaseModel):
      ticker: str; name: str; exchange: str = ""; flagship_project: str = ""
      reporting_currency: str = "USD"; documents: list[Document]
      def technical_report(self) -> Document   # first type == technical_report; raises ValueError if none
  def load_manifest(path: Path) -> Manifest     # raises ValueError with the pydantic message on bad input
  ```

- [ ] **Step 1: Write tests** `test_load_valid_manifest` (tmp yaml with one technical report → `m.technical_report().file`), `test_missing_filing_date_raises` (ValueError), `test_no_technical_report_raises`.
- [ ] **Step 2: Run** `uv run pytest tests/unit/ingest/test_manifest.py -v` → FAIL.
- [ ] **Step 3: Implement** the models and `load_manifest` (yaml.safe_load → `Manifest.model_validate`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `D2: manifest loader`.

---

### Task 3: PDF page extraction + synthetic fixture report

**Files:**
- Create: `src/orebody/ingest/extract.py`, `tests/fixtures/make_pdf.py`, `tests/conftest.py`, `tests/unit/ingest/test_extract.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class Extracted: doc_id: str; sha256: str; n_pages: int; pages_dir: Path
  def extract_pages(pdf_path: Path, pages_root: Path) -> Extracted
      # doc_id = pdf_path.stem; writes pages_root/<doc_id>/0001.txt ... (1-indexed, 4 digits); idempotent: skips if sha256 file matches
  def read_page(pages_dir: Path, n: int) -> str
  ```
- `tests/fixtures/make_pdf.py: def make_report(path: Path) -> Path` builds a 6-page PDF with PyMuPDF:
  - p1 title "Fixture Copper Project NI 43-101 Technical Report"; p2 "TABLE OF CONTENTS" with lines `1 Summary ........ 3`, `21 Capital and Operating Costs ........ 5`, `22 Economic Analysis ........ 6`; p3 heading `1 Summary` + "The Project has a mine life of 18 years and produces an average of 50,000 tonnes of payable copper per year."; p4 heading `14 Mineral Resource Estimates` + filler; p5 heading `21 Capital and Operating Costs` + "Initial capital cost is estimated at US$1,240 million." + "Sustaining capital totals US$310 million over the life of mine." + "C1 cash cost is US$1.85/lb."; p6 heading `22 Economic Analysis` + "At a base case copper price of US$4.00/lb the post-tax NPV at an 8% discount rate is US$2,100 million with an IRR of 22.8%." + "The effective tax rate is 27%."
- `tests/conftest.py`: fixture `fixture_pdf(tmp_path_factory)` → path from `make_report`.

- [ ] **Step 1: Write tests** `test_extract_writes_one_file_per_page` (n_pages == 6, `0005.txt` contains "US$1,240 million"), `test_extract_is_idempotent` (second call does not rewrite; compare mtimes), `test_read_page_out_of_range_raises`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `make_report` (fitz `insert_text` per page, 11pt), `extract_pages` (`page.get_text("text")`), `read_page`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `D3: PDF page extraction and synthetic fixture report`.

---

### Task 4: NI 43-101 item index

**Files:**
- Create: `config/sections.yaml`, `src/orebody/index/ni43101.py`, `tests/unit/index/test_ni43101.py`

**Interfaces:**
- `config/sections.yaml`: `items: {1: "Summary", 2: "Introduction", 3: "Reliance on Other Experts", 4: "Property Description and Location", 5: "Accessibility", 6: "History", 7: "Geological Setting", 8: "Deposit Types", 9: "Exploration", 10: "Drilling", 11: "Sample Preparation", 12: "Data Verification", 13: "Mineral Processing", 14: "Mineral Resource Estimates", 15: "Mineral Reserve Estimates", 16: "Mining Methods", 17: "Recovery Methods", 18: "Project Infrastructure", 19: "Market Studies and Contracts", 20: "Environmental Studies", 21: "Capital and Operating Costs", 22: "Economic Analysis", 23: "Adjacent Properties", 24: "Other Relevant Data", 25: "Interpretation and Conclusions", 26: "Recommendations", 27: "References"}` (title = first words only, matching tolerates the rest).
- Produces:
  ```python
  def load_patterns(path: Path = Path("config/sections.yaml")) -> dict[int, str]
  @dataclass(frozen=True)
  class ItemSpan: item: int; start: int; end: int     # 1-indexed pages, inclusive
  def build_index(pages: list[str], patterns: dict[int, str]) -> dict[int, ItemSpan]
  ```
  Algorithm (pinned): heading regex per item = `^\s*(?:ITEM\s+)?{n}(?:\.0)?[\s.:\-–]+{title}` with `re.I | re.M`; `toc_end` = the largest page number ≤ 15 whose text has ≥ 5 lines ending in digits; an item's start = the first page > `toc_end` matching its regex; `end` = (next found item's start − 1) or last page; items with no match are omitted (caller logs them).

- [ ] **Step 1: Write tests** on the fixture pages: `test_index_skips_toc` (item 21 → start 5, not 2), `test_index_ends_at_next_item` (item 21 end == 5, item 22 end == 6), `test_missing_item_omitted` (item 27 not in result), `test_load_patterns_has_27_items`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** per the pinned algorithm.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `D4: NI 43-101 item index`.

---

### Task 5: Units parser

**Files:**
- Create: `src/orebody/core/units.py`, `tests/unit/core/test_units.py`

**Interfaces:**
- Produces:
  ```python
  LB_PER_T = 2204.62
  @dataclass(frozen=True)
  class Quantity: value: float; unit: str; currency: str | None   # unit ∈ {"M","t","pct","per_lb","per_t","years","t_per_year","lb"}; value already scaled (M = millions)
  def parse_quantity(text: str) -> Quantity | None
  def to_usd_m(q: Quantity, fx_local_per_usd: float | None) -> float   # q.unit == "M"; CAD/AUD need fx else ValueError
  def to_usd_per_t(q: Quantity) -> float                                # per_lb → ×LB_PER_T; per_t unchanged
  ```
  Currency detection: `US$`/`USD`/`$`→"USD" (bare `$` is "USD" only if no `C$`/`A$` elsewhere in the string), `C$`/`CAD`→"CAD", `A$`/`AUD`→"AUD". Scale words: `million|M|mm` → M; `billion|B|bn` → ×1000 M; `thousand|k` → ÷1000 M. Tonnage: `Mt` → ×1e6 t, `kt` → ×1e3 t, `tonnes|t` → t; `tpa|t/a|tonnes per year|tonnes per annum` → t_per_year. `Mlb`→×1e6 lb, `Blb`→×1e9 lb. `%` → pct. `/lb` → per_lb, `/t|/tonne` → per_t. `years|year|yr` → years.

- [ ] **Step 1: Write a parametrized test** with these rows (text → expected `(value, unit, currency)`): `"US$1,240 million"→(1240,"M","USD")`; `"C$1.2 billion"→(1200,"M","CAD")`; `"$709 million"→(709,"M","USD")`; `"412 Mt"→(412e6,"t",None)`; `"0.48%"→(0.48,"pct",None)`; `"2.1 Blb"→(2.1e9,"lb",None)`; `"US$4.00/lb"→(4.0,"per_lb","USD")`; `"US$1.85/lb"→(1.85,"per_lb","USD")`; `"50,000 tonnes per year"→(50000,"t_per_year",None)`; `"18 years"→(18,"years",None)`; `"US$8,800/t"→(8800,"per_t","USD")`; `"no number here"→None`. Plus `test_to_usd_m_with_fx` (`Quantity(1200,"M","CAD")`, fx 1.35 → 888.89 ±0.01), `test_to_usd_m_cad_without_fx_raises`, `test_usd_per_lb_to_per_t` (4.00 → 8818.48 ±0.01).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** with one compiled regex for number+scale+unit and small helper tables.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `D5: units parser`.

---

### Task 6: NPV engine

**Files:**
- Create: `src/orebody/core/npv.py`, `tests/unit/core/test_npv.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class NpvInputs:
      mine_life_years: int; annual_payable_metal_t: float; unit_cost_usd_per_t: float
      initial_capex_usd_m: float; sustaining_capex_usd_m: float; tax_rate: float; discount_rate: float
      construction_years: int = 2; ramp_up_year1: float = 0.7
  @dataclass(frozen=True)
  class NpvResult: npv_usd_m: float; irr: float | None; payback_years: float | None; cashflows_usd_m: list[float]
  def npv(inp: NpvInputs, price_usd_per_t: float) -> NpvResult
  ```
  Cash-flow model (pinned, SPEC §7): years 1..construction_years each `-initial_capex/construction_years`; then `mine_life_years` production years where metal = annual × (ramp_up_year1 in the first production year, else 1), revenue = metal×price/1e6, opex = metal×unit_cost/1e6, sustaining = sustaining_total/mine_life, pretax = revenue−opex−sustaining, tax = max(pretax,0)×tax_rate, cf = pretax−tax. NPV = Σ cf_t/(1+r)^t for t = 1..N (end-of-year). IRR by bisection on [−0.99, 10], None if no sign change. Payback = production years until cumulative cash flow ≥ 0, linearly interpolated within the year; None if never.

- [ ] **Step 1: Write tests** with hand computations in comments:
  - `test_npv_clean_fixture`: life 2, construction 1, capex 100, metal 10,000 t, cost 5,000 $/t, sustaining 0, tax 0, ramp 1.0, r 0.10, price 10,000 → cashflows `[-100, 50, 50]`, npv ≈ −12.02 (−90.909+41.322+37.566), irr ≈ 0.0 (2x²−x−1=0 → x=1), payback 2.0.
  - `test_npv_with_tax_and_ramp`: life 3, construction 1, capex 120, metal 20,000, price 9,000, cost 4,000, sustaining 30, tax 0.25, ramp 0.5, r 0.08 → cashflows `[-120, 30, 67.5, 67.5]`, npv ≈ 17.81 (±0.02).
  - `test_negative_project_irr_none_when_no_sign_change` (all cashflows negative → irr None, payback None).
  - `test_zero_mine_life_raises` (ValueError).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `npv`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `D6: parametric NPV engine with IRR and payback`.

---

### Task 7: Tier-1 matcher

**Files:**
- Create: `src/orebody/core/matcher.py`, `tests/unit/core/test_matcher.py`

**Interfaces:**
- Produces:
  ```python
  def normalize_ws(s: str) -> str                       # collapse whitespace, strip, unify ’→', –→-
  def quote_on_page(page_text: str, quote: str) -> bool # normalized substring test, case-sensitive
  def number_on_page(page_text: str, value_orig: str) -> bool
      # extracts the first number token from value_orig (e.g. "1,240" from "US$1,240 million"),
      # strips thousands separators, and tests whether the same number (same printed precision) appears
      # on the page as a standalone numeric token (not a substring of a longer number)
  ```

- [ ] **Step 1: Write tests**: `test_quote_found_despite_line_breaks`, `test_quote_missing`, `test_number_found_with_commas`, `test_number_not_substring` ("1,240" must not match "11,240"), `test_number_decimal_precision` ("22.8" matches "22.8%" and not "22.85"), `test_number_missing`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** with regex `(?<![\d.])<escaped number>(?![\d])` after normalizing commas on both sides.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `D7: tier-1 quote and number matcher`.

---

### Task 8: LLM provider interface, FakeProvider, cost, AnthropicProvider

**Files:**
- Create: `src/orebody/llm/provider.py`, `src/orebody/llm/fake.py`, `src/orebody/llm/cost.py`, `src/orebody/llm/anthropic_provider.py`, `config/models.yaml`, `tests/unit/llm/test_fake.py`, `tests/unit/llm/test_cost.py`, `tests/unit/llm/test_anthropic_live.py`

**Interfaces:**
- `config/models.yaml`: `financial_analyst: {model: claude-opus-5-5, effort: medium}` and `prices_usd_per_mtok: {claude-opus-5-5: {input: 4.0, output: 20.0, cache_read: 0.20}, claude-sonnet-5-5: {input: 2.0, output: 10.0, cache_read: 0.20}}`.
- Produces:
  ```python
  class Usage(BaseModel): input_tokens: int; output_tokens: int; cache_read_input_tokens: int = 0
  class Completion(BaseModel): parsed: dict; raw_text: str; usage: Usage; model: str; cost_usd: float; request_key: str
  class MissingFixture(Exception): ...
  class LLMProvider(Protocol):
      def complete(self, *, system: str, user: str, schema: type[BaseModel], model: str, effort: str) -> Completion
  def request_key(system: str, user: str, schema_name: str, model: str) -> str   # sha256 hex[:16]
  def cost_usd(model: str, usage: Usage, prices: dict) -> float
  class FakeProvider:            # __init__(fixture_dir: Path); reads <fixture_dir>/<request_key>.json = {"parsed":..., "raw_text":..., "usage":..., "model":...}; raises MissingFixture(key) if absent
  class AnthropicProvider:       # __init__(record_dirs: list[Path], prices: dict); calls client.messages.parse(model=, max_tokens=16000, system=, messages=[{"role":"user","content":user}], output_format=schema, output_config={"effort": effort}); raises RuntimeError if response.stop_reason == "refusal"; writes the fixture JSON into every record_dir
  ```
  No `temperature`, no `thinking`, no prefill. Server-side fallbacks are deliberately not used in this slice (keeps `messages.parse` on the stable client); the refusal check is the guard.

- [ ] **Step 1: Write tests** `test_fake_replays_fixture` (write a fixture file for a known key, call complete, parsed round-trips), `test_fake_missing_raises_with_key`, `test_cost_usd` (opus: 100k in, 10k out → 0.4+0.2 = 0.60), and `test_live_parse_records_fixture` marked `@pytest.mark.live`, skipped without `ANTHROPIC_API_KEY`, which asks for a tiny schema `{"answer": str}` and asserts a fixture file appears and `cost_usd > 0`.
- [ ] **Step 2: Run** `uv run pytest tests/unit/llm -v` → FAIL (live test SKIPPED).
- [ ] **Step 3: Implement** the four modules.
- [ ] **Step 4: Run** → PASS; then run once with the key: `uv run pytest -m live -v` → PASS and a fixture file exists.
- [ ] **Step 5: Commit** `D8: LLM provider interface, fake replay, Anthropic provider, cost accounting` (include the tiny live fixture).

---

### Task 9: Agent schemas, context builder, Financial Analyst

**Files:**
- Create: `src/orebody/agents/schemas.py`, `src/orebody/agents/context.py`, `src/orebody/agents/financial_analyst.py`, `prompts/financial_analyst.md`, `tests/unit/agents/test_schemas.py`, `tests/unit/agents/test_context.py`, `tests/unit/agents/test_financial_analyst.py`

**Interfaces:**
- Produces:
  ```python
  class Claim(BaseModel):
      field: str; claim_type: Literal["number","entity","date"]
      value_orig: str; unit_orig: str | None = None; currency_orig: str | None = None
      doc_id: str; page: int; quote: str = Field(max_length=300)
  class EconInputs(BaseModel):   # all Optional; None = not disclosed
      mine_life_years: float | None; annual_payable_metal_t: float | None; unit_cost_usd_per_t: float | None
      initial_capex_usd_m: float | None; sustaining_capex_usd_m: float | None; tax_rate: float | None
      discount_rate: float | None; company_base_price_usd_per_t: float | None; company_npv_usd_m: float | None
      company_irr: float | None; fx_stated_local_per_usd: float | None
      def missing(self) -> list[str]
  class FinancialAnalystOutput(BaseModel):
      inputs: EconInputs; claims: list[Claim]; notes: str
      # validator: every non-None inputs field has exactly one claim with the same `field`
  @dataclass(frozen=True)
  class ContextBundle: text: str; pages: set[int]; items_found: list[int]; items_missing: list[int]
  def build_context(pages_dir: Path, index: dict[int, ItemSpan], items: tuple[int, ...] = (1, 21, 22), max_pages_per_item: int = 40) -> ContextBundle
      # text = for each item: "=== Item {n}: pages {s}-{e} ===" then per page "--- page {p} ---\n{text}"
  def load_prompt(path: Path) -> tuple[str, str]        # (version, body) from a "version: N" first line
  def run_financial_analyst(provider: LLMProvider, bundle: ContextBundle, doc_id: str, model: str, effort: str, prompt_path: Path) -> tuple[FinancialAnalystOutput, Completion]
      # raises ValueError if any claim.page not in bundle.pages or claim.doc_id != doc_id
  ```
- `prompts/financial_analyst.md` (exact copy):
  ```
  version: 1
  You are the Financial Analyst for a mining equity research note. You will be given page-marked excerpts from one NI 43-101 technical report. Extract the economic inputs listed in the output schema.
  Rules:
  1. Use only the provided pages. If a value is not stated in them, return null for that field and say so in `notes`. Never estimate.
  2. For every non-null field, add one claim: `field` = the same field name; `value_orig` = the value exactly as printed (e.g. "US$1,240 million", "22.8%", "US$4.00/lb"); `page` = the number from the nearest "--- page N ---" marker above the text; `quote` = a verbatim span of at most 300 characters from that page containing the value.
  3. Convert to the schema's units yourself only in the numeric field (USD millions, USD per tonne, tonnes per year, fractions for rates: 22.8% → 0.228). Use 2204.62 lb per tonne. If the report's currency is not USD, use the FX rate stated in the report and record it in `fx_stated_local_per_usd` with its own claim.
  4. Prefer the base-case post-tax NPV and the discount rate attached to it. Prefer C1 cost net of by-products; if only AISC is stated, use it and say so in `notes`.
  5. Do not include any text outside the schema.
  ```

- [ ] **Step 1: Write tests**: `test_output_requires_claim_per_input` (input set, no claim → ValidationError), `test_missing_lists_none_fields`, `test_build_context_marks_pages` (fixture index → text contains "--- page 5 ---" and `pages == {3,5,6}`, `items_missing == []`), `test_build_context_reports_missing_item` (index without 22 → `items_missing == [22]`), `test_claim_page_outside_context_rejected` (FakeProvider fixture whose claim cites page 9 → ValueError), `test_run_financial_analyst_happy` (FakeProvider fixture authored by hand for the synthetic report: inputs 18 / 50000 / 4078.55 / 1240 / 310 / 0.27 / 0.08 / 8818.48 / 2100 / 0.228 / None with matching claims → returns output; usage recorded).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the three modules and the prompt file. The fake fixtures for the two tests are written by the test itself into `tmp_path` using `request_key`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `D9: Financial Analyst agent with structured claims and page-bounded context`.

---

### Task 10: Tier-1 verification

**Files:**
- Create: `src/orebody/verify/tier1.py`, `tests/unit/verify/test_tier1.py`

**Interfaces:**
- Produces:
  ```python
  class VerifiedClaim(Claim): tier1_status: Literal["pass","fail"]; tier1_reason: str; final_status: Literal["verified","unverified"]
  def verify_tier1(claims: list[Claim], read_page: Callable[[int], str]) -> list[VerifiedClaim]
      # pass iff quote_on_page AND (claim_type != "number" or number_on_page); reason names which test failed
  def verification_rate(vc: list[VerifiedClaim]) -> float
  ```

- [ ] **Step 1: Write tests** against fixture pages: `test_good_claim_passes`, `test_quote_not_on_page_fails` (paraphrased quote → fail, reason "quote"), `test_number_not_on_page_fails` (value_orig "US$1,250 million" with a real quote → fail, reason "number"), `test_rate` (2 of 3 → 0.667).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `D10: tier-1 claim verification`.

---

### Task 11: Markdown renderer

**Files:**
- Create: `src/orebody/render/markdown.py`, `tests/unit/render/test_markdown.py`

**Interfaces:**
- Produces:
  ```python
  DISCLAIMER = "This note is an automated synthesis of the company's public disclosures as of the stated date. It is not investment advice, contains no forecast of returns, and the stance expressed describes disclosed fundamentals only. Every figure links to its source page; figures marked \"unverified\" could not be matched to a source and should not be relied on."
  @dataclass(frozen=True)
  class PriceDeck: spot_usd_per_t: float; deck_a_usd_per_t: float | None; deck_b_usd_per_t: float | None; source: str
  def render_section3(*, ticker: str, name: str, as_of: date, doc_id: str, inputs: EconInputs, claims: list[VerifiedClaim],
                      deck: PriceDeck, results: dict[str, NpvResult] | None, missing: list[str], run_id: str, cost_usd: float) -> str
  ```
  Layout (pinned): H1 `{name} ({ticker}) — Economics, as of {as_of}`; status line `Verification: {verified}/{total} claims verified · run {run_id} · cost US${cost:.2f}`; a table of disclosed inputs, one row per non-None field: `| Field | Value (USD, metric) | As printed | Source |` where Source is a footnote marker `[^n]` and unverified rows append ` ⚠ unverified`; then **Rebuilt NPV** table with rows base / spot / deck A / deck B: price (USD/lb and USD/t), NPV (USD M), IRR, payback; then the line `Reconciliation: rebuilt base-case NPV US${x} M vs company-stated US${y} M → gap {z:+.1f}%`; if `results is None`: the line `NPV not computable: missing {missing}`; footnotes `[^n]: {doc_id}, p.{page}: "{quote}"`; final paragraph = `DISCLAIMER`.

- [ ] **Step 1: Write tests**: `test_render_contains_footnote_per_claim`, `test_footnote_shows_original_value` (C$ claim → "As printed" column shows `C$...`), `test_unverified_row_tagged`, `test_reconciliation_line` (rebuilt 1850, company 2100 → "−11.9%"), `test_render_missing_inputs` (results None → "NPV not computable: missing ['sustaining_capex_usd_m']"), `test_disclaimer_verbatim`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `D11: Section 3 Markdown renderer with footnoted citations`.

---

### Task 12: `orebody run` CLI and the live demo run

**Files:**
- Create: `src/orebody/cli.py`, `tests/unit/test_cli.py`, `README.md`

**Interfaces:**
- `orebody run TICKER --as-of YYYY-MM-DD --spot FLOAT (USD/lb) [--deck-a FLOAT] [--deck-b FLOAT] [--provider anthropic|fake] [--data-dir data] [--fixtures tests/fixtures/llm]`
- Pipeline (pinned order): load manifest → `extract_pages` for the technical report into `data/pages` → `build_index` → `build_context` → provider (`AnthropicProvider(record_dirs=[fixtures, run_dir])` or `FakeProvider(fixtures)`) → `run_financial_analyst` with model/effort from `config/models.yaml` → `verify_tier1` → convert inputs to `NpvInputs` (if `missing()` is empty) and run `npv` at company base price, spot, deck A, deck B (prices given per lb, converted with `to_usd_per_t`) → `render_section3` → write `run_dir/{context.txt, output.json, claims.json, note.md, stats.json}` where `run_id = f"{ticker}-{as_of}-{HHMMSS}"` and `stats.json` = `{verified, total, rate, cost_usd, seconds, model, prompt_version, items_missing, doc_sha256}` → print the stats line.
- `--as-of` is recorded in the note and `stats.json` (no document filtering in this slice; the manifest holds one document).

- [ ] **Step 1: Write test** `test_run_fake_end_to_end` (Typer `CliRunner`; fixture PDF + manifest in `tmp_path`; FakeProvider fixture from Task 9's happy-path case; asserts `note.md` exists, contains "Reconciliation:", `stats.json["total"] >= 8`).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `cli.py` and a 15-line `README.md` (install, run command, where outputs land).
- [ ] **Step 4: Run** `make lint test` → PASS.
- [ ] **Step 5: Commit** `D12: orebody run CLI, fake end-to-end`.
- [ ] **Step 6: Live run on the demo company**: `uv run orebody run MARI --as-of 2026-11-05 --spot <today's COMEX copper USD/lb> --deck-a 3.50 --deck-b 5.00`. Expected: stats line with rate ≥ 0.8 and cost ≤ US$2. If the index misses Item 21 or 22, add the heading variant to `config/sections.yaml` and re-run (fixture replay makes prompt edits free; a new context means one more live call).
- [ ] **Step 7: Read the note against the report**: capex, NPV, IRR, price, mine life, tax rate. Record any wrong figure in `reports/audit.md` (create the folder; this file is committed).
- [ ] **Step 8: Commit** `D12b: first live note for MARI` (fixtures and `reports/audit.md`; no PDF, no `data/`).
- [ ] **Step 9: Update SPEC.md** §0 (Phase D done, spend to date), Phase D statuses, and append the §12 session-log entry with the stats line pasted in. Commit `D13: spec log after demo slice`.

---

## Demo script (5 minutes)

1. Show SPEC.md §1–§3 for 60 seconds: the claim, the paper's evidence, the Verifier as the departure.
2. Run `uv run orebody run MARI --as-of 2026-11-05 --spot <spot> --provider fake` live (instant, replays the recorded response) and open `note.md`.
3. Point at the capex row, open the PDF at the footnoted page, show the printed number.
4. Show the Rebuilt NPV table and the reconciliation gap; change `--spot` and re-run to show re-pricing.
5. Open `data/runs/<run_id>/` to show the prompt, the raw response, and `stats.json` with cost.
6. Close on SPEC §11: what is built (Phase D), what comes next (F0.2 onward), and the Stage 2 expert evaluation the proposal promises.

## Fallback if the live run fails

Demo with `--provider fake` on the synthetic fixture report (`tests/fixtures/make_pdf.py` output) and say so: the mechanism is identical, the data is synthetic.

## Return path after the demo

SPEC.md §0 → "Next feature: F0.2". Phase D features map back: D2→F1.1, D3→F1.2, D4→F2.1 (trimmed), D5→F3.1 (trimmed), D6→F3.3, D7→F3.6 (trimmed), D8→F4.1+F4.2, D9→F5.3 (trimmed, Section 3 only), D10→F6.1, D11→F5.6 (trimmed), D12→F7.1 (trimmed). Trimmed features keep status `IN PROGRESS` in §11 with a note "demo slice built; remaining AC: ...".
