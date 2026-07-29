"""Subscription plans + the entitlement rules.

One place defines what each plan costs, which markets it unlocks, and who is
allowed past the paywall — so the API, the admin panel and the UI can never
disagree about access.

Prices here are the source of truth shown in the UI. The PayPal *plan ids* are
supplied by the environment (they're created once in the PayPal dashboard), so
deploying to sandbox vs. live is a config change, not a code change.
"""
from __future__ import annotations

import datetime as dt

from app.config import settings

# code -> label, markets unlocked, prices
PLANS: dict[str, dict] = {
    "egx": {
        "code": "egx",
        "label": "EGX",
        "blurb": "Daily Egyptian Exchange signals.",
        "markets": ["EGX"],
        "monthly": 5.0,
        "annual": 40.0,
    },
    "us": {
        "code": "us",
        "label": "US",
        "blurb": "Daily US stock signals.",
        "markets": ["US"],
        "monthly": 7.0,
        "annual": 60.0,
    },
    "both": {
        "code": "both",
        "label": "EGX + US",
        "blurb": "Both markets — everything we publish.",
        "markets": ["EGX", "US"],
        "monthly": 10.0,
        "annual": 90.0,
    },
}

PERIODS = ("monthly", "annual")
# Roles that never need to pay. `staff` gets full market access but no admin panel.
FREE_ROLES = ("admin", "staff")


def plan_markets(plan: str | None) -> list[str]:
    p = PLANS.get((plan or "").lower())
    return list(p["markets"]) if p else []


def price_of(plan: str, period: str) -> float | None:
    p = PLANS.get((plan or "").lower())
    return p.get(period) if p and period in PERIODS else None


def paypal_plan_id(plan: str, period: str) -> str | None:
    """PayPal billing-plan id for a (plan, period), from env:
    PAYPAL_PLAN_EGX_MONTHLY, PAYPAL_PLAN_BOTH_ANNUAL, ..."""
    key = f"paypal_plan_{plan}_{period}".lower()
    return getattr(settings, key, "") or None


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _aware(d: dt.datetime | None) -> dt.datetime | None:
    """Rows written by different drivers can come back naive; compare safely."""
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def subscription_active(user) -> bool:
    until = _aware(getattr(user, "plan_until", None))
    return bool(getattr(user, "plan", None) and until and until > _utcnow())


def allowed_markets(user) -> list[str]:
    """Markets this account may read right now."""
    if getattr(user, "role", "") in FREE_ROLES:
        return ["EGX", "US"]
    return plan_markets(user.plan) if subscription_active(user) else []


def can_access(user, market: str | None) -> bool:
    """True if the account may read this market (None = any market they hold)."""
    allowed = allowed_markets(user)
    if not market:
        return bool(allowed)
    return market.strip().upper() in allowed


def extend(current: dt.datetime | None, period: str) -> dt.datetime:
    """New expiry after paying for `period` — extends an unexpired term rather than
    truncating it, so renewing early never costs the user days."""
    base = _aware(current)
    now = _utcnow()
    start = base if (base and base > now) else now
    return start + dt.timedelta(days=365 if period == "annual" else 30)


def public_plans() -> list[dict]:
    """Plan catalogue for the pricing/register UI."""
    out = []
    for p in PLANS.values():
        out.append({
            "code": p["code"], "label": p["label"], "blurb": p["blurb"],
            "markets": p["markets"], "monthly": p["monthly"], "annual": p["annual"],
            "annual_saving": round(p["monthly"] * 12 - p["annual"], 2),
            "paypal_plan_monthly": paypal_plan_id(p["code"], "monthly"),
            "paypal_plan_annual": paypal_plan_id(p["code"], "annual"),
        })
    return out
