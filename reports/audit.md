# Audit — first live note for MARI (demo slice, 2026-11-05)

Run `MARI-2026-11-05-104632` made the live call (claude-opus-5-5, effort medium, prompt v1,
fixture `tests/fixtures/llm/1bc990a873026319.json`, 72,073 input / 2,540 output tokens,
US$0.3391). It aborted after the call because the model invented a document id; the pipeline
now stamps `doc_id` itself (commit "D9: pipeline stamps claim doc_id"). Runs
`MARI-2026-11-05-104838` and `-104923` replay that recording and produced the note.

Stats: `verified 10/10 rate=1.00 cost=US$0.3391 items_missing=[]`.

## Figures checked by hand against the report (page = PDF page in `data/pages/...`)

| Field | Note | Report | Page | Verdict |
|---|---|---|---|---|
| Initial capex | US$586.6 million | "Initial capital costs are estimated to be US$586.6 million." | 329 | correct |
| Post-tax NPV8% | US$709 million | "On a post-tax basis, the NPV8% is US$709 million" | 55 | correct (base case) |
| Post-tax IRR | 30.9% | same sentence | 55 | correct |
| Base copper price | US$4.30/lb | "The flat long-term copper price used in the analysis is US$4.30/lb" | 54 | correct |
| Mine life | 12.7 years | "The project has a planned mine life of 12.7 years." | 54 | correct (company summary says ~13-year reserve life; report states 12.7) |
| Tax rate | 27% | "The Chilean corporate income tax system consists of 27% income tax." | 329 | correct |
| Discount rate | 8% | "based on an 8% discount rate" | 54 | correct |
| Sustaining capital | US$529 million | "LOM sustaining capital ... US$529 million" | 306, 329 | correct, but see note 2 |
| Unit cost | US$1.84/lb (cash cost) | "Cash Costs* US$/lb Cu $1.84" | 55 | correct; AISC is US$2.29/lb (model said so in `notes`) |
| Annual payable metal | 50,000 t/a cathode | "to produce 50,000 t/a of copper cathode" | 46 | nameplate, see note 1 |

No figure in the note is wrong. All ten claims passed tier-1 (quote and number on the cited page).

## Notes on the rebuilt NPV (gap −19.6%: rebuilt US$570 M vs stated US$709 M)

1. **Annual metal.** The engine uses the 50,000 t/a nameplate for every production year; the
   report's cash-flow table gives 539,424 t recovered over 12.7 years (≈42,500 t/a average), so
   the engine over-produces in late years but also applies a 0.7 ramp in year 1 that the report
   may not. Net effect is modest; the main gap is item 3.
2. **Expansion capital.** Page 329 states expansion capital of US$77 million separately from
   sustaining capital (US$529 million). `NpvInputs` has no expansion field, so the rebuilt case
   omits it (which would *lower* the rebuilt NPV further).
3. **Model shape.** The engine spreads capex evenly over a default 2-year construction period and
   charges sustaining capital evenly over the mine life; the company's model has its own schedule,
   working-capital, depreciation and royalty treatment. SPEC §7 expects a gap; the note reports
   it rather than tuning parameters to hide it (CLAUDE.md rule 4).
4. **Mine life rounding.** The engine takes integer production years (13 for 12.7); the note's
   Value column shows 12.7 as disclosed (fixed in "D11: show a fractional mine life as disclosed").

## Open items for the post-demo return path

- Add `expansion_capex_usd_m` and a per-year production profile to `NpvInputs` (F3.3).
- The index needed a TOC rule change for this report (dot-leader pages, contiguous run); add a
  second real report to the fixture set before F2.1.
- Spot price was US$6.71/lb from a 2026-10-13 quote (no live feed in this slice; F1.4 `prices.py`).
