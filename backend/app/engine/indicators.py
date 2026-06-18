"""Technical indicators and the per-day feature vector.

Hand-rolled with pandas/numpy (no TA-Lib needed). Every feature at row t uses
ONLY data up to and including t — no look-ahead — so the same code is safe for
both the live scan and the historical backtest.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_SET_VERSION = "1"

# Minimum bars before features are meaningful (200-day SMA + a little).
MIN_BARS = 210


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df (sorted by date) with indicator columns added."""
    df = df.sort_values("date").reset_index(drop=True).copy()
    close, high, low, vol = df["close"], df["high"], df["low"], df["volume"]

    df["sma20"] = close.rolling(20).mean()
    df["sma50"] = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["rsi14"] = _rsi(close, 14)
    macd, macd_sig = _macd(close)
    df["macd"] = macd
    df["macd_signal"] = macd_sig
    df["macd_hist"] = macd - macd_sig
    df["atr14"] = _atr(df, 14)
    df["roc10"] = close.pct_change(10) * 100
    df["roc20"] = close.pct_change(20) * 100
    df["vol_avg20"] = vol.rolling(20).mean()
    df["vol_ratio"] = vol / df["vol_avg20"]
    df["value_traded20"] = (close * vol).rolling(20).mean()
    df["high20"] = high.rolling(20).max()
    df["high52w"] = high.rolling(252).max()
    df["low52w"] = low.rolling(252).min()
    return df


def feature_row(df_ind: pd.DataFrame, i: int) -> dict | None:
    """Build the feature dict for row i of an indicator-augmented frame.

    Returns None if there isn't enough history or values are missing.
    """
    if i < MIN_BARS or i >= len(df_ind):
        return None
    r = df_ind.iloc[i]
    close = float(r["close"])
    if not np.isfinite(close) or close <= 0:
        return None

    def pct_vs(level) -> float | None:
        level = float(level) if pd.notna(level) else None
        return None if not level else (close / level - 1.0) * 100.0

    high20 = float(r["high20"]) if pd.notna(r["high20"]) else None
    high52 = float(r["high52w"]) if pd.notna(r["high52w"]) else None
    low52 = float(r["low52w"]) if pd.notna(r["low52w"]) else None

    feats = {
        "close": close,
        "price_vs_sma20": pct_vs(r["sma20"]),
        "price_vs_sma50": pct_vs(r["sma50"]),
        "price_vs_sma200": pct_vs(r["sma200"]),
        "sma50_vs_sma200": (
            (float(r["sma50"]) / float(r["sma200"]) - 1.0) * 100.0
            if pd.notna(r["sma50"]) and pd.notna(r["sma200"]) and float(r["sma200"]) > 0
            else None
        ),
        "rsi14": float(r["rsi14"]) if pd.notna(r["rsi14"]) else None,
        "macd_hist": float(r["macd_hist"]) if pd.notna(r["macd_hist"]) else None,
        "roc10": float(r["roc10"]) if pd.notna(r["roc10"]) else None,
        "roc20": float(r["roc20"]) if pd.notna(r["roc20"]) else None,
        "vol_ratio": float(r["vol_ratio"]) if pd.notna(r["vol_ratio"]) else None,
        "atr14": float(r["atr14"]) if pd.notna(r["atr14"]) else None,
        "atr_pct": (
            float(r["atr14"]) / close * 100.0 if pd.notna(r["atr14"]) else None
        ),
        "value_traded20": float(r["value_traded20"]) if pd.notna(r["value_traded20"]) else None,
        # Distance below the recent 20-day high: 0 means at a breakout.
        "dist_from_high20": pct_vs(high20),
        "pos_52w": (
            (close - low52) / (high52 - low52) * 100.0
            if high52 and low52 and high52 > low52
            else None
        ),
        "breakout20": bool(high20 is not None and close >= high20 * 0.999),
        "golden_cross": bool(
            pd.notna(r["sma50"]) and pd.notna(r["sma200"]) and float(r["sma50"]) > float(r["sma200"])
        ),
    }
    return feats


def latest_features(df: pd.DataFrame) -> dict | None:
    """Indicators + feature vector for the most recent bar (used by the live scan)."""
    if df is None or len(df) < MIN_BARS:
        return None
    df_ind = add_indicators(df)
    return feature_row(df_ind, len(df_ind) - 1)
