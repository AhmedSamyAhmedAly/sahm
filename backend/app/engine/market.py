"""Market-context features — the missing 'what is the whole market doing?' signal.

A breakout 'strong buy' during an EGX-wide pullback is the classic failure mode:
the single-stock technicals look identical to one in a rally. So we build a simple
equal-weight EGX index from the active universe and derive, per day:

  * mkt_above_sma50 — is the market in an uptrend (index above its 50-day average)?
  * mkt_roc20       — 20-day market momentum (%).
  * mkt_breadth     — % of stocks trading above their own 50-day average (0-100).

Each stock then also gets a RELATIVE-strength feature (its 20-day return minus the
market's). These feed the ML model and the signal-gating, so buys are aware of the
regime they're issued into. Computed on the fly (no extra table): full history for
the weekly train, a bounded recent window for the nightly scan.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Asset, DailyBar

# Market feature names added to each stock's vector.
MARKET_FEATURES = ["mkt_above_sma50", "mkt_roc20", "mkt_breadth", "rel_strength"]


def compute_market_frame(db: Session, lookback_days: int | None = None) -> pd.DataFrame:
    """Per-date market context. Index = datetime64; cols = the market_* features
    (minus rel_strength, which is per-stock and added at merge time).

    lookback_days limits the read to recent *trading* days (for the nightly scan);
    None loads full history (weekly train/backtest).
    """
    q = (
        select(DailyBar.date, DailyBar.ticker, DailyBar.close)
        .join(Asset, Asset.ticker == DailyBar.ticker)
        .where(Asset.is_active.is_(True))
    )
    if lookback_days:
        maxd = db.execute(select(func.max(DailyBar.date))).scalar()
        if maxd:
            # ~1.6 calendar days per trading day, plus a buffer for SMA50 warm-up.
            cutoff = maxd - dt.timedelta(days=int(lookback_days * 1.6) + 20)
            q = q.where(DailyBar.date >= cutoff)

    rows = db.execute(q).all()
    if not rows:
        return pd.DataFrame(columns=["mkt_above_sma50", "mkt_roc20", "mkt_breadth"])

    df = pd.DataFrame(rows, columns=["date", "ticker", "close"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    wide = df.pivot_table(index="date", columns="ticker", values="close").sort_index()
    wide.index = pd.to_datetime(wide.index)

    # Equal-weight index from daily mean return (robust to listings/delistings).
    rets = wide.pct_change()
    mkt_ret = rets.mean(axis=1, skipna=True)
    idx = (1.0 + mkt_ret.fillna(0.0)).cumprod()
    idx_sma50 = idx.rolling(50, min_periods=20).mean()
    above = (idx > idx_sma50).astype(float)
    roc20 = idx.pct_change(20) * 100.0

    each_sma50 = wide.rolling(50, min_periods=30).mean()
    have = each_sma50.notna().sum(axis=1).replace(0, np.nan)
    breadth = (wide > each_sma50).sum(axis=1) / have * 100.0

    return pd.DataFrame({
        "mkt_above_sma50": above,
        "mkt_roc20": roc20,
        "mkt_breadth": breadth,
    })


def market_row_for(mframe: pd.DataFrame, date) -> dict | None:
    """Latest market features at or before `date` (handles holidays/missing days)."""
    if mframe is None or mframe.empty:
        return None
    ts = pd.Timestamp(date)
    sub = mframe.loc[mframe.index <= ts]
    if sub.empty:
        return None
    r = sub.iloc[-1]
    return {
        "mkt_above_sma50": (float(r["mkt_above_sma50"]) if pd.notna(r["mkt_above_sma50"]) else None),
        "mkt_roc20": (float(r["mkt_roc20"]) if pd.notna(r["mkt_roc20"]) else None),
        "mkt_breadth": (float(r["mkt_breadth"]) if pd.notna(r["mkt_breadth"]) else None),
    }


def merge_market(feats: dict, mrow: dict | None) -> dict:
    """Add market features + relative strength to a stock's feature dict (in place)."""
    mrow = mrow or {}
    feats["mkt_above_sma50"] = mrow.get("mkt_above_sma50")
    feats["mkt_roc20"] = mrow.get("mkt_roc20")
    feats["mkt_breadth"] = mrow.get("mkt_breadth")
    roc20 = feats.get("roc20")
    mkt_roc20 = mrow.get("mkt_roc20")
    feats["rel_strength"] = (
        float(roc20) - float(mkt_roc20)
        if roc20 is not None and mkt_roc20 is not None else None
    )
    return feats
