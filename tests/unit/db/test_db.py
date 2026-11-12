"""F0.3 SQLite schema + migration runner. Every test uses a fresh database in tmp_path."""

import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from orebody.db import (
    MIGRATIONS_DIR,
    connect,
    current_version,
    init_db,
    migrate,
    migration_files,
)

TABLES = {
    "companies",
    "documents",
    "runs",
    "notes",
    "claims",
    "judge_scores",
    "overrides",
    "prices",
    "schema_migrations",
}
SHA = "a" * 64


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {r[0] for r in rows} - {"sqlite_sequence"}


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = connect(tmp_path / "t.sqlite")
    migrate(c)
    return c


def _seed(conn: sqlite3.Connection) -> None:
    """One company, document, run and note, so claims have something to point at."""
    conn.execute("INSERT INTO companies (ticker, name) VALUES ('FIX', 'Fixture Copper')")
    conn.execute(
        "INSERT INTO documents (doc_id, ticker, type, filing_date, path, sha256) "
        "VALUES ('d1', 'FIX', 'technical_report', '2025-10-09', 'raw/FIX/r.pdf', ?)",
        (SHA,),
    )
    conn.execute(
        "INSERT INTO runs (run_id, ticker, as_of, started_at) "
        "VALUES ('r1', 'FIX', '2026-11-05', '2026-11-05T10:00:00Z')"
    )
    conn.execute(
        "INSERT INTO notes (note_id, run_id, ticker, created_at) "
        "VALUES ('n1', 'r1', 'FIX', '2026-11-05T10:01:00Z')"
    )


def _claim(conn: sqlite3.Connection, **kw) -> None:
    row = {
        "claim_id": "c1",
        "note_id": "n1",
        "section": 3,
        "field": "initial_capex",
        "claim_type": "number",
        "value_orig": "US$1,240 million",
        "doc_id": "d1",
        "page": 5,
        "quote": "Initial capital cost is estimated at US$1,240 million.",
        "final_status": "verified",
    } | kw
    cols = ", ".join(row)
    marks = ", ".join("?" * len(row))
    conn.execute(f"INSERT INTO claims ({cols}) VALUES ({marks})", list(row.values()))


# --- runner ----------------------------------------------------------------------------------


def test_fresh_database_gets_every_table(tmp_path: Path) -> None:
    c = connect(tmp_path / "t.sqlite")
    assert current_version(c) == 0
    applied = migrate(c)
    # Expected list updated for 0002_run_stats (F6.4) with the user's approval, 2026-11-12
    assert applied == ["0001_initial", "0002_run_stats"]
    assert TABLES <= _tables(c)
    assert current_version(c) == 2


def test_migrate_is_idempotent(conn: sqlite3.Connection) -> None:
    assert migrate(conn) == []
    assert current_version(conn) == 2  # 0002_run_stats (F6.4)


