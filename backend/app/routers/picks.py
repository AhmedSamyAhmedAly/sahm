"""Picks: the ranked daily recommendations that power the dashboard."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, require_market_access
from app.models import Asset, DailyBar, Recommendation, User
from app.schemas import PickOut, PicksResponse

router = APIRouter(prefix="/api", tags=["picks"])


def _avg_value_per_ticker(db: Session, lookback_days: int = 30) -> dict[str, float]:
    """Recent average daily traded value (close x volume) per ticker — a cheap proxy
    for liquidity / spread tightness. One grouped query over the recent window."""
    maxd = db.execute(select(func.max(DailyBar.date))).scalar()
    if maxd is None:
        return {}
    cutoff = maxd - dt.timedelta(days=lookback_days)
    rows = db.execute(
        select(DailyBar.ticker, func.avg(DailyBar.close * DailyBar.volume))
        .where(DailyBar.date >= cutoff)
        .group_by(DailyBar.ticker)
    ).all()
    return {t: float(v) for t, v in rows if v is not None}


def _liquidity_tier(avg_value: float | None) -> str | None:
    """Bucket a stock's traded value against this market's liquidity floor. A wide
    spread (the cost you can't avoid) is most likely on the 'thin' names."""
    if avg_value is None:
        return None
    floor = settings.min_avg_value_traded or 1.0
    ratio = avg_value / floor
    if ratio >= 5:
        return "high"
    if ratio >= 1.5:
        return "ok"
    return "thin"


def _bands_list(rec: Recommendation) -> list[dict]:
    """Compact per-band scenarios for the pills (sorted by target)."""
    bp = rec.band_probs or {}
    out = [
        {"target_pct": b.get("target_pct"), "horizon_days": b.get("horizon_days"),
         "prob": b.get("prob"), "n": b.get("n")}
        for b in bp.values()
        if b.get("target_pct") is not None
    ]
    out.sort(key=lambda x: (x["target_pct"] or 0))
    return out


def _latest_close_per_ticker(db: Session) -> dict[str, float]:
    """Most recent close we have for every ticker (so unscored stocks can still
    show their last price)."""
    sub = (
        select(DailyBar.ticker, func.max(DailyBar.date).label("md"))
        .group_by(DailyBar.ticker)
        .subquery()
    )
    rows = db.execute(
        select(DailyBar.ticker, DailyBar.close).join(
            sub, (DailyBar.ticker == sub.c.ticker) & (DailyBar.date == sub.c.md)
        )
    ).all()
    return {t: float(c) for t, c in rows if c is not None}


def band_override(rec: Recommendation, target: float | None, horizon: int | None) -> dict | None:
    """Recompute a pick's band-dependent fields for a chosen target/horizon."""
    if target is None or horizon is None or not rec.band_probs:
        return None
    key = f"t{int(round(target * 100))}_h{horizon}"
    bp = rec.band_probs.get(key)
    if not bp:
        return None
    entry = float(rec.entry_price) if rec.entry_price is not None else None
    stop = float(rec.stop_loss) if rec.stop_loss is not None else None
    tp = round(entry * (1 + target), 4) if entry else None
    rr = round((tp - entry) / (entry - stop), 2) if (entry and stop and entry > stop) else None
    # NB: the rating (signal) stays fixed — switching the target band only changes
    # the profit target and its hit-probability, not the conviction rating.
    return {
        "success_prob": bp.get("prob"), "success_n": bp.get("n"),
        "target_pct": target, "horizon_days": horizon,
        "expected_hold": bp.get("hold"), "target_price": tp, "risk_reward": rr,
    }


def _to_pick(rank: int, rec: Recommendation, asset: Asset | None,
             ov: dict | None = None, last_close: float | None = None,
             avg_value: float | None = None) -> PickOut:
    feats = rec.features or {}
    ov = ov or {}
    return PickOut(
        rank=rank,
        ticker=rec.ticker,
        name=asset.name if asset else None,
        sector=asset.sector if asset else None,
        signal=ov.get("signal", rec.signal),
        score=rec.score,
        last_close=last_close,
        success_prob=ov.get("success_prob", rec.success_prob),
        success_n=ov.get("success_n", rec.success_n),
        target_pct=ov.get("target_pct", rec.target_pct),
        horizon_days=ov.get("horizon_days", rec.horizon_days),
        entry_price=float(rec.entry_price) if rec.entry_price is not None else None,
        target_price=ov.get("target_price",
                            float(rec.target_price) if rec.target_price is not None else None),
        stop_loss=float(rec.stop_loss) if rec.stop_loss is not None else None,
        risk_reward=ov.get("risk_reward", feats.get("risk_reward")),
        expected_hold_days=ov.get("expected_hold", rec.expected_hold_days),
        reasons=rec.reasons or [],
        bands=_bands_list(rec),
        avg_value_traded=avg_value,
        liquidity=_liquidity_tier(avg_value),
        news_sentiment=rec.news_sentiment,
        news_label=rec.news_label,
        news_thesis=rec.news_thesis,
        news_catalyst=rec.news_catalyst,
    )


@router.get("/picks", response_model=PicksResponse)
def get_picks(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    signal: str | None = Query(None, description="filter on the effective signal"),
    sector: str | None = None,
    min_score: float = 0.0,
    target: float | None = Query(None, description="target band, e.g. 0.10"),
    horizon: int | None = Query(None, description="horizon days for the band, e.g. 10"),
    market: str | None = Query(None, description="filter by exchange, e.g. EGX or US"),
    limit: int = 200,
):
    # Picks change at most once a day, so let the browser reuse its copy for a few
    # minutes — repeated visits then don't re-read Neon (keeps free-tier transfer low).
    response.headers["Cache-Control"] = "private, max-age=180"

    # The website can be scoped to one market (exchange). Assets carry an `exchange`
    # column and tickers are namespaced (COMI.EGX, AAPL.US), so every count/query
    # below is filtered to the requested market when one is given.
    mkt = market.strip().upper() if market else None
    # Paywall: market data requires an active plan covering this market.
    require_market_access(user, mkt)

    # Latest scan date *within this market* — a market with no scan yet (e.g. US
    # before its pipeline runs) returns None here and yields an empty, honest response.
    latest_date_q = select(func.max(Recommendation.date))
    if mkt:
        latest_date_q = latest_date_q.join(
            Asset, Asset.ticker == Recommendation.ticker
        ).where(Asset.exchange == mkt)
    latest_date = db.execute(latest_date_q).scalar()

    universe_q = select(func.count(Asset.id)).where(Asset.is_listed.is_(True))
    active_q = select(func.count(Asset.id)).where(Asset.is_active.is_(True))
    if mkt:
        universe_q = universe_q.where(Asset.exchange == mkt)
        active_q = active_q.where(Asset.exchange == mkt)
    universe = db.execute(universe_q).scalar() or 0
    active = db.execute(active_q).scalar() or 0
    if latest_date is None:
        return PicksResponse(date=None, universe_size=universe, active_count=active, picks=[])

    q = (
        select(Recommendation, Asset)
        .join(Asset, Asset.ticker == Recommendation.ticker, isouter=True)
        .where(Recommendation.date == latest_date, Recommendation.score >= min_score)
    )
    if mkt:
        q = q.where(Asset.exchange == mkt)
    if sector:
        q = q.where(Asset.sector == sector)
    rows = db.execute(q).all()

    closes = _latest_close_per_ticker(db)
    avg_values = _avg_value_per_ticker(db)

    # Apply the chosen band, filter on the effective signal, then rank by the
    # effective success probability (with a light news nudge). Tuple shape:
    # (kind, rec, asset, ov, sort_key).
    w = settings.news_weight
    items: list = []
    rec_tickers = set()
    for rec, asset in rows:
        rec_tickers.add(rec.ticker)
        ov = band_override(rec, target, horizon)
        eff_signal = (ov or {}).get("signal", rec.signal)
        if signal and eff_signal != signal:
            continue
        eff_prob = ((ov or {}).get("success_prob", rec.success_prob)) or 0.0
        items.append(("rec", rec, asset, ov, eff_prob + w * (rec.news_sentiment or 0.0)))

    # Every other LISTED stock that didn't pass the scan filters: show it as a
    # data-only row (last price, no prediction). Skipped when a specific signal
    # is requested, since unscored stocks have no signal.
    if not signal:
        listed_q = select(Asset).where(Asset.is_listed.is_(True))
        if mkt:
            listed_q = listed_q.where(Asset.exchange == mkt)
        listed = db.execute(listed_q).scalars().all()
        for asset in listed:
            if asset.ticker in rec_tickers:
                continue
            if sector and asset.sector != sector:
                continue
            items.append(("data", None, asset, None, -1.0))

    items.sort(key=lambda x: x[4], reverse=True)
    items = items[:limit]
    picks = []
    for i, (kind, rec, asset, ov, _) in enumerate(items):
        if kind == "rec":
            picks.append(_to_pick(i + 1, rec, asset, ov, closes.get(rec.ticker),
                                  avg_values.get(rec.ticker)))
        else:
            av = avg_values.get(asset.ticker)
            picks.append(PickOut(
                rank=i + 1, ticker=asset.ticker, name=asset.name, sector=asset.sector,
                signal=None, score=None, last_close=closes.get(asset.ticker),
                avg_value_traded=av, liquidity=_liquidity_tier(av),
            ))
    return PicksResponse(
        date=latest_date, universe_size=universe, active_count=active, picks=picks
    )
