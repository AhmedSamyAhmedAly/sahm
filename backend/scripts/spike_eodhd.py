"""Spike: verify the EODHD token + EGX coverage/history depth.

Run once the real token is set:
    python scripts/spike_eodhd.py

Prints the EGX symbol count and the available history range for a few liquid
names. Confirms whether the data is deep enough (5+ years) for backtesting.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.eodhd.client import EODHDClient  # noqa: E402

PROBE = ["COMI.EGX", "HRHO.EGX", "SWDY.EGX", "TMGH.EGX", "ABUK.EGX"]


def main():
    print(f"Token configured: {bool(settings.eodhd_api_token)}  exchange={settings.egx_exchange}")
    client = EODHDClient()
    ping = client.ping()
    print("Ping:", ping)
    if not ping["ok"]:
        print("\n>>> Token/plan problem. Get a valid token covering EGX from eodhd.com.")
        sys.exit(1)

    syms = client.symbol_list()
    print(f"\nEGX symbols returned: {len(syms)}")
    print("Sample:", [s.get("Code") for s in syms[:10]])

    print("\nHistory depth per probe ticker:")
    for t in PROBE:
        try:
            bars = client.eod(t)
            if bars:
                print(f"  {t:12s} {len(bars):5d} bars  {bars[0]['date']} -> {bars[-1]['date']}")
            else:
                print(f"  {t:12s} no bars")
        except Exception as e:  # noqa: BLE001
            print(f"  {t:12s} ERROR {e}")

    print("\nGo/no-go: need ~1250+ bars (5y) for trustworthy backtests.")


if __name__ == "__main__":
    main()
