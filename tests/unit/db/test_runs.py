"""F6.4 run record in SQLite."""

from datetime import date
from pathlib import Path

import pytest

from orebody.db import connect, current_version, migrate
from orebody.db.runs import RunRow, get_run, record_run
from orebody.verify.stats import RunStats

STATS = RunStats(
    total=10,
    verified=9,
    tier1_pass=9,
    verification_rate=0.9,
    tier1_rate=0.9,
    unverified_by_section={3: 1},
    cost_usd=0.3391,
    seconds=4.2,
)


@pytest.fixture
def conn(tmp_path: Path):
    c = connect(tmp_path / "t.sqlite")
    migrate(c)
    return c


def _row(**kw) -> RunRow:
    base = dict(
        run_id="MARI-2026-11-05-104923",
        ticker="MARI",
        company_name="Marimaca Copper Corp.",
        as_of=date(2026, 11, 5),
        started_at="2026-11-05T10:49:23Z",
        models={"financial_analyst": {"model": "claude-opus-5-5", "effort": "medium"}},
        prompt_versions={"financial_analyst": "1"},
        document_ids=["MARI/2025-08-25_MarimacaOxide_FS_NI43-101"],
        price_deck={"spot_usd_per_lb": 6.71, "deck_a_usd_per_lb": 3.5, "source": "cli"},
    )
    return RunRow(**(base | kw))


def test_migration_0002_adds_the_stats_column(conn) -> None:
    assert current_version(conn) == 2
    cols = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
    assert "stats" in cols


def test_running_then_done(conn) -> None:
    record_run(conn, _row())
    assert get_run(conn, "MARI-2026-11-05-104923")["status"] == "running"
    record_run(conn, _row(status="done", stats=STATS))
    r = get_run(conn, "MARI-2026-11-05-104923")
    assert r["status"] == "done"
    assert r["stats"]["verified"] == 9 and r["stats"]["unverified_by_section"] == {"3": 1}
    assert r["cost_usd"] == pytest.approx(0.3391) and r["wall_seconds"] == pytest.approx(4.2)
    assert r["models"]["financial_analyst"]["model"] == "claude-opus-5-5"
    assert r["as_of"] == "2026-11-05"
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1  # upsert, not insert


def test_company_row_is_created_if_missing(conn) -> None:
    record_run(conn, _row())
    row = conn.execute("SELECT name FROM companies WHERE ticker = 'MARI'").fetchone()
    assert row[0] == "Marimaca Copper Corp."


def test_existing_company_row_is_left_alone(conn) -> None:
    conn.execute(
        "INSERT INTO companies (ticker, name, exchange) VALUES ('MARI', 'Marimaca', 'TSX')"
    )
    record_run(conn, _row())
    row = conn.execute("SELECT name, exchange FROM companies WHERE ticker = 'MARI'").fetchone()
    assert tuple(row) == ("Marimaca", "TSX")


def test_unknown_status_is_rejected(conn) -> None:
    with pytest.raises(Exception, match="CHECK"):
        record_run(conn, _row(status="paused"))


def test_get_missing_run(conn) -> None:
    assert get_run(conn, "nope") is None
