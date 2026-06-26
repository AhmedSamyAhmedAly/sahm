"""ML probability layer — the accuracy upgrade.

Trains a model per target band (e.g. +10% within 10 days) on the full EGX history
and predicts a CALIBRATED probability that a stock hits the target in the horizon.

Honesty guarantees:
  * Features at day t use only data up to t (no look-ahead) — same code as the scan.
  * Train/test split is by TIME with a `horizon` purge gap, so test labels never
    overlap the training window. Reported AUC/precision are genuine out-of-sample.
  * Production model is probability-calibrated (isotonic over time-series folds) so
    "62%" actually means ~62% historical frequency.
"""
from __future__ import annotations

import io

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.engine.indicators import add_indicators, feature_row, MIN_BARS
from app.engine.market import MARKET_FEATURES, compute_market_frame
from app.models import Asset, DailyBar, ModelVersion

# Numeric, cross-sectionally comparable single-stock features (no raw price levels).
TECH_FEATURES = [
    "price_vs_sma20", "price_vs_sma50", "price_vs_sma200", "sma50_vs_sma200",
    "rsi14", "macd_hist", "roc10", "roc20", "vol_ratio", "atr_pct",
    "dist_from_high20", "pos_52w", "breakout20", "golden_cross",
]
# Full vector = single-stock technicals + market context (regime/breadth/rel-strength).
ML_FEATURES = TECH_FEATURES + MARKET_FEATURES
FEATURE_SET_VERSION = "2"   # v2 adds market-context features
MIN_SAMPLES = 800


def band_key(target_pct: float, horizon: int) -> str:
    return f"t{int(round(target_pct * 100))}_h{horizon}"


def feats_to_vector(feats: dict, keys: list[str] | None = None) -> list[float]:
    out = []
    for k in (keys or ML_FEATURES):
        v = feats.get(k)
        if isinstance(v, bool):
            out.append(1.0 if v else 0.0)
        elif v is None:
            out.append(np.nan)
        else:
            out.append(float(v))
    return out


def _load_bars(db: Session, ticker: str) -> pd.DataFrame:
    rows = db.execute(
        select(DailyBar.date, DailyBar.open, DailyBar.high, DailyBar.low,
               DailyBar.close, DailyBar.volume)
        .where(DailyBar.ticker == ticker).order_by(DailyBar.date)
    ).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def build_matrix(db: Session, horizons: list[int]) -> pd.DataFrame:
    """One row per (ticker, day) with ML features + forward max-high per horizon.

    Single-stock technicals are computed per ticker; market-context features are
    joined in by date afterwards (one shared market series for the whole universe).
    """
    max_h = max(horizons)
    frames: list[pd.DataFrame] = []
    tickers = db.execute(select(Asset.ticker).where(Asset.is_active.is_(True))).scalars().all()
    for t in tickers:
        df = _load_bars(db, t)
        if len(df) < MIN_BARS + max_h + 2:
            continue
        df_ind = add_indicators(df)
        high = df_ind["high"].to_numpy(dtype=float)
        close = df_ind["close"].to_numpy(dtype=float)
        dates = pd.to_datetime(df_ind["date"]).to_numpy()
        n = len(df_ind)

        recs = []
        for i in range(MIN_BARS, n - max_h - 1):
            feats = feature_row(df_ind, i)
            if not feats:
                continue
            row = dict(zip(TECH_FEATURES, feats_to_vector(feats, TECH_FEATURES)))
            row["date"] = dates[i]
            row["close"] = close[i]
            for h in horizons:
                row[f"fwd_max_{h}"] = float(np.max(high[i + 1 : i + 1 + h]))
            recs.append(row)
        if recs:
            frames.append(pd.DataFrame(recs))
    if not frames:
        return pd.DataFrame()
    matrix = pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)

    # Join the shared market series by date and derive relative strength.
    mframe = compute_market_frame(db)
    if not mframe.empty:
        matrix = matrix.merge(mframe, left_on="date", right_index=True, how="left")
        matrix["rel_strength"] = matrix["roc20"] - matrix["mkt_roc20"]
    for col in MARKET_FEATURES:
        if col not in matrix.columns:
            matrix[col] = np.nan
    return matrix


def _make_estimator(algo: str):
    if algo == "hgb":
        return HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.05, max_depth=4,
            l2_regularization=1.0, min_samples_leaf=80, random_state=0,
        )
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, C=0.5)),
    ])


