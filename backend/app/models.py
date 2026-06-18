"""SQLAlchemy ORM models. Portable types only (work on SQLite + Postgres)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    """A friend with access. Registration is gated by the invite code."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="member")  # admin | member
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    watchlist: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_watch_user_ticker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="watchlist")


class Asset(Base):
    """One row per security on the exchange."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # COMI.EGX
    name: Mapped[str | None] = mapped_column(String(256))
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    asset_type: Mapped[str | None] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16), default="EGX")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)  # passes filters
    is_listed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class DailyBar(Base):
    """Daily OHLCV (adjusted)."""

    __tablename__ = "daily_bars"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_bar_ticker_date"),
        Index("ix_bar_ticker_date", "ticker", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), ForeignKey("assets.ticker"), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(18, 4))
    high: Mapped[float | None] = mapped_column(Numeric(18, 4))
    low: Mapped[float | None] = mapped_column(Numeric(18, 4))
    close: Mapped[float | None] = mapped_column(Numeric(18, 4))
    adj_close: Mapped[float | None] = mapped_column(Numeric(18, 4))
    volume: Mapped[float | None] = mapped_column(Numeric(20, 2))


class Recommendation(Base):
    """A ranked call for a given scan date — self-describing for audit/explainability."""

    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("date", "ticker", name="uq_rec_date_ticker"),
        Index("ix_rec_date_score", "date", "score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(32), ForeignKey("assets.ticker"), nullable=False)
    signal: Mapped[str] = mapped_column(String(16))  # strong_buy|buy|hold|sell|strong_sell
    score: Mapped[float] = mapped_column(Float)  # 0-100 opportunity score
    success_prob: Mapped[float | None] = mapped_column(Float)  # backtested hit-rate (0-1)
    success_n: Mapped[int | None] = mapped_column(Integer)  # sample size behind the prob
    target_pct: Mapped[float | None] = mapped_column(Float)  # which band the prob refers to
    horizon_days: Mapped[int | None] = mapped_column(Integer)
    entry_price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    target_price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(18, 4))
    expected_hold_days: Mapped[float | None] = mapped_column(Float)
    reasons: Mapped[list | None] = mapped_column(JSON)  # list[str] explainability
    features: Mapped[dict | None] = mapped_column(JSON)  # snapshot used at call time
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    outcome: Mapped["Outcome | None"] = relationship(
        back_populates="recommendation", uselist=False, cascade="all, delete-orphan"
    )


class Outcome(Base):
    """Realized result of a recommendation once its horizon has elapsed."""

    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id"), unique=True, nullable=False
    )
    hit_target: Mapped[bool | None] = mapped_column(Boolean)  # reached target before stop/horizon
    return_pct: Mapped[float | None] = mapped_column(Float)  # close-to-close over horizon
    max_gain: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    days_to_target: Mapped[int | None] = mapped_column(Integer)
    validated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    recommendation: Mapped[Recommendation] = relationship(back_populates="outcome")


class BacktestStat(Base):
    """Walk-forward backtest result: the honest Success % per score band + target."""

    __tablename__ = "backtest_stats"
    __table_args__ = (
        UniqueConstraint(
            "score_band", "target_pct", "horizon_days", name="uq_bt_band_target_horizon"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score_band: Mapped[str] = mapped_column(String(16))  # e.g. "80-90"
    target_pct: Mapped[float] = mapped_column(Float)
    horizon_days: Mapped[int] = mapped_column(Integer)
    n_samples: Mapped[int] = mapped_column(Integer)
    hit_rate: Mapped[float] = mapped_column(Float)  # 0-1 — the Success %
    avg_return: Mapped[float | None] = mapped_column(Float)
    avg_days_to_target: Mapped[float | None] = mapped_column(Float)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)


class ModelVersion(Base):
    """A trained ML model for one target band + its honest out-of-sample metrics."""

    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    band_key: Mapped[str] = mapped_column(String(32), index=True)  # e.g. "t10_h10"
    target_pct: Mapped[float] = mapped_column(Float)
    horizon_days: Mapped[int] = mapped_column(Integer)
    algo: Mapped[str] = mapped_column(String(32))                  # hgb | logreg
    feature_set_version: Mapped[str] = mapped_column(String(16), default="1")
    n_samples: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict | None] = mapped_column(JSON)            # auc, precision, base_rate...
    artifact: Mapped[bytes | None] = mapped_column(LargeBinary)   # joblib-pickled pipeline
    is_production: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    trained_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)


class PipelineRun(Base):
    """Audit log of each daily scan."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_date: Mapped[dt.date] = mapped_column(Date, index=True)
    data_date: Mapped[dt.date | None] = mapped_column(Date)  # latest bar date used
    universe_size: Mapped[int | None] = mapped_column(Integer)
    active_count: Mapped[int | None] = mapped_column(Integer)
    ranked_count: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
