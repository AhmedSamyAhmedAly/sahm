"""Portfolio: holdings + P/L, daily alerts / sell suggestions, and a deterministic
budget allocator. All read against the latest end-of-day data."""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Asset, DailyBar, Holding, Recommendation, User
from app.schemas import (
    AllocationItem, AllocationResponse, BudgetIn, BulkHoldingsIn, BulkResult,
    HoldingIn, HoldingOut, HoldingUpdate, PortfolioResponse, SellIn,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _norm_ticker(t: str) -> str:
    t = t.strip().upper()
    return t if "." in t else f"{t}.{settings.egx_exchange}"


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
        sold_qty=float(h.sold_qty or 0),
        avg_sell_price=(float(h.avg_sell_price) if h.avg_sell_price is not None else None),
        realized_pnl=round(float(h.realized_pnl or 0), 2),
    )


def _add_or_average(db: Session, user_id: int, ticker: str, buy_price: float, qty: float) -> Holding:
    """Average-in if an open position in this ticker already exists, else create one."""
    existing = db.execute(
        select(Holding).where(Holding.user_id == user_id, Holding.ticker == ticker,
                              Holding.closed.is_(False))
    ).scalars().first()
    if existing and float(existing.quantity) > 0:
        old_q = float(existing.quantity)
        new_q = old_q + qty
        existing.buy_price = round((float(existing.buy_price) * old_q + buy_price * qty) / new_q, 4)
        existing.quantity = new_q
        return existing
    h = Holding(user_id=user_id, ticker=ticker, buy_price=buy_price, quantity=qty)
    db.add(h)
    return h


@router.get("", response_model=PortfolioResponse)
def get_portfolio(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    all_holdings = db.execute(
        select(Holding).where(Holding.user_id == user.id).order_by(Holding.created_at)
    ).scalars().all()
    names = dict(db.execute(select(Asset.ticker, Asset.name)).all())
    closes, _ = _latest_closes(db)
    recs = _latest_recs(db)

    realized_total = sum(float(h.realized_pnl or 0) for h in all_holdings)
    open_holdings = [h for h in all_holdings if not h.closed and float(h.quantity) > 0]
    out = [_enrich(h, names, closes, recs) for h in open_holdings]
    invested = sum(h.invested for h in out)
    current = sum(h.current_value or h.invested for h in out)
    pnl = current - invested
    return PortfolioResponse(
        budget=user.budget, invested=round(invested, 2), current_value=round(current, 2),
        pnl=round(pnl, 2), pnl_pct=(round(pnl / invested * 100, 2) if invested else None),
        realized_pnl=round(realized_total, 2), earnings=round(pnl + realized_total, 2),
        holdings=out,
    )


@router.post("/holdings/{holding_id}/sell", response_model=HoldingOut)
def sell_holding(holding_id: int, req: SellIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    h = db.get(Holding, holding_id)
    if h is None or h.user_id != user.id:
        raise HTTPException(status_code=404, detail="Holding not found")
    if req.sell_price <= 0 or req.units <= 0:
        raise HTTPException(status_code=400, detail="Sell price and units must be positive")
    units = min(req.units, float(h.quantity))
    if units <= 0:
        raise HTTPException(status_code=400, detail="Nothing left to sell")

    gain = (req.sell_price - float(h.buy_price)) * units
    old_sold = float(h.sold_qty or 0)
    old_avg = float(h.avg_sell_price or 0)
    new_sold = old_sold + units
    h.avg_sell_price = round((old_avg * old_sold + req.sell_price * units) / new_sold, 4)
    h.sold_qty = new_sold
    h.realized_pnl = float(h.realized_pnl or 0) + gain
    h.quantity = float(h.quantity) - units
    if h.quantity <= 1e-9:
        h.quantity = 0
        h.closed = True
    db.commit()
    db.refresh(h)
    names = dict(db.execute(select(Asset.ticker, Asset.name)).all())
    closes, _ = _latest_closes(db)
    return _enrich(h, names, closes, _latest_recs(db))


@router.get("/history")
def history(db: Session = Depends(get_db), user: User = Depends(get_current_user),
            days: int = Query(90, description="lookback window; 0 = all available")):
    """Current holdings valued over time vs. cost basis, over a date range."""
    holdings = db.execute(
        select(Holding).where(Holding.user_id == user.id)
    ).scalars().all()
    if not holdings:
        return {"series": [], "invested": 0}

    qty = defaultdict(float)
    invested = 0.0
    for h in holdings:
        qty[h.ticker] += float(h.quantity)
        invested += float(h.buy_price) * float(h.quantity)
    tickers = list(qty.keys())

    data_date = db.execute(select(func.max(DailyBar.date))).scalar()
    if data_date is None:
        return {"series": [], "invested": round(invested, 2)}
    start = None if days <= 0 else (data_date - dt.timedelta(days=days))

    q = select(DailyBar.date, DailyBar.ticker, DailyBar.close).where(DailyBar.ticker.in_(tickers))
    if start is not None:
        q = q.where(DailyBar.date >= start)
    q = q.order_by(DailyBar.date)

    by_date: dict = defaultdict(dict)
    for d, t, c in db.execute(q).all():
        if c is not None:
            by_date[d][t] = float(c)

    last: dict = {}
    series = []
    for d in sorted(by_date):
        last.update(by_date[d])
        value = sum(last.get(t, 0.0) * qty[t] for t in tickers)
        series.append({"date": str(d), "value": round(value, 2),
                       "invested": round(invested, 2), "profit": round(value - invested, 2)})
    return {"series": series, "invested": round(invested, 2)}


@router.post("/holdings", response_model=HoldingOut)
def add_holding(req: HoldingIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    ticker = _norm_ticker(req.ticker)
    if req.buy_price <= 0 or req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Buy price and quantity must be positive")
    h = _add_or_average(db, user.id, ticker, req.buy_price, req.quantity)
    db.commit()
    db.refresh(h)
    names = dict(db.execute(select(Asset.ticker, Asset.name)).all())
    closes, _ = _latest_closes(db)
    return _enrich(h, names, closes, _latest_recs(db))


@router.patch("/holdings/{holding_id}", response_model=HoldingOut)
def update_holding(holding_id: int, req: HoldingUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    h = db.get(Holding, holding_id)
    if h is None or h.user_id != user.id:
        raise HTTPException(status_code=404, detail="Holding not found")
    if req.buy_price is not None:
        if req.buy_price <= 0:
            raise HTTPException(status_code=400, detail="Buy price must be positive")
        h.buy_price = req.buy_price
    if req.quantity is not None:
        if req.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")
        h.quantity = req.quantity
    db.commit()
    db.refresh(h)
    names = dict(db.execute(select(Asset.ticker, Asset.name)).all())
    closes, _ = _latest_closes(db)
    return _enrich(h, names, closes, _latest_recs(db))


@router.post("/holdings/bulk", response_model=BulkResult)
def import_holdings(req: BulkHoldingsIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    added, errors = 0, []
    for it in req.items:
        try:
            if it.buy_price <= 0 or it.quantity <= 0:
                errors.append(f"{it.ticker}: price/quantity must be positive")
                continue
            _add_or_average(db, user.id, _norm_ticker(it.ticker), it.buy_price, it.quantity)
            added += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"{it.ticker}: {e}")
    db.commit()
    return BulkResult(added=added, skipped=len(req.items) - added, errors=errors[:10])


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
