"""Portfolio: holdings + P/L, daily alerts / sell suggestions, and a deterministic
budget allocator. All read against the latest end-of-day data."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Asset, DailyBar, Holding, Recommendation, User
from app.schemas import (
    AllocationItem, AllocationResponse, BudgetIn, HoldingIn, HoldingOut,
    PortfolioResponse,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _latest_closes(db: Session) -> tuple[dict, object]:
    data_date = db.execute(select(func.max(DailyBar.date))).scalar()
    closes = {}
    if data_date is not None:
        closes = {
            t: float(c)
            for t, c in db.execute(
                select(DailyBar.ticker, DailyBar.close).where(DailyBar.date == data_date)
            ).all()
            if c is not None
        }
    return closes, data_date


def _latest_recs(db: Session) -> dict[str, Recommendation]:
    latest = db.execute(select(func.max(Recommendation.date))).scalar()
    if latest is None:
        return {}
    rows = db.execute(
        select(Recommendation).where(Recommendation.date == latest)
    ).scalars().all()
    return {r.ticker: r for r in rows}


def _enrich(h: Holding, names: dict, closes: dict, recs: dict) -> HoldingOut:
    buy = float(h.buy_price)
    qty = float(h.quantity)
    invested = buy * qty
    price = closes.get(h.ticker)
    cur_val = price * qty if price is not None else None
    pnl = (cur_val - invested) if cur_val is not None else None
    pnl_pct = ((price / buy - 1) * 100) if (price and buy) else None

    rec = recs.get(h.ticker)
    signal = rec.signal if rec else None
    target = float(rec.target_price) if rec and rec.target_price is not None else None
    stop = float(rec.stop_loss) if rec and rec.stop_loss is not None else None

    alert = None
    sell = False
    if signal in ("sell", "strong_sell"):
        alert, sell = f"Signal turned {signal.replace('_', ' ')}", True
    elif price is not None and target is not None and price >= target:
        alert, sell = "Target reached", True
    elif price is not None and stop is not None and price <= stop:
        alert, sell = "Stop hit", True

    return HoldingOut(
        id=h.id, ticker=h.ticker, name=names.get(h.ticker), buy_price=buy, quantity=qty,
        invested=round(invested, 2),
        current_price=price, current_value=round(cur_val, 2) if cur_val is not None else None,
        pnl=round(pnl, 2) if pnl is not None else None,
        pnl_pct=round(pnl_pct, 2) if pnl_pct is not None else None,
        signal=signal, success_prob=(rec.success_prob if rec else None),
        target_price=target, stop_loss=stop, alert=alert, sell_suggested=sell,
    )


@router.get("", response_model=PortfolioResponse)
def get_portfolio(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    holdings = db.execute(
        select(Holding).where(Holding.user_id == user.id).order_by(Holding.created_at)
    ).scalars().all()
    names = dict(db.execute(select(Asset.ticker, Asset.name)).all())
    closes, _ = _latest_closes(db)
    recs = _latest_recs(db)

    out = [_enrich(h, names, closes, recs) for h in holdings]
    invested = sum(h.invested for h in out)
    current = sum(h.current_value or h.invested for h in out)
    pnl = current - invested
    return PortfolioResponse(
        budget=user.budget, invested=round(invested, 2), current_value=round(current, 2),
        pnl=round(pnl, 2), pnl_pct=(round(pnl / invested * 100, 2) if invested else None),
        holdings=out,
    )


@router.post("/holdings", response_model=HoldingOut)
def add_holding(req: HoldingIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    ticker = req.ticker.strip().upper()
    if "." not in ticker:
        ticker = f"{ticker}.{settings.egx_exchange}"
    if req.buy_price <= 0 or req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Buy price and quantity must be positive")
    h = Holding(user_id=user.id, ticker=ticker, buy_price=req.buy_price, quantity=req.quantity)
    db.add(h)
    db.commit()
    db.refresh(h)
    names = dict(db.execute(select(Asset.ticker, Asset.name)).all())
    closes, _ = _latest_closes(db)
    return _enrich(h, names, closes, _latest_recs(db))


@router.delete("/holdings/{holding_id}")
def delete_holding(holding_id: int, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    h = db.get(Holding, holding_id)
    if h is None or h.user_id != user.id:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(h)
    db.commit()
    return {"deleted": holding_id}


@router.put("/budget")
def set_budget(req: BudgetIn, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    user.budget = max(0.0, req.budget)
    db.commit()
    return {"budget": user.budget}


@router.post("/allocate", response_model=AllocationResponse)
def allocate(req: BudgetIn | None = None, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    budget = (req.budget if req and req.budget else None) or user.budget
    if not budget or budget <= 0:
        raise HTTPException(status_code=400, detail="Set a budget first")

    latest = db.execute(select(func.max(Recommendation.date))).scalar()
    recs = db.execute(
        select(Recommendation, Asset)
        .join(Asset, Asset.ticker == Recommendation.ticker, isouter=True)
        .where(Recommendation.date == latest,
               Recommendation.signal.in_(("buy", "strong_buy")),
               Recommendation.success_prob.is_not(None))
        .order_by(Recommendation.success_prob.desc())
        .limit(settings.alloc_top_n)
    ).all() if latest else []
    if not recs:
        raise HTTPException(status_code=400, detail="No buy candidates available to allocate")

    # Weight by success probability, cap each position, renormalize, size to whole shares.
    probs = [float(r.success_prob) for r, _ in recs]
    total = sum(probs) or 1.0
    cap = settings.alloc_max_position_pct
    shares_w = [min(p / total, cap) for p in probs]
    sw = sum(shares_w) or 1.0
    shares_w = [w / sw for w in shares_w]

    allocations, used = [], 0.0
    for (rec, asset), w in zip(recs, shares_w):
        entry = float(rec.entry_price) if rec.entry_price is not None else None
        if not entry:
            continue
        target_amt = budget * w
        shares = int(math.floor(target_amt / entry))
        amount = round(shares * entry, 2)
        used += amount
        allocations.append(AllocationItem(
            ticker=rec.ticker, name=asset.name if asset else None, signal=rec.signal,
            success_prob=rec.success_prob, suggested_amount=amount, shares=shares,
            entry_price=round(entry, 4),
            target_price=float(rec.target_price) if rec.target_price is not None else None,
        ))
    allocations = [a for a in allocations if a.shares > 0]
    return AllocationResponse(
        budget=round(budget, 2), leftover_cash=round(budget - used, 2),
        allocations=allocations,
        note=("Diversified across the top buy signals, weighted by success rate and capped at "
              f"{int(cap * 100)}% per stock. Suggestion only — not financial advice."),
    )
