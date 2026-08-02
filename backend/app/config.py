"""Central configuration, read from environment / .env.

Secrets (EODHD_API_TOKEN, JWT_SECRET, DATABASE_URL) come from the environment in
production (Render/Vercel/GitHub Actions). Everything else has a sane default and
is overridable, so behaviour is tunable without code changes.

Multi-market
------------
The engine runs one MARKET at a time (an exchange: EGX, US, ...). The active market
is chosen by the ``MARKET`` env var (default ``EGX``) or the CLI ``--market`` flag,
and selects a :class:`MarketProfile` — the per-market knobs that differ (exchange
code, currency, liquidity floor, news sources/language/region). Everything the two
markets share (target bands, signal ratios, ATR, news weight) stays global. Each
market keeps its own assets/bars/recommendations (namespaced tickers + the
``exchange`` column) and its own models/backtest-stats (the ``exchange`` column),
so EGX and US never clobber each other in the same database.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class MarketProfile:
    """The per-market knobs that differ between exchanges."""

    code: str                  # exchange code == Asset.exchange, e.g. "EGX" / "US"
    name: str                  # human label, e.g. "Egyptian Exchange"
    currency: str              # display currency of the liquidity floor
    min_history_days: int = 120         # bars needed before a stock is tradable
    min_avg_value_traded: float = 200_000.0   # currency/day, 20-day average
    extra_tickers: str = ""    # comma-separated codes EODHD omits from the list
    # For virtual exchanges (EODHD "US" bundles NYSE/Nasdaq/OTC/pink-sheets), keep
    # only symbols whose sub-exchange is in this set. Empty = accept all. This keeps
    # the US universe to the main boards so the bootstrap stays tractable.
    symbol_exchanges: str = ""
    # --- news overlay ---
    news_langs: str = "en"     # comma-separated Google-News languages
    news_region: str = "US"    # Google-News country (gl)
    news_query_en: str = "(stock OR shares)"   # English disambiguation clause
    news_query_ar: str = ""    # Arabic clause (EGX only; empty = skip Arabic)
    news_trusted_sources: str = ""             # trusted-publisher whitelist

    @property
    def extra_ticker_list(self) -> list[str]:
        out = []
        for s in self.extra_tickers.split(","):
            s = s.strip().upper()
            if s:
                out.append(s if "." in s else f"{s}.{self.code}")
        return out

    @property
    def symbol_exchange_set(self) -> set[str]:
        return {s.strip().upper() for s in self.symbol_exchanges.split(",") if s.strip()}

    @property
    def news_lang_list(self) -> list[str]:
        return [s.strip() for s in self.news_langs.split(",") if s.strip()]

    @property
    def news_trusted_list(self) -> list[str]:
        return [s.strip().lower() for s in self.news_trusted_sources.split(",") if s.strip()]


# The markets the app can scan. Add a new exchange here (+ the frontend MARKETS
# list + its GitHub Actions workflows) to bring another market online.
MARKETS: dict[str, MarketProfile] = {
    "EGX": MarketProfile(
        code="EGX",
        name="Egyptian Exchange",
        currency="EGP",
        min_history_days=120,
        min_avg_value_traded=200_000.0,           # EGP/day
        extra_tickers="BIGP,FNAR",
        news_langs="ar,en",
        news_region="EG",
        news_query_en="(EGX OR Egypt stock OR shares)",
        news_query_ar="البورصة المصرية",
        news_trusted_sources=(
            "reuters.com,reuters,bloomberg.com,bloomberg,asharqbusiness.com,asharq business,"
            "asharq,enterprise.press,enterprise,mubasher.info,mubasher,zawya.com,zawya,"
            "ahram.org.eg,ahram online,al-ahram,daily news egypt,dailynewsegypt.com,"
            "amwalalghad.com,amwal al ghad,almalnews.com,al mal,al-mal,alborsanews.com,"
            "al borsa,alborsa,egypttoday.com,egypt today,arabfinance.com,arab finance,"
            "investing.com,investing,cnbc.com,cnbc,reuters arabic"
        ),
    ),
    "US": MarketProfile(
        code="US",
        name="US Stocks",
        currency="USD",
        min_history_days=120,
        # Broader liquid US: a ~$5M/day dollar-volume floor keeps NYSE/Nasdaq names
        # that actually trade (roughly the top ~1,500-3,000) and drops the illiquid tail.
        min_avg_value_traded=5_000_000.0,          # USD/day
        extra_tickers="",
        # Main US boards only — drops OTC / pink-sheets (illiquid, and they'd bloat
        # the full-history bootstrap). EODHD tags each symbol with its sub-exchange.
        symbol_exchanges="NYSE,NASDAQ,NYSE ARCA,NYSE MKT,NYSE AMERICAN,AMEX,BATS,NMS",
        news_langs="en",
        news_region="US",
        news_query_en="(NYSE OR NASDAQ OR stock OR shares OR earnings)",
        news_query_ar="",
        news_trusted_sources=(
            "reuters.com,reuters,bloomberg.com,bloomberg,cnbc.com,cnbc,wsj.com,"
            "wall street journal,barrons.com,barron's,barrons,marketwatch.com,marketwatch,"
            "ft.com,financial times,forbes.com,forbes,businesswire.com,business wire,"
            "globenewswire.com,globe newswire,prnewswire.com,pr newswire,"
            "seekingalpha.com,seeking alpha,investing.com,investing,"
            "finance.yahoo.com,yahoo finance,fool.com,motley fool,thestreet.com,the street"
        ),
    ),
}

_DEFAULT_MARKET = "EGX"
# Active market for THIS process. Seeded from the MARKET env var; the CLI --market
# flag can override it at runtime via set_active_market().
_active_market = os.getenv("MARKET", _DEFAULT_MARKET).strip().upper() or _DEFAULT_MARKET


def set_active_market(code: str) -> None:
    """Override the active market (used by the CLI --market flag)."""
    global _active_market
    code = (code or "").strip().upper()
    if code not in MARKETS:
        raise ValueError(f"unknown market {code!r}; known: {', '.join(MARKETS)}")
    _active_market = code


def active_market_code() -> str:
    return _active_market if _active_market in MARKETS else _DEFAULT_MARKET


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
    invite_code: str = "saeed-invite"
    # Set OPEN_REGISTRATION=true to let anyone sign up (public growth); otherwise
    # registration stays gated by the shared invite_code.
    open_registration: bool = False

    # --- access ---
    # The ONE bootstrap admin. This email is always admin; other roles are stored
    # per user (admin | staff | member) and managed from the admin panel.
    admin_email: str = "ahmed.samy@sahm.app"
    # Grace period for brand-new accounts so people can look around before paying.
    # 0 disables the trial entirely.
    trial_days: int = 0

    # --- billing ---
    # Which provider takes the money. "lemonsqueezy" is a Merchant of Record: it is
    # the legal seller, handles worldwide VAT, and pays out to a bank — which is what
    # makes it work where PayPal cannot receive funds (e.g. Egypt).
    billing_provider: str = "lemonsqueezy"      # lemonsqueezy | paypal | none

    # --- Lemon Squeezy ---
    lemon_api_key: str = ""
    lemon_store: str = ""             # your store subdomain, e.g. "saeed" in saeed.lemonsqueezy.com
    lemon_webhook_secret: str = ""    # the signing secret you set on the webhook
    # Variant ids from the dashboard (Products -> a product -> variant). One per
    # (plan, period) — see scripts/lemon_list_variants.py and docs/MONETIZATION.md.
    lemon_variant_egx_monthly: str = ""
    lemon_variant_egx_annual: str = ""
    lemon_variant_us_monthly: str = ""
    lemon_variant_us_annual: str = ""
    lemon_variant_both_monthly: str = ""
    lemon_variant_both_annual: str = ""

    @property
    def lemon_configured(self) -> bool:
        return bool(self.lemon_api_key and self.lemon_store)

    # --- billing (PayPal Subscriptions) ---
    # "sandbox" while testing, "live" for real money.
    paypal_env: str = "sandbox"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""     # from the PayPal webhook you create
    # Billing-plan ids created once in the PayPal dashboard (see docs/MONETIZATION.md)
    paypal_plan_egx_monthly: str = ""
    paypal_plan_egx_annual: str = ""
    paypal_plan_us_monthly: str = ""
    paypal_plan_us_annual: str = ""
    paypal_plan_both_monthly: str = ""
    paypal_plan_both_annual: str = ""

    # --- ads ---
    # Pasted from your ad network (AdSense/Ezoic/...). The <script> tag goes in
    # ads_head_snippet; each slot renders ads_slot_html with {slot} substituted.
    ads_enabled: bool = False
    ads_head_snippet: str = ""
    ads_slot_html: str = ""

    @property
    def paypal_api_base(self) -> str:
        return ("https://api-m.paypal.com" if self.paypal_env.strip().lower() == "live"
                else "https://api-m.sandbox.paypal.com")

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    # --- web ---
    cors_origins: str = "http://localhost:5173"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- market / engine ---
    egx_exchange: str = "EGX"            # legacy alias; prefer the active `exchange`
    egx_top_n: int = 25
    # The active market is chosen by the MARKET env var (default EGX) or the CLI
    # --market flag — see active_market_code() / set_active_market() above. Liquidity
    # floors, extra tickers and the news config are per-market (MarketProfile / MARKETS).

    # Targets / horizons the backtester measures (the "Success %"), one per risk
    # profile shown as a Suggestions tab:
    #   (0.10,10) aggressive (high profit, short, high risk) + the rating band
    #   (0.05,30) balanced (medium profit, medium term)
    #   (0.03,40) safest (low profit, long term, highest hit-rate)
    # The "best value" tab is computed (best profit-per-day at high confidence).
    target_bands: list[tuple[float, int]] = [
        (0.03, 40),
        (0.05, 30),
        (0.10, 10),
    ]
    # Fallback default band (used only when ML models aren't trained yet).
    primary_target_pct: float = 0.05
    primary_horizon_days: int = 30

    # The RATING (super/strong/buy/…) is read from this band — the hardest target
    # with the model's strongest edge over the market, so conviction is meaningful.
    # It is deliberately separate from the headline profit target below.
    conviction_target_pct: float = 0.10
    conviction_horizon_days: int = 10

    # Confidence-first TARGET: among bands whose hit-probability clears this floor,
    # the scan headlines the one with the best PROFIT-PER-DAY (most profit in the
    # least time). The model's calibrated confidence caps ~88% on EGX, so the floor
    # is set where it's actually reachable; the UI's confidence filter surfaces the
    # highest-confidence picks honestly (with the model's real number).
    min_confidence: float = 0.80

    # ATR-based trade levels.
    atr_stop_mult: float = 1.5     # stop = entry - 1.5 * ATR
    atr_period: int = 14

    # --- news overlay (daily job only; never the web API) ---
    news_enabled: bool = True
    news_shortlist_n: int = 30           # only enrich the top N buy candidates (cost guard)
    openai_model: str = "gpt-4o-mini"    # cheap; used when OPENAI_API_TOKEN is set
    news_model: str = "claude-haiku-4-5"  # used when only ANTHROPIC_API_TOKEN is set
    news_weight: float = 0.03            # light re-rank weight within the shortlist
    # Recency window passed to Google News as a `when:Nd` operator. Without it the
    # feed ranks by RELEVANCE, which on EGX/English routinely returned months-old
    # headlines in the top 8 — stale news that could demote a live signal.
    news_max_age_days: int = 7
    # Trusted-source whitelist: when on, headlines from any publisher NOT in this
    # market's list are dropped before analysis (so sentiment is built on reputable
    # sources only). The list itself is per-market (MarketProfile.news_trusted_sources).
    news_trusted_only: bool = True

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

    # --- active market (delegates to the selected MarketProfile) ---
    @property
    def active_market(self) -> str:
        """Exchange code of the market this process is scanning (EGX, US, ...)."""
        return active_market_code()

    @property
    def profile(self) -> MarketProfile:
        return MARKETS[self.active_market]

    @property
    def exchange(self) -> str:
        return self.profile.code

    @property
    def market_name(self) -> str:
        return self.profile.name

    @property
    def currency(self) -> str:
        return self.profile.currency

    @property
    def min_history_days(self) -> int:
        return self.profile.min_history_days

    @property
    def min_avg_value_traded(self) -> float:
        return self.profile.min_avg_value_traded

    @property
    def extra_ticker_list(self) -> list[str]:
        return self.profile.extra_ticker_list

    @property
    def news_lang_list(self) -> list[str]:
        return self.profile.news_lang_list

    @property
    def news_trusted_list(self) -> list[str]:
        return self.profile.news_trusted_list

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
