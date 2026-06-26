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

from app.database import Base  # noqa: E402
from app.models import BacktestStat, ModelVersion  # noqa: E402

SRC = "sqlite:///./sahm.db"
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
    url = os.environ["DATABASE_URL"]
    tgt = create_engine(url, pool_pre_ping=True, insertmanyvalues_page_size=80)
    src = create_engine(SRC)

    Base.metadata.create_all(bind=tgt)

    # Widen signal column so 'super_strong_sell' (17 chars) fits the old VARCHAR(16).
    try:
        with tgt.begin() as c:
            c.execute(text("ALTER TABLE recommendations ALTER COLUMN signal TYPE VARCHAR(24)"))
    except Exception as e:  # noqa: BLE001
        print(f"  (signal widen skipped: {type(e).__name__})")

    # Clear existing result rows (reverse order for FKs).
    with tgt.begin() as c:
        for _model, name in reversed(TABLES):
            c.execute(text(f"DELETE FROM {name}"))

    for model, name in TABLES:
        with src.connect() as s:
            rows = [dict(r._mapping) for r in s.execute(select(model.__table__)).all()]
        if not rows:
            print(f"  {name}: 0 rows (skip)")
            continue
        print(f"copying {name} ({len(rows)}) ...")
        _insert_with_retry(tgt, model.__table__, rows, name)

    # Bump sequences past the copied ids so future inserts don't collide.
    with tgt.begin() as c:
        for _model, name in TABLES:
            seq = c.execute(
                text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": name}
            ).scalar()
            if seq:
                c.execute(text(
                    f"SELECT setval('{seq}', (SELECT COALESCE(MAX(id), 1) FROM {name}))"
                ))

    with tgt.connect() as c:
        for _model, name in TABLES:
            n = c.execute(text(f"SELECT count(*) FROM {name}")).scalar()
            print(f"  {name}: {n} in Neon")
    print("done.")


if __name__ == "__main__":
    main()
