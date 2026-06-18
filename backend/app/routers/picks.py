"""Picks: the ranked daily recommendations that power the dashboard."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, nullslast, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Asset, Recommendation, WatchlistItem
from app.schemas import PickOut, PicksResponse
from app.models import User

router = APIRouter(prefix="/api", tags=["picks"])


def _to_pick(rank: int, rec: Recommendation, asset: Asset | None, watched: bool) -> PickOut:
    feats = rec.features or {}
    return PickOut(
        rank=rank,
        ticker=rec.ticker,
        name=asset.name if asset else None,
        sector=asset.sector if asset else None,
        signal=rec.signal,
        score=rec.score,
        success_prob=rec.success_prob,
        success_n=rec.success_n,
        target_pct=rec.target_pct,
        horizon_days=rec.horizon_days,
        entry_price=float(rec.entry_price) if rec.entry_price is not None else None,
        target_price=float(rec.target_price) if rec.target_price is not None else None,
        stop_loss=float(rec.stop_loss) if rec.stop_loss is not None else None,
        risk_reward=feats.get("risk_reward"),
        expected_hold_days=rec.expected_hold_days,
        reasons=rec.reasons or [],
        watched=watched,
        news_sentiment=rec.news_sentiment,
        news_label=rec.news_label,
        news_thesis=rec.news_thesis,
        news_catalyst=rec.news_catalyst,
    )


@router.get("/picks", response_model=PicksResponse)
def get_picks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    signal: str | None = Query(None, description="filter: strong_buy|buy|hold|sell|strong_sell"),
    sector: str | None = None,
    min_score: float = 0.0,
    limit: int = 200,
):
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
    if signal:
        q = q.where(Recommendation.signal == signal)
    if sector:
        q = q.where(Asset.sector == sector)
    # Rank by calibrated success probability first (NULLs sort last in SQLite/PG
    # under DESC), then by the rule score as a tiebreak.
    q = q.order_by(
        nullslast(Recommendation.success_prob.desc()), Recommendation.score.desc()
    ).limit(limit)

    watched = {
        t for (t,) in db.execute(
            select(WatchlistItem.ticker).where(WatchlistItem.user_id == user.id)
        ).all()
    }
    rows = db.execute(q).all()
    # Light, honest re-rank: nudge by news sentiment without touching success_prob.
    w = settings.news_weight
    rows = sorted(
        rows,
        key=lambda r: (r[0].success_prob or 0.0) + w * (r[0].news_sentiment or 0.0),
        reverse=True,
    )
    picks = [
        _to_pick(i + 1, rec, asset, rec.ticker in watched)
        for i, (rec, asset) in enumerate(rows)
    ]
    return PicksResponse(
        date=latest_date, universe_size=universe, active_count=active, picks=picks
    )
