"""Create the PayPal product + the six billing plans, then print the env vars.

Doing this by hand in the dashboard means 6 forms and 6 ids copied without typos.
This reads the prices from app/plans.py (the same numbers the UI shows), creates
everything through the API, and prints the exact variables to paste into Railway.

    cd backend
    # sandbox first:
    PAYPAL_ENV=sandbox PAYPAL_CLIENT_ID=... PAYPAL_CLIENT_SECRET=... \
        python scripts/paypal_setup_plans.py

    # when it all works, repeat with the LIVE app credentials:
    PAYPAL_ENV=live PAYPAL_CLIENT_ID=... PAYPAL_CLIENT_SECRET=... \
        python scripts/paypal_setup_plans.py

Safe to re-run: it reuses a product/plan with the same name instead of duplicating.
Note PayPal plan prices are IMMUTABLE — to change a price, create new plans (re-run
after editing app/plans.py) and point the env vars at the new ids.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from app.config import settings  # noqa: E402
from app.plans import PERIODS, PLANS  # noqa: E402

PRODUCT_NAME = "Saeed signals"
CYCLE = {"monthly": ("MONTH", 1), "annual": ("YEAR", 1)}


def token() -> str:
    if not settings.paypal_configured:
        sys.exit("Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET first.")
    r = requests.post(
        f"{settings.paypal_api_base}/v1/oauth2/token",
        auth=(settings.paypal_client_id, settings.paypal_client_secret),
        data={"grant_type": "client_credentials"}, timeout=30,
    )
    if r.status_code != 200:
        sys.exit(f"PayPal auth failed ({r.status_code}): {r.text[:300]}")
    return r.json()["access_token"]


def _headers(tok: str) -> dict:
    return {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        # Idempotency: a retried create returns the original instead of a duplicate.
        "PayPal-Request-Id": str(uuid.uuid4()),
    }


def find_product(tok: str) -> str | None:
    r = requests.get(f"{settings.paypal_api_base}/v1/catalogs/products?page_size=20",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    if r.status_code != 200:
        return None
    for p in r.json().get("products", []):
        if p.get("name") == PRODUCT_NAME:
            return p.get("id")
    return None


def ensure_product(tok: str) -> str:
    existing = find_product(tok)
    if existing:
        print(f"product: reusing {existing}")
        return existing
    r = requests.post(
        f"{settings.paypal_api_base}/v1/catalogs/products",
        headers=_headers(tok),
        json={
            "name": PRODUCT_NAME,
            "description": "Daily EGX & US stock signals with backtested success rates.",
            "type": "SERVICE",
            "category": "SOFTWARE",
        }, timeout=30)
    if r.status_code >= 400:
        sys.exit(f"create product failed ({r.status_code}): {r.text[:300]}")
    pid = r.json()["id"]
    print(f"product: created {pid}")
    return pid


def existing_plans(tok: str, product_id: str) -> dict[str, str]:
    """name -> plan id, for plans already under this product."""
    out: dict[str, str] = {}
    page = 1
    while True:
        r = requests.get(
            f"{settings.paypal_api_base}/v1/billing/plans"
            f"?product_id={product_id}&page_size=20&page={page}&total_required=true",
            headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        if r.status_code != 200:
            break
        data = r.json()
        for p in data.get("plans", []):
            out[p.get("name", "")] = p.get("id")
        if len(data.get("plans", [])) < 20:
            break
        page += 1
    return out


def create_plan(tok: str, product_id: str, name: str, price: float, period: str) -> str:
    unit, count = CYCLE[period]
    body = {
        "product_id": product_id,
        "name": name,
        "description": f"{name} — cancel any time.",
        "status": "ACTIVE",
        "billing_cycles": [{
            "frequency": {"interval_unit": unit, "interval_count": count},
            "tenure_type": "REGULAR",
            "sequence": 1,
            "total_cycles": 0,   # 0 = renew forever until cancelled
            "pricing_scheme": {
                "fixed_price": {"value": f"{price:.2f}", "currency_code": "USD"}
            },
        }],
        "payment_preferences": {
            "auto_bill_outstanding": True,
            "setup_fee_failure_action": "CONTINUE",
            "payment_failure_threshold": 2,
        },
    }
    r = requests.post(f"{settings.paypal_api_base}/v1/billing/plans",
                      headers=_headers(tok), json=body, timeout=30)
    if r.status_code >= 400:
        sys.exit(f"create plan '{name}' failed ({r.status_code}): {r.text[:400]}")
    return r.json()["id"]


def main() -> None:
    env = settings.paypal_env.strip().lower()
    print(f"PayPal environment: {env.upper()}  ({settings.paypal_api_base})")
    if env == "live":
        if input("This creates LIVE plans that take real money. Type 'yes' to continue: ").strip() != "yes":
            sys.exit("aborted")

    tok = token()
    product_id = ensure_product(tok)
    have = existing_plans(tok, product_id)

    env_lines: list[str] = []
    for code, plan in PLANS.items():
        for period in PERIODS:
            price = plan[period]
            name = f"Saeed {plan['label']} {period.title()}"
            if name in have:
                plan_id = have[name]
                print(f"  {name:28s} ${price:<6.2f} reusing {plan_id}")
            else:
                plan_id = create_plan(tok, product_id, name, price, period)
                print(f"  {name:28s} ${price:<6.2f} created {plan_id}")
            env_lines.append(f"PAYPAL_PLAN_{code.upper()}_{period.upper()}={plan_id}")

    print("\n" + "=" * 64)
    print("Paste these into the Railway BACKEND service variables:\n")
    print(f"PAYPAL_ENV={env}")
    print(f"PAYPAL_CLIENT_ID={settings.paypal_client_id}")
    print("PAYPAL_CLIENT_SECRET=<your secret>")
    for line in env_lines:
        print(line)
    print("\nThen create the webhook (docs/MONETIZATION.md step D) and set")
    print("PAYPAL_WEBHOOK_ID=... — without it, renewals never extend access.")
    print("=" * 64)

    out = Path("paypal_plan_ids.json")
    out.write_text(json.dumps({"product_id": product_id, "env": env,
                               "vars": dict(l.split("=", 1) for l in env_lines)}, indent=2),
                   encoding="utf-8")
    print(f"(also written to backend/{out.name})")


if __name__ == "__main__":
    main()
