"""Synthetic EGX data so the platform is fully runnable WITHOUT a live EODHD token.

Generates ~6 years of plausible daily bars (trend + momentum bursts + noise) for a
set of real-looking EGX tickers, then it can be backtested/scanned exactly like
real data. Replace with real ingestion once the EODHD token works.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, DailyBar

# Real EGX names (for realism); the price series is synthetic.
_NAMES = {
    "COMI": ("Commercial International Bank", "Financials"),
    "HRHO": ("EFG Hermes Holding", "Financials"),
    "SWDY": ("Elsewedy Electric", "Industrials"),
    "TMGH": ("Talaat Moustafa Group", "Real Estate"),
    "ABUK": ("Abu Qir Fertilizers", "Materials"),
    "EFIH": ("e-finance", "Technology"),
    "FWRY": ("Fawry", "Technology"),
    "JUFO": ("Juhayna Food Industries", "Consumer Staples"),
    "EAST": ("Eastern Company", "Consumer Staples"),
    "ORWE": ("Oriental Weavers", "Consumer Discretionary"),
    "SKPC": ("Sidi Kerir Petrochemicals", "Materials"),
    "EKHO": ("Egypt Kuwait Holding", "Industrials"),
    "MFPC": ("Misr Fertilizers (MOPCO)", "Materials"),
    "PHDC": ("Palm Hills Development", "Real Estate"),
    "ESRS": ("Ezz Steel", "Materials"),
    "HELI": ("Heliopolis Housing", "Real Estate"),
    "AMOC": ("Alexandria Mineral Oils", "Energy"),
    "CIEB": ("Credit Agricole Egypt", "Financials"),
    "ORHD": ("Orascom Development Egypt", "Real Estate"),
    "MNHD": ("Madinet Nasr Housing", "Real Estate"),
}


def _gen_series(rng: np.random.Generator, n: int, start_price: float) -> np.ndarray:
    """Geometric random walk with periodic momentum regimes."""
    drift = rng.normal(0.0003, 0.0004)
    vol = rng.uniform(0.012, 0.030)
    rets = rng.normal(drift, vol, n)
    # Inject a few momentum bursts so breakouts/signals actually occur.
    for _ in range(max(2, n // 250)):
        s = rng.integers(0, n - 20)
        rets[s : s + rng.integers(5, 20)] += rng.uniform(0.004, 0.012)
    price = start_price * np.exp(np.cumsum(rets))
    return np.maximum(price, 0.5)


def seed_synthetic(db: Session, years: int = 6, seed: int = 42) -> dict:
    """Idempotent: skips if data already present."""
    if db.execute(select(Asset).limit(1)).first():
        return {"skipped": "data already present"}

    rng = np.random.default_rng(seed)
    today = dt.date.today()
    # ~252 trading days/year, Sun-Thu approximation via weekday skip.
    days: list[dt.date] = []
    d = today - dt.timedelta(days=int(years * 365.25))
    while d <= today:
        if d.weekday() not in (4, 5):  # skip Fri/Sat (EGX trades Sun-Thu)
            days.append(d)
        d += dt.timedelta(days=1)
    n = len(days)

    bars = 0
    for code, (name, sector) in _NAMES.items():
        ticker = f"{code}.EGX"
        db.add(Asset(ticker=ticker, name=name, sector=sector,
                     asset_type="common stock", exchange="EGX",
                     is_active=True, is_listed=True))
        close = _gen_series(rng, n, rng.uniform(5, 90))
        prev = close[0]
        for i, day in enumerate(days):
            c = float(close[i])
            o = float(prev * (1 + rng.normal(0, 0.004)))
            hi = max(o, c) * (1 + abs(rng.normal(0, 0.006)))
            lo = min(o, c) * (1 - abs(rng.normal(0, 0.006)))
            vol = float(rng.uniform(50_000, 2_000_000) * (1 + abs(rng.normal(0, 0.4))))
            db.add(DailyBar(ticker=ticker, date=day, open=round(o, 4),
                            high=round(hi, 4), low=round(lo, 4), close=round(c, 4),
                            adj_close=round(c, 4), volume=round(vol, 2)))
            prev = c
            bars += 1
        db.commit()

    return {"assets": len(_NAMES), "bars": bars, "days": n}
