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
    created_at: dt.datetime | None = None
    last_login_at: dt.datetime | None = None
    watchlist_count: int = 0


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "member"


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


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
    watched: bool = False
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
