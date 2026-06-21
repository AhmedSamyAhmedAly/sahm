"""Database engine + session. Portable across SQLite (local) and Postgres (prod)."""
from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

log = logging.getLogger("sahm.db")


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        # check_same_thread=False so FastAPI's threadpool can share the connection.
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    from app import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)


def _column_migrations() -> list[tuple[str, str, str]]:
    """Idempotent ADD COLUMN migrations for columns added after first deploy.
    `create_all` makes missing *tables* but never alters existing ones, so these
    keep an already-provisioned Postgres/SQLite in sync on startup."""
    is_sqlite = engine.dialect.name == "sqlite"
    boolean = "INTEGER DEFAULT 0" if is_sqlite else "BOOLEAN DEFAULT FALSE"
    return [
        ("contact_messages", "contact", "VARCHAR(256)"),
        ("users", "first_name", "VARCHAR(80)"),
        ("users", "last_name", "VARCHAR(80)"),
        ("users", "mobile", "VARCHAR(40)"),
        ("users", "avatar", "TEXT"),
        ("holdings", "from_budget", boolean),
    ]


def ensure_schema() -> None:
    """create_all + idempotent ADD COLUMN migrations. Safe to call on every
    startup; lets a plain `git push` deploy migrate itself (no manual step)."""
    init_db()
    for table, col, coltype in _column_migrations():
        # One transaction per ALTER: on Postgres a failed statement aborts the
        # whole transaction, so an "already exists" must not poison the others.
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
            log.info("schema: added %s.%s", table, col)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if "exist" not in msg and "duplicate" not in msg:
                log.warning("schema: could not add %s.%s: %s", table, col, e)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
