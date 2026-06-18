# Sahm — Business / User Guide

How to read and use the dashboard. Plain language, no code.

> **Important & honest:** Sahm is a *research/decision-support* tool, **not financial advice** and
> **not a guarantee**. The numbers are probabilities learned from history — they tip the odds in your
> favour, they don't remove risk. You review every pick and place every trade yourself (in Thndr).

---

## The big idea

Every trading day, Sahm scans the whole Egyptian Exchange (EGX), scores each liquid stock, and
ranks them by the **probability that the stock rises to a target within a set number of days**. That
probability is **calibrated on 16 years of real EGX history** — so when it says "50%", historically
about half of stocks that looked like this hit the target.

The headline target is **+10% within 10 trading days**. (Other targets — +5%, +15%, +20% — are
tracked on the Track Record page.)

---

## The top cards (KPIs)


| Card                  | Meaning                                                                                                                                                                                |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Stocks scanned**    | How many liquid EGX stocks passed the filters and were analysed today (e.g. 211).                                                                                                      |
| **Strong buys today** | How many stocks earned the highest signal tier today.                                                                                                                                  |
| **Live win rate**     | Of *past* picks whose 10-day window has finished, how many hit target. Shows "—" until picks start maturing (≈2 weeks after launch), then fills in. This is the real-money scoreboard. |
| **Data date**         | The date of the latest price bar used. EGX data is end-of-day, so this is usually the last close.                                                                                      |


---

## The "Today's Buys" table — column by column


| Column        | What it means                                                                                                                                                                  | How to use it                                                                                                                |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| **#**         | Rank — the list is sorted by **Success %** (best opportunity on top).                                                                                                          | Start from the top.                                                                                                          |
| **Stock**     | Ticker (e.g. ROTO) + full company name.                                                                                                                                        | Click any row to open the stock's detail page.                                                                               |
| **Signal**    | A tier badge: **STRONG BUY / BUY / HOLD / SELL / STRONG SELL**. It reflects how much better-than-average the model thinks this stock is (probability vs. the market baseline). | STRONG BUY = clearly above average odds. HOLD = around average. Treat SELL tiers as "avoid / consider exiting", not "short". |
| **Score**     | A 0–100 **technical score** (the green bar) from transparent rules: trend, momentum, volume, breakout, volatility.                                                             | A quick read of *chart strength*. The "why" behind it is on the detail page.                                                 |
| **Success %** | The **calibrated probability** the stock hits its target (e.g. **+10% / 10d**) — with **n=** the number of historical cases the estimate is based on.                          | This is the core number. Higher = better odds. `n` tells you how much evidence backs it (bigger = more trustworthy).         |
| **Entry**     | Suggested entry price (the latest close).                                                                                                                                      | Where you'd buy. If the stock gaps far above this next day, the plan changes — be patient.                                   |
| **Target**    | The price that equals the target gain (Entry +10%).                                                                                                                            | Your take-profit level.                                                                                                      |
| **Stop**      | A volatility-based **stop-loss** (computed from the stock's ATR, ~1.5× its typical daily range below entry).                                                                   | Your "I was wrong, get out" level. **Always set it.** This caps the loss.                                                    |
| **R:R**       | **Risk-to-Reward** ratio = (Target − Entry) ÷ (Entry − Stop).                                                                                                                  | 2.0 means you risk 1 to make 2. Prefer higher R:R; be choosy below ~1.3.                                                     |
| **Hold**      | Expected days to reach target (historical average for this kind of setup).                                                                                                     | Roughly how long to give the trade before the thesis expires.                                                                |


### Filters / sort (top-right of the table)

- **Search** — type a ticker or company name.
- **Signal dropdown** — show only Strong buy / Buy / Hold, etc.
- **Sort** — by **Success %** (default), **Score**, or **Risk/Reward**.

---

## A simple, disciplined way to use it

1. **Shortlist:** look at the top of the list (highest Success %), ideally **Signal = BUY/STRONG BUY**
  and **R:R ≥ 1.5** with a healthy **n**.
2. **Inspect:** click the row → read the **chart** (entry/target/stop drawn on it), the **score
  breakdown**, and the **"why" reasons**. Check the **past calls** to see how this name behaved before.
3. **Plan the trade:** decide your position size so that if the **Stop** hits, the loss is an amount
  you're comfortable with (e.g. risk ≤ 1–2% of your capital per trade).
4. **Execute in Thndr:** buy near **Entry**, set the **Stop**, aim for the **Target**.
5. **Exit rules:** take profit at Target, cut at Stop, and if neither hits by the **Hold** horizon,
  re-evaluate (the edge fades after the window).
6. **Review:** the **Track Record** page shows whether the system is actually working over time.

> Never put everything in one name. Spread across several picks; the probabilities work *on average*,
> not on any single trade.

---

## The Stock Detail page (click any row)

- **Price chart** with your **Entry / Target / Stop** lines drawn on it.
- **Trade plan** card: entry, target, stop, Success %, Risk/Reward.
- **Score breakdown**: how each factor (trend, momentum, volume, breakout, volatility) contributed.
- **Why this pick**: the specific reasons in plain English (e.g. "breaking above 20-day high",
"strong volume surge").
- **Past calls & outcomes**: every previous signal on this stock and whether it hit target — honesty
built in.
- **☆ Watch**: star a stock to follow it (per-user watchlist).

---

## The Track Record page (the trust anchor)

- **Live win rate / avg return**: real results of matured picks.
- **Model accuracy (out-of-sample)**: how the model performed on years of *unseen* history —
**AUC** (skill: 0.5 = none, ~0.6 = a real modest edge), **top-picks hit-rate vs baseline**, and
**Lift** (how many times more often the top picks hit target vs. average).
- **Backtested success rate by score band**: higher score bands should hit targets more often.
- **Cumulative realized return**: an equity-curve view of graded calls.

### What the honest numbers look like (validated on 16y EGX)


| Target         | Top-picks hit-rate | Market baseline | Lift      |
| -------------- | ------------------ | --------------- | --------- |
| +5% / 10d      | ~72%               | 58%             | 1.23×     |
| **+10% / 10d** | ~49%               | 34%             | **1.47×** |
| +15% / 20d     | ~46%               | 36%             | 1.29×     |
| +20% / 20d     | ~33%               | 25%             | 1.30×     |


**Read this honestly:** the model's top picks hit +10% about **1.5× more often than random**. That's
a genuine, usable edge — but ~half still don't hit, which is why **stops and diversification matter**.
No legitimate system predicts the market with "99%" certainty; anyone promising that is misleading you.

---

## Accounts & access

- The site is **invite-only**. New users register with the **invite code**; existing members log in
with email + password.
- Roles: **admin** (you) and **member** (friends). Same dashboard for everyone.