def test_new_migration_applies_once_in_order(tmp_path: Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    (d / "0001_initial.sql").write_text((MIGRATIONS_DIR / "0001_initial.sql").read_text())
    (d / "0002_add_flag.sql").write_text(
        "ALTER TABLE companies ADD COLUMN flagged INTEGER DEFAULT 0;"
    )
    c = connect(tmp_path / "t.sqlite")
    assert migrate(c, d) == ["0001_initial", "0002_add_flag"]
    assert migrate(c, d) == []
    assert current_version(c) == 2
    cols = {r[1] for r in c.execute("PRAGMA table_info(companies)")}
    assert "flagged" in cols


def test_failing_migration_leaves_no_trace(tmp_path: Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    (d / "0001_ok.sql").write_text("CREATE TABLE a (x INTEGER);")
    (d / "0002_bad.sql").write_text("CREATE TABLE b (x INTEGER);\nTHIS IS NOT SQL;")
    c = connect(tmp_path / "t.sqlite")
    with pytest.raises(sqlite3.Error):
        migrate(c, d)
    assert current_version(c) == 1  # 0001 kept, 0002 rolled back
    assert "a" in _tables(c) and "b" not in _tables(c)


@pytest.mark.parametrize("bad", ["001_short.sql", "0003-dash.sql", "0004_x.txt", "init.sql"])
def test_badly_named_migration_rejected(tmp_path: Path, bad: str) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    (d / "0001_ok.sql").write_text("SELECT 1;")
    (d / bad).write_text("SELECT 1;")
    with pytest.raises(ValueError, match=bad.replace(".", r"\.")):
        migration_files(d)


def test_duplicate_version_rejected(tmp_path: Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    (d / "0001_a.sql").write_text("SELECT 1;")
    (d / "0001_b.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="0001"):
        migration_files(d)


def test_connect_turns_foreign_keys_on(tmp_path: Path) -> None:
    c = connect(tmp_path / "sub" / "dir" / "t.sqlite")  # parent dirs are created
    assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_init_db_creates_the_file(tmp_path: Path) -> None:
    path = tmp_path / "data" / "orebody.sqlite"
    assert init_db(path) == ["0001_initial", "0002_run_stats"]  # 0002 added in F6.4
    assert path.exists()
    assert init_db(path) == []


# --- schema rules --------------------------------------------------------------------------


def test_valid_claim_round_trips(conn: sqlite3.Connection) -> None:
    _seed(conn)
    _claim(conn)
    row = conn.execute("SELECT * FROM claims WHERE claim_id = 'c1'").fetchone()
    assert row["page"] == 5 and row["tier1_status"] == "na" and row["tier2_status"] == "skipped"


def test_claim_needs_an_existing_note(conn: sqlite3.Connection) -> None:
    _seed(conn)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        _claim(conn, note_id="no-such-note")


def test_number_claim_without_source_rejected(conn: sqlite3.Connection) -> None:
    # Ground rule 3: no number without a source
    _seed(conn)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        _claim(conn, doc_id=None, page=None)


def test_synthesis_claim_may_lack_a_source(conn: sqlite3.Connection) -> None:
    _seed(conn)
    _claim(
        conn,
        claim_id="s1",
        claim_type="synthesis",
        doc_id=None,
        page=None,
        quote=None,
        value_orig=None,
        final_status="synthesis",
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"claim_type": "guess"},
        {"section": 6},
        {"section": 0},
        {"tier1_status": "maybe"},
        {"final_status": "probably"},
        {"page": 0},
        {"quote": "x" * 301},
        {"final_status": "synthesis"},  # a number claim cannot carry the synthesis status
    ],
)
def test_claim_constraints(conn: sqlite3.Connection, bad: dict) -> None:
    _seed(conn)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        _claim(conn, **bad)


def test_document_sha256_unique_per_company(conn: sqlite3.Connection) -> None:
    _seed(conn)
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(
            "INSERT INTO documents (doc_id, ticker, type, filing_date, path, sha256) "
            "VALUES ('d2', 'FIX', 'technical_report', '2025-10-09', 'raw/FIX/copy.pdf', ?)",
            (SHA,),
        )


def test_stance_language_is_constrained(conn: sqlite3.Connection) -> None:
    # Ground rule 10: only Favourable / Neutral / Unfavourable
    _seed(conn)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("UPDATE notes SET stance = 'Buy' WHERE note_id = 'n1'")


def test_price_cache_needs_a_source_and_unit(conn: sqlite3.Connection) -> None:
    sql = "INSERT INTO prices VALUES ('Cu', '2026-11-05', 4.95, ?, ?, '2026-11-05T21:00:00Z')"
    conn.execute(sql, ("USD/lb", "yfinance HG=F"))
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(sql.replace("'Cu'", "'Zn'"), ("USD/lb", ""))
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(sql.replace("'Cu'", "'Ni'"), ("USD/kg", "x"))


# --- CLI -------------------------------------------------------------------------------------


def test_db_init_cli(tmp_path: Path) -> None:
    from orebody.cli import app

    path = tmp_path / "orebody.sqlite"
    first = CliRunner().invoke(app, ["db", "init", "--path", str(path)])
    assert first.exit_code == 0, first.output
    assert "applied 0001_initial" in first.output
    assert "applied 0002_run_stats" in first.output  # F6.4
    again = CliRunner().invoke(app, ["db", "init", "--path", str(path)])
    assert again.exit_code == 0 and "up to date (version 2)" in again.output
