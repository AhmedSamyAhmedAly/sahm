"""Transparent rule-based scoring: feature vector -> 0-100 score + signal + reasons.

Every point added/removed is tied to a named, human-readable reason so each pick
is fully explainable on the dashboard ("why").
"""
from __future__ import annotations


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def score_features(f: dict) -> dict:
    """Return {score, signal, reasons, components}."""
    reasons: list[str] = []
    components: dict[str, float] = {}

    # --- Trend (above moving averages, golden cross) ---
    trend = 50.0
    for key, label in (("price_vs_sma20", "20-day"), ("price_vs_sma50", "50-day"),
                       ("price_vs_sma200", "200-day")):
        v = f.get(key)
        if v is None:
            continue
        trend += 7 if v > 0 else -7
    if f.get("golden_cross"):
        trend += 8
        reasons.append("Uptrend: 50-day average above 200-day")
    if (f.get("price_vs_sma50") or 0) > 0 and (f.get("price_vs_sma200") or 0) > 0:
        reasons.append("Price above its 50- and 200-day averages")
    components["trend"] = _clamp(trend)

    # --- Momentum (RSI, MACD, rate of change) ---
    mom = 50.0
    rsi = f.get("rsi14")
    if rsi is not None:
        if 55 <= rsi <= 70:
            mom += 12
            reasons.append(f"Healthy momentum (RSI {rsi:.0f})")
        elif 70 < rsi <= 80:
            mom += 4  # strong but getting hot
        elif rsi > 80:
            mom -= 6
            reasons.append(f"Overbought (RSI {rsi:.0f}) — higher pullback risk")
        elif rsi < 40:
            mom -= 8
    mh = f.get("macd_hist")
    if mh is not None:
        mom += 8 if mh > 0 else -8
        if mh > 0:
            reasons.append("MACD positive (momentum building)")
    roc = f.get("roc20")
    if roc is not None:
        mom += max(-10, min(10, roc / 2))
    components["momentum"] = _clamp(mom)

    # --- Volume confirmation ---
    volsc = 50.0
    vr = f.get("vol_ratio")
    if vr is not None:
        if vr >= 2.0:
            volsc += 16
            reasons.append(f"Strong volume surge ({vr:.1f}x average)")
        elif vr >= 1.3:
            volsc += 8
            reasons.append(f"Above-average volume ({vr:.1f}x)")
        elif vr < 0.6:
            volsc -= 8
    components["volume"] = _clamp(volsc)

    # --- Breakout / position ---
    brk = 50.0
    if f.get("breakout20"):
        brk += 18
        reasons.append("Breaking above its 20-day high")
    dist = f.get("dist_from_high20")
    if dist is not None and -3 <= dist < 0:
        brk += 8
        reasons.append("Coiling just below resistance")
    pos = f.get("pos_52w")
    if pos is not None and pos >= 80:
        brk += 6
        reasons.append("Trading near its 52-week high")
    components["breakout"] = _clamp(brk)

    # --- Volatility sanity (avoid dead or insane names) ---
    volat = 50.0
    atr_pct = f.get("atr_pct")
    if atr_pct is not None:
        if atr_pct < 1.0:
            volat -= 6  # too quiet to move
        elif atr_pct > 9.0:
            volat -= 6  # too wild
            reasons.append("Very high volatility — size positions carefully")
        else:
            volat += 4
    components["volatility"] = _clamp(volat)

    # Weighted blend.
    weights = {"trend": 0.28, "momentum": 0.27, "volume": 0.15,
               "breakout": 0.22, "volatility": 0.08}
    score = sum(components[k] * w for k, w in weights.items())
    score = round(_clamp(score), 1)

    return {
        "score": score,
        "signal": signal_for(score),
        "reasons": reasons[:6],
        "components": {k: round(v, 1) for k, v in components.items()},
    }


# Ordered worst -> best, so a tier can be nudged up/down by index.
SIGNAL_ORDER = [
    "super_strong_sell", "strong_sell", "sell", "hold", "buy",
    "strong_buy", "super_strong_buy",
]


def _shift(signal: str, by: int) -> str:
    """Move a signal up (+) or down (-) the tier ladder, clamped to the ends."""
    try:
        i = SIGNAL_ORDER.index(signal)
    except ValueError:
        return signal
    return SIGNAL_ORDER[max(0, min(len(SIGNAL_ORDER) - 1, i + by))]


def signal_for(score: float) -> str:
    """Pure rule-score tier (used when no ML model is trained yet)."""
    if score >= 88:
        return "super_strong_buy"
    if score >= 78:
        return "strong_buy"
    if score >= 63:
        return "buy"
    if score >= 45:
        return "hold"
    if score >= 30:
        return "sell"
    if score >= 18:
        return "strong_sell"
    return "super_strong_sell"


