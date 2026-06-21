"""Idempotent v7 migration: user profile fields + holdings.from_budget.

    python scripts/migrate_v7.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine, ensure_schema  # noqa: E402


def main() -> None:
    # ensure_schema runs create_all + the idempotent ADD COLUMN migrations
    # (dialect-aware boolean default), so this is just a thin manual entrypoint.
    ensure_schema()
    print(f"done. dialect={engine.dialect.name}")


if __name__ == "__main__":
    main()
