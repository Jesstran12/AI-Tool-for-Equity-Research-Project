# Orebody demo script — professor meeting, 2026-11-05

Target length: 5 minutes of demo, then questions. Everything below runs offline from a recorded
response, so nothing can fail on network or API. Total API spend to date: US$0.34.

---

## 0. Before you walk in (10 minutes, the night before)

1. Open a terminal in `~/project-4`. On a fresh clone first run `uv sync && make fetch-mari`
   (downloads the public report, 18 MB). Then run the demo command once so a fresh run folder
   exists:
   ```
   uv run orebody run MARI --as-of 2026-11-05 --spot 6.71 --deck-a 3.50 --deck-b 5.00 --provider fake
   ```
   Expected last line: `MARI-2026-11-05-HHMMSS: verified 10/10 rate=1.00 cost=US$0.3391 ...`
2. Open the PDF `data/raw/MARI/2025-08-25_MarimacaOxide_FS_NI43-101.pdf` in Preview and leave
   it open. You will jump to PDF page **329** (printed "Page 304") and PDF page **55** (printed
   "Page 30"). Use Preview's "Go to Page" with the PDF index, not the printed number.
3. Open `data/runs/<the run id>/note.md` in VS Code with Markdown preview (Cmd+Shift+V) so the
   tables render. Keep the raw file in a second tab for the footnotes.
4. Open `SPEC.md` scrolled to §1 "Intent".
5. Check `make lint test` is green (87 passed, 1 skipped). Do not run anything with
   `--provider anthropic` during the demo; it spends money and takes 40 seconds.
6. Have `reports/audit.md` open in a tab for the questions section.

---

## 1. The claim (60 seconds) — show SPEC.md §1

Say roughly:

> "The proposal is AI-written equity research for copper juniors that nobody covers. Francis and
> Zhang 2026 showed a four-agent GPT-4o pipeline whose reports general readers rated above Value
> Line, but they never measured factual accuracy, and a trading desk throws a note away on the
> first wrong capex figure. So the thing I am adding is a verification layer: every number in the
> note is a claim with a document, a page and a verbatim quote, checked by code against the page,
> and the NPV is rebuilt from the disclosed inputs rather than quoted."

Point at the three anti-goals in §2: no untraceable number, no invented economics, no return
language.

---

## 2. Run it (30 seconds) — terminal

Run:
```
uv run orebody run MARI --as-of 2026-11-05 --spot 6.71 --deck-a 3.50 --deck-b 5.00 --provider fake
```

Say:

> "One command: ticker, as-of date, today's copper price, two price decks. This replays the
> recorded model response from this morning, so it is instant. The live call cost 34 cents and
> took about 40 seconds. The stats line says 10 of 10 claims verified."

Explain the as-of date in one sentence: documents filed after that date are excluded, so a note
can be regenerated as of any past date.

---

## 3. The note (90 seconds) — note.md preview

Walk the first table top to bottom, briefly:

> "This is Section 3, Economics, for Marimaca's 2025 feasibility study. Each row is one disclosed
> input. Left column is normalised to USD and metric, the next column is the value exactly as the
> report prints it, and the Source column is a footnote to a page. The model is only allowed to
> return a number together with a verbatim quote from the page it cites."

Then the proof. Point at `initial_capex_usd_m | US$587 M | US$586.6 million | [^4]`. Scroll to
footnote 4: `p.329: "Initial capital costs are estimated to be US$586.6 million."` Switch to
Preview, go to PDF page 329, and show the sentence on the page.

> "The footnote is checked by code, not by the model: the quote must be a substring of the page
> text and the printed number must appear on that page as a standalone token. If either fails the
> row is tagged unverified. On this report all ten passed."

Optional second proof if time: footnote 9, PDF page 55, "post-tax NPV8% is US$709 million, IRR
30.9%".

---

## 4. Rebuilt NPV and re-pricing (60 seconds)

Point at the **Rebuilt NPV** table and the reconciliation line.

> "The engine rebuilds the project cash flows from those inputs: 12.7-year life, 50,000 tonnes a
> year, cash cost 1.84 dollars a pound, 587 million capex, 529 million sustaining, 27 percent
> tax, 8 percent discount rate. At the company's own 4.30 price it gets 570 million against the
> company's 709, a gap of about 20 percent, and the note prints that gap instead of hiding it.
> The gap is the parametric model being simpler than Ausenco's: flat production instead of the
> real schedule, a default two-year build, and I do not yet model the 77 million of expansion
> capital the report lists separately. That is written up in the audit file."

Then re-price live. In the terminal run the same command with `--spot 5.00`:
```
uv run orebody run MARI --as-of 2026-11-05 --spot 5.00 --deck-a 3.50 --deck-b 5.00 --provider fake
```
Open the new note and show the spot row changed while the base row and all footnotes did not.

