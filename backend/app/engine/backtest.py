"""Historical backtester — the honest "Success %".

For every historical day, we compute the same score the live scan would have
produced (features use only past data), then look FORWARD over the horizon: did
the price rise to the target before the window closed? Aggregating these by
score band gives a real, defensible hit-rate:

    "Stocks that scored 80-90 hit +10% within 10 days 62% of the time (n=340)."

Because the scoring rules are FIXED (not fitted to the data), the full-history
hit-rate is an honest historical frequency, not a curve-fit number. An optional
`start`/`end` window supports out-of-sample checks.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.engine.indicators import add_indicators, feature_row, MIN_BARS
from app.engine.signals import score_features, score_band
from app.models import Asset, BacktestStat, DailyBar


def backtest_ticker(
    df: pd.DataFrame,
    target_bands: list[tuple[float, int]],
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> list[dict]:
    """Yield one sample per (day, target_band) with hit / days_to_target / fwd return."""
    if df is None or len(df) < MIN_BARS + 5:
        return []
    df_ind = add_indicators(df)
    close = df_ind["close"].to_numpy(dtype=float)
    high = df_ind["high"].to_numpy(dtype=float)
    dates = pd.to_datetime(df_ind["date"]).dt.date.to_numpy()
    n = len(df_ind)
    max_h = max(h for _, h in target_bands)

    samples: list[dict] = []
    for i in range(MIN_BARS, n - 1):
        d = dates[i]
        if start and d < start:
            continue
        if end and d > end:
            continue
        feats = feature_row(df_ind, i)
        if not feats:
            continue
        sc = score_features(feats)
        band = score_band(sc["score"])
        entry = close[i]
        if entry <= 0:
            continue
        for target_pct, horizon in target_bands:
            j_end = min(i + horizon, n - 1)
            if j_end <= i:
                continue
            fwd_high = high[i + 1 : j_end + 1]
            if fwd_high.size == 0:
                continue
            target = entry * (1.0 + target_pct)
            hit_idx = np.argmax(fwd_high >= target) if np.any(fwd_high >= target) else -1
            hit = hit_idx >= 0
            days_to = int(hit_idx + 1) if hit else None
            fwd_return = (close[j_end] / entry - 1.0) * 100.0
            samples.append(
                {
                    "score_band": band,
                    "target_pct": target_pct,
                    "horizon_days": horizon,
                    "hit": hit,
                    "days_to_target": days_to,
                    "fwd_return": fwd_return,
                }
            )
        # don't sample within max_h of the end (incomplete forward window)
        if i >= n - 1 - max_h:
            break
    return samples


def aggregate(samples: list[dict]) -> dict[tuple, dict]:
    """Group samples by (score_band, target_pct, horizon) -> stats."""
    if not samples:
        return {}
    df = pd.DataFrame(samples)
    out: dict[tuple, dict] = {}
    keys = ["score_band", "target_pct", "horizon_days"]
    for key, g in df.groupby(keys):
        hits = g["hit"]
        days = g.loc[g["hit"], "days_to_target"]
        out[tuple(key)] = {
            "score_band": key[0],
            "target_pct": float(key[1]),
            "horizon_days": int(key[2]),
            "n_samples": int(len(g)),
            "hit_rate": float(hits.mean()),
            "avg_return": float(g["fwd_return"].mean()),
            "avg_days_to_target": (float(days.mean()) if len(days) else None),
        }
    return out


def _load_bars(db: Session, ticker: str) -> pd.DataFrame:
    rows = db.execute(
        select(DailyBar.date, DailyBar.open, DailyBar.high, DailyBar.low,
               DailyBar.close, DailyBar.volume)
        .where(DailyBar.ticker == ticker)
        .order_by(DailyBar.date)
    ).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def run_backtest(
    db: Session,
    target_bands: list[tuple[float, int]] | None = None,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> dict:
    """Backtest the whole active universe and persist BacktestStat rows."""
    target_bands = target_bands or settings.target_bands
    tickers = db.execute(select(Asset.ticker).where(Asset.is_active.is_(True))).scalars().all()

    all_samples: list[dict] = []
    for t in tickers:
        df = _load_bars(db, t)
        all_samples.extend(backtest_ticker(df, target_bands, start, end))

    stats = aggregate(all_samples)

    # Replace the stored table with the fresh computation.
    db.query(BacktestStat).delete()
    for s in stats.values():
        db.add(
            BacktestStat(
                score_band=s["score_band"],
                target_pct=s["target_pct"],
                horizon_days=s["horizon_days"],
                n_samples=s["n_samples"],
                hit_rate=s["hit_rate"],
                avg_return=s["avg_return"],
                avg_days_to_target=s["avg_days_to_target"],
            )
        )
    db.commit()
    return {"tickers": len(tickers), "samples": len(all_samples), "bands": len(stats)}


def load_stats_map(db: Session) -> dict[tuple, BacktestStat]:
    """Map (score_band, target_pct, horizon) -> BacktestStat for quick lookup."""
    rows = db.execute(select(BacktestStat)).scalars().all()
    return {(r.score_band, r.target_pct, r.horizon_days): r for r in rows}


def lookup(
    stats_map: dict[tuple, BacktestStat],
    score: float,
    target_pct: float,
    horizon: int,
) -> BacktestStat | None:
    return stats_map.get((score_band(score), target_pct, horizon))
