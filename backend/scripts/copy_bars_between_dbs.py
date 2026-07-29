"""Copy one market's daily_bars from one serving DB to another.

The per-market local caches hold full history for the markets they scan, but a
market whose cache lives only in CI (EGX) has its chart bars in the OLD serving DB.
This moves those across during a provider migration.

Skips bars the target already has (per ticker, by max date), so it is re-runnable.

    SRC_DATABASE_URL=<old>  DST_DATABASE_URL=<new>  MARKET=EGX \
        python scripts/copy_bars_between_dbs.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select  # noqa: E402

from app.database import normalize_db_url  # noqa: E402
from app.models import Asset, DailyBar  # noqa: E402

BATCH = 500


def _insert(engine, rows):
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        for attempt in range(6):
            try:
                with engine.begin() as c:
                    c.execute(DailyBar.__table__.insert(), chunk)
                break
            except Exception:  # noqa: BLE001
                if attempt == 5:
                    raise
                time.sleep(1.5 * (attempt + 1))


def main() -> None:
    src = create_engine(normalize_db_url(os.environ["SRC_DATABASE_URL"]), pool_pre_ping=True)
    dst = create_engine(normalize_db_url(os.environ["DST_DATABASE_URL"]), pool_pre_ping=True,
                        insertmanyvalues_page_size=80)
    market = os.environ.get("MARKET", "EGX").upper()

    with src.connect() as c:
        tickers = [t for (t,) in c.execute(
            select(Asset.ticker).where(Asset.exchange == market).order_by(Asset.ticker)).all()]
    print(f"{market}: {len(tickers)} tickers in source")

    with dst.connect() as c:
        have_tickers = {t for (t,) in c.execute(select(Asset.ticker)).all()}
        have_max = dict(c.execute(
            select(DailyBar.ticker, func.max(DailyBar.date)).group_by(DailyBar.ticker)).all())

    total = 0
    with src.connect() as s:
        for i, t in enumerate(tickers):
            if t not in have_tickers:
                continue  # asset row must exist in the target first
            q = select(DailyBar.__table__).where(DailyBar.ticker == t)
            if have_max.get(t):
                q = q.where(DailyBar.date > have_max[t])
            rows = [dict(r._mapping) for r in s.execute(q).all()]
            if not rows:
                continue
            for r in rows:
                r.pop("id", None)
            _insert(dst, rows)
            total += len(rows)
            if (i + 1) % 100 == 0:
                print(f"  …{i + 1}/{len(tickers)} tickers, {total} bars")
    print(f"copied {total} {market} bars")

    with dst.connect() as c:
        n = c.execute(select(func.count()).select_from(DailyBar.__table__)).scalar()
        print("target daily_bars total:", n)


if __name__ == "__main__":
    main()
