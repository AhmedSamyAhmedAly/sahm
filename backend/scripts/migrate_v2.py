"""Idempotent v2 migration: add new columns to existing tables (users, recommendations).

`Base.metadata.create_all` creates NEW tables but never ALTERs existing ones, so on a
DB that already holds v1 data (Neon prod) the new columns must be added explicitly.
Safe to re-run: each ALTER is wrapped and "column already exists" is ignored.

    python scripts/migrate_v2.py        # uses DATABASE_URL from env/.env
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import engine, init_db  # noqa: E402

_BOOL_TRUE = "TRUE"

# (table, column, column_type_sql)
_COLUMNS = [
    ("users", "is_active", f"BOOLEAN DEFAULT {_BOOL_TRUE}"),
    ("users", "last_login_at", "TIMESTAMP"),
    ("recommendations", "news_sentiment", "DOUBLE PRECISION"),
    ("recommendations", "news_label", "VARCHAR(16)"),
    ("recommendations", "news_thesis", "VARCHAR(512)"),
    ("recommendations", "news_catalyst", "BOOLEAN"),
    ("recommendations", "news", "JSON"),
]


def main() -> None:
    init_db()  # create any brand-new tables first
    dialect = engine.dialect.name
    added, skipped = 0, 0
    with engine.begin() as conn:
        for table, col, coltype in _COLUMNS:
            # SQLite ADD COLUMN doesn't accept DOUBLE PRECISION; map to REAL.
            t = coltype.replace("DOUBLE PRECISION", "REAL") if dialect == "sqlite" else coltype
            sql = f"ALTER TABLE {table} ADD COLUMN {col} {t}"
            try:
                conn.execute(text(sql))
                print(f"+ added {table}.{col}")
                added += 1
            except Exception as e:  # noqa: BLE001 — duplicate column is expected on re-run
                msg = str(e).lower()
                if "exist" in msg or "duplicate" in msg:
                    print(f"= {table}.{col} already present")
                    skipped += 1
                else:
                    raise
    # Backfill is_active for any pre-existing rows where it landed NULL.
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_active = TRUE WHERE is_active IS NULL"))
    print(f"done. added={added} skipped={skipped} dialect={dialect}")


if __name__ == "__main__":
    main()
