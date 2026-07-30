"""Ingestion: pull the active market's symbols + price history into the local DB."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.eodhd.client import EODHDClient
from app.models import Asset, DailyBar

_INCLUDE_TYPES = {"common stock", "etf", "fund", "mutual fund", "unit"}


def refresh_assets(client: EODHDClient, db: Session) -> list[str]:
    """Upsert the active market's symbol list into `assets`. Returns its tickers.

    Everything here is scoped to ``settings.exchange`` so running the US ingest never
    touches EGX rows (and vice versa) — critically, de-listing only ever considers
    the current exchange's assets.
    """
    ex = settings.exchange
    rows = client.symbol_list(ex)
    existing = {
        a.ticker: a
        for a in db.execute(select(Asset).where(Asset.exchange == ex)).scalars()
    }
    # For a virtual exchange (e.g. "US"), keep only the configured sub-exchanges
    # (main boards) so we don't ingest the illiquid OTC/pink-sheet tail.
    keep_subs = settings.profile.symbol_exchange_set
    seen: set[str] = set()
    tickers: list[str] = []

    for r in rows:
        atype = (r.get("Type") or "").lower()
        if atype and atype not in _INCLUDE_TYPES:
            continue
        if keep_subs and (r.get("Exchange") or "").upper() not in keep_subs:
            continue
        code = r.get("Code")
        if not code:
            continue
        ticker = f"{code}.{ex}"
        seen.add(ticker)
        tickers.append(ticker)
        a = existing.get(ticker)
        if a is None:
            db.add(Asset(
                ticker=ticker, name=r.get("Name"), asset_type=atype or None,
                exchange=ex, is_listed=True,
            ))
        else:
            a.name = r.get("Name") or a.name
            a.asset_type = atype or a.asset_type
            a.is_listed = True

    # Always-include extras: valid EGX securities EODHD leaves out of the symbol
    # list but still serves via eod/fundamentals (verified per-ticker so we never
    # add a non-existent code).
    for ticker in settings.extra_ticker_list:
        if ticker in seen:
            continue
        # Verify the symbol exists via EOD prices — available on every paid plan
        # (incl. the $19.99 EOD tier), unlike fundamentals.
        try:
            if not client.eod(ticker):
                continue
        except Exception:
            continue  # not a real symbol / no access
        # Best-effort nicer company name from fundamentals; needs a fundamentals
        # plan, so on cheaper plans this is skipped and the ticker code stands in.
        name, atype = None, "common stock"
        try:
            gen = client.fundamentals(ticker).get("General") or {}
            name = gen.get("Name")
            atype = (gen.get("Type") or atype).lower()
        except Exception:
            pass
        seen.add(ticker)
        tickers.append(ticker)
        a = existing.get(ticker)
        if a is None:
            db.add(Asset(ticker=ticker, name=name, asset_type=atype,
                         exchange=ex, is_listed=True))
        else:
            a.name = name or a.name
            a.asset_type = atype
            a.is_listed = True

    # De-list anything no longer in the exchange list (extras are in `seen`, so kept).
    for ticker, a in existing.items():
        if ticker not in seen:
            a.is_listed = False
    db.commit()
    return tickers


def ingest_prices(client: EODHDClient, db: Session, tickers: list[str],
                  full_history: bool = True, max_backfill_days: int | None = None) -> int:
    """Fetch EOD bars per ticker and insert any that are missing.

    full_history=True pulls everything EODHD has (needed for the backtest).
    Otherwise it tops up from the latest stored bar.

    `max_backfill_days` bounds how far back a top-up may reach for a ticker that has
    NO bars yet. Without it such a ticker silently pulls its entire history — which
    is right for a training cache, but floods a serving database that deliberately
    keeps only a chart window. Defaults to `settings.min_history_days * 2`, enough
    for the indicators (they need `MIN_BARS` of history) plus warm-up.
    """
    if max_backfill_days is None:
        max_backfill_days = max(settings.min_history_days * 2, 380)

    # Latest stored bar for every ticker in ONE query. Asking per ticker meant
    # thousands of round-trips, which dominates the runtime against a remote DB.
    want = set(tickers)
    last_by_ticker: dict[str, dt.date] = {
        t: d for t, d in db.execute(
            select(DailyBar.ticker, func.max(DailyBar.date)).group_by(DailyBar.ticker)
        ).all() if t in want
    }

    inserted = 0
    for ticker in tickers:
        last = last_by_ticker.get(ticker)
        start = None
        if not full_history:
            start = (last - dt.timedelta(days=5) if last            # small overlap, deduped below
                     else dt.date.today() - dt.timedelta(days=max_backfill_days))
        try:
            bars = client.eod(ticker, start=start)
        except Exception:
            continue  # one bad symbol shouldn't abort the whole run

        # Only load the dates we might collide with. On a top-up that's just the
        # recent window (huge DB-transfer saving vs. reading the whole history).
        have_q = select(DailyBar.date).where(DailyBar.ticker == ticker)
        if start is not None:
            have_q = have_q.where(DailyBar.date >= start)
        have = {d for (d,) in db.execute(have_q).all()}
        for b in bars:
            try:
                d = dt.date.fromisoformat(b["date"])
            except (KeyError, ValueError):
                continue
            if d in have:
                continue
            db.add(DailyBar(
                ticker=ticker, date=d,
                open=b.get("open"), high=b.get("high"), low=b.get("low"),
                close=b.get("close"), adj_close=b.get("adjusted_close"),
                volume=b.get("volume"),
            ))
            inserted += 1
        db.commit()
    return inserted


def tickers_without_bars(db: Session) -> list[str]:
    """This market's listed tickers that have NO bars yet (i.e. not yet ingested).
    Used to pull a huge universe (e.g. US) in resumable batches across several runs."""
    ex = settings.exchange
    have = select(DailyBar.ticker).distinct().subquery()
    return db.execute(
        select(Asset.ticker)
        .where(Asset.is_listed.is_(True), Asset.exchange == ex,
               Asset.ticker.notin_(select(have.c.ticker)))
        .order_by(Asset.ticker)
    ).scalars().all()


def ingest_batch(client: EODHDClient, db: Session, batch: int | None = None) -> dict:
    """Resumable full-history ingest. Refreshes the symbol list, then pulls the FULL
    history for up to `batch` not-yet-ingested tickers (all of them if batch is None).

    Re-run until ``remaining == 0``: each run tops up the persistent history cache, so
    a universe too big to fetch in one job (US) comes in a chunk at a time. Liquidity
    filters are recomputed each run so the active set grows as data lands.
    """
    ex = settings.exchange
    refresh_assets(client, db)                       # know the full universe (1 API call)
    pending = tickers_without_bars(db)
    todo = pending[:batch] if batch else pending
    inserted = ingest_prices(client, db, todo, full_history=True)
    active = apply_liquidity_filters(db)
    remaining = len(pending) - len(todo)
    return {
        "market": ex, "batch": (batch or len(todo)),
        "ingested_this_run": len(todo), "bars_inserted": inserted,
        "active": active, "remaining": remaining,
    }


def apply_liquidity_filters(db: Session) -> int:
    """Mark this market's assets active if they have enough history and traded value.
    Thresholds (min history, min avg value traded) come from the active MarketProfile."""
    active = 0
    assets = db.execute(
        select(Asset).where(Asset.is_listed.is_(True), Asset.exchange == settings.exchange)
    ).scalars().all()
    for a in assets:
        rows = db.execute(
            select(DailyBar.close, DailyBar.volume)
            .where(DailyBar.ticker == a.ticker)
            .order_by(DailyBar.date.desc())
            .limit(20)
        ).all()
        count = db.execute(
            select(func.count(DailyBar.id)).where(DailyBar.ticker == a.ticker)
        ).scalar() or 0
        if count < settings.min_history_days or not rows:
            a.is_active = False
            continue
        vals = [float(c) * float(v) for c, v in rows if c and v]
        avg_value = sum(vals) / len(vals) if vals else 0.0
        a.is_active = avg_value >= settings.min_avg_value_traded
        if a.is_active:
            active += 1
    db.commit()
    return active
