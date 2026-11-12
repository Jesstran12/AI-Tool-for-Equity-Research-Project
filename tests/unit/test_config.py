"""F0.2 config loader: defaults, overrides, and the rejections ground rules require."""

from datetime import date
from pathlib import Path

import pytest
import yaml

from orebody.config import AGENT_DEFAULTS, CONFIG_DIR, load_config
from orebody.llm.cost import load_prices

SECTIONS = (CONFIG_DIR / "sections.yaml").read_text()
PRICES_BLOCK = {
    "prices_usd_per_mtok": {
        "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.20},
        "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.20},
    }
}


def _dir(tmp_path: Path, models: dict, prices: str | None = None, fx: str | None = None) -> Path:
    d = tmp_path / "config"
    d.mkdir()
    (d / "models.yaml").write_text(yaml.safe_dump(models))
    (d / "sections.yaml").write_text(SECTIONS)
    if prices is not None:
        (d / "prices.yaml").write_text(prices)
    if fx is not None:
        (d / "fx.yaml").write_text(fx)
    return d


def _models(**agents) -> dict:
    return {**agents, **PRICES_BLOCK}


# --- the repo's own config --------------------------------------------------------------------


def test_repo_config_loads() -> None:
    c = load_config()
    fa = c.agent("financial_analyst")
    assert (fa.model, fa.effort) == ("claude-opus-5-5", "medium")
    assert sorted(c.sections) == list(range(1, 28))
    assert c.market.proxies["Cu"] == "HG=F"
    assert (c.market.deck_a_usd_per_lb, c.market.deck_b_usd_per_lb) == (3.50, 5.00)
    assert c.fx == {}


def test_prices_match_the_cost_logger() -> None:
    # llm/cost.py keeps reading models.yaml directly; both must see the same numbers
    c = load_config()
    raw = load_prices(CONFIG_DIR / "models.yaml")
    assert {m: p.model_dump() for m, p in c.prices.items()} == {
        m: {"cache_read": 0.0, **p} for m, p in raw.items()
    }


# --- defaults ---------------------------------------------------------------------------------


def test_missing_agents_get_d31_defaults(tmp_path: Path) -> None:
    fa = {"model": "claude-opus-5-5", "effort": "high"}
    c = load_config(_dir(tmp_path, _models(financial_analyst=fa)))
    assert c.agent("financial_analyst").effort == "high"  # file wins over default
    for name, d in AGENT_DEFAULTS.items():
        if name != "financial_analyst":
            assert c.agent(name).model_dump() == d
    # D31 tiering
    assert c.agent("verifier_tier2").model == "claude-opus-5-5"
    assert c.agent("project_analyst").model == "claude-sonnet-5-5"


def test_optional_files_absent_give_defaults(tmp_path: Path) -> None:
    c = load_config(_dir(tmp_path, _models()))
    assert c.market.proxies == {"Cu": "HG=F"}
    assert c.market.overrides == {}
    assert c.market.deck_a_usd_per_lb is None
    assert c.fx == {}


def test_unknown_agent_raises_with_its_name(tmp_path: Path) -> None:
    c = load_config(_dir(tmp_path, _models()))
    with pytest.raises(KeyError, match="geologist"):
        c.agent("geologist")


# --- overrides --------------------------------------------------------------------------------


def test_single_model_override_keeps_effort(tmp_path: Path) -> None:
    c = load_config(_dir(tmp_path, _models()), single_model="claude-sonnet-5-5")
    assert {a.model for a in c.agents.values()} == {"claude-sonnet-5-5"}
    assert c.agent("financial_analyst").effort == AGENT_DEFAULTS["financial_analyst"]["effort"]


def test_price_override_and_fx_are_parsed(tmp_path: Path) -> None:
    prices = """
proxies: {Cu: HG=F}
overrides:
  Cu: {value: 4.95, unit: USD/lb, as_of: 2026-11-10, source: "COMEX settle, desk sheet"}
deck_a_usd_per_lb: 4.00
"""
    fx = 'rates:\n  CAD: {usd_per_unit: 0.72, as_of: 2026-11-10, source: "Bank of Canada"}\n'
    c = load_config(_dir(tmp_path, _models(), prices=prices, fx=fx))
    o = c.market.overrides["Cu"]
    assert (o.value, o.unit, o.as_of) == (4.95, "USD/lb", date(2026, 11, 10))
    assert c.market.deck_a_usd_per_lb == 4.00 and c.market.deck_b_usd_per_lb is None
    assert c.fx["CAD"].usd_per_unit == 0.72


# --- rejections -------------------------------------------------------------------------------


@pytest.mark.parametrize("effort", ["extreme", "MEDIUM", "", "auto"])
def test_invalid_effort_rejected(tmp_path: Path, effort: str) -> None:
    d = _dir(tmp_path, _models(financial_analyst={"model": "claude-opus-5-5", "effort": effort}))
    with pytest.raises(ValueError, match="models.yaml.*financial_analyst.*effort"):
        load_config(d)


@pytest.mark.parametrize("key", ["temperature", "top_p", "thinking", "budget_tokens"])
def test_sampling_and_thinking_params_rejected(tmp_path: Path, key: str) -> None:
    # Ground rule 6: never pass temperature; omit thinking (adaptive). Current models 400 on these.
    agent = {"model": "claude-opus-5-5", "effort": "medium", key: 0.2}
    with pytest.raises(ValueError, match=key):
        load_config(_dir(tmp_path, _models(financial_analyst=agent)))


def test_model_without_price_rejected(tmp_path: Path) -> None:
    d = _dir(tmp_path, _models(advisor={"model": "claude-haiku-5-5", "effort": "low"}))
    with pytest.raises(ValueError, match="claude-haiku-5-5.*price"):
        load_config(d)


def test_single_model_without_price_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="claude-fable-5-1.*price"):
        load_config(_dir(tmp_path, _models()), single_model="claude-fable-5-1")


def test_bad_price_unit_rejected(tmp_path: Path) -> None:
    prices = 'overrides:\n  Cu: {value: 9900, unit: "USD/kg", as_of: 2026-11-10, source: x}\n'
    with pytest.raises(ValueError, match="prices.yaml.*unit"):
        load_config(_dir(tmp_path, _models(), prices=prices))


def test_fx_rate_without_source_rejected(tmp_path: Path) -> None:
    # No number without a source (ground rule 3), config included
    fx = "rates:\n  CAD: {usd_per_unit: 0.72, as_of: 2026-11-10}\n"
    with pytest.raises(ValueError, match="fx.yaml.*source"):
        load_config(_dir(tmp_path, _models(), fx=fx))


def test_missing_required_file_names_it(tmp_path: Path) -> None:
    d = _dir(tmp_path, _models())
    (d / "sections.yaml").unlink()
    with pytest.raises(ValueError, match="sections.yaml"):
        load_config(d)


def test_repo_config_dir_is_untouched() -> None:
    # Loading must not write anything into config/
    before = sorted(p.name for p in CONFIG_DIR.iterdir())
    load_config()
    assert sorted(p.name for p in CONFIG_DIR.iterdir()) == before
