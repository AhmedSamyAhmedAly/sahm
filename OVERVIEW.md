# Saaed — EGX Stock Signals 📈

**Saaed** (written **Sa📈d** — the green rising chart in the logo) is a private web app for me and
my friends that scans the **Egyptian Exchange (EGX)** every trading day and surfaces the stocks with
the strongest setups — each with an **honest, backtested success rate** and a clear **buy / target /
stop** plan, plus a personal **portfolio** tracker.

🔗 **Live app:** https://sahmfe.vercel.app
🔑 **To join:** open the link → *Register with invite* → invite code **`sahm-invite`** → set a budget.

> ⚠️ **Not financial advice.** Everything in Saaed is an algorithmic *suggestion* that **can be wrong**.
> It tips the odds, it doesn't remove risk. You review and place every trade yourself. Trading can
> lose money.

---

## What it actually does

Every trading morning (before the market opens) Saaed:
1. Pulls the latest end-of-day prices for the whole EGX from a market-data provider.
2. Scores every liquid stock 0–100 from transparent technical rules (trend, momentum, volume, breakout).
3. Runs a machine-learning model (trained on **16 years** of EGX history) to estimate the **probability**
   each stock hits a target (e.g. **+10% within 10 days**).
4. Adds **entry / target / stop** levels and a fresh **AI news read** (Arabic + English headlines →
   sentiment + a one-line thesis + ⚡catalyst flags) for the top picks.
5. Publishes the ranked list to the website.

### The honest part
The "**Success %**" is a *real, measured* number — out-of-sample on years of unseen history, the
model's top picks hit +10% in 10 days about **49% of the time vs. ~34% for the market** (≈**1.5× better
than random**). That's a genuine edge — **not** a "99% guaranteed" promise (anyone claiming that is
lying). About half still miss, which is exactly why stops and diversification matter.

---

## The pages

- **Suggestions** (home) — the daily curated **buy** ideas, ranked by Success %. Pick your target
  (+5% / +10% / +15% / +20% over 10–20 days), search, sort, and tap any stock for details.
- **All Stocks** — a simple searchable list of the whole EGX universe.
- **Portfolio** — add the stocks you own (or import a CSV); it shows live **P/L**, **earnings**
  (realized + unrealized) with a performance chart, **sell** with price + units (partial sells track
  your average sell price), **average-in** when you buy more of something you hold, a **budget**, and a
  **suggested allocation** that splits your budget across the best signals.
- **Stock detail** — price chart, score breakdown, the "why", AI news, and the stock's **past calls &
  outcomes**.
- **Track Record** (admins) — the proof page: live win-rate, model accuracy (AUC, lift), and
  backtested hit-rate by score band.
- **Admin** (admins) — manage members (roles, suspend, reset), read **Contact** messages.

---

## Good to know
- **Data is end-of-day** (the Egyptian Exchange has no live/intraday feed from our provider), which
  suits the **swing-trading** horizon (days to ~2 weeks) — scan after close, act near the next open.
- It refreshes **once per trading day** (Sun–Thu, early morning Cairo time).
- Built for a small group; access is invite-only.

---

## Under the hood (for the curious)
- **Frontend:** React + Vite. **API:** FastAPI (Python). **Database:** Postgres (Neon).
- **Hosting:** Vercel (frontend + serverless API), all on free tiers.
- **Engine:** pandas + scikit-learn (gradient-boosted trees, probability-calibrated, no look-ahead
  leakage). **News AI:** OpenAI on the daily job only.
- **Automation:** a nightly GitHub Action runs the full scan and publishes results.

---

*Made with ❤️ for EGX traders. Questions? Use the in-app **Contact** page.*
