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


def signal_for(score: float) -> str:
    if score >= 80:
        return "strong_buy"
    if score >= 65:
        return "buy"
    if score >= 45:
        return "hold"
    if score >= 30:
        return "sell"
    return "strong_sell"


def score_band(score: float) -> str:
    """Bucket a 0-100 score into a 10-wide band label, e.g. '80-90'."""
    lo = int(min(90, max(0, score // 10 * 10)))
    return f"{lo}-{lo + 10}"
