"""Pydantic request/response models for the API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, EmailStr


# ---- auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    invite_code: str = ""
    # The plan the visitor picked on the register form. Stored as INTENT only —
    # access is granted after payment (or an admin grant), never at signup.
    plan: str | None = None
    period: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ---- billing / subscriptions ----
class ActivateSubscriptionRequest(BaseModel):
    subscription_id: str


class CheckoutRequest(BaseModel):
    """Ask for a hosted-checkout link. Price/markets come from the server's plan
    catalogue — the client only names which plan it wants."""
    plan: str
    period: str = "monthly"
    redirect_to: str | None = None


class SubscriptionOut(BaseModel):
    plan: str | None = None
    plan_until: dt.datetime | None = None
    plan_source: str | None = None
    active: bool = False
    markets: list[str] = []
    role: str = "member"
    needs_payment: bool = True


class GrantSubscriptionRequest(BaseModel):
    """Admin: give (or revoke) a plan without payment."""
    plan: str | None = None          # egx | us | both | None to revoke
    days: int | None = None          # length from now; ignored if `until` given
    until: dt.datetime | None = None
    note: str | None = None


# ---- admin ----
class AdminUserOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    is_primary: bool = False   # the protected bootstrap admin (ADMIN_EMAIL)
    created_at: dt.datetime | None = None
    last_login_at: dt.datetime | None = None
    # subscription state
    plan: str | None = None
    plan_until: dt.datetime | None = None
    plan_source: str | None = None
    subscription_active: bool = False
    markets: list[str] = []


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "member"


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


# ---- admin stats ----
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
    # Entitlement, so the SPA can gate markets without a second round-trip.
    plan: str | None = None
    plan_until: dt.datetime | None = None
    markets: list[str] = []
    needs_payment: bool = False


# ---- picks / stocks ----
class PickOut(BaseModel):
    rank: int
    ticker: str
    name: str | None = None
    sector: str | None = None
    signal: str | None = None   # None = unscored (didn't pass scan filters), data-only
    score: float | None = None
    last_close: float | None = None        # latest end-of-day close we have
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
    # Per-band scenarios for the pills: [{target_pct, horizon_days, prob, n}, ...].
    bands: list[dict] = []
    # Liquidity / tradeability (how wide the spread is likely to be).
    avg_value_traded: float | None = None       # recent avg daily traded value
    liquidity: str | None = None                # "high" | "ok" | "thin" (vs market floor)
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
