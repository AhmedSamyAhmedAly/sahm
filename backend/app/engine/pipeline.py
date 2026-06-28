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
from app.engine import market as mkt
from app.engine import ml
from app.engine import news as news_mod
from app.engine.indicators import add_indicators, feature_row, MIN_BARS
from app.engine.levels import trade_levels
from app.engine.signals import decide_signal, news_demote, score_features
from app.models import Asset, DailyBar, Outcome, PipelineRun, Recommendation


def _load_bars(db: Session, ticker: str, limit: int = 400) -> pd.DataFrame:
    """Recent bars only (last `limit`). The scan's indicators need ~210 bars, so
    pulling the full 16-yr history here is pure wasted DB transfer — keep it light.
    Full history is only loaded by the (weekly) backtest/train jobs."""
    rows = db.execute(
        select(DailyBar.date, DailyBar.open, DailyBar.high, DailyBar.low,
               DailyBar.close, DailyBar.volume)
        .where(DailyBar.ticker == ticker)
        .order_by(DailyBar.date.desc())
        .limit(limit)
    ).all()
    if not rows:
        return pd.DataFrame()
    rows = list(reversed(rows))
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _best_band(band_probs: dict, min_conf: float, exclude: set | None = None) -> dict | None:
    """Confidence-first pick: among bands clearing the confidence floor, the most
    profit in the least time — LARGEST target, then SHORTEST horizon. If none
    clears the floor, fall back to the single most confident band."""
    exclude = exclude or set()
    cands = [b for k, b in band_probs.items()
             if k not in exclude and b.get("prob") is not None]
    if not cands:
        return None

    def ppd(b):  # profit per day = most profit in the least time
        return (b["target_pct"] or 0) / max(1, b["horizon_days"] or 1)

    qualifying = [b for b in cands if b["prob"] >= min_conf]
    if qualifying:
        return max(qualifying, key=ppd)
    return max(cands, key=lambda b: b["prob"])


def run_scan(db: Session, scan_date: dt.date | None = None) -> dict:
    """Score every active asset for the latest bar and persist recommendations."""
    stats_map = bt.load_stats_map(db)
    bundle = ml.ModelBundle(db)   # calibrated ML models, if trained
    primary_t = settings.primary_target_pct
    primary_h = settings.primary_horizon_days

    data_date = db.execute(select(func.max(DailyBar.date))).scalar()
    scan_date = scan_date or data_date or dt.date.today()

    # Shared market-context series (regime/breadth) for the recent window — feeds
    # both the ML probability and the signal gating so buys know the regime.
    mframe = mkt.compute_market_frame(db, lookback_days=160)

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
        # Merge the market context for THIS stock's latest bar date.
        last_date = df_ind["date"].iloc[-1]
        mkt.merge_market(feats, mkt.market_row_for(mframe, last_date))
        sc = score_features(feats)
        entry = feats["close"]
        atr = feats.get("atr14")

        # Score every trained band (prob + gated tier) so we can choose the best
        # play and so the user can still switch target/horizon later.
        band_probs = {}
        for (t, h) in settings.target_bands:
            st = bt.lookup(stats_map, sc["score"], t, h)
            bp = bundle.prob(feats, t, h) if bundle.ready else None
            if bp is not None:
                bsig, _ = decide_signal(bp, bundle.base_rate(t, h), sc["score"], feats)
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

        # RATING (super/strong/buy/…): read from the high-edge conviction band so it
        # actually measures how much better than the market this stock is.
        cv_t, cv_h = settings.conviction_target_pct, settings.conviction_horizon_days
        cv_prob = bundle.prob(feats, cv_t, cv_h) if bundle.ready else None
        if cv_prob is not None:
            signal, extra = decide_signal(
                cv_prob, bundle.base_rate(cv_t, cv_h), sc["score"], feats)
            sc["reasons"] = (extra + sc["reasons"])[:6]
        else:
            signal = sc["signal"]

        # TARGET (headline profit): confidence-first best play — most profit in the
        # least time that clears the floor. Exclude the rating-only conviction band.
        cv_key = ml.band_key(cv_t, cv_h)
        best = _best_band(band_probs, settings.min_confidence, exclude={cv_key})
        if best is None:
            continue
        prim_t, prim_h = best["target_pct"], best["horizon_days"]
        success_prob = best["prob"]
        success_n = best["n"]
        expected_hold = best["hold"]
        levels = trade_levels(entry, atr, prim_t)

        db.add(Recommendation(
            date=scan_date, ticker=a.ticker, signal=signal, score=sc["score"],
            success_prob=success_prob, success_n=success_n,
            target_pct=prim_t, horizon_days=prim_h,
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
        risk_flag = bool(res.get("risk_flag"))
        label = res.get("label") or "neutral"
        rec.news_sentiment = sentiment
        rec.news_label = label
        rec.news_thesis = (res.get("thesis") or "")[:500]
        rec.news_catalyst = bool(headlines) and abs(sentiment) >= 0.5
        rec.news = {
            "headlines": headlines,
            "catalysts": res.get("catalysts") or [],
            "risk_flag": risk_flag,
            "engine": res.get("engine"),
        }
        # Protect against walking into bad news: a clearly negative / risk-flagged
        # trusted headline lowers the buy tier (never raises it).
        if headlines:
            new_sig, reason = news_demote(rec.signal, label, risk_flag)
            if new_sig != rec.signal:
                rec.signal = new_sig
                reasons = list(rec.reasons or [])
                if reason:
                    rec.reasons = ([reason] + reasons)[:6]
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