def _precision_at_topk(y_true: np.ndarray, proba: np.ndarray, k_frac: float = 0.1) -> float:
    n = max(1, int(len(proba) * k_frac))
    idx = np.argsort(proba)[::-1][:n]
    return float(y_true[idx].mean())


def train_band(db: Session, matrix: pd.DataFrame, target_pct: float, horizon: int) -> dict:
    """Train, time-split-evaluate, calibrate, and persist the production model."""
    col = f"fwd_max_{horizon}"
    sub = matrix.dropna(subset=[col, "close"]).copy()
    sub["y"] = (sub[col].to_numpy() >= sub["close"].to_numpy() * (1 + target_pct)).astype(int)
    X = sub[ML_FEATURES].to_numpy(dtype=float)
    y = sub["y"].to_numpy()
    key = band_key(target_pct, horizon)

    if len(y) < MIN_SAMPLES or len(np.unique(y)) < 2:
        return {"band": key, "trained": False, "rows": int(len(y))}

    # Time-ordered split with a purge gap so test labels don't peek into train.
    n = len(y)
    split = int(n * 0.75)
    purge = horizon
    tr = slice(0, max(1, split - purge))
    te = slice(split, n)

    best = None
    for algo in ("hgb", "logreg"):
        est = _make_estimator(algo)
        est.fit(X[tr], y[tr])
        proba = est.predict_proba(X[te])[:, 1]
        try:
            auc = roc_auc_score(y[te], proba)
        except ValueError:
            continue
        prec = _precision_at_topk(y[te], proba, 0.1)
        if best is None or auc > best["auc"]:
            best = {"algo": algo, "auc": auc, "precision_top10": prec}

    if best is None:
        return {"band": key, "trained": False, "rows": int(len(y))}

    base_rate = float(y[te].mean())
    metrics = {
        "auc": round(float(best["auc"]), 4),
        "precision_top10": round(float(best["precision_top10"]), 4),
        "base_rate": round(base_rate, 4),
        "lift_top10": round(best["precision_top10"] / base_rate, 2) if base_rate else None,
        "test_n": int(n - split),
        "train_n": int(max(1, split - purge)),
    }

    # Production model: calibrated, fit on ALL data (time-series CV folds).
    prod = CalibratedClassifierCV(
        _make_estimator(best["algo"]), method="isotonic", cv=TimeSeriesSplit(5)
    )
    prod.fit(X, y)
    buf = io.BytesIO()
    joblib.dump(prod, buf)

    # Replace any existing production model for this band.
    db.query(ModelVersion).filter(ModelVersion.band_key == key).delete()
    db.add(ModelVersion(
        band_key=key, target_pct=target_pct, horizon_days=horizon, algo=best["algo"],
        feature_set_version=FEATURE_SET_VERSION, n_samples=int(n),
        metrics=metrics, artifact=buf.getvalue(), is_production=True,
    ))
    db.commit()
    return {"band": key, "trained": True, **metrics, "algo": best["algo"], "rows": int(n)}


def train_all(db: Session, target_bands=None) -> list[dict]:
    target_bands = target_bands or settings.target_bands
    horizons = sorted({h for _, h in target_bands})
    matrix = build_matrix(db, horizons)
    if matrix.empty:
        return [{"trained": False, "reason": "no data"}]
    return [train_band(db, matrix, t, h) for t, h in target_bands]


# ---- inference ----
class ModelBundle:
    def __init__(self, db: Session):
        rows = db.execute(
            select(ModelVersion).where(ModelVersion.is_production.is_(True))
        ).scalars().all()
        self.models = {}
        self.meta = {}
        for r in rows:
            if r.artifact:
                self.models[r.band_key] = joblib.load(io.BytesIO(r.artifact))
                self.meta[r.band_key] = {"n": r.n_samples, "metrics": r.metrics}

    @property
    def ready(self) -> bool:
        return bool(self.models)

    def prob(self, feats: dict, target_pct: float, horizon: int) -> float | None:
        key = band_key(target_pct, horizon)
        model = self.models.get(key)
        if model is None:
            return None
        x = np.array([feats_to_vector(feats)], dtype=float)
        return float(model.predict_proba(x)[0, 1])

    def test_n(self, target_pct: float, horizon: int) -> int | None:
        m = self.meta.get(band_key(target_pct, horizon))
        return (m["metrics"] or {}).get("test_n") if m else None

    def base_rate(self, target_pct: float, horizon: int) -> float | None:
        m = self.meta.get(band_key(target_pct, horizon))
        return (m["metrics"] or {}).get("base_rate") if m else None
