"""Reconcile the live DB to the current models: create missing tables and add any
missing columns (additive, safe). Fixes 500s after new model fields are deployed
without a matching migration.

    DATABASE_URL=... python scripts/migrate_sync.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import Base, engine, init_db  # noqa: E402


def main() -> None:
    init_db()  # creates any brand-new tables
    insp = inspect(engine)
    dialect = engine.dialect
    added = 0
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                table.create(conn, checkfirst=True)
                print(f"created table {table.name}")
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                coltype = col.type.compile(dialect=dialect)
                ddl = f'ALTER TABLE {table.name} ADD COLUMN "{col.name}" {coltype}'
                conn.execute(text(ddl))
                print(f"+ {table.name}.{col.name} {coltype}")
                added += 1
    print(f"done. columns_added={added} dialect={dialect.name}")


if __name__ == "__main__":
    main()
