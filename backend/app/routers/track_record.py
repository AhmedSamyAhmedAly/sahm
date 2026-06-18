"""Track record: backtested hit-rates + realized live outcomes (the trust anchor)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import BacktestStat, Outcome, Recommendation, User
from app.schemas import BacktestStatOut, TrackRecordResponse

router = APIRouter(prefix="/api", tags=["track-record"])


@router.get("/track-record", response_model=TrackRecordResponse)
def track_record(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Backtested stats, ordered by band then target.
    bt_rows = db.execute(
        select(BacktestStat).order_by(
            BacktestStat.score_band.desc(), BacktestStat.target_pct
        )
    ).scalars().all()
    backtest = [
        BacktestStatOut(
            score_band=r.score_band, target_pct=r.target_pct, horizon_days=r.horizon_days,
            n_samples=r.n_samples, hit_rate=r.hit_rate, avg_return=r.avg_return,
            avg_days_to_target=r.avg_days_to_target,
        )
        for r in bt_rows
    ]

    # Realized live outcomes (only graded ones).
    graded = db.execute(
        select(Recommendation, Outcome)
        .join(Outcome, Outcome.recommendation_id == Recommendation.id)
        .order_by(Recommendation.date)
    ).all()
    n = len(graded)
    if n:
        hits = sum(1 for _, oc in graded if oc.hit_target)
        win_rate = hits / n
        avg_ret = sum((oc.return_pct or 0.0) for _, oc in graded) / n
    else:
        win_rate = None
        avg_ret = None

    # Equity curve: cumulative realized return of graded calls over time.
    equity, cum = [], 0.0
    for rec, oc in graded:
        cum += (oc.return_pct or 0.0)
        equity.append({"date": str(rec.date), "ticker": rec.ticker,
                       "return_pct": oc.return_pct, "cumulative": round(cum, 2)})

    return TrackRecordResponse(
        live_win_rate=win_rate, live_graded=n, live_avg_return=avg_ret,
        backtest=backtest, equity_curve=equity,
    )
