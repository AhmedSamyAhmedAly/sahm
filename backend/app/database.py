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
