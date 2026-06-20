"""The daily scan: features -> score -> backtested probability -> levels -> store.

Also grades past recommendations whose horizon has elapsed, so the live track
record stays current.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import delete, func, nullslast, select
from sqlalchemy.orm import Session

from app.config import settings
from app.engine import backtest as bt
from app.engine import ml
from app.engine import news as news_mod
from app.engine.indicators import add_indicators, feature_row, MIN_BARS
from app.engine.levels import trade_levels
from app.engine.signals import ml_signal, score_features
from app.models import Asset, DailyBar, Outcome, PipelineRun, Recommendation


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


def run_scan(db: Session, scan_date: dt.date | None = None) -> dict:
    """Score every active asset for the latest bar and persist recommendations."""
    stats_map = bt.load_stats_map(db)
    bundle = ml.ModelBundle(db)   # calibrated ML models, if trained
    primary_t = settings.primary_target_pct
    primary_h = settings.primary_horizon_days

    data_date = db.execute(select(func.max(DailyBar.date))).scalar()
    scan_date = scan_date or data_date or dt.date.today()

    assets = db.execute(select(Asset).where(Asset.is_active.is_(True))).scalars().all()
    universe = db.execute(
        select(func.count(Asset.id)).where(Asset.is_listed.is_(True))
    ).scalar() or 0

    # Clear any prior run for this date (idempotent).
    db.execute(delete(Recommendation).where(Recommendation.date == scan_date))
    db.commit()

    ranked = 0
    for a in assets:
        df = _load_bars(db, a.ticker)
        if len(df) < MIN_BARS:
            continue
        df_ind = add_indicators(df)
        feats = feature_row(df_ind, len(df_ind) - 1)
        if not feats:
            continue
        sc = score_features(feats)
        entry = feats["close"]
        atr = feats.get("atr14")
        levels = trade_levels(entry, atr, primary_t)

        stat = bt.lookup(stats_map, sc["score"], primary_t, primary_h)
        # Prefer the calibrated ML probability; fall back to the backtest hit-rate.
        ml_prob = bundle.prob(feats, primary_t, primary_h) if bundle.ready else None
        if ml_prob is not None:
            success_prob = ml_prob
            success_n = bundle.test_n(primary_t, primary_h) or (stat.n_samples if stat else None)
            signal = ml_signal(ml_prob, bundle.base_rate(primary_t, primary_h))
        else:
            success_prob = stat.hit_rate if stat else None
            success_n = stat.n_samples if stat else None
            signal = sc["signal"]
        expected_hold = stat.avg_days_to_target if stat else None

        # Compute every trained band so the user can switch target/horizon later.
        band_probs = {}
        for (t, h) in settings.target_bands:
            st = bt.lookup(stats_map, sc["score"], t, h)
            bp = bundle.prob(feats, t, h) if bundle.ready else None
            if bp is not None:
                bsig = ml_signal(bp, bundle.base_rate(t, h))
                bn = bundle.test_n(t, h) or (st.n_samples if st else None)
            else:
                bp = st.hit_rate if st else None
                bsig = sc["signal"]
                bn = st.n_samples if st else None
            band_probs[ml.band_key(t, h)] = {
                "prob": bp, "n": bn, "signal": bsig,
                "hold": (st.avg_days_to_target if st else None),
                "target_pct": t, "horizon_days": h,
            }

        db.add(Recommendation(
            date=scan_date, ticker=a.ticker, signal=signal, score=sc["score"],
            success_prob=success_prob, success_n=success_n,
            target_pct=primary_t, horizon_days=primary_h,
            entry_price=levels["entry_price"], target_price=levels["target_price"],
            stop_loss=levels["stop_loss"], expected_hold_days=expected_hold,
            reasons=sc["reasons"], band_probs=band_probs,
            features={**feats, "components": sc["components"],
                      "risk_reward": levels["risk_reward"]},
        ))
        ranked += 1

    db.add(PipelineRun(
        run_date=dt.date.today(), data_date=data_date, universe_size=universe,
        active_count=len(assets), ranked_count=ranked,
    ))
    db.commit()

    news_done = enrich_news(db, scan_date) if settings.news_enabled else 0
    return {"scan_date": str(scan_date), "ranked": ranked, "active": len(assets),
            "news_enriched": news_done,
            "universe": universe}


def enrich_news(db: Session, scan_date: dt.date) -> int:
    """Fetch + assess news for the shortlist (top buy candidates) and store it.

    Cost guard: only the top `news_shortlist_n` buy/strong_buy picks are enriched —
    never the whole universe. Failures per ticker are swallowed (news is supplementary).
    """
    rows = db.execute(
        select(Recommendation)
        .where(Recommendation.date == scan_date,
               Recommendation.signal.in_(("buy", "strong_buy")))
        .order_by(nullslast(Recommendation.success_prob.desc()))
        .limit(settings.news_shortlist_n)
    ).scalars().all()
    if not rows:
        return 0

    names = dict(db.execute(select(Asset.ticker, Asset.name)).all())
    done = 0
    for rec in rows:
        try:
            res = news_mod.analyze(names.get(rec.ticker), rec.ticker)
        except Exception:
            continue
        sentiment = float(res.get("sentiment") or 0.0)
        headlines = res.get("headlines") or []
        rec.news_sentiment = sentiment
        rec.news_label = res.get("label") or "neutral"
        rec.news_thesis = (res.get("thesis") or "")[:500]
        rec.news_catalyst = bool(headlines) and abs(sentiment) >= 0.5
        rec.news = {
            "headlines": headlines,
            "catalysts": res.get("catalysts") or [],
            "risk_flag": bool(res.get("risk_flag")),
            "engine": res.get("engine"),
        }
        done += 1
    db.commit()
    return done


def grade_due(db: Session) -> int:
    """Grade recommendations whose horizon has fully elapsed and aren't graded yet."""
    pending = db.execute(
        select(Recommendation)
        .outerjoin(Outcome, Outcome.recommendation_id == Recommendation.id)
        .where(Outcome.id.is_(None))
    ).scalars().all()

    graded = 0
    for rec in pending:
        entry = float(rec.entry_price) if rec.entry_price else None
        horizon = rec.horizon_days or settings.primary_horizon_days
        if not entry:
            continue
        fwd = db.execute(
            select(DailyBar.high, DailyBar.low, DailyBar.close)
            .where(DailyBar.ticker == rec.ticker, DailyBar.date > rec.date)
            .order_by(DailyBar.date)
            .limit(horizon)
        ).all()
        if len(fwd) < horizon:
            continue  # not matured yet

        highs = np.array([float(h) for h, _, _ in fwd])
        lows = np.array([float(l) for _, l, _ in fwd])
        closes = np.array([float(c) for _, _, c in fwd])
        target = entry * (1.0 + (rec.target_pct or settings.primary_target_pct))

        hit_mask = highs >= target
        hit = bool(hit_mask.any())
        days_to = int(np.argmax(hit_mask) + 1) if hit else None
        db.add(Outcome(
            recommendation_id=rec.id,
            hit_target=hit,
            return_pct=float((closes[-1] / entry - 1.0) * 100.0),
            max_gain=float((highs.max() / entry - 1.0) * 100.0),
            max_drawdown=float((lows.min() / entry - 1.0) * 100.0),
            days_to_target=days_to,
        ))
        graded += 1
    db.commit()
    return graded
