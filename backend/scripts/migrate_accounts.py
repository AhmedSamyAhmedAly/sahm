"""Copy accounts from the OLD Neon DB to the NEW one.

Small tables only (users, watchlist), so this stays well under any transfer quota
on the old DB. IDs are preserved to keep all FK links intact, then Postgres
sequences are bumped past the max id.

    OLD_DATABASE_URL=<old neon>  DATABASE_URL=<new neon>  python scripts/migrate_accounts.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, insert, select, text  # noqa: E402

from app.database import Base  # noqa: E402
from app.models import User, WatchlistItem  # noqa: E402

# FK-safe INSERT order; DELETE runs in reverse.
TABLES = [
    (User, "users"),
    (WatchlistItem, "watchlist_items"),
]


def _norm(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def _insert_with_retry(engine, table, rows, label):
    for attempt in range(6):
        try:
            with engine.begin() as c:
                c.execute(insert(table), rows)
            break
        except Exception:  # noqa: BLE001 — retry dropped connections
            if attempt == 5:
                raise
            time.sleep(1.5 * (attempt + 1))
    print(f"  {label}: {len(rows)} rows")


def main() -> None:
    src = create_engine(_norm(os.environ["OLD_DATABASE_URL"]), pool_pre_ping=True)
    tgt = create_engine(_norm(os.environ["DATABASE_URL"]), pool_pre_ping=True,
                        insertmanyvalues_page_size=80)

    Base.metadata.create_all(bind=tgt)

    # Read everything from the old DB first (one short connection).
    data = {}
    with src.connect() as s:
        for model, name in TABLES:
            try:
                data[name] = [dict(r._mapping)
                              for r in s.execute(select(model.__table__)).all()]
                print(f"read {name}: {len(data[name])}")
            except Exception as e:  # noqa: BLE001
                print(f"read {name}: SKIP ({type(e).__name__})")
                data[name] = []

    # Clear target result rows (reverse FK order) then load.
    with tgt.begin() as c:
        for _model, name in reversed(TABLES):
            c.execute(text(f"DELETE FROM {name}"))

    for model, name in TABLES:
        rows = data.get(name) or []
        if not rows:
            print(f"  {name}: 0 rows (skip)")
            continue
        _insert_with_retry(tgt, model.__table__, rows, name)

    # Bump sequences past copied ids.
    with tgt.begin() as c:
        for _model, name in TABLES:
            seq = c.execute(
                text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": name}
            ).scalar()
            if seq:
                c.execute(text(
                    f"SELECT setval('{seq}', (SELECT COALESCE(MAX(id), 1) FROM {name}))"
                ))

    print("--- in new DB ---")
    with tgt.connect() as c:
        for _model, name in TABLES:
            n = c.execute(text(f"SELECT count(*) FROM {name}")).scalar()
            print(f"  {name}: {n}")
        users = c.execute(text("SELECT email, role FROM users ORDER BY id")).all()
        for email, role in users:
            print(f"    - {email} ({role})")
    print("done.")


if __name__ == "__main__":
    main()
