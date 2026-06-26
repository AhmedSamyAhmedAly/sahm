"""Resilient seed of a fresh Neon DB from the local SQLite copy.

Neon (esp. a far region / free tier) drops big INSERT statements, so we use a
small insertmanyvalues page size and retry each batch on a dropped connection.

    DATABASE_URL=<neon direct url> python scripts/seed_neon_resilient.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, insert, select, text  # noqa: E402

from app.database import Base  # noqa: E402
from app.models import Asset, DailyBar  # noqa: E402

SRC = "sqlite:///./sahm.db"
BATCH = 500


def _insert_with_retry(engine, table, rows, label):
    done = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        for attempt in range(6):
            try:
                with engine.begin() as c:
                    c.execute(insert(table), chunk)
                break
            except Exception as e:  # noqa: BLE001 — retry dropped connections
                if attempt == 5:
                    raise
                time.sleep(1.5 * (attempt + 1))
        done += len(chunk)
        if done % 20000 < BATCH:
            print(f"  {label}: {done}/{len(rows)}")
    print(f"  {label}: {done} done")


def main() -> None:
    url = os.environ["DATABASE_URL"]
    # Small page size => small statements Neon won't drop; pre_ping reconnects.
    tgt = create_engine(url, pool_pre_ping=True, insertmanyvalues_page_size=100)
    src = create_engine(SRC)

    Base.metadata.create_all(bind=tgt)

    # Clean the data tables we own (keep users/holdings/contact untouched — empty anyway).
    with tgt.begin() as c:
        c.execute(text("DELETE FROM daily_bars"))
        c.execute(text("DELETE FROM assets"))

    with src.connect() as s:
        assets = [dict(r._mapping) for r in s.execute(select(Asset.__table__)).all()]
        bars = [dict(r._mapping) for r in s.execute(select(DailyBar.__table__)).all()]
    # drop autoincrement ids so Postgres assigns fresh ones
    for r in assets:
        r.pop("id", None)
    for r in bars:
        r.pop("id", None)

    print(f"copying {len(assets)} assets ...")
    _insert_with_retry(tgt, Asset.__table__, assets, "assets")
    print(f"copying {len(bars)} daily_bars ...")
    _insert_with_retry(tgt, DailyBar.__table__, bars, "daily_bars")

    with tgt.connect() as c:
        na = c.execute(text("select count(*) from assets")).scalar()
        nb = c.execute(text("select count(*) from daily_bars")).scalar()
    print(f"done. assets={na} daily_bars={nb}")


if __name__ == "__main__":
    main()
