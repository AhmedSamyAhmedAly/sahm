"""Trade levels: entry, target (chosen +X%), ATR-based stop, and risk/reward."""
from __future__ import annotations

from app.config import settings


def trade_levels(entry: float, atr: float | None, target_pct: float) -> dict:
    """Compute target/stop for an entry price.

    Target is a fixed +target_pct move. Stop is ATR-based (falls back to a fixed
    percentage if ATR is unavailable) so it adapts to each name's volatility.
    """
    target = entry * (1.0 + target_pct)
    if atr and atr > 0:
        stop = entry - settings.atr_stop_mult * atr
    else:
        stop = entry * (1.0 - target_pct / 2.0)  # fallback: half the target as risk
    stop = max(stop, 0.01)

    risk = entry - stop
    reward = target - entry
    rr = round(reward / risk, 2) if risk > 0 else None
    return {
        "entry_price": round(entry, 4),
        "target_price": round(target, 4),
        "stop_loss": round(stop, 4),
        "risk_reward": rr,
        "stop_pct": round((stop / entry - 1.0) * 100.0, 2),
    }
