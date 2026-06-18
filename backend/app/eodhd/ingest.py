"""Ingestion: pull EGX symbols + full price history into the local DB."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.eodhd.client import EODHDClient
from app.models import Asset, DailyBar

_INCLUDE_TYPES = {"common stock", "etf", "fund", "mutual fund", "unit"}


def refresh_assets(client: EODHDClient, db: Session) -> list[str]:
    """Upsert the exchange symbol list into `assets`. Returns active-listed tickers."""
    rows = client.symbol_list()
    existing = {a.ticker: a for a in db.execute(select(Asset)).scalars()}
    seen: set[str] = set()
    tickers: list[str] = []

    for r in rows:
        atype = (r.get("Type") or "").lower()
        if atype and atype not in _INCLUDE_TYPES:
            continue
        code = r.get("Code")
        if not code:
            continue
        ticker = f"{code}.{settings.egx_exchange}"
        seen.add(ticker)
        tickers.append(ticker)
        a = existing.get(ticker)
        if a is None:
            db.add(Asset(
                ticker=ticker, name=r.get("Name"), asset_type=atype or None,
                exchange=settings.egx_exchange, is_listed=True,
            ))
        else:
            a.name = r.get("Name") or a.name
            a.asset_type = atype or a.asset_type
            a.is_listed = True

    # De-list anything no longer in the exchange list.
    for ticker, a in existing.items():
        if ticker not in seen:
            a.is_listed = False
    db.commit()
    return tickers


def ingest_prices(client: EODHDClient, db: Session, tickers: list[str],
                  full_history: bool = True) -> int:
    """Fetch EOD bars per ticker and insert any that are missing.

    full_history=True pulls everything EODHD has (needed for the backtest).
    Otherwise it tops up from the latest stored bar.
    """
    inserted = 0
    for ticker in tickers:
        last = db.execute(
            select(func.max(DailyBar.date)).where(DailyBar.ticker == ticker)
        ).scalar()
        start = None
        if not full_history and last:
            start = last - dt.timedelta(days=5)  # small overlap, deduped below
        try:
            bars = client.eod(ticker, start=start)
        except Exception:
            continue  # one bad symbol shouldn't abort the whole run

        have = {
            d for (d,) in db.execute(
                select(DailyBar.date).where(DailyBar.ticker == ticker)
            ).all()
        }
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


def apply_liquidity_filters(db: Session) -> int:
    """Mark assets active if they have enough history and recent traded value."""
    active = 0
    assets = db.execute(select(Asset).where(Asset.is_listed.is_(True))).scalars().all()
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
