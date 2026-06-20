"""Idempotent v5 migration: add contact_messages.contact (reply email/mobile).

    python scripts/migrate_v5.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import engine, init_db  # noqa: E402

_COLUMNS = [("contact_messages", "contact", "VARCHAR(256)")]


def main() -> None:
    init_db()
    added = skipped = 0
    with engine.begin() as conn:
        for table, col, coltype in _COLUMNS:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
                print(f"+ added {table}.{col}")
                added += 1
            except Exception as e:  # noqa: BLE001
                if "exist" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"= {table}.{col} already present")
                    skipped += 1
                else:
                    raise
    print(f"done. added={added} skipped={skipped} dialect={engine.dialect.name}")


if __name__ == "__main__":
    main()
