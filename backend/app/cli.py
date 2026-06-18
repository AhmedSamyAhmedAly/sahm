"""Command-line entrypoints.

  python -m app.cli initdb            # create tables
  python -m app.cli seed              # load synthetic data (no token needed)
  python -m app.cli ingest            # pull real EGX data (needs EODHD token)
  python -m app.cli backtest          # compute Success % from history
  python -m app.cli scan              # run the daily scan -> recommendations
  python -m app.cli grade             # grade matured past recommendations
  python -m app.cli daily             # ingest -> grade -> backtest -> scan (cloud job)
  python -m app.cli demo              # seed -> backtest -> scan (full local demo)
"""
from __future__ import annotations

import sys

from app.config import settings
from app.database import SessionLocal, init_db
from app.engine import backtest as bt
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


def _scan():
    with SessionLocal() as db:
        print(run_scan(db))


def _grade():
    with SessionLocal() as db:
        print("graded:", grade_due(db))


def _daily():
    _ingest()
    _grade()
    _backtest()
    _scan()


def _demo():
    init_db()
    _seed()
    _backtest()
    _scan()
    print("Demo ready. Start the API:  uvicorn app.main:app --reload")


_COMMANDS = {
    "initdb": init_db,
    "seed": _seed,
    "ingest": _ingest,
    "backtest": _backtest,
    "scan": _scan,
    "grade": _grade,
    "daily": _daily,
    "demo": _demo,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in _COMMANDS:
        print(__doc__)
        print("token configured:", bool(settings.eodhd_api_token))
        sys.exit(0 if len(sys.argv) < 2 else 1)
    init_db()
    _COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
