"""`orebody run TICKER --as-of DATE --spot USD/lb`: one technical report → Section 3 note."""

from __future__ import annotations

import json
import time
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer
import yaml

from orebody.agents.context import build_context
from orebody.agents.financial_analyst import load_prompt, run_financial_analyst
from orebody.agents.schemas import EconInputs
from orebody.core.npv import NpvInputs, NpvResult, npv
from orebody.core.units import Quantity, to_usd_per_t
from orebody.index.ni43101 import build_index, load_patterns
from orebody.ingest.extract import extract_pages, read_page
from orebody.ingest.manifest import load_manifest
from orebody.llm.anthropic_provider import AnthropicProvider
from orebody.llm.cost import load_prices
from orebody.llm.fake import FakeProvider
from orebody.llm.provider import LLMProvider
from orebody.render.markdown import PriceDeck, render_section3
from orebody.verify.tier1 import verification_rate, verify_tier1

app = typer.Typer(no_args_is_help=True, add_completion=False)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
PROMPT_PATH = ROOT / "prompts" / "financial_analyst.md"
NPV_FIELDS = (
    "mine_life_years",
    "annual_payable_metal_t",
    "unit_cost_usd_per_t",
    "initial_capex_usd_m",
    "sustaining_capex_usd_m",
    "tax_rate",
    "discount_rate",
    "company_base_price_usd_per_t",
)


@app.callback()
def main() -> None:
    """Orebody: source-linked equity research notes for copper juniors."""


def _per_lb(price: float | None) -> float | None:
    return None if price is None else to_usd_per_t(Quantity(price, "per_lb", "USD"))


def _npv_results(
    inputs: EconInputs, deck: PriceDeck
) -> tuple[dict[str, NpvResult] | None, list[str]]:
    missing = [f for f in NPV_FIELDS if getattr(inputs, f) is None]
    if missing:
        return None, missing
    npv_inputs = NpvInputs(
        mine_life_years=int(round(inputs.mine_life_years)),
        annual_payable_metal_t=inputs.annual_payable_metal_t,
        unit_cost_usd_per_t=inputs.unit_cost_usd_per_t,
        initial_capex_usd_m=inputs.initial_capex_usd_m,
        sustaining_capex_usd_m=inputs.sustaining_capex_usd_m,
        tax_rate=inputs.tax_rate,
        discount_rate=inputs.discount_rate,
    )
    prices = {
        "base": inputs.company_base_price_usd_per_t,
        "spot": deck.spot_usd_per_t,
        "deck_a": deck.deck_a_usd_per_t,
        "deck_b": deck.deck_b_usd_per_t,
    }
    return {k: npv(npv_inputs, p) for k, p in prices.items() if p is not None}, []