def ml_signal(prob: float, base_rate: float | None) -> str:
    """Plain ML tier from prob-vs-baseline ratio (no confluence). Kept for callers
    that only have a probability; the scan uses `decide_signal` for the real gating."""
    base = base_rate or 0.33
    ratio = prob / base if base > 0 else 1.0
    if ratio >= 1.5:
        return "strong_buy"
    if ratio >= 1.15:
        return "buy"
    if ratio >= 0.9:
        return "hold"
    if ratio >= 0.6:
        return "sell"
    return "strong_sell"


def decide_signal(
    prob: float | None,
    base_rate: float | None,
    score: float,
    feats: dict,
) -> tuple[str, list[str]]:
    """The real signal decision: ML conviction + rule-score + confluence + market
    regime. Returns (signal, extra_reasons). Upgrades to SUPER only when several
    independent confirmations agree, and demotes buys in a down market.
    """
    from app.config import settings

    reasons: list[str] = []
    if prob is None:
        return signal_for(score), reasons

    base = base_rate or 0.33
    ratio = prob / base if base > 0 else 1.0

    # Base tier from the model's edge over the market base-rate.
    if ratio >= settings.strong_ratio_min:
        sig = "strong_buy"
    elif ratio >= settings.buy_ratio_min:
        sig = "buy"
    elif ratio >= settings.hold_ratio_min:
        sig = "hold"
    elif ratio >= settings.sell_ratio_min:
        sig = "sell"
    else:
        sig = "strong_sell"

    rsi = feats.get("rsi14")
    vol_ratio = feats.get("vol_ratio")
    regime = feats.get("mkt_above_sma50")          # 1.0 / 0.0 / None
    breadth = feats.get("mkt_breadth")
    rel = feats.get("rel_strength")

    overbought = rsi is not None and rsi > settings.overbought_rsi
    vol_ok = vol_ratio is None or vol_ratio >= settings.super_vol_min
    regime_up = regime is None or regime >= 0.5    # unknown -> don't block
    regime_down = regime is not None and regime < 0.5

    # --- upgrade to SUPER STRONG BUY on confluence ---
    if (sig == "strong_buy" and ratio >= settings.super_ratio_min
            and score >= settings.super_score_min and vol_ok and not overbought
            and regime_up and (rel is None or rel >= 0)):
        sig = "super_strong_buy"
        reasons.append("High conviction: model, trend, volume and market all aligned")

    # --- upgrade to SUPER STRONG SELL (symmetric) ---
    if (sig == "strong_sell" and ratio <= settings.super_sell_ratio_max
            and score <= settings.super_sell_score_max
            and (regime_down or (rel is not None and rel < 0))):
        sig = "super_strong_sell"
        reasons.append("Strong avoid: weak model odds, broken trend, soft market")

    # --- market-regime demotion: don't issue top buys into a falling market ---
    if settings.market_regime_gate and regime_down and sig in ("super_strong_buy", "strong_buy"):
        sig = _shift(sig, -1)
        reasons.append("Market below its 50-day average — buy conviction lowered")

    # --- overbought caution on any remaining buy ---
    if overbought and sig in ("super_strong_buy", "strong_buy"):
        sig = _shift(sig, -1)
        reasons.append(f"Overbought (RSI {rsi:.0f}) — buy conviction lowered")

    if sig in ("super_strong_buy", "strong_buy") and breadth is not None and breadth >= 60:
        reasons.append(f"Broad market participation ({breadth:.0f}% above 50-day)")

    return sig, reasons


def news_demote(signal: str, news_label: str | None, risk_flag: bool) -> tuple[str, str | None]:
    """Lower a buy when trusted news is clearly negative / risk-flagged.
    Returns (signal, reason_or_None). Never upgrades on positive news (the model,
    not headlines, owns the upside; news only protects against walking into trouble).
    """
    if signal not in ("super_strong_buy", "strong_buy", "buy"):
        return signal, None
    if news_label == "negative" and risk_flag:
        return _shift(signal, -2), "Negative news + risk flag — buy downgraded"
    if news_label == "negative" or risk_flag:
        return _shift(signal, -1), "Cautious on negative news — buy downgraded"
    return signal, None


def score_band(score: float) -> str:
    """Bucket a 0-100 score into a 10-wide band label, e.g. '80-90'."""
    lo = int(min(90, max(0, score // 10 * 10)))
    return f"{lo}-{lo + 10}"
