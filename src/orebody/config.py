"""F0.2 typed config: one object for models, prices, FX and section titles.

Files in config/ (SPEC §5.1):
- models.yaml     required. Per-agent {model, effort}; `prices_usd_per_mtok` per model id.
                  Agents missing from the file get the D31 defaults below. An agent entry with any
                  other key (temperature, top_p, thinking, budget_tokens) is rejected: current
                  models return 400 for sampling params and thinking budgets (ground rule 6).
- sections.yaml   required. NI 43-101 item number -> heading title (existing loader).
- prices.yaml     optional. yfinance proxy per commodity, manual overrides (value, unit, as-of,
                  source), default decks A/B in USD/lb. Absent file -> Cu proxy HG=F, nothing else.
- fx.yaml         optional. Fallback FX when the report states none (D14). Absent -> empty.

Overrides: `single_model` (D31 "a single-model run is one flag") replaces every agent's model and
keeps its effort. CLI flags (e.g. --deck-a) beat config defaults; that wiring is in the CLI.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from orebody.index.ni43101 import load_patterns

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

# Valid output_config.effort values on claude-opus-5-5 and claude-sonnet-5-5 (claude-api reference,
# checked 2026-11-11). Opus 5.5 defaults to medium, Sonnet 5.5 to high, so effort is always pinned.
Effort = Literal["low", "medium", "high", "xhigh", "max"]

# SPEC D31: Financial Analyst and tier-2 Verifier on Opus; Project Analyst, Advisor, vision
# fallback on Sonnet. Efforts are the models' API defaults, pinned so a default change upstream
# cannot change a run (ground rule 6).
AGENT_DEFAULTS: dict[str, dict[str, str]] = {
    "financial_analyst": {"model": "claude-opus-5-5", "effort": "medium"},
    "verifier_tier2": {"model": "claude-opus-5-5", "effort": "medium"},
    "project_analyst": {"model": "claude-sonnet-5-5", "effort": "high"},
    "advisor": {"model": "claude-sonnet-5-5", "effort": "high"},
    "vision": {"model": "claude-sonnet-5-5", "effort": "high"},
}


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    model: str
    effort: Effort


class ModelPrice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    input: float
    output: float
    cache_read: float = 0.0


class PriceOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    value: float
    unit: Literal["USD/lb", "USD/t"]
    as_of: date
    source: str


class MarketConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    proxies: dict[str, str] = {"Cu": "HG=F"}
    overrides: dict[str, PriceOverride] = {}
    deck_a_usd_per_lb: float | None = None
    deck_b_usd_per_lb: float | None = None


class FxRate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    usd_per_unit: float
    as_of: date
    source: str


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)
    agents: dict[str, AgentConfig]
    prices: dict[str, ModelPrice]  # USD per million tokens, by model id
    market: MarketConfig
    fx: dict[str, FxRate]  # by ISO currency code
    sections: dict[int, str]

    def agent(self, name: str) -> AgentConfig:
        """The agent's config; KeyError names the agent if it is unknown."""
        if name not in self.agents:
            raise KeyError(f"unknown agent {name!r}; known: {', '.join(sorted(self.agents))}")
        return self.agents[name]

    def price_table(self) -> dict[str, dict[str, float]]:
        """Prices in the plain-dict shape llm/cost.py and AnthropicProvider take."""
        return {m: p.model_dump() for m, p in self.prices.items()}


def _errors(e: ValidationError) -> str:
    """One line per pydantic error: 'field.path: message', joined with '; '."""
    return "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())


def _read_yaml(path: Path, required: bool) -> dict:
    if not path.exists():
        if required:
            raise ValueError(f"{path.name} not found in {path.parent}")
        return {}
    return yaml.safe_load(path.read_text()) or {}


def load_config(config_dir: Path = CONFIG_DIR, single_model: str | None = None) -> Config:
    """Load and validate config/. Raises ValueError naming the file and field on bad input,
    including an agent whose model has no price (cost logging needs one, ground rule 7)."""
    config_dir = Path(config_dir)
    raw = dict(_read_yaml(config_dir / "models.yaml", required=True))
    raw_prices = raw.pop("prices_usd_per_mtok", {}) or {}

    try:
        prices = {m: ModelPrice.model_validate(p) for m, p in raw_prices.items()}
    except ValidationError as e:
        raise ValueError(f"models.yaml: prices_usd_per_mtok: {_errors(e)}") from e

    agents: dict[str, AgentConfig] = {}
    for name in sorted(set(AGENT_DEFAULTS) | set(raw)):
        entry = raw.get(name, AGENT_DEFAULTS.get(name))
        try:
            agent = AgentConfig.model_validate(entry)
        except ValidationError as e:
            raise ValueError(f"models.yaml: agent {name}: {_errors(e)}") from e
        if single_model:
            agent = agent.model_copy(update={"model": single_model})
        agents[name] = agent
    for name, agent in agents.items():
        if agent.model not in prices:
            raise ValueError(
                f"{agent.model} (agent {name}) has no price in models.yaml prices_usd_per_mtok"
            )

    if not (config_dir / "sections.yaml").exists():
        raise ValueError(f"sections.yaml not found in {config_dir}")
    sections = load_patterns(config_dir / "sections.yaml")

    try:
        market = MarketConfig.model_validate(_read_yaml(config_dir / "prices.yaml", False))
    except ValidationError as e:
        raise ValueError(f"prices.yaml: {_errors(e)}") from e

    fx: dict[str, FxRate] = {}
    for code, rate in (_read_yaml(config_dir / "fx.yaml", False).get("rates") or {}).items():
        try:
            fx[code] = FxRate.model_validate(rate)
        except ValidationError as e:
            raise ValueError(f"fx.yaml: {code}: {_errors(e)}") from e

    return Config(agents=agents, prices=prices, market=market, fx=fx, sections=sections)
