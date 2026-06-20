"""Pydantic request/response models for the API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, EmailStr


# ---- auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    invite_code: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ---- admin ----
class AdminUserOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    is_primary: bool = False   # the protected bootstrap admin (ADMIN_EMAIL)
    created_at: dt.datetime | None = None
    last_login_at: dt.datetime | None = None


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "member"


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


# ---- portfolio ----
class HoldingIn(BaseModel):
    ticker: str
    buy_price: float
    quantity: float


class HoldingOut(BaseModel):
    id: int
    ticker: str
    name: str | None = None
    buy_price: float
    quantity: float
    invested: float
    current_price: float | None = None
    current_value: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    signal: str | None = None
    success_prob: float | None = None
    target_price: float | None = None   # suggested target sell price
    stop_loss: float | None = None
    alert: str | None = None          # e.g. "Signal turned sell", "Target reached"
    sell_suggested: bool = False
    sold_qty: float = 0
    avg_sell_price: float | None = None
    realized_pnl: float = 0


class HoldingUpdate(BaseModel):
    buy_price: float | None = None
    quantity: float | None = None


class BulkHoldingsIn(BaseModel):
    items: list[HoldingIn]


class BulkResult(BaseModel):
    added: int
    skipped: int
    errors: list[str] = []


class PortfolioResponse(BaseModel):
    budget: float | None = None
    invested: float = 0
    current_value: float = 0
    pnl: float = 0                 # unrealized P/L on open holdings
    pnl_pct: float | None = None
    realized_pnl: float = 0        # banked from sells
    earnings: float = 0            # realized + unrealized
    holdings: list[HoldingOut] = []


class BudgetIn(BaseModel):
    budget: float


class SellIn(BaseModel):
    sell_price: float
    units: float


class ContactIn(BaseModel):
    title: str
    description: str | None = None
    attachments: list[dict] = []   # [{name, type, data(base64)}]


class ContactMessageOut(BaseModel):
    id: int
    email: str | None = None
    title: str
    description: str | None = None
    attachments: list[dict] = []
    resolved: bool = False
    created_at: dt.datetime | None = None


class AllocationItem(BaseModel):
    ticker: str
    name: str | None = None
    signal: str
    success_prob: float | None = None
    suggested_amount: float
    shares: int
    entry_price: float | None = None
    target_price: float | None = None


class AllocationResponse(BaseModel):
    budget: float
    leftover_cash: float
    allocations: list[AllocationItem] = []
    note: str


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    admins: int
    logins_last_7d: int
    recommendations: int
    last_scan_date: dt.date | None = None
    universe_size: int
    active_assets: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    role: str
    budget: float | None = None   # so the SPA can gate on "budget set"


# ---- picks / stocks ----
class PickOut(BaseModel):
    rank: int
    ticker: str
    name: str | None = None
    sector: str | None = None
    signal: str
    score: float
    success_prob: float | None = None      # 0-1 backtested hit-rate
    success_n: int | None = None
    target_pct: float | None = None
    horizon_days: int | None = None
    entry_price: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    risk_reward: float | None = None
    expected_hold_days: float | None = None
    reasons: list[str] = []
    # live news overlay (separate from success_prob)
    news_sentiment: float | None = None
    news_label: str | None = None
    news_thesis: str | None = None
    news_catalyst: bool | None = None


class PicksResponse(BaseModel):
    date: dt.date | None
    universe_size: int
    active_count: int
    picks: list[PickOut]


class BarOut(BaseModel):
    date: dt.date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None


class StockDetail(BaseModel):
    ticker: str
    name: str | None
    sector: str | None
    latest: PickOut | None
    components: dict | None = None
    bars: list[BarOut]
    history: list[dict]   # past recommendations + outcomes for this name
    news: dict | None = None   # {headlines:[...], catalysts, risk_flag, engine}


# ---- track record ----
class BacktestStatOut(BaseModel):
    score_band: str
    target_pct: float
    horizon_days: int
    n_samples: int
    hit_rate: float
    avg_return: float | None
    avg_days_to_target: float | None


class ModelMetricOut(BaseModel):
    band_key: str
    target_pct: float
    horizon_days: int
    algo: str
    n_samples: int
    auc: float | None = None
    precision_top10: float | None = None
    base_rate: float | None = None
    lift_top10: float | None = None


class TrackRecordResponse(BaseModel):
    live_win_rate: float | None
    live_graded: int
    live_avg_return: float | None
    backtest: list[BacktestStatOut]
    equity_curve: list[dict]   # cumulative realized return over time
    models: list[ModelMetricOut] = []
