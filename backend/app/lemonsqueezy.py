"""Lemon Squeezy client — checkout links, subscription reads, webhook verification.

Lemon Squeezy is a Merchant of Record: it sells on our behalf, collects the money
(cards, PayPal, Apple/Google Pay), handles VAT worldwide, and pays out to a bank.
That's what lets this work from a country where PayPal can't receive funds.

Trust model: the browser only ever gets a checkout URL. Entitlements are granted
solely from signed webhooks or a server-side API read — never from anything the
client claims.
"""
from __future__ import annotations

import hashlib
import hmac
import urllib.parse

import requests

from app.config import settings

API = "https://api.lemonsqueezy.com/v1"


class LemonError(RuntimeError):
    pass


def _headers() -> dict:
    if not settings.lemon_api_key:
        raise LemonError("LEMON_API_KEY is not set")
    return {
        "Authorization": f"Bearer {settings.lemon_api_key}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
    }


def _get(path: str) -> dict:
    r = requests.get(f"{API}{path}", headers=_headers(), timeout=30)
    if r.status_code >= 400:
        raise LemonError(f"GET {path} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def get_subscription(sub_id: str) -> dict:
    """Authoritative subscription record (status, variant, renews_at)."""
    return _get(f"/subscriptions/{sub_id}").get("data", {})


def list_variants() -> list[dict]:
    """Every variant in the account — used by the setup script to print ids."""
    out: list[dict] = []
    url = "/variants?page[size]=100"
    while url:
        data = _get(url)
        out.extend(data.get("data", []))
        nxt = (data.get("links") or {}).get("next")
        url = nxt.replace(API, "") if nxt else None
    return out


def cancel_subscription(sub_id: str) -> None:
    r = requests.delete(f"{API}/subscriptions/{sub_id}", headers=_headers(), timeout=30)
    if r.status_code >= 400:
        raise LemonError(f"cancel -> {r.status_code}: {r.text[:200]}")


def store_subdomain() -> str:
    """Just the subdomain, however LEMON_STORE was written.

    People naturally paste the whole thing ("saeed.lemonsqueezy.com", or with
    https://), which would otherwise build a double-domain checkout URL.
    """
    s = (settings.lemon_store or "").strip()
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    s = s.rstrip("/")
    if s.endswith(".lemonsqueezy.com"):
        s = s[: -len(".lemonsqueezy.com")]
    return s.split("/")[0].split(".")[0] if s else ""


def checkout_url(variant_id: str, *, email: str, user_id: int,
                 redirect_to: str | None = None) -> str:
    """A hosted-checkout link for one variant.

    `custom[user_id]` comes back on every webhook, which is how a payment is tied to
    an account — email alone is unreliable (people pay with a different address).
    """
    store = store_subdomain()
    if not store:
        raise LemonError("LEMON_STORE is not set")
    if not variant_id:
        raise LemonError("No Lemon Squeezy variant configured for that plan")
    params = {
        "checkout[email]": email,
        "checkout[custom][user_id]": str(user_id),
        "embed": "0",
    }
    if redirect_to:
        params["checkout[success_url]"] = redirect_to
    q = urllib.parse.urlencode(params)
    return f"https://{store}.lemonsqueezy.com/buy/{variant_id}?{q}"


def verify_webhook(signature: str | None, body: bytes) -> bool:
    """HMAC-SHA256 of the raw body against the signing secret.

    Returns False rather than raising, so a failure can never be mistaken for a
    valid event. Uses a constant-time compare.
    """
    if not signature or not settings.lemon_webhook_secret:
        return False
    digest = hmac.new(
        settings.lemon_webhook_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(digest, signature.strip())


def plan_period_for(variant_id: str | int) -> tuple[str, str] | None:
    """Map a Lemon Squeezy variant id back to our (plan, period)."""
    from app.plans import PERIODS, PLANS

    want = str(variant_id)
    for code in PLANS:
        for period in PERIODS:
            configured = getattr(settings, f"lemon_variant_{code}_{period}", "") or ""
            if configured and str(configured) == want:
                return code, period
    return None
