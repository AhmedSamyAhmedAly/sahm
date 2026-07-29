"""One-time (re-runnable) serving-DB bar diet + backfill for a market.

Neon's free tier is small, so daily_bars must stay lean: charts need ~1y of bars
for ACTIVE stocks and only a last-price window for inactive ones. This script,
per market (MARKET env; both if MARKET=ALL):

  1. PRUNES Neon bars older than the class window (active: ACTIVE_DAYS, inactive:
     INACTIVE_DAYS), measured from that market's latest bar date.
  2. BACKFILLS missing bars from the local cache within those windows — covering
     tickers Neon has never seen (e.g. the rest of the US universe) and gaps.

    MARKET=US DATABASE_URL=<neon> LOCAL_DB_URL=sqlite:///./sahm-us.db \
        python scripts/prune_backfill_bars.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select, text  # noqa: E402

from app.database import normalize_db_url  # noqa: E402
from app.models import Asset, DailyBar  # noqa: E402

ACTIVE_DAYS = int(os.environ.get("ACTIVE_DAYS", "380"))     # ~260 trading days (1Y chart)
INACTIVE_DAYS = int(os.environ.get("INACTIVE_DAYS", "45"))  # last-price + liquidity window
BATCH = 300
# Stop inserting if the serving DB approaches its storage cap (Neon free = 512 MB).
# Active (tradeable) tickers are filled FIRST, so a stop only costs junk-ticker bars.
MAX_DB_MB = int(os.environ.get("MAX_DB_MB", "0"))  # 0 = no cap


def _insert(engine, table, rows):
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        for attempt in range(6):
            try:
                with engine.begin() as c:
                    c.execute(table.insert(), chunk)
                break
            except Exception:  # noqa: BLE001
                if attempt == 5:
                    raise
                time.sleep(1.5 * (attempt + 1))


def process_market(tgt, src, market: str) -> None:
    print(f"--- {market} ---")
    with tgt.connect() as c:
        maxd = c.execute(
            select(func.max(DailyBar.date))
            .where(DailyBar.ticker.in_(select(Asset.ticker).where(Asset.exchange == market)))
        ).scalar()
    with src.connect() as s:
        local_maxd = s.execute(select(func.max(DailyBar.date))).scalar()
    ref = max(d for d in (maxd, local_maxd) if d is not None) if (maxd or local_maxd) else None
    if ref is None:
        print("  no bars anywhere — skip")
        return
    act_floor = ref - dt.timedelta(days=ACTIVE_DAYS)
    inact_floor = ref - dt.timedelta(days=INACTIVE_DAYS)
    print(f"  ref={ref}  active>={act_floor}  inactive>={inact_floor}")

    # 1) prune Neon
    with tgt.begin() as c:
        n1 = c.execute(text(
            "DELETE FROM daily_bars WHERE date < :f AND ticker IN "
            "(SELECT ticker FROM assets WHERE exchange = :ex AND is_active)"),
            {"f": act_floor, "ex": market}).rowcount
        n2 = c.execute(text(
            "DELETE FROM daily_bars WHERE date < :f AND ticker IN "
            "(SELECT ticker FROM assets WHERE exchange = :ex AND NOT is_active)"),
            {"f": inact_floor, "ex": market}).rowcount
    print(f"  pruned: {n1} active-old + {n2} inactive-old rows")

    # 2) backfill gaps from local within the windows
    with src.connect() as s:
        local_assets = {t: a for t, a in s.execute(
            select(Asset.ticker, Asset.is_active).where(Asset.exchange == market)).all()}
    if not local_assets:
        print("  local cache has no assets for this market — skip backfill")
        return
    with tgt.connect() as c:
        neon_max = dict(c.execute(
            select(DailyBar.ticker, func.max(DailyBar.date))
            .where(DailyBar.ticker.in_(select(Asset.ticker).where(Asset.exchange == market)))
            .group_by(DailyBar.ticker)).all())
        neon_tickers = {t for (t,) in c.execute(
            select(Asset.ticker).where(Asset.exchange == market)).all()}

    total = 0
    # ACTIVE (tradeable) first: if we hit the storage cap, we lose only junk-ticker
    # bars, never the charts of stocks the app actually recommends.
    todo = sorted(local_assets.items(), key=lambda kv: not kv[1])
    with src.connect() as s:
        for i, (ticker, is_active) in enumerate(todo):
            if ticker not in neon_tickers:
                continue  # asset row must exist first (push_serving handles new assets)
            if MAX_DB_MB and i % 200 == 0:
                with tgt.connect() as c:
                    mb = c.execute(text(
                        "SELECT pg_database_size(current_database())/1024/1024")).scalar()
                if mb >= MAX_DB_MB:
                    print(f"  ⚠ storage cap reached ({mb} MB >= {MAX_DB_MB}); stopping backfill "
                          f"after {total} rows (active tickers were filled first)")
                    break
            floor = act_floor if is_active else inact_floor
            start = neon_max.get(ticker)
            lo = max(floor, start + dt.timedelta(days=1)) if start else floor
            rows = [dict(r._mapping) for r in s.execute(
                select(DailyBar.__table__)
                .where(DailyBar.ticker == ticker, DailyBar.date >= lo)).all()]
            if not rows:
                continue
            for r in rows:
                r.pop("id", None)
            try:
                _insert(tgt, DailyBar.__table__, rows)
            except Exception as e:  # noqa: BLE001 — out of space: stop cleanly, keep what we have
                print(f"  ⚠ insert stopped at {ticker}: {type(e).__name__} — {total} rows written")
                break
            total += len(rows)
            if (i + 1) % 500 == 0:
                print(f"  …{i + 1}/{len(todo)} tickers, {total} rows so far")
    print(f"  backfilled: {total} rows")


def main() -> None:
    tgt = create_engine(normalize_db_url(os.environ["DATABASE_URL"]), pool_pre_ping=True,
                        insertmanyvalues_page_size=80)
    src = create_engine(os.environ.get("LOCAL_DB_URL", "sqlite:///./sahm.db"))
    want = os.environ.get("MARKET", "ALL").upper()
    markets = ["EGX", "US"] if want == "ALL" else [want]
    for m in markets:
        process_market(tgt, src, m)
    with tgt.connect() as c:
        n = c.execute(text("SELECT count(*) FROM daily_bars")).scalar()
        sz = c.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()
        print(f"done. daily_bars rows={n}  db={sz}")


if __name__ == "__main__":
    main()
