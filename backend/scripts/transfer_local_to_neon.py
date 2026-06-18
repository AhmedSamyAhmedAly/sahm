"""One-off: copy assets + daily_bars from local SQLite into the target DB (Neon).

Avoids re-downloading 16 years from EODHD. Target DB comes from DATABASE_URL env.
IDs are dropped so Postgres assigns fresh ones (keeps the SERIAL sequence correct
for future inserts from the daily GitHub Action).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sqlalchemy import create_engine, text

from app.database import engine as target_engine, init_db

SRC = "sqlite:///./sahm.db"


def main():
    init_db()  # ensure target tables exist
    src = create_engine(SRC)

    with target_engine.connect() as t:
        existing = t.execute(text("select count(*) from daily_bars")).scalar()
    if existing:
        print(f"target already has {existing} bars — aborting to avoid duplicates")
        return

    for table in ("assets", "daily_bars"):
        df = pd.read_sql_table(table, src)
        if "id" in df.columns:
            df = df.drop(columns=["id"])
        df.to_sql(table, target_engine, if_exists="append", index=False,
                  chunksize=5000, method="multi")
        print(f"copied {len(df):>7} rows -> {table}")

    with target_engine.connect() as t:
        a = t.execute(text("select count(*) from assets")).scalar()
        b = t.execute(text("select count(*) from daily_bars")).scalar()
    print(f"done. assets={a} daily_bars={b}")


if __name__ == "__main__":
    main()