@app.command()
def run(
    ticker: str,
    as_of: Annotated[datetime, typer.Option(formats=["%Y-%m-%d"], help="As-of date")],
    spot: Annotated[float, typer.Option(help="Spot copper price, USD/lb")],
    deck_a: Annotated[float | None, typer.Option(help="Price deck A, USD/lb")] = None,
    deck_b: Annotated[float | None, typer.Option(help="Price deck B, USD/lb")] = None,
    provider: Annotated[str, typer.Option(help="anthropic | fake")] = "anthropic",
    data_dir: Annotated[Path, typer.Option(help="Data root (raw/, pages/, runs/)")] = Path("data"),
    fixtures: Annotated[Path, typer.Option(help="Recorded LLM responses")] = Path(
        "tests/fixtures/llm"
    ),
) -> None:
    """Build the Section 3 (Economics) note for TICKER from its technical report."""
    t0 = time.time()
    as_of_date: date = as_of.date()
    ticker = ticker.upper()
    raw_dir = data_dir / "raw" / ticker
    manifest_path = raw_dir / "manifest.yaml"
    if not manifest_path.exists():
        typer.echo(f"error: {manifest_path} not found", err=True)
        raise typer.Exit(code=2)
    manifest = load_manifest(manifest_path)
    report = manifest.technical_report()
    if report.filing_date > as_of_date:
        typer.echo(
            f"error: technical report filed {report.filing_date} is after as-of {as_of_date}",
            err=True,
        )
        raise typer.Exit(code=2)

    pdf_path = raw_dir / report.file
    if not pdf_path.exists():
        typer.echo(
            f"error: {pdf_path} not found. Company PDFs are not committed; download it as "
            "described in README.md (or run `make demo-data` for the synthetic FIX company).",
            err=True,
        )
        raise typer.Exit(code=2)

    run_id = f"{ticker}-{as_of_date.isoformat()}-{datetime.now().strftime('%H%M%S')}"
    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    extracted = extract_pages(pdf_path, data_dir / "pages")
    pages = [read_page(extracted.pages_dir, n) for n in range(1, extracted.n_pages + 1)]
    index = build_index(pages, load_patterns(CONFIG_DIR / "sections.yaml"))
    bundle = build_context(extracted.pages_dir, index)
    (run_dir / "context.txt").write_text(bundle.text)
    if bundle.items_missing:
        typer.echo(f"warning: items not found in index: {bundle.items_missing}", err=True)

    models = yaml.safe_load((CONFIG_DIR / "models.yaml").read_text())
    model, effort = models["financial_analyst"]["model"], models["financial_analyst"]["effort"]
    llm: LLMProvider
    if provider == "fake":
        llm = FakeProvider(fixtures)
    elif provider == "anthropic":
        llm = AnthropicProvider(
            record_dirs=[fixtures, run_dir], prices=load_prices(CONFIG_DIR / "models.yaml")
        )
    else:
        typer.echo(f"error: unknown provider {provider!r}", err=True)
        raise typer.Exit(code=2)
    prompt_version, system = load_prompt(PROMPT_PATH)
    (run_dir / "request.json").write_text(
        json.dumps(
            {"model": model, "effort": effort, "prompt_version": prompt_version, "system": system},
            indent=2,
        )
    )

    output, completion = run_financial_analyst(
        llm, bundle, extracted.doc_id, model, effort, PROMPT_PATH
    )
    (run_dir / "output.json").write_text(
        json.dumps(
            {
                "parsed": completion.parsed,
                "usage": completion.usage.model_dump(),
                "model": completion.model,
                "cost_usd": completion.cost_usd,
                "request_key": completion.request_key,
                "raw_text": completion.raw_text,
            },
            indent=2,
        )
    )

    verified = verify_tier1(output.claims, lambda n: read_page(extracted.pages_dir, n))
    (run_dir / "claims.json").write_text(json.dumps([c.model_dump() for c in verified], indent=2))

    deck = PriceDeck(
        spot_usd_per_t=_per_lb(spot),
        deck_a_usd_per_t=_per_lb(deck_a),
        deck_b_usd_per_t=_per_lb(deck_b),
        source="cli",
    )
    results, missing = _npv_results(output.inputs, deck)
    note = render_section3(
        ticker=ticker,
        name=manifest.name,
        as_of=as_of_date,
        doc_id=extracted.doc_id,
        inputs=output.inputs,
        claims=verified,
        deck=deck,
        results=results,
        missing=missing,
        run_id=run_id,
        cost_usd=completion.cost_usd,
    )
    (run_dir / "note.md").write_text(note)

    rate = verification_rate(verified)
    stats = {
        "run_id": run_id,
        "ticker": ticker,
        "as_of": as_of_date.isoformat(),
        "verified": sum(1 for c in verified if c.final_status == "verified"),
        "total": len(verified),
        "rate": round(rate, 4),
        "cost_usd": round(completion.cost_usd, 6),
        "seconds": round(time.time() - t0, 1),
        "model": completion.model,
        "prompt_version": prompt_version,
        "items_missing": bundle.items_missing,
        "doc_sha256": extracted.sha256,
        "npv_missing_fields": missing,
    }
    (run_dir / "stats.json").write_text(json.dumps(stats, indent=2))
    typer.echo(
        f"{run_id}: verified {stats['verified']}/{stats['total']} rate={rate:.2f} "
        f"cost=US${stats['cost_usd']:.4f} seconds={stats['seconds']} "
        f"items_missing={bundle.items_missing} note={run_dir / 'note.md'}"
    )


@app.command()
def discover(
    as_of: Annotated[datetime, typer.Option(formats=["%Y-%m-%d"], help="As-of date")],
    candidates: Annotated[Path, typer.Option(help="Hand-kept SEDAR+-only candidates")] = (
        CONFIG_DIR / "candidates.yaml"
    ),
    out: Annotated[Path, typer.Option(help="Output JSON")] = Path("data/universe/candidates.json"),
) -> None:
    """Find candidate copper projects with a technical report (SPEC §10.2, F1.5)."""
    from orebody.ingest import discover as disc

    found = disc.discover(
        disc.EdgarClient(disc.http_fetch),
        candidates if candidates.exists() else None,
        as_of.date(),
    )
    disc.write_candidates(found, out)
    n_in = sum(c.included for c in found)
    typer.echo(f"{n_in} included, {len(found) - n_in} excluded -> {out}")


@app.command()
def crosscheck(
    ticker: str,
    data_dir: Annotated[Path, typer.Option(help="Data root (raw/)")] = Path("data"),
) -> None:
    """Compare each collected document with its EDGAR copy (F1.8)."""
    from orebody.ingest.alternate import crosscheck_folder
    from orebody.ingest.discover import EdgarClient, http_fetch

    rows = crosscheck_folder(data_dir / "raw" / ticker.upper(), EdgarClient(http_fetch))
    for r in rows:
        if r["status"] != "no_alternate":
            typer.echo(f"{r['status']:<11} {r.get('number_overlap', 0):.2f}  {r['file']}")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    typer.echo(" ".join(f"{k}={v}" for k, v in sorted(counts.items())))
