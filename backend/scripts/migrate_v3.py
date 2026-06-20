"""Idempotent v3 migration: per-band probs + portfolio budget. (holdings table is
created automatically by init_db since it's a brand-new table.)

    python scripts/migrate_v3.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import engine, init_db  # noqa: E402

_COLUMNS = [
    ("users", "budget", "DOUBLE PRECISION"),
    ("recommendations", "band_probs", "JSON"),
]


def main() -> None:
    init_db()  # creates the new `holdings` table
    dialect = engine.dialect.name
    added = skipped = 0
    with engine.begin() as conn:
        for table, col, coltype in _COLUMNS:
            t = coltype.replace("DOUBLE PRECISION", "REAL") if dialect == "sqlite" else coltype
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
