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

    # EGX securities EODHD omits from the exchange-symbol-list but still serves via
    # the eod/fundamentals endpoints. Comma-separated codes (e.g. "BIGP,FNAR").
    extra_tickers: str = "BIGP,FNAR"

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
    # Fallback default band (used only when ML models aren't trained yet).
    primary_target_pct: float = 0.05
    primary_horizon_days: int = 10

    # The RATING (super/strong/buy/…) is read from this band — the hardest target
    # with the model's strongest edge over the market, so conviction is meaningful.
    # It is deliberately separate from the headline profit target below.
    conviction_target_pct: float = 0.10
    conviction_horizon_days: int = 10

    # Confidence-first TARGET: for each stock the scan headlines the BIGGEST target
    # whose hit-probability is >= this. So picks advertise reliable profit, sized
    # per stock, rather than forcing one global %. (Separate from the rating above.)
    min_confidence: float = 0.60

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
    # Trusted-source whitelist: when on, headlines from any publisher NOT in this
    # list are dropped before analysis (so sentiment is built on reputable sources
    # only). Matched against the Google News publisher name AND its domain.
    news_trusted_only: bool = True
    news_trusted_sources: str = (
        "reuters.com,reuters,bloomberg.com,bloomberg,asharqbusiness.com,asharq business,"
        "asharq,enterprise.press,enterprise,mubasher.info,mubasher,zawya.com,zawya,"
        "ahram.org.eg,ahram online,al-ahram,daily news egypt,dailynewsegypt.com,"
        "amwalalghad.com,amwal al ghad,almalnews.com,al mal,al-mal,alborsanews.com,"
        "al borsa,alborsa,egypttoday.com,egypt today,arabfinance.com,arab finance,"
        "investing.com,investing,cnbc.com,cnbc,reuters arabic"
    )

    # --- signal conviction / gating (the "super strong" tiers + market regime) ---
    # Tiers are set by the model's edge = prob / market base-rate. The model's real
    # top-decile lift is ~1.3-1.4x, so thresholds are tuned to THAT (the old 1.5x
    # bar was above the model's achievable range, so nothing ever qualified).
    buy_ratio_min: float = 1.08          # prob must beat the base rate by >= 8%
    strong_ratio_min: float = 1.22       # clear positive edge -> strong buy
    super_ratio_min: float = 1.35        # near the top of the model's range -> super
    hold_ratio_min: float = 0.92         # within ~base rate -> hold
    sell_ratio_min: float = 0.72         # below base -> sell (else strong_sell)
    # A pick is upgraded to SUPER only on confluence: top ML edge AND a strong
    # rule-score AND volume confirmation AND not overbought AND a healthy market.
    super_score_min: float = 65.0        # rule-score floor for a super buy
    super_sell_ratio_max: float = 0.45   # ML ratio ceiling for a super sell
    super_sell_score_max: float = 30.0   # rule-score ceiling for a super sell
    overbought_rsi: float = 78.0         # above this, no super buy (pullback risk)
    super_vol_min: float = 1.2           # volume must be >= this x average to confirm
    market_regime_gate: bool = True      # in a down market, demote buys one notch

    # --- portfolio budget allocator ---
    alloc_top_n: int = 8                  # how many top picks to spread a budget across
    alloc_max_position_pct: float = 0.25  # cap any single position at 25% (diversification)

    @property
    def extra_ticker_list(self) -> list[str]:
        out = []
        for s in self.extra_tickers.split(","):
            s = s.strip().upper()
            if s:
                out.append(s if "." in s else f"{s}.{self.egx_exchange}")
        return out

    @property
    def news_lang_list(self) -> list[str]:
        return [s.strip() for s in self.news_langs.split(",") if s.strip()]

    @property
    def news_trusted_list(self) -> list[str]:
        return [s.strip().lower() for s in self.news_trusted_sources.split(",") if s.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
