"""Picks: the ranked daily recommendations that power the dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Asset, Recommendation, User, WatchlistItem
from app.schemas import PickOut, PicksResponse

router = APIRouter(prefix="/api", tags=["picks"])


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
    return {
        "success_prob": bp.get("prob"), "success_n": bp.get("n"),
        "signal": bp.get("signal") or rec.signal,
        "target_pct": target, "horizon_days": horizon,
        "expected_hold": bp.get("hold"), "target_price": tp, "risk_reward": rr,
    }


def _to_pick(rank: int, rec: Recommendation, asset: Asset | None, watched: bool,
             ov: dict | None = None) -> PickOut:
    feats = rec.features or {}
    ov = ov or {}
    return PickOut(
        rank=rank,
        ticker=rec.ticker,
        name=asset.name if asset else None,
        sector=asset.sector if asset else None,
        signal=ov.get("signal", rec.signal),
        score=rec.score,
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
        watched=watched,
        news_sentiment=rec.news_sentiment,
        news_label=rec.news_label,
        news_thesis=rec.news_thesis,
        news_catalyst=rec.news_catalyst,
    )


@router.get("/assets")
def list_assets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Lightweight ticker list for the portfolio dropdown."""
    rows = db.execute(
        select(Asset.ticker, Asset.name).where(Asset.is_listed.is_(True)).order_by(Asset.ticker)
    ).all()
    return [{"ticker": t, "name": n} for t, n in rows]


@router.get("/picks", response_model=PicksResponse)
def get_picks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    signal: str | None = Query(None, description="filter on the effective signal"),
    sector: str | None = None,
    min_score: float = 0.0,
    target: float | None = Query(None, description="target band, e.g. 0.10"),
    horizon: int | None = Query(None, description="horizon days for the band, e.g. 10"),
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
    if sector:
        q = q.where(Asset.sector == sector)
    rows = db.execute(q).all()

    watched = {
        t for (t,) in db.execute(
            select(WatchlistItem.ticker).where(WatchlistItem.user_id == user.id)
        ).all()
    }

    # Apply the chosen band, filter on the effective signal, then rank by the
    # effective success probability (with a light news nudge).
    w = settings.news_weight
    items = []
    for rec, asset in rows:
        ov = band_override(rec, target, horizon)
        eff_signal = (ov or {}).get("signal", rec.signal)
        if signal and eff_signal != signal:
            continue
        eff_prob = ((ov or {}).get("success_prob", rec.success_prob)) or 0.0
        items.append((rec, asset, ov, eff_prob + w * (rec.news_sentiment or 0.0)))

    items.sort(key=lambda x: x[3], reverse=True)
    items = items[:limit]
    picks = [
        _to_pick(i + 1, rec, asset, rec.ticker in watched, ov)
        for i, (rec, asset, ov, _) in enumerate(items)
    ]
    return PicksResponse(
        date=latest_date, universe_size=universe, active_count=active, picks=picks
    )
