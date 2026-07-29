"""Load a FRESH serving database (e.g. Railway Postgres) from what we already have.

Sources, in order of preference per table:
  * assets / recommendations / model_versions / backtest_stats / outcomes / users
        -> copied from the OLD serving DB (OLD_DATABASE_URL) when reachable
  * daily_bars for a market  -> from that market's local cache (LOCAL_DB_URL),
        trimmed to a chart window so the new DB stays small
  * US everything            -> from the local US cache, which is the source of truth

Idempotent-ish: it only inserts rows the target doesn't already have (matched on
each table's natural key), so a re-run tops up rather than duplicating.

    NEW_DATABASE_URL=<railway>  OLD_DATABASE_URL=<neon>  \
    LOCAL_DB_URL=sqlite:///./sahm-us.db  MARKET=US       \
        python scripts/migrate_to_new_db.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select  # noqa: E402

from app.database import Base, normalize_db_url  # noqa: E402
from app.models import (  # noqa: E402
    Asset, BacktestStat, DailyBar, ModelVersion, Outcome, Recommendation, User,
)

# Chart history to load per ticker. Railway charges ~$0.15/GB-month with no hard cap,
# so every stock gets a full year (the Neon-era short window for illiquid names is no
# longer needed). Tradeable names are still loaded first.
CHART_DAYS = int(os.environ.get("CHART_DAYS", "380"))                    # ~1Y, tradeable
INACTIVE_CHART_DAYS = int(os.environ.get("INACTIVE_CHART_DAYS", "380"))  # ~1Y, the rest
BATCH = 300


def _insert(engine, table, rows, label=""):
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        for attempt in range(6):
            try:
                with engine.begin() as c:
                    c.execute(table.insert(), chunk)
                break
            except Exception:  # noqa: BLE001 — retry transient drops
                if attempt == 5:
                    raise
                time.sleep(1.5 * (attempt + 1))
    if label:
        print(f"  {label}: +{len(rows)} rows")


def _rows(engine, table, where=None):
    q = select(table)
    if where is not None:
        q = q.where(where)
    with engine.connect() as c:
        out = [dict(r._mapping) for r in c.execute(q).all()]
    for r in out:
        r.pop("id", None)   # let the target assign ids
    return out


def copy_simple(src, tgt, model, key_cols, label):
    """Copy rows whose natural key isn't already in the target."""
    if src is None:
        return
    have = set()
    with tgt.connect() as c:
        for r in c.execute(select(*[getattr(model, k) for k in key_cols])).all():
            have.add(tuple(r))
    rows = [r for r in _rows(src, model.__table__)
            if tuple(r[k] for k in key_cols) not in have]
    if rows:
        _insert(tgt, model.__table__, rows, label)
    else:
        print(f"  {label}: nothing new")


def main() -> None:
    tgt = create_engine(normalize_db_url(os.environ["NEW_DATABASE_URL"]),
                        pool_pre_ping=True, insertmanyvalues_page_size=80)
    old_url = os.environ.get("OLD_DATABASE_URL")
    src = create_engine(normalize_db_url(old_url), pool_pre_ping=True) if old_url else None
    local = create_engine(os.environ["LOCAL_DB_URL"]) if os.environ.get("LOCAL_DB_URL") else None
    market = os.environ.get("MARKET", "").upper()

    print("creating schema on the new database…")
    Base.metadata.create_all(bind=tgt)

    if src is not None:
        print("copying from the old serving DB…")
        copy_simple(src, tgt, User, ["email"], "users")
        copy_simple(src, tgt, Asset, ["ticker"], "assets")
        copy_simple(src, tgt, BacktestStat,
                    ["exchange", "score_band", "target_pct", "horizon_days"], "backtest_stats")
        copy_simple(src, tgt, ModelVersion, ["exchange", "band_key"], "model_versions")
        copy_simple(src, tgt, Recommendation, ["date", "ticker"], "recommendations")

    if local is not None and market:
        print(f"loading {market} from the local cache…")
        # Assets first (bars/recs have an FK to assets.ticker).
        with tgt.connect() as c:
            have_assets = {t for (t,) in c.execute(select(Asset.ticker)).all()}
        arows = [r for r in _rows(local, Asset.__table__, Asset.exchange == market)
                 if r["ticker"] not in have_assets]
        if arows:
            _insert(tgt, Asset.__table__, arows, "assets")

        # Models + stats for this market.
        copy_simple(local, tgt, BacktestStat,
                    ["exchange", "score_band", "target_pct", "horizon_days"], "backtest_stats")
        copy_simple(local, tgt, ModelVersion, ["exchange", "band_key"], "model_versions")

        # Latest scan's recommendations.
        with local.connect() as c:
            latest = c.execute(select(func.max(Recommendation.date))).scalar()
        if latest:
            with tgt.connect() as c:
                have = {(d, t) for d, t in c.execute(
                    select(Recommendation.date, Recommendation.ticker)).all()}
            rrows = [r for r in _rows(local, Recommendation.__table__,
                                      Recommendation.date == latest)
                     if (r["date"], r["ticker"]) not in have]
            if rrows:
                _insert(tgt, Recommendation.__table__, rrows, f"recommendations ({latest})")

        # Chart bars, trimmed: active tickers get ~1Y, the rest a short window.
        with local.connect() as c:
            maxd = c.execute(select(func.max(DailyBar.date))).scalar()
            actives = {t for (t,) in c.execute(
                select(Asset.ticker).where(Asset.is_active.is_(True),
                                           Asset.exchange == market)).all()}
            all_t = [t for (t,) in c.execute(
                select(Asset.ticker).where(Asset.exchange == market)).all()]
        if maxd:
            act_floor = maxd - dt.timedelta(days=CHART_DAYS)
            inact_floor = maxd - dt.timedelta(days=INACTIVE_CHART_DAYS)
            with tgt.connect() as c:
                have_bar = dict(c.execute(
                    select(DailyBar.ticker, func.max(DailyBar.date)).group_by(DailyBar.ticker)).all())
            # Tradeable names first, so an interruption never costs a real chart.
            ordered = sorted(all_t, key=lambda t: t not in actives)
            total = 0
            with local.connect() as c:
                for i, t in enumerate(ordered):
                    floor = act_floor if t in actives else inact_floor
                    start = have_bar.get(t)
                    lo = max(floor, start + dt.timedelta(days=1)) if start else floor
                    rows = [dict(r._mapping) for r in c.execute(
                        select(DailyBar.__table__).where(
                            DailyBar.ticker == t, DailyBar.date >= lo)).all()]
                    if not rows:
                        continue
                    for r in rows:
                        r.pop("id", None)
                    _insert(tgt, DailyBar.__table__, rows)
                    total += len(rows)
                    if (i + 1) % 500 == 0:
                        print(f"  …{i + 1}/{len(ordered)} tickers, {total} bars")
            print(f"  daily_bars: +{total} rows")

    with tgt.connect() as c:
        for m in (Asset, DailyBar, Recommendation, ModelVersion, BacktestStat, Outcome, User):
            n = c.execute(select(func.count()).select_from(m.__table__)).scalar()
            print(f"  {m.__tablename__}: {n}")
    print("done.")


if __name__ == "__main__":
    main()