> "Re-pricing costs nothing because the extraction is cached; only the arithmetic reruns."

---

## 5. Reproducibility (45 seconds) — the run folder

Open `data/runs/<run id>/` and show the six files:

- `context.txt` — the 64 pages the model was shown (Items 1, 21, 22 of the report only, never
  the whole 361 pages; that is how a note costs under a dollar).
- `request.json` — model id, effort, prompt version, the system prompt.
- `output.json` — the raw structured response, token usage, cost.
- `claims.json` — every claim with its tier-1 pass/fail and reason.
- `note.md`, `stats.json`.

> "Every run records model, prompt version, document hash and cost, and every live response is
> saved as a fixture, so a rerun months later can be diffed against this one."

---

## 6. Close (30 seconds) — SPEC.md §11

Scroll to §11.

> "What exists today is the Phase D slice: one section, one agent, tier-1 verification, for one
> company. The full plan is five sections, five agents, a second LLM verification tier, a
> dashboard with the PDF viewer, ten companies, and a results summary with verification rate,
> cost and time per note. That is the artefact a Stage 2 expert evaluation would be run on, which
> is what the proposal promises for the spring."

Stop talking and take questions.

---

## Likely questions and honest answers

**"How do you know the model did not make the numbers up?"**
It can, and the design assumes it will. The model must return a quote with each number; code
checks the quote is on the cited page and the number is on that page. Anything that fails is
tagged unverified in the note. The model also cannot cite a page it was not shown; that is
rejected before rendering. A paraphrased quote fails. There is also a hand audit in
`reports/audit.md` where I checked all ten figures against the report myself.

**"Was the live run clean?"**
Almost. The model invented a document id because my prompt never told it one. I changed the
pipeline to stamp the id itself and replayed the recording; everything else was right first time.
The one other change the real report forced was in the table-of-contents detection: this
report's contents run to page 25 and my first rule assumed 15.

**"Why is the rebuilt NPV 20 percent below the company's?"**
Model shape, not wrong inputs. See step 4. The spec treats the gap as an output to report, not
an error to tune away. Closing it means adding the production schedule and expansion capital to
the engine, which is on the list.

**"What did this cost?"**
34 cents for the one live call, plus a fraction of a cent for a smoke test. The per-note target
is 2 dollars, the project ceiling is 50.

**"Which model?"**
Claude Opus 5.5 at medium effort for the financial analyst, via the official SDK with structured
output. Model ids and effort are pinned in `config/models.yaml`; the prompt carries a version
number.

**"Can it do this for any company?"**
Any company with an NI 43-101 technical report in the drop folder. It has run on one real report
and one synthetic one. The index that finds the right sections is the part most likely to need
work on the next report, which is why a second real report is the first thing to add.

**"Does it generate alpha / give a recommendation?"**
No, by design. Francis and Zhang found no strategy generated alpha. The product is synthesis,
speed and coverage. Stance language is restricted to Favourable, Neutral or Unfavourable on
disclosed fundamentals, there are no price targets, and the disclaimer at the bottom of every
note is fixed text.

**"What about the paper's LLM judges?"**
The paper found them unstable, 48 to 96 percent depending on model, so the spec lists
"LLM-judge scores presented as evidence of quality" as an anti-goal. Judges will exist for
internal regression checks only; the quality claim rests on verification rate and human audit.

**"What is next?"**
Config loader, SQLite ledger, the remaining four sections and agents, tier-2 LLM verification,
the dashboard with PDF page viewer and snippet highlight, then the ten-company run and the
results summary. Roughly four weeks of sessions per the spec.

---

## Things not to say

- Any return, upside, or target language about Marimaca.
- "The model verified the numbers." Code verified them; the model only proposed them.
- "It works on any report." It has worked on one real report and needed two fixes to do so.
- Do not quote today's spot price as authoritative. US$6.71 is a 2026-10-13 quote; the slice has
  no price feed yet.

---

## If something breaks

- Replay fails (missing fixture): the recorded response lives in
  `tests/fixtures/llm/1bc990a873026319.json`; check that file exists and that `--provider fake`
  is on the command. The request key depends on the prompt file and the extracted pages, so do
  not edit `prompts/financial_analyst.md` or `config/sections.yaml` before the demo.
- Markdown preview looks wrong: show the raw `note.md` in the terminal with `cat`; the tables
  are readable as text.
- Preview page confusion: PDF index 329 is printed page 304; PDF 55 is printed 30; PDF 54 is
  printed 29; PDF 306 is printed 281; PDF 46 is printed 21.
- Everything fails: the mechanism is identical on the synthetic report; run
  `uv run python tests/fixtures/make_pdf.py /tmp/fixture.pdf` to build it, say the data is
  synthetic, and walk through the same steps with `tests/unit/test_cli.py` as the proof.
