"""Idempotent v8 migration: remove the Portfolio + Contact + Profile features.

Drops the now-unused tables (sales, holdings, contact_messages) and the
columns those features added to users (budget, first_name, last_name, mobile,
avatar). Safe to run repeatedly on SQLite (>=3.35) and Postgres.

    python scripts/migrate_v8.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import engine, ensure_schema  # noqa: E402

# Order matters: sales references holdings, so drop it first.
_DROP_TABLES = ("sales", "holdings", "contact_messages")
_DROP_COLUMNS = (
    ("users", "budget"),
    ("users", "first_name"),
    ("users", "last_name"),
    ("users", "mobile"),
    ("users", "avatar"),
)


def _exec(sql: str) -> None:
    """Run one statement in its own transaction; tolerate 'does not exist'."""
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
        print(f"ok: {sql}")
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if "exist" in msg or "no such" in msg:
            print(f"skip (already gone): {sql}")
        else:
            print(f"warn: could not run [{sql}]: {e}")


def main() -> None:
    # Keep the rest of the schema in sync first (create_all + column adds).
    ensure_schema()

    for table in _DROP_TABLES:
        _exec(f"DROP TABLE IF EXISTS {table}")

    for table, col in _DROP_COLUMNS:
        # Postgres supports IF EXISTS; SQLite (>=3.35) does not, so fall back.
        if engine.dialect.name == "sqlite":
            _exec(f"ALTER TABLE {table} DROP COLUMN {col}")
        else:
            _exec(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {col}")

    print(f"done. dialect={engine.dialect.name}")


if __name__ == "__main__":
    main()
