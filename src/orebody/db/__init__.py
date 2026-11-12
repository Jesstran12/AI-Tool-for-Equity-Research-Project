"""F0.3 SQLite store and plain-SQL migration runner (SPEC §5.6).

Migrations are files `NNNN_name.sql` in `migrations/`, applied once each in numeric order, each
inside its own transaction, and recorded in `schema_migrations(version, name, applied_at)`.
A failing migration leaves no trace: its tables are rolled back and its version is not recorded.
Foreign keys are switched on for every connection (SQLite leaves them off by default).
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
DEFAULT_DB = Path("data/orebody.sqlite")


_FILE = re.compile(r"(\d{4})_([A-Za-z0-9_]+)\.sql")
_TRACKING = """CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TEXT NOT NULL
)"""


def connect(path: Path | str) -> sqlite3.Connection:
    """Open (creating parent dirs) with foreign keys on and rows as sqlite3.Row."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Autocommit mode: migrate() opens and closes its own transactions explicitly.
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migration_files(migrations_dir: Path = MIGRATIONS_DIR) -> list[tuple[int, str, Path]]:
    """(version, name, path) sorted by version. Raises ValueError on a file not named NNNN_x.sql
    or on two files with the same version."""
    found: dict[int, Path] = {}
    for path in sorted(Path(migrations_dir).iterdir()):
        if path.is_dir() or path.name.startswith("."):
            continue
        m = _FILE.fullmatch(path.name)
        if not m:
            raise ValueError(f"migration file {path.name} is not named NNNN_name.sql")
        version = int(m.group(1))
        if version in found:
            raise ValueError(
                f"duplicate migration version {m.group(1)}: {found[version].name}, {path.name}"
            )
        found[version] = path
    return [(v, p.stem, p) for v, p in sorted(found.items())]


def current_version(conn: sqlite3.Connection) -> int:
    """Highest applied version; 0 for a fresh database."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if not exists:
        return 0
    return conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]


def migrate(conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations; return the names applied (empty when up to date)."""
    conn.execute(_TRACKING)
    done = current_version(conn)
    applied: list[str] = []
    for version, name, path in migration_files(migrations_dir):
        if version <= done:
            continue
        now = datetime.now(UTC).isoformat(timespec="seconds")
        # One script per migration: its DDL and its schema_migrations row commit together or
        # not at all (SQLite DDL is transactional). Names are [A-Za-z0-9_], safe to inline.
        script = (
            "BEGIN;\n"
            + path.read_text()
            + f"\n;INSERT INTO schema_migrations VALUES ({version}, '{name}', '{now}');\nCOMMIT;"
        )
        try:
            conn.executescript(script)
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        applied.append(name)
    return applied


def init_db(path: Path | str = DEFAULT_DB) -> list[str]:
    """`orebody db init`: create or upgrade the database at `path`; return migrations applied."""
    conn = connect(path)
    try:
        return migrate(conn)
    finally:
        conn.close()
