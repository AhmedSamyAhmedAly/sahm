"""Command-line entrypoints.

  python -m app.cli initdb            # create tables
  python -m app.cli seed              # load synthetic data (no token needed)
  python -m app.cli ingest            # pull real EGX data (needs EODHD token)
  python -m app.cli backtest          # compute Success % bands from history
  python -m app.cli train             # train calibrated ML models (accuracy layer)
  python -m app.cli scan              # run the daily scan -> recommendations
  python -m app.cli grade             # grade matured past recommendations
  python -m app.cli daily             # ingest -> grade -> backtest -> train -> scan
  python -m app.cli demo              # seed -> backtest -> train -> scan (local demo)
  python -m app.cli create-user EMAIL PASSWORD [admin|member]
"""
from __future__ import annotations

import sys

from app.config import settings
from app.database import SessionLocal, init_db
from app.engine import backtest as bt
from app.engine import ml
from app.engine.pipeline import grade_due, run_scan


def _seed():
    from app.seed import seed_synthetic
    with SessionLocal() as db:
        print(seed_synthetic(db))


def _ingest():
    from app.eodhd.client import EODHDClient
    from app.eodhd.ingest import apply_liquidity_filters, ingest_prices, refresh_assets
    client = EODHDClient()
    ping = client.ping()
    print("EODHD:", ping)
    if not ping["ok"]:
        print("Cannot ingest — fix the token/plan first.")
        sys.exit(1)
    with SessionLocal() as db:
        tickers = refresh_assets(client, db)
        print(f"assets: {len(tickers)}")
        inserted = ingest_prices(client, db, tickers, full_history=True)
        print(f"bars inserted: {inserted}")
        active = apply_liquidity_filters(db)
        print(f"active: {active}")


def _backtest():
    with SessionLocal() as db:
        print(bt.run_backtest(db))


def _train():
    with SessionLocal() as db:
        for r in ml.train_all(db):
            print(r)


def _scan():
    with SessionLocal() as db:
        print(run_scan(db))


def _grade():
    with SessionLocal() as db:
        print("graded:", grade_due(db))


def _create_user(argv: list[str]):
    from sqlalchemy import select
    from app.auth import hash_password
    from app.models import User

    if len(argv) < 2:
        print("usage: create-user EMAIL PASSWORD [admin|member]")
        sys.exit(1)
    email, password = argv[0].lower(), argv[1]
    role = argv[2] if len(argv) > 2 else "member"
    if len(password) < 8:
        print("password must be at least 8 characters")
        sys.exit(1)
    with SessionLocal() as db:
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            existing.hashed_password = hash_password(password)
            existing.role = role
            db.commit()
            print(f"updated {email} ({role})")
        else:
            db.add(User(email=email, hashed_password=hash_password(password), role=role))
            db.commit()
            print(f"created {email} ({role})")


def _daily():
    _ingest()
    _grade()
    _backtest()
    _train()
    _scan()


def _demo():
    init_db()
    _seed()
    _backtest()
    _train()
    _scan()
    print("Demo ready. Start the API:  uvicorn app.main:app --reload")


_COMMANDS = {
    "initdb": init_db,
    "seed": _seed,
    "ingest": _ingest,
    "backtest": _backtest,
    "train": _train,
    "scan": _scan,
    "grade": _grade,
    "daily": _daily,
    "demo": _demo,
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("token configured:", bool(settings.eodhd_api_token))
        sys.exit(0)
    cmd = sys.argv[1]
    init_db()
    if cmd == "create-user":
        _create_user(sys.argv[2:])
        return
    if cmd not in _COMMANDS:
        print(__doc__)
        sys.exit(1)
    _COMMANDS[cmd]()


if __name__ == "__main__":
    main()
