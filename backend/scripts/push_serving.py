"""Push only the SMALL serving slice to Neon (reads the local sahm.db file).

The full 16-year history + all training stay on the free GitHub Actions cache, so
Neon never takes a bulk read. Each run pushes just:
  * recommendations for the latest scan date (replaces that date)
  * daily bars newer than what Neon already has (today's bars, for the charts)
  * outcomes that were newly graded (matured past calls)

IDs are NOT preserved — Neon auto-assigns them and outcomes are linked by the
natural key (date, ticker). That keeps it collision-proof even though the local
file (built fresh in CI) and Neon (seeded from elsewhere) use different id spaces.

    DATABASE_URL=<neon>  python scripts/push_serving.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, insert, select, text  # noqa: E402

from app.database import Base  # noqa: E402
from app.models import DailyBar, Outcome, Recommendation  # noqa: E402

SRC = "sqlite:///./sahm.db"
BATCH = 300


def _insert(engine, table, rows):
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        for attempt in range(6):
            try:
                with engine.begin() as c:
                    c.execute(insert(table), chunk)
                break
            except Exception:  # noqa: BLE001 — retry dropped connections
                if attempt == 5:
                    raise
                time.sleep(1.5 * (attempt + 1))


def _rec_map(conn) -> dict:
    """(date, ticker) -> recommendation id, for the given connection."""
    return {(d, t): i for i, d, t in conn.execute(
        select(Recommendation.id, Recommendation.date, Recommendation.ticker)).all()}


def main() -> None:
    url = os.environ["DATABASE_URL"]
    tgt = create_engine(url, pool_pre_ping=True, insertmanyvalues_page_size=80)
    src = create_engine(SRC)
    Base.metadata.create_all(bind=tgt)

    # Idempotent: super_strong_sell (17 chars) needs more than the old VARCHAR(16).
    try:
        with tgt.begin() as c:
            c.execute(text("ALTER TABLE recommendations ALTER COLUMN signal TYPE VARCHAR(24)"))
    except Exception:  # noqa: BLE001
        pass

    with tgt.connect() as c:
        neon_max_bar = c.execute(select(func.max(DailyBar.date))).scalar()
        neon_oc_recids = {r for (r,) in c.execute(select(Outcome.recommendation_id)).all()}

    # Read the small slice from the local file.
    with src.connect() as s:
        latest = s.execute(select(func.max(Recommendation.date))).scalar()
        recs = ([dict(r._mapping) for r in s.execute(
            select(Recommendation.__table__).where(Recommendation.date == latest)).all()]
            if latest else [])
        # local rec id -> (date, ticker), to remap outcome FKs onto Neon's ids
        local_key = {i: (d, t) for i, d, t in s.execute(
            select(Recommendation.id, Recommendation.date, Recommendation.ticker)).all()}
        outcomes = [dict(r._mapping) for r in s.execute(select(Outcome.__table__)).all()]
        if neon_max_bar is None:
            bars = [dict(r._mapping) for r in s.execute(select(DailyBar.__table__)).all()]
        else:
            bars = [dict(r._mapping) for r in s.execute(
                select(DailyBar.__table__).where(DailyBar.date > neon_max_bar)).all()]

    # Recommendations: replace just the latest date; drop ids (Neon auto-assigns).
    if recs:
        for r in recs:
            r.pop("id", None)
        with tgt.begin() as c:
            c.execute(text("DELETE FROM recommendations WHERE date = :d"), {"d": latest})
        _insert(tgt, Recommendation.__table__, recs)

    # New bars (today's) — strictly newer than Neon's max, so no (ticker,date) dups.
    for b in bars:
        b.pop("id", None)
    if bars:
        _insert(tgt, DailyBar.__table__, bars)

    # Outcomes: remap local rec id -> (date,ticker) -> Neon rec id; skip existing.
    with tgt.connect() as c:
        neon_map = _rec_map(c)
    new_oc = []
    for o in outcomes:
        key = local_key.get(o["recommendation_id"])
        neon_id = neon_map.get(key) if key else None
        if neon_id is None or neon_id in neon_oc_recids:
            continue
        o.pop("id", None)
        o["recommendation_id"] = neon_id
        new_oc.append(o)
    if new_oc:
        _insert(tgt, Outcome.__table__, new_oc)

    with tgt.connect() as c:
        print(f"pushed: recs({latest})={len(recs)} new_bars={len(bars)} new_outcomes={len(new_oc)}")
        print("neon totals -> recs:",
              c.execute(text("select count(*) from recommendations")).scalar(),
              "| bars:", c.execute(text("select count(*) from daily_bars")).scalar(),
              "| outcomes:", c.execute(text("select count(*) from outcomes")).scalar())


if __name__ == "__main__":
    main()
