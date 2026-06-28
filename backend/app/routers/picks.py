"""Picks: the ranked daily recommendations that power the dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Asset, DailyBar, Recommendation, User
from app.schemas import PickOut, PicksResponse

router = APIRouter(prefix="/api", tags=["picks"])


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
             ov: dict | None = None, last_close: float | None = None) -> PickOut:
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
    limit: int = 200,
):
    # Picks change at most once a day, so let the browser reuse its copy for a few
    # minutes — repeated visits then don't re-read Neon (keeps free-tier transfer low).
    response.headers["Cache-Control"] = "private, max-age=180"
    latest_date = db.execute(select(func.max(Recommendation.date))).scalar()
    universe = db.execute(
        select(func.count(Asset.id)).where(Asset.is_listed.is_(True))
    ).scalar() or 0
    active = db.execute(
        select(func.count(Asset.id)).where(Asset.is_active.is_(True))
    ).scalar() or 0
    if latest_date is None:
        return PicksResponse(date=None, universe_size=universe, active_count=active, picks=[])

    q = (
        select(Recommendation, Asset)
        .join(Asset, Asset.ticker == Recommendation.ticker, isouter=True)
        .where(Recommendation.date == latest_date, Recommendation.score >= min_score)
    )
    if sector:
        q = q.where(Asset.sector == sector)
    rows = db.execute(q).all()

    closes = _latest_close_per_ticker(db)

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
        listed = db.execute(select(Asset).where(Asset.is_listed.is_(True))).scalars().all()
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
            picks.append(_to_pick(i + 1, rec, asset, ov, closes.get(rec.ticker)))
        else:
            picks.append(PickOut(
                rank=i + 1, ticker=asset.ticker, name=asset.name, sector=asset.sector,
                signal=None, score=None, last_close=closes.get(asset.ticker),
            ))
    return PicksResponse(
        date=latest_date, universe_size=universe, active_count=active, picks=picks
    )
