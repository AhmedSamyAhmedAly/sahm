"""Push the *small* result tables from local SQLite to Neon.

The heavy backtest/train/scan run locally (fast, no flaky link); only the compact
outputs travel to Neon: today's picks, graded outcomes, hit-rate bands, and the
pickled models. IDs are preserved so FK links (outcome -> recommendation) survive,
then Postgres sequences are bumped past the max id.

    DATABASE_URL=<neon url> python scripts/push_results_to_neon.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, insert, select, text  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import BacktestStat, ModelVersion  # noqa: E402

# Local history file to read results from. Defaults to the EGX cache; the US job
# points this at sahm-us.db via LOCAL_DB_URL.
SRC = os.environ.get("LOCAL_DB_URL", "sqlite:///./sahm.db")
BATCH = 300

# Weekly training outputs only — these are small and replaced wholesale. The
# (large) recommendations / bars / outcomes are handled incrementally by
# push_serving.py so Neon never takes a bulk write.
TABLES = [
    (BacktestStat, "backtest_stats"),
    (ModelVersion, "model_versions"),
]


def _insert_with_retry(engine, table, rows, label):
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
    print(f"  {label}: {len(rows)} rows")


def main() -> None:
    ex = settings.exchange  # active market (MARKET env; default EGX)
    url = os.environ["DATABASE_URL"]
    tgt = create_engine(url, pool_pre_ping=True, insertmanyvalues_page_size=80)
    src = create_engine(SRC)

    # create_all + self-heal the per-market `exchange` column on Neon before we scope.
    Base.metadata.create_all(bind=tgt)
    _ensure_exchange_column(tgt)

    # Widen signal column so 'super_strong_sell' (17 chars) fits the old VARCHAR(16).
    try:
        with tgt.begin() as c:
            c.execute(text("ALTER TABLE recommendations ALTER COLUMN signal TYPE VARCHAR(24)"))
    except Exception as e:  # noqa: BLE001
        print(f"  (signal widen skipped: {type(e).__name__})")

    print(f"pushing results for market={ex}")
    # Clear only THIS market's result rows (never the other exchange's models/stats).
    with tgt.begin() as c:
        for _model, name in reversed(TABLES):
            c.execute(text(f"DELETE FROM {name} WHERE exchange = :ex"), {"ex": ex})

    for model, name in TABLES:
        with src.connect() as s:
            rows = [dict(r._mapping) for r in s.execute(
                select(model.__table__).where(model.__table__.c.exchange == ex)).all()]
        if not rows:
            print(f"  {name}: 0 rows (skip)")
            continue
        # Drop local ids — Neon auto-assigns, so EGX and US id spaces never collide.
        for r in rows:
            r.pop("id", None)
        print(f"copying {name} ({len(rows)}, {ex}) ...")
        _insert_with_retry(tgt, model.__table__, rows, name)

    with tgt.connect() as c:
        for _model, name in TABLES:
            n = c.execute(text(f"SELECT count(*) FROM {name}")).scalar()
            mine = c.execute(
                text(f"SELECT count(*) FROM {name} WHERE exchange = :ex"), {"ex": ex}).scalar()
            print(f"  {name}: {mine} {ex} / {n} total in Neon")
    print("done.")


def _ensure_exchange_column(tgt) -> None:
    """Add the per-market `exchange` column to the result tables on an existing Neon
    DB (idempotent) so scoping by market works even before the first multi-market push."""
    with tgt.begin() as c:
        for name in ("model_versions", "backtest_stats"):
            try:
                c.execute(text(
                    f"ALTER TABLE {name} ADD COLUMN IF NOT EXISTS exchange VARCHAR(16) DEFAULT 'EGX'"))
                c.execute(text(f"UPDATE {name} SET exchange = 'EGX' WHERE exchange IS NULL"))
            except Exception as e:  # noqa: BLE001
                print(f"  (exchange-column ensure skipped for {name}: {type(e).__name__})")


if __name__ == "__main__":
    main()
