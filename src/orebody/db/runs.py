"""F6.4: write the run record (SPEC §5.5) to the `runs` table.

`record_run` upserts by run_id, so `orebody run` can write status 'running' when it starts and
'done' or 'failed' at the end. The company row is created with ticker and name if missing (the
runs.ticker foreign key needs it); `orebody ingest` fills in the rest.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from pydantic import BaseModel

from orebody.verify.stats import RunStats


class RunRow(BaseModel):
    run_id: str
    ticker: str
    company_name: str
    as_of: date
    started_at: str  # ISO 8601 UTC
    status: str = "running"  # running | done | failed
    git_sha: str = ""
    models: dict = {}
    prompt_versions: dict = {}
    document_ids: list[str] = []
    excluded_docs: list[str] = []
    price_deck: dict = {}
    stats: RunStats | None = None


_JSON_COLUMNS = ("models", "prompt_versions", "document_ids", "excluded_docs", "price_deck", "fx")


def record_run(conn: sqlite3.Connection, row: RunRow) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO companies (ticker, name) VALUES (?, ?)",
        (row.ticker, row.company_name),
    )
    stats = row.stats.model_dump() if row.stats else {}
    conn.execute(
        """INSERT INTO runs (run_id, ticker, as_of, started_at, git_sha, models, prompt_versions,
               document_ids, excluded_docs, price_deck, cost_usd, wall_seconds, status, stats)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(run_id) DO UPDATE SET status = excluded.status,
               cost_usd = excluded.cost_usd, wall_seconds = excluded.wall_seconds,
               stats = excluded.stats, document_ids = excluded.document_ids,
               excluded_docs = excluded.excluded_docs, price_deck = excluded.price_deck,
               models = excluded.models, prompt_versions = excluded.prompt_versions""",
        (
            row.run_id,
            row.ticker,
            row.as_of.isoformat(),
            row.started_at,
            row.git_sha,
            json.dumps(row.models),
            json.dumps(row.prompt_versions),
            json.dumps(row.document_ids),
            json.dumps(row.excluded_docs),
            json.dumps(row.price_deck),
            row.stats.cost_usd if row.stats else 0.0,
            row.stats.seconds if row.stats else None,
            row.status,
            json.dumps(stats),
        ),
    )


def get_run(conn: sqlite3.Connection, run_id: str) -> dict | None:
    """The stored row as a dict with JSON columns decoded; None if absent."""
    r = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if r is None:
        return None
    out = dict(r)
    for col in (*_JSON_COLUMNS, "stats"):
        out[col] = json.loads(out[col])
    return out
