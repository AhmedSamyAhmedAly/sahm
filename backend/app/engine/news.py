"""Live news + AI-sentiment overlay (runs in the daily job only — never the web API).

EODHD has no per-stock EGX news, so we pull fresh headlines from Google News in
Arabic + English for the shortlisted picks, then read them with Claude Haiku to
produce a sentiment score, a one-line thesis, and catalyst/risk flags.

This is a LIVE signal — it improves timing/decisions and is shown separately from
the backtested Success %. It is not a trained model feature.
"""
from __future__ import annotations

import json
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from app.config import settings

_GN = "https://news.google.com/rss/search"
_UA = {"User-Agent": "Mozilla/5.0 (compatible; SahmBot/1.0)"}

# Arabic + English keyword fallback (used only when no Anthropic token is set).
_POS = {"surge", "beats", "profit", "growth", "upgrade", "wins", "record", "expansion",
        "dividend", "approval", "rises", "gains", "ربح", "ارتفاع", "نمو", "صفقة", "أرباح", "توزيعات"}
_NEG = {"loss", "fraud", "probe", "downgrade", "lawsuit", "decline", "halt", "default",
        "warns", "cuts", "falls", "drops", "خسارة", "هبوط", "تحقيق", "غرامة", "تراجع", "أزمة"}

_SCHEMA = {
    "type": "object",
    "properties": {
        "sentiment": {"type": "number"},  # -1 (very negative) .. 1 (very positive)
        "label": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "thesis": {"type": "string"},
        "catalysts": {"type": "array", "items": {"type": "string"}},
        "risk_flag": {"type": "boolean"},
    },
    "required": ["sentiment", "label", "thesis", "catalysts", "risk_flag"],
    "additionalProperties": False,
}

_INSTRUCTIONS = (
    "You are an equity news analyst for the Egyptian Exchange (EGX). You read "
    "recent headlines (Arabic and English) about one company and judge their likely "
    "short-term (1-2 week) impact on the share price. Be sober and skeptical: ignore "
    "generic market noise, weight concrete events (earnings, deals, regulatory, "
    "dividends, lawsuits). Return sentiment in [-1,1], a label, a ONE-sentence thesis "
    "in English, key catalysts (short phrases), and risk_flag=true if there is a "
    "material negative/uncertainty. If headlines are irrelevant or absent, return "
    "neutral with an empty thesis."
)


def fetch_headlines(name: str | None, ticker: str, limit: int = 8) -> list[dict]:
    """Google News RSS in each configured language. Returns deduped recent items."""
    code = ticker.split(".")[0]
    company = (name or code).strip()
    queries = {
        "en": f'"{company}" (EGX OR Egypt stock OR shares)',
        "ar": f'"{company}" البورصة المصرية',
    }
    seen: set[str] = set()
    items: list[dict] = []
    for lang in settings.news_lang_list:
        q = queries.get(lang, f'"{company}"')
        gl, ceid = ("EG", f"EG:{lang}")
        url = f"{_GN}?q={urllib.parse.quote(q)}&hl={lang}&gl={gl}&ceid={ceid}"
        try:
            resp = requests.get(url, headers=_UA, timeout=15)
            if resp.status_code != 200:
                continue
            root = ET.fromstring(resp.content)
        except Exception:
            continue
        for item in root.iterfind(".//item"):
            title = (item.findtext("title") or "").strip()
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            src = item.find("source")
            items.append({
                "title": title,
                "url": (item.findtext("link") or "").strip(),
                "date": (item.findtext("pubDate") or "").strip(),
                "source": (src.text.strip() if src is not None and src.text else ""),
                "lang": lang,
            })
            if len(items) >= limit:
                break
    return items[:limit]


def _keyword_assess(headlines: list[dict]) -> dict:
    pos = neg = 0
    for h in headlines:
        words = set(h["title"].lower().split())
        pos += len(words & _POS)
        neg += len(words & _NEG)
    total = pos + neg
    score = 0.0 if total == 0 else round((pos - neg) / total, 2)
    label = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
    return {"sentiment": score, "label": label, "thesis": "", "catalysts": [],
            "risk_flag": neg > pos, "engine": "keyword"}


def _payload(name: str | None, headlines: list[dict]) -> str:
    bullets = "\n".join(f"- ({h['lang']}) {h['title']}" for h in headlines)
    return f"Company: {name}\nRecent headlines:\n{bullets}"


def _coerce(data: dict, engine: str) -> dict:
    return {
        "sentiment": float(data.get("sentiment") or 0.0),
        "label": data.get("label") or "neutral",
        "thesis": data.get("thesis") or "",
        "catalysts": data.get("catalysts") or [],
        "risk_flag": bool(data.get("risk_flag")),
        "engine": engine,
    }


def _openai_assess(name: str | None, headlines: list[dict]) -> dict | None:
    try:
        from openai import OpenAI
    except Exception:
        return None
    if not settings.openai_api_token:
        return None
    try:
        client = OpenAI(api_key=settings.openai_api_token)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _INSTRUCTIONS + " Respond ONLY with a JSON object "
                 'with keys: sentiment (number -1..1), label ("positive"|"neutral"|"negative"), '
                 "thesis (string), catalysts (array of strings), risk_flag (boolean)."},
                {"role": "user", "content": _payload(name, headlines)},
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
        )
        text = resp.choices[0].message.content
        return _coerce(json.loads(text), settings.openai_model) if text else None
    except Exception:
        return None


def _anthropic_assess(name: str | None, headlines: list[dict]) -> dict | None:
    try:
        import anthropic
    except Exception:
        return None
    if not settings.anthropic_api_token:
        return None
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_token)
        resp = client.messages.create(
            model=settings.news_model,
            max_tokens=600,
            system=[{"type": "text", "text": _INSTRUCTIONS,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": _payload(name, headlines)}],
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        )
        text = next((b.text for b in resp.content if b.type == "text"), None)
        return _coerce(json.loads(text), settings.news_model) if text else None
    except Exception:
        return None


def assess(name: str | None, headlines: list[dict]) -> dict:
    """Return {sentiment,label,thesis,catalysts,risk_flag,engine}. Never raises.

    Provider order: OpenAI (if key set) -> Anthropic (if key set) -> keyword fallback.
    """
    if not headlines:
        return {"sentiment": 0.0, "label": "neutral", "thesis": "",
                "catalysts": [], "risk_flag": False, "engine": "none"}
    return (_openai_assess(name, headlines)
            or _anthropic_assess(name, headlines)
            or _keyword_assess(headlines))


def analyze(name: str | None, ticker: str) -> dict:
    """Fetch + assess. Returns the assessment plus the headlines used."""
    headlines = fetch_headlines(name, ticker)
    result = assess(name, headlines)
    result["headlines"] = headlines
    return result
