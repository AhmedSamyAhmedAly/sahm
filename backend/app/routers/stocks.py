"""Stock detail + per-user watchlist."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Asset, DailyBar, Outcome, Recommendation, User, WatchlistItem
from app.routers.picks import _to_pick
from app.schemas import BarOut, StockDetail

router = APIRouter(prefix="/api", tags=["stocks"])


@router.get("/stocks/{ticker}", response_model=StockDetail)
def stock_detail(
    ticker: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    bars: int = 260,
):
    asset = db.execute(select(Asset).where(Asset.ticker == ticker)).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Unknown ticker")

    bar_rows = db.execute(
        select(DailyBar.date, DailyBar.open, DailyBar.high, DailyBar.low,
               DailyBar.close, DailyBar.volume)
        .where(DailyBar.ticker == ticker)
        .order_by(DailyBar.date.desc())
        .limit(bars)
    ).all()
    bar_list = [
        BarOut(date=d, open=_f(o), high=_f(h), low=_f(l), close=_f(c), volume=_f(v))
        for d, o, h, l, c, v in reversed(bar_rows)
    ]

    latest_date = db.execute(select(func.max(Recommendation.date))).scalar()
    latest_rec = None
    if latest_date is not None:
        latest_rec = db.execute(
            select(Recommendation)
            .where(Recommendation.ticker == ticker, Recommendation.date == latest_date)
        ).scalar_one_or_none()

    watched = db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user.id, WatchlistItem.ticker == ticker
        )
    ).scalar_one_or_none() is not None

    latest_pick = _to_pick(1, latest_rec, asset, watched) if latest_rec else None
    components = (latest_rec.features or {}).get("components") if latest_rec else None

    # Past calls + how they turned out.
    hist_rows = db.execute(
        select(Recommendation, Outcome)
        .join(Outcome, Outcome.recommendation_id == Recommendation.id, isouter=True)
        .where(Recommendation.ticker == ticker)
        .order_by(Recommendation.date.desc())
        .limit(40)
    ).all()
    history = [
        {
            "date": str(rec.date),
            "signal": rec.signal,
            "score": rec.score,
            "entry_price": _f(rec.entry_price),
            "target_price": _f(rec.target_price),
            "stop_loss": _f(rec.stop_loss),
            "hit_target": (oc.hit_target if oc else None),
            "return_pct": (oc.return_pct if oc else None),
            "days_to_target": (oc.days_to_target if oc else None),
        }
        for rec, oc in hist_rows
    ]

    return StockDetail(
        ticker=ticker, name=asset.name, sector=asset.sector,
        latest=latest_pick, components=components, bars=bar_list, history=history,
    )


@router.post("/watchlist/{ticker}")
def add_watch(ticker: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    exists = db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user.id, WatchlistItem.ticker == ticker
        )
    ).scalar_one_or_none()
    if not exists:
        db.add(WatchlistItem(user_id=user.id, ticker=ticker))
        db.commit()
    return {"ticker": ticker, "watched": True}


@router.delete("/watchlist/{ticker}")
def remove_watch(ticker: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    db.query(WatchlistItem).filter(
        WatchlistItem.user_id == user.id, WatchlistItem.ticker == ticker
    ).delete()
    db.commit()
    return {"ticker": ticker, "watched": False}


def _f(x) -> float | None:
    return float(x) if x is not None else None
