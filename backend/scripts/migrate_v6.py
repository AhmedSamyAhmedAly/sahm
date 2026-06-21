"""Idempotent v6 migration: create the `sales` table (sell-transaction history).

`init_db()` (create_all) makes any missing table, so this just ensures the new
`sales` table exists on an already-provisioned database (e.g. Neon).

    python scripts/migrate_v6.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect  # noqa: E402

from app.database import engine, init_db  # noqa: E402


def main() -> None:
    init_db()  # creates `sales` (and any other missing table) if absent
    present = "sales" in inspect(engine).get_table_names()
    print(f"done. sales_table={'present' if present else 'MISSING'} dialect={engine.dialect.name}")


if __name__ == "__main__":
    main()
