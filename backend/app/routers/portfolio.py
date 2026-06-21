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
from app.models import Asset, DailyBar, Holding, Recommendation, Sale, User
from app.schemas import (
    AllocationItem, AllocationResponse, BudgetIn, BulkHoldingsIn, BulkResult,
    HoldingIn, HoldingOut, HoldingUpdate, PortfolioResponse, SaleOut, SaleUpdate,
    SellIn,
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

    # Sell reason is price-based only: hit the profit target, or hit the stop.
    alert = None
    sell = False
    if price is not None and target is not None and price >= target:
        alert, sell = "Take profit", True
    elif price is not None and stop is not None and price <= stop:
        alert, sell = "Stop loss", True

    return HoldingOut(
        id=h.id, ticker=h.ticker, name=names.get(h.ticker), buy_price=buy, quantity=qty,
        invested=round(invested, 2),
        current_price=price, current_value=round(cur_val, 2) if cur_val is not None else None,
        pnl=round(pnl, 2) if pnl is not None else None,
        pnl_pct=round(pnl_pct, 2) if pnl_pct is not None else None,
        signal=signal, success_prob=(rec.success_prob if rec else None),
        target_price=target, stop_loss=stop, alert=alert, sell_suggested=sell,
        from_budget=bool(h.from_budget),
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


def _recompute_realized(db: Session, h: Holding) -> None:
    """Derive a holding's realized aggregates from its individual sale rows."""
    rows = db.execute(select(Sale).where(Sale.holding_id == h.id)).scalars().all()
    sold = sum(float(s.units) for s in rows)
    h.sold_qty = sold
    h.avg_sell_price = (
        round(sum(float(s.sell_price) * float(s.units) for s in rows) / sold, 4)
        if sold > 0 else None
    )
    h.realized_pnl = round(sum(float(s.gain) for s in rows), 4)


def _credit_budget(user: User, amount: float) -> None:
    """Move cash in/out of the user's liquid budget (never below 0)."""
    user.budget = round(max(0.0, float(user.budget or 0.0) + amount), 2)


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

    buy = float(h.buy_price)
    gain = (req.sell_price - buy) * units
    db.add(Sale(user_id=user.id, holding_id=h.id, ticker=h.ticker, units=units,
                sell_price=req.sell_price, buy_price=buy, gain=round(gain, 4)))
    db.flush()
    h.quantity = float(h.quantity) - units
    if h.quantity <= 1e-9:
        h.quantity = 0
        h.closed = True
    _recompute_realized(db, h)
    _credit_budget(user, req.sell_price * units)  # proceeds return to liquid budget
    db.commit()
    db.refresh(h)
    names = dict(db.execute(select(Asset.ticker, Asset.name)).all())
    closes, _ = _latest_closes(db)
    return _enrich(h, names, closes, _latest_recs(db))


def _sale_out(s: Sale, names: dict) -> SaleOut:
    return SaleOut(
        id=s.id, holding_id=s.holding_id, ticker=s.ticker, name=names.get(s.ticker),
        units=float(s.units), sell_price=float(s.sell_price), buy_price=float(s.buy_price),
        gain=round(float(s.gain), 2), proceeds=round(float(s.sell_price) * float(s.units), 2),
        created_at=s.created_at,
    )


@router.get("/sales", response_model=list[SaleOut])
def list_sales(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(
        select(Sale).where(Sale.user_id == user.id).order_by(Sale.created_at.desc())
    ).scalars().all()
    names = dict(db.execute(select(Asset.ticker, Asset.name)).all())
    return [_sale_out(s, names) for s in rows]


@router.patch("/sales/{sale_id}", response_model=SaleOut)
def update_sale(sale_id: int, req: SaleUpdate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    s = db.get(Sale, sale_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Sale not found")
    h = db.get(Holding, s.holding_id)
    if h is None:
        raise HTTPException(status_code=404, detail="Holding not found")

    new_units = float(req.units) if req.units is not None else float(s.units)
    new_price = float(req.sell_price) if req.sell_price is not None else float(s.sell_price)
    if new_units <= 0 or new_price <= 0:
        raise HTTPException(status_code=400, detail="Sell price and units must be positive")
    # You can't sell more than was ever held: remaining + this sale's old units.
    max_units = float(h.quantity) + float(s.units)
    if new_units > max_units + 1e-9:
        raise HTTPException(status_code=400, detail=f"Can sell at most {round(max_units, 4)} units")

    old_proceeds = float(s.sell_price) * float(s.units)
    h.quantity = round(float(h.quantity) - (new_units - float(s.units)), 6)
    s.units, s.sell_price = new_units, new_price
    s.gain = round((new_price - float(s.buy_price)) * new_units, 4)
    h.closed = h.quantity <= 1e-9
    if h.closed:
        h.quantity = 0
    _recompute_realized(db, h)
    _credit_budget(user, (new_price * new_units) - old_proceeds)
    db.commit()
    db.refresh(s)
    return _sale_out(s, dict(db.execute(select(Asset.ticker, Asset.name)).all()))


@router.delete("/sales/{sale_id}")
def delete_sale(sale_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    s = db.get(Sale, sale_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Sale not found")
    h = db.get(Holding, s.holding_id)
    proceeds = float(s.sell_price) * float(s.units)
    if h is not None:
        h.quantity = round(float(h.quantity) + float(s.units), 6)
        h.closed = False
    db.delete(s)
    db.flush()
    if h is not None:
        _recompute_realized(db, h)
    _credit_budget(user, -proceeds)  # undo the proceeds that were credited
    db.commit()
    return {"deleted": sale_id}


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
    if req.deduct:
        _credit_budget(user, -(req.buy_price * req.quantity))  # cash spent leaves the budget
        h.from_budget = True
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
    # If it was bought from the budget, hand back the cost basis of what's still held
    # (sold units already returned their cash as proceeds).
    if h.from_budget:
        _credit_budget(user, float(h.buy_price) * float(h.quantity))
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
