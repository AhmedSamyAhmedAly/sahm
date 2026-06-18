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


# ---- track record ----
class BacktestStatOut(BaseModel):
    score_band: str
    target_pct: float
    horizon_days: int
    n_samples: int
    hit_rate: float
    avg_return: float | None
    avg_days_to_target: float | None


class TrackRecordResponse(BaseModel):
    live_win_rate: float | None
    live_graded: int
    live_avg_return: float | None
    backtest: list[BacktestStatOut]
    equity_curve: list[dict]   # cumulative realized return over time
