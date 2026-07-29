"""List Lemon Squeezy products/variants and suggest the env vars to set.

Lemon Squeezy doesn't let you create subscription variants over the API, so the six
products are made once in the dashboard. This reads them back, matches them to our
plans by price + billing interval, and prints the LEMON_VARIANT_* lines — so you
don't hand-copy six ids.

    cd backend
    # LEMON_API_KEY and LEMON_STORE come from .env
    python scripts/lemon_list_variants.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import lemonsqueezy as lemon  # noqa: E402
from app.config import settings  # noqa: E402
from app.plans import PERIODS, PLANS  # noqa: E402


def main() -> None:
    if not settings.lemon_api_key:
        sys.exit("Set LEMON_API_KEY in backend/.env first "
                 "(Lemon Squeezy → Settings → API → new key).")
    try:
        variants = lemon.list_variants()
    except lemon.LemonError as e:
        sys.exit(f"Lemon Squeezy API error: {e}")

    if not variants:
        sys.exit("No variants found — create the six subscription products first "
                 "(see docs/MONETIZATION.md).")

    print(f"{len(variants)} variant(s) in the account:\n")
    rows = []
    for v in variants:
        a = v.get("attributes") or {}
        price = (a.get("price") or 0) / 100.0          # cents
        interval = (a.get("interval") or "").lower()   # month | year | None
        rows.append({
            "id": str(v.get("id")),
            "name": a.get("name") or "",
            "price": price,
            "interval": interval,
            "subscription": bool(a.get("is_subscription")),
        })
        print(f"  id={v.get('id'):<10} ${price:<8.2f} interval={interval or '-':<6} "
              f"sub={'yes' if a.get('is_subscription') else 'no ':<4} {a.get('name')}")

    # Match each of our (plan, period) to a variant by price + interval.
    want_interval = {"monthly": "month", "annual": "year"}
    print("\n" + "=" * 64)
    print("Suggested Railway BACKEND variables:\n")
    print("BILLING_PROVIDER=lemonsqueezy")
    print(f"LEMON_STORE={settings.lemon_store or '<your-store-subdomain>'}")
    print("LEMON_API_KEY=<your api key>")
    print("LEMON_WEBHOOK_SECRET=<the signing secret you set on the webhook>")
    missing = []
    for code, plan in PLANS.items():
        for period in PERIODS:
            price = plan[period]
            match = next((r for r in rows
                          if abs(r["price"] - price) < 0.01
                          and r["interval"] == want_interval[period]), None)
            var = f"LEMON_VARIANT_{code.upper()}_{period.upper()}"
            if match:
                print(f"{var}={match['id']}    # {plan['label']} {period} ${price:.2f}")
            else:
                missing.append(f"{var}  (no variant at ${price:.2f}/{want_interval[period]})")
    print("=" * 64)
    if missing:
        print("\n⚠ No variant matched these — create them in the dashboard:")
        for m in missing:
            print("   -", m)
        print("\nPrices must match app/plans.py exactly: "
              + ", ".join(f"{p['label']} ${p['monthly']}/mo ${p['annual']}/yr"
                          for p in PLANS.values()))


if __name__ == "__main__":
    main()
