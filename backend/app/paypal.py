"""Minimal PayPal Subscriptions client.

Only what we need: an OAuth token, reading a subscription, cancelling one, and
verifying a webhook signature. Everything is verified server-side — the browser
never decides whether a subscription is real.
"""
from __future__ import annotations

import time

import requests

from app.config import settings

_token: dict = {"value": "", "expires": 0.0}


class PayPalError(RuntimeError):
    pass


def _access_token() -> str:
    """Cached client-credentials token (PayPal tokens last ~9h)."""
    if _token["value"] and _token["expires"] > time.time() + 60:
        return _token["value"]
    if not settings.paypal_configured:
        raise PayPalError("PayPal is not configured (missing client id/secret)")
    r = requests.post(
        f"{settings.paypal_api_base}/v1/oauth2/token",
        auth=(settings.paypal_client_id, settings.paypal_client_secret),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    if r.status_code != 200:
        raise PayPalError(f"PayPal auth failed ({r.status_code}): {r.text[:200]}")
    data = r.json()
    _token["value"] = data["access_token"]
    _token["expires"] = time.time() + float(data.get("expires_in", 3000))
    return _token["value"]


def _get(path: str) -> dict:
    r = requests.get(
        f"{settings.paypal_api_base}{path}",
        headers={"Authorization": f"Bearer {_access_token()}"},
        timeout=30,
    )
    if r.status_code >= 400:
        raise PayPalError(f"PayPal GET {path} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def get_subscription(subscription_id: str) -> dict:
    """The authoritative record: status, plan id, next billing time."""
    return _get(f"/v1/billing/subscriptions/{subscription_id}")


def cancel_subscription(subscription_id: str, reason: str = "User requested") -> None:
    r = requests.post(
        f"{settings.paypal_api_base}/v1/billing/subscriptions/{subscription_id}/cancel",
        headers={"Authorization": f"Bearer {_access_token()}",
                 "Content-Type": "application/json"},
        json={"reason": reason[:127]},
        timeout=30,
    )
    if r.status_code not in (204, 200):
        raise PayPalError(f"PayPal cancel -> {r.status_code}: {r.text[:200]}")


def verify_webhook(headers, body: bytes) -> bool:
    """Ask PayPal whether a webhook really came from them.

    Returns False (never raises) so a verification outage can't be mistaken for a
    valid event — the caller must ignore anything unverified.
    """
    if not settings.paypal_webhook_id or not settings.paypal_configured:
        return False
    try:
        payload = {
            "auth_algo": headers.get("paypal-auth-algo"),
            "cert_url": headers.get("paypal-cert-url"),
            "transmission_id": headers.get("paypal-transmission-id"),
            "transmission_sig": headers.get("paypal-transmission-sig"),
            "transmission_time": headers.get("paypal-transmission-time"),
            "webhook_id": settings.paypal_webhook_id,
            "webhook_event": __import__("json").loads(body.decode("utf-8")),
        }
        if not all(payload[k] for k in
                   ("auth_algo", "cert_url", "transmission_id", "transmission_sig",
                    "transmission_time")):
            return False
        r = requests.post(
            f"{settings.paypal_api_base}/v1/notifications/verify-webhook-signature",
            headers={"Authorization": f"Bearer {_access_token()}",
                     "Content-Type": "application/json"},
            json=payload, timeout=30,
        )
        return r.status_code == 200 and r.json().get("verification_status") == "SUCCESS"
    except Exception:  # noqa: BLE001 — treat any failure as "not verified"
        return False


def plan_period_for(paypal_plan_id: str) -> tuple[str, str] | None:
    """Map a PayPal plan id back to our (plan, period)."""
    from app.plans import PERIODS, PLANS
    for code in PLANS:
        for period in PERIODS:
            from app.plans import paypal_plan_id as ours
            if ours(code, period) and ours(code, period) == paypal_plan_id:
                return code, period
    return None
