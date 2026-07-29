"""Database engine + session. Portable across SQLite (local) and Postgres (prod)."""
from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

log = logging.getLogger("saeed.db")


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        # check_same_thread=False so FastAPI's threadpool can share the connection.
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


def normalize_db_url(url: str) -> str:
    """Force the psycopg (v3) driver on Postgres URLs.

    Hosts hand out bare ``postgres://`` / ``postgresql://`` URLs, which SQLAlchemy
    maps to psycopg2 — a driver we don't install (we ship psycopg 3). Rewriting the
    scheme here means any provider's connection string works as-is.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DB_URL = normalize_db_url(settings.database_url)
engine = create_engine(DB_URL, **_engine_kwargs(DB_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _has_column(conn, table: str, col: str) -> bool:
    if engine.dialect.name == "sqlite":
        rows = conn.execute(text(f"PRAGMA table_info({table})")).all()
        return any(r[1] == col for r in rows)
    row = conn.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": col}).first()
    return row is not None


def _has_table(conn, table: str) -> bool:
    if engine.dialect.name == "sqlite":
        row = conn.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t"
        ), {"t": table}).first()
    else:
        row = conn.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name=:t"
        ), {"t": table}).first()
    return row is not None


# Columns added to EXISTING tables after the first release. create_all() only ever
# creates missing tables — it never alters one — so every added column must be
# listed here or a deploy will 500 on the first query that mentions it.
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    # (table, column, SQL type)
    ("users", "plan", "VARCHAR(16)"),
    ("users", "plan_until", "TIMESTAMP"),
    ("users", "plan_source", "VARCHAR(16)"),
    ("users", "paypal_subscription_id", "VARCHAR(64)"),
]


def _ensure_added_columns() -> None:
    """Idempotently add post-release columns to existing tables."""
    with engine.begin() as conn:
        for table, col, coltype in _ADDED_COLUMNS:
            if not _has_table(conn, table) or _has_column(conn, table, col):
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
            log.info("schema: added %s.%s", table, col)


def _ensure_market_columns() -> None:
    """Add the per-market `exchange` column to the model/stat/run tables on an
    existing database (idempotent). New DBs already get it from create_all; this
    lets an already-populated Neon DB (and the CI SQLite cache) self-migrate.

    Existing rows predate multi-market, so they are all EGX — backfilled as such.
    backtest_stats also carries a unique constraint that must now include exchange:
    on Postgres we swap the constraint in place (keeps EGX's stats); on SQLite (the
    disposable CI cache) we just drop the table — it's fully regenerated every retrain.
    """
    is_sqlite = engine.dialect.name == "sqlite"
    with engine.begin() as conn:
        # Simple ADD COLUMN + backfill for the two artifact/audit tables.
        for table in ("model_versions", "pipeline_runs"):
            if _has_table(conn, table) and not _has_column(conn, table, "exchange"):
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN exchange VARCHAR(16) DEFAULT 'EGX'"))
                conn.execute(text(
                    f"UPDATE {table} SET exchange = 'EGX' WHERE exchange IS NULL"))
                log.info("schema: added %s.exchange", table)

        # backtest_stats needs the unique constraint to include exchange too.
        if _has_table(conn, "backtest_stats") and not _has_column(conn, "backtest_stats", "exchange"):
            if is_sqlite:
                conn.execute(text("DROP TABLE backtest_stats"))  # recreated below by create_all
                log.info("schema: dropped backtest_stats (SQLite) — regenerated on next retrain")
            else:
                conn.execute(text(
                    "ALTER TABLE backtest_stats ADD COLUMN exchange VARCHAR(16) DEFAULT 'EGX'"))
                conn.execute(text("UPDATE backtest_stats SET exchange = 'EGX' WHERE exchange IS NULL"))
                # Swap (score_band,target_pct,horizon) -> (exchange,...) uniqueness.
                conn.execute(text(
                    "ALTER TABLE backtest_stats DROP CONSTRAINT IF EXISTS uq_bt_band_target_horizon"))
                conn.execute(text(
                    "ALTER TABLE backtest_stats ADD CONSTRAINT uq_bt_market_band_target_horizon "
                    "UNIQUE (exchange, score_band, target_pct, horizon_days)"))
                log.info("schema: added backtest_stats.exchange + market-scoped unique constraint")


def init_db() -> None:
    """Create all tables + self-migrate the per-market columns. Safe to call repeatedly."""
    from app import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    for step, fn in (("added-column", _ensure_added_columns),
                     ("market-column", _ensure_market_columns)):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 — never block startup on a best-effort migration
            log.warning("schema: %s migration skipped: %s", step, e)
    Base.metadata.create_all(bind=engine)  # recreate anything the migration dropped


def _type_migrations() -> list[tuple[str, str, str]]:
    """Idempotent widen-column migrations (Postgres only; SQLite ignores varchar
    length so it's a no-op there). (table, column, new_type)."""
    if engine.dialect.name == "sqlite":
        return []
    return [
        # super_strong_sell is 17 chars — the old VARCHAR(16) can't hold it.
        ("recommendations", "signal", "VARCHAR(24)"),
    ]


def ensure_schema() -> None:
    """create_all + idempotent widen migrations. Safe to call on every startup;
    lets a plain `git push` deploy migrate itself (no manual step)."""
    init_db()
    for table, col, coltype in _type_migrations():
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE {table} ALTER COLUMN {col} TYPE {coltype}"))
            log.info("schema: widened %s.%s -> %s", table, col, coltype)
        except Exception as e:  # noqa: BLE001
            log.warning("schema: could not widen %s.%s: %s", table, col, e)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
