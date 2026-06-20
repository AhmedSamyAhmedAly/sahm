"""Idempotent v4 migration: holding sell-tracking columns. (contact_messages is a
new table, created automatically by init_db.)

    python scripts/migrate_v4.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import engine, init_db  # noqa: E402

_COLUMNS = [
    ("holdings", "sold_qty", "DOUBLE PRECISION DEFAULT 0"),
    ("holdings", "avg_sell_price", "DOUBLE PRECISION"),
    ("holdings", "realized_pnl", "DOUBLE PRECISION DEFAULT 0"),
    ("holdings", "closed", "BOOLEAN DEFAULT FALSE"),
]


def main() -> None:
    init_db()  # creates the new contact_messages table
    dialect = engine.dialect.name
    added = skipped = 0
    with engine.begin() as conn:
        for table, col, coltype in _COLUMNS:
            t = coltype.replace("DOUBLE PRECISION", "REAL") if dialect == "sqlite" else coltype
            t = t.replace("DEFAULT FALSE", "DEFAULT 0") if dialect == "sqlite" else t
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {t}"))
                print(f"+ added {table}.{col}")
                added += 1
            except Exception as e:  # noqa: BLE001
                if "exist" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"= {table}.{col} already present")
                    skipped += 1
                else:
                    raise
    print(f"done. added={added} skipped={skipped} dialect={dialect}")


if __name__ == "__main__":
    main()
