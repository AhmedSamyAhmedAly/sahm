"""Central configuration, read from environment / .env.

Secrets (EODHD_API_TOKEN, JWT_SECRET, DATABASE_URL) come from the environment in
production (Render/Vercel/GitHub Actions). Everything else has a sane default and
is overridable, so behaviour is tunable without code changes.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- secrets ---
    eodhd_api_token: str = ""
    # News sentiment LLM (daily job only). Either provider works; OpenAI is tried
    # first if set, else Anthropic, else free keyword sentiment.
    openai_api_token: str = ""
    anthropic_api_token: str = ""
    database_url: str = "sqlite:///./sahm.db"
    jwt_secret: str = "change-me"
    invite_code: str = "sahm-invite"

    # --- access ---
    # The ONE admin. This email is always admin; everyone else is always member.
    admin_email: str = "ahmed.samy@sahm.app"

    # --- web ---
    cors_origins: str = "http://localhost:5173"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- market / engine ---
    egx_exchange: str = "EGX"
    egx_top_n: int = 25

    # Liquidity filters for the tradable universe.
    min_history_days: int = 120          # need enough bars for indicators
    min_avg_value_traded: float = 200_000.0   # EGP/day, 20-day average

    # Targets / horizons the backtester measures (the "Success %").
    # Each (target_pct, horizon_days): did price rise >= target within horizon?
    target_bands: list[tuple[float, int]] = [
        (0.05, 10),
        (0.10, 10),
        (0.15, 20),
        (0.20, 20),
    ]
    # Default band shown as the headline Success % on a pick.
    primary_target_pct: float = 0.10
    primary_horizon_days: int = 10

    # ATR-based trade levels.
    atr_stop_mult: float = 1.5     # stop = entry - 1.5 * ATR
    atr_period: int = 14

    # --- news overlay (daily job only; never the web API) ---
    news_enabled: bool = True
    news_shortlist_n: int = 30           # only enrich the top N buy candidates (cost guard)
    openai_model: str = "gpt-4o-mini"    # cheap; used when OPENAI_API_TOKEN is set
    news_model: str = "claude-haiku-4-5"  # used when only ANTHROPIC_API_TOKEN is set
    news_weight: float = 0.03            # light re-rank weight within the shortlist
    news_langs: str = "ar,en"            # comma-separated

    @property
    def news_lang_list(self) -> list[str]:
        return [s.strip() for s in self.news_langs.split(",") if s.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
