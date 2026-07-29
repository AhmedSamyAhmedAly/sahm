"""Register the PayPal webhook and print its id.

The webhook is what keeps subscriptions alive: without it the first payment works
and every subscriber silently expires at the end of their first period, because
nothing tells us the renewal happened.

    cd backend
    # credentials come from .env (PAYPAL_ENV / CLIENT_ID / CLIENT_SECRET)
    WEBHOOK_URL=https://<your-backend>/api/billing/webhook \
        python scripts/paypal_setup_webhook.py

Re-runnable: if a webhook already points at that URL it is reused (and its event
list is updated) rather than duplicated.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from app.config import settings  # noqa: E402

# The events the billing router actually handles.
EVENTS = [
    "PAYMENT.SALE.COMPLETED",            # the renewal payment — the important one
    "PAYMENT.SALE.DENIED",
    "BILLING.SUBSCRIPTION.ACTIVATED",
    "BILLING.SUBSCRIPTION.RE-ACTIVATED",
    "BILLING.SUBSCRIPTION.CANCELLED",
    "BILLING.SUBSCRIPTION.EXPIRED",
    "BILLING.SUBSCRIPTION.SUSPENDED",
]


def token() -> str:
    if not settings.paypal_configured:
        sys.exit("Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET (in backend/.env) first.")
    r = requests.post(
        f"{settings.paypal_api_base}/v1/oauth2/token",
        auth=(settings.paypal_client_id, settings.paypal_client_secret),
        data={"grant_type": "client_credentials"}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"PayPal auth failed ({r.status_code}): {r.text[:300]}")
    return r.json()["access_token"]


def main() -> None:
    url = os.environ.get("WEBHOOK_URL", "").strip()
    if not url:
        sys.exit("Set WEBHOOK_URL=https://<your-backend>/api/billing/webhook")
    if not url.startswith("https://"):
        sys.exit("PayPal only accepts an HTTPS webhook URL.")

    tok = token()
    hdr = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    print(f"PayPal environment: {settings.paypal_env.upper()}")
    print(f"webhook url: {url}")

    # Reuse an existing webhook for this URL if there is one.
    existing = requests.get(f"{settings.paypal_api_base}/v1/notifications/webhooks",
                            headers=hdr, timeout=30)
    hook_id = None
    if existing.status_code == 200:
        for w in existing.json().get("webhooks", []):
            if w.get("url") == url:
                hook_id = w.get("id")
                break

    if hook_id:
        # Keep the event list in sync with what the code handles.
        patch = requests.patch(
            f"{settings.paypal_api_base}/v1/notifications/webhooks/{hook_id}",
            headers=hdr,
            json=[{"op": "replace", "path": "/event_types",
                   "value": [{"name": e} for e in EVENTS]}], timeout=30)
        print(f"reused existing webhook {hook_id}"
              + ("" if patch.status_code < 400 else f" (event update failed: {patch.status_code})"))
    else:
        r = requests.post(f"{settings.paypal_api_base}/v1/notifications/webhooks",
                          headers=hdr,
                          json={"url": url, "event_types": [{"name": e} for e in EVENTS]},
                          timeout=30)
        if r.status_code >= 400:
            sys.exit(f"create webhook failed ({r.status_code}): {r.text[:400]}")
        hook_id = r.json()["id"]
        print(f"created webhook {hook_id}")

    print("\nsubscribed events:")
    for e in EVENTS:
        print(f"  - {e}")
    print("\n" + "=" * 60)
    print("Add this to the Railway BACKEND service variables:\n")
    print(f"PAYPAL_WEBHOOK_ID={hook_id}")
    print("=" * 60)
    print("Until it is set, incoming webhooks are REJECTED (unverified events are")
    print("never trusted), so renewals won't extend anyone's access.")


if __name__ == "__main__":
    main()
