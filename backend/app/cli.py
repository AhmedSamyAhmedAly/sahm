"""Command-line entrypoints.

  python -m app.cli initdb            # create tables
  python -m app.cli seed              # load synthetic data (no token needed)
  python -m app.cli ingest            # pull real market data (needs EODHD token)
  python -m app.cli backtest          # compute Success % bands from history
  python -m app.cli train             # train calibrated ML models (accuracy layer)
  python -m app.cli scan              # run the daily scan -> recommendations
  python -m app.cli grade             # grade matured past recommendations
  python -m app.cli news              # refresh news overlay only (cheap; intraday)
  python -m app.cli daily             # LIGHT nightly: ingest top-up -> grade -> scan
  python -m app.cli retrain           # HEAVY weekly: backtest + train
  python -m app.cli demo              # seed -> backtest -> train -> scan (local demo)
  python -m app.cli create-user EMAIL PASSWORD [admin|member]

Every data/engine command runs against ONE market (exchange). Choose it with
``--market EGX`` / ``--market US`` (or the ``MARKET`` env var); default is EGX.
EGX and US keep separate assets, models and recommendations, so the two never
collide even in the same database.
"""
from __future__ import annotations

import sys

from app.config import active_market_code, set_active_market, settings
from app.database import SessionLocal, init_db
from app.engine import backtest as bt
from app.engine import ml
from app.engine.pipeline import enrich_news, grade_due, run_scan


def _seed():
    from app.seed import seed_synthetic
    with SessionLocal() as db:
        print(seed_synthetic(db))


def _run_ingest(full_history: bool):
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
        inserted = ingest_prices(client, db, tickers, full_history=full_history)
        print(f"bars inserted: {inserted}")
        active = apply_liquidity_filters(db)
        print(f"active: {active}")


# Set by --batch on the command line (resumable chunked full-history ingest).
_INGEST_BATCH: int | None = None


def _ingest():
    """First-time full-history pull. With --batch N, ingest only the next N not-yet-
    ingested tickers (resumable) — re-run until it prints `remaining=0`. Without
    --batch, pull the whole universe in one go (fine for EGX; too heavy for US)."""
    if _INGEST_BATCH is None:
        _run_ingest(full_history=True)
        return
    from app.eodhd.client import EODHDClient
    from app.eodhd.ingest import ingest_batch
    client = EODHDClient()
    ping = client.ping()
    print("EODHD:", ping)
    if not ping["ok"]:
        print("Cannot ingest — fix the token/plan first.")
        sys.exit(1)
    with SessionLocal() as db:
        res = ingest_batch(client, db, _INGEST_BATCH)
    print(res)
    print(f"remaining={res['remaining']}")   # workflows grep this to know when done


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


def _news():
    """Refresh only the news overlay for THIS market's latest scan (cheap; intraday)."""
    from sqlalchemy import func, select
    from app.models import Asset, Recommendation
    with SessionLocal() as db:
        ex_tickers = select(Asset.ticker).where(Asset.exchange == settings.exchange)
        latest = db.execute(
            select(func.max(Recommendation.date))
            .where(Recommendation.ticker.in_(ex_tickers))
        ).scalar()
        if latest is None:
            print(f"no {settings.exchange} recommendations yet — run scan first")
            return
        print("news refreshed:", enrich_news(db, latest), "for", latest, settings.exchange)


def _retrain():
    """Heavy: recompute backtest stats + retrain ML. Run weekly, not nightly."""
    _backtest()
    _train()


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
    """Nightly (light): top-up new prices, grade, scan -> fresh suggestions.
    No backtest/train here — that's `retrain`, run weekly (keeps DB transfer low)."""
    _run_ingest(full_history=False)
    _grade()
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
    "retrain": _retrain,
    "scan": _scan,
    "grade": _grade,
    "news": _news,
    "daily": _daily,
    "demo": _demo,
}


def _parse_market(argv: list[str]) -> list[str]:
    """Pull a `--market CODE` / `--market=CODE` flag out of argv (sets the active
    market) and return the remaining args. Defaults to the MARKET env / EGX."""
    rest: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--market" and i + 1 < len(argv):
            set_active_market(argv[i + 1])
            i += 2
            continue
        if a.startswith("--market="):
            set_active_market(a.split("=", 1)[1])
            i += 1
            continue
        rest.append(a)
        i += 1
    return rest


def _extract_batch(argv: list[str]) -> list[str]:
    """Pull `--batch N` / `--batch=N` out of argv and set the ingest batch size."""
    global _INGEST_BATCH
    rest: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--batch" and i + 1 < len(argv):
            _INGEST_BATCH = int(argv[i + 1]); i += 2; continue
        if a.startswith("--batch="):
            _INGEST_BATCH = int(a.split("=", 1)[1]); i += 1; continue
        rest.append(a); i += 1
    return rest


def main():
    args = _extract_batch(_parse_market(sys.argv[1:]))
    if not args:
        print(__doc__)
        print("active market:", active_market_code(), "| token configured:",
              bool(settings.eodhd_api_token))
        sys.exit(0)
    cmd = args[0]
    init_db()
    print(f"[market={settings.exchange}] {cmd}")
    if cmd == "create-user":
        _create_user(args[1:])
        return
    if cmd not in _COMMANDS:
        print(__doc__)
        sys.exit(1)
    _COMMANDS[cmd]()


if __name__ == "__main__":
    main()
