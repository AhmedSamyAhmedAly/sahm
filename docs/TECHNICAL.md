# Sahm — Technical Documentation

Architecture, data model, the prediction engine + ML, the API, and how it's deployed.

---

## 1. Stack overview

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + Vite, React Router, Recharts. Static SPA on **Vercel**. |
| **API** | FastAPI (ASGI) on **Vercel Python serverless** (`@vercel/python`). |
| **Engine / jobs** | Python (pandas, NumPy, scikit-learn) — runs in the CLI + **GitHub Actions**, not in the API. |
| **Database** | **Neon** (managed Postgres) in prod; SQLite locally. SQLAlchemy 2.0 ORM. |
| **Auth** | JWT (PyJWT) + bcrypt password hashing, invite-code registration. |
| **Data source** | **EODHD** financial API (EGX prices + fundamentals). |
| **CI / scheduler** | GitHub Actions (daily scan). |

### Why this shape
The **web API is read-mostly and lightweight** — it only serves rows already computed and stored in
Postgres, so it needs *none* of the heavy ML libraries. That's why dependencies are split
(`requirements.txt` = API; `requirements-engine.txt` = pandas/scikit-learn for the engine), keeping
the serverless bundle small and fast. All the heavy lifting (ingest, backtest, train, scan) happens
in a scheduled job that writes results to the DB.

---

## 2. Architecture & data flow

```
                 ┌──────────────────────── GitHub Actions (daily, Sun–Thu) ───────────────────────┐
                 │  python -m app.cli daily                                                        │
   EODHD API ───▶│  ingest → grade outcomes → backtest → train ML → scan → write Recommendations   │──▶ Neon Postgres
                 └────────────────────────────────────────────────────────────────────────────────┘            ▲
                                                                                                                 │ read
   Browser ──▶ Vercel (React SPA, sahmfe.vercel.app) ──HTTPS /api──▶ Vercel (FastAPI serverless, sahm-eta.vercel.app)
```

- The **scan** is precomputed; the browser just fetches ranked rows → instant, cheap, scalable.
- The frontend talks to the API via `VITE_API_URL`; the API allows the site origin via `CORS_ORIGINS`.

---

## 3. Repository layout

```
sahm/
  backend/
    app/
      main.py            FastAPI app (lifespan init, CORS, routers, /health, /status)
      config.py          pydantic-settings (env-driven)
      database.py        SQLAlchemy engine/session (SQLite⇄Postgres)
      models.py          ORM tables
      schemas.py         Pydantic request/response models
      auth.py            bcrypt hashing + JWT encode/decode
      deps.py            get_current_user / require_admin
      routers/           auth, picks, stocks, track_record
      engine/
        indicators.py    technical features (no look-ahead)
        signals.py       rule-based 0–100 score + signal tiers
        levels.py        ATR entry/target/stop + risk:reward
        backtest.py      walk-forward hit-rates per score band
        ml.py            calibrated ML models (the accuracy layer)
        pipeline.py      run_scan + grade_due
      eodhd/             client.py + ingest.py
      cli.py             initdb|seed|ingest|backtest|train|scan|grade|daily|demo|create-user
      seed.py            synthetic data (token-free dev)
      scripts/           spike_eodhd.py, transfer_local_to_neon.py
      api/index.py       Vercel serverless entry (exposes ASGI `app`)
      vercel.json        Vercel Python build/route config
      requirements.txt / requirements-engine.txt
      Dockerfile         (alt. container deploy)
  frontend/              React + Vite SPA (Login, Dashboard, StockDetail, TrackRecord)
  .github/workflows/daily-scan.yml
  render.yaml            (optional Render blueprint)
  docs/                  this guide + the business guide
```

---

## 4. Data model (SQLAlchemy → Postgres/SQLite)

| Table | Purpose / key fields |
|-------|----------------------|
| **users** | id, email (unique), hashed_password (bcrypt), role (`admin`/`member`). |
| **watchlist_items** | per-user starred tickers (user_id, ticker). |
| **assets** | one row per security: ticker (`COMI.EGX`), name, sector, asset_type, `is_active` (passed liquidity filters), `is_listed`. |
| **daily_bars** | adjusted OHLCV per ticker/date (unique ticker+date). |
| **recommendations** | one scan result: date, ticker, signal, score, **success_prob**, success_n, target_pct, horizon_days, entry/target/stop, expected_hold_days, reasons (JSON), features (JSON snapshot). |
| **outcomes** | graded result once horizon elapsed: hit_target, return_pct, max_gain, max_drawdown, days_to_target. |
| **backtest_stats** | hit-rate per (score_band, target_pct, horizon) from the walk-forward backtest. |
| **model_versions** | trained ML model per band: algo, **metrics** (auc, precision, lift…), `artifact` (joblib-pickled calibrated pipeline), is_production. |
| **pipeline_runs** | audit log of each scan (universe size, active count, ranked count, data date). |

Portable column types only, so the same models run on SQLite and Postgres.

---

## 5. The prediction engine

### 5.1 Features — `engine/indicators.py`
From daily OHLCV (pandas), per bar: SMA 20/50/200, EMA20, RSI(14), MACD + histogram, ATR(14),
ROC(10/20), volume vs 20-day avg, 20-day & 52-week highs/lows, distance from 20-day high, 52-week
position, breakout flag, golden-cross flag. Derived **cross-sectional** features (percent distances,
ratios) so they're comparable across stocks of any price level.

**No look-ahead:** every feature at bar *t* uses only data up to *t*. The exact same function feeds
both the live scan and the historical backtest/training — so there's no train/serve skew.
`MIN_BARS = 210` ensures enough history (200-day SMA) before a stock is scored.

### 5.2 Rule score — `engine/signals.py`
A transparent 0–100 **Opportunity Score** blended from five components (trend 0.28, momentum 0.27,
breakout 0.22, volume 0.15, volatility 0.08). Each rule appends a human-readable **reason**. Used for
the displayed Score + the "why", and as a fallback signal when no ML model exists.

### 5.3 Trade levels — `engine/levels.py`
- **Entry** = latest close.
- **Target** = entry × (1 + target_pct) (default +10%).
- **Stop** = entry − `atr_stop_mult`×ATR (default 1.5×ATR), so it adapts to each stock's volatility.
- **Risk:Reward** = (target − entry)/(entry − stop).

### 5.4 Backtester (honest baseline) — `engine/backtest.py`
For every historical bar, replays the score and looks **forward** over the horizon: did the high reach
the target before the window closed? Aggregated per **score band × target** into a hit-rate
(`backtest_stats`). Because the scoring rules are **fixed** (not fit to the data), this is an honest
historical frequency, not a curve-fit.

### 5.5 ML accuracy layer — `engine/ml.py`  ★ the main accuracy upgrade
Trains a model per target band on the full EGX history.

- **Dataset:** one row per (ticker, day) of the cross-sectional features; label = "did the forward
  max-high reach the target within the horizon?" (built once, labels derived per band).
- **Models:** `HistGradientBoostingClassifier` vs `LogisticRegression` (imputer+scaler pipeline);
  the higher **out-of-sample AUC** wins.
- **Validation (no leakage):** the data is sorted by time and split **train (older 75%) / test
  (newer 25%) with a purge gap of `horizon` days** between them, so test labels can't peek into the
  training window. Reported metrics (AUC, top-decile precision, base rate, lift) are genuine
  out-of-sample.
- **Calibration:** the production model is `CalibratedClassifierCV(method="isotonic",
  cv=TimeSeriesSplit(5))` fit on all data — so a "50%" output really means ~50% historical frequency.
- **Storage:** the pickled pipeline + metrics are stored in `model_versions` (one production model per
  band). `ModelBundle` loads them for inference.

### 5.6 Daily pipeline — `engine/pipeline.py`
`run_scan`: for each active asset → latest features → rule score → **calibrated ML probability** for
the primary band → trade levels → store a `Recommendation`. The **signal tier** is derived from the
probability vs the band's base rate (`ml_signal`), and rows are **ranked by `success_prob`**.
`grade_due`: once a pick's horizon elapses, compute the realized `Outcome` (hit/return/drawdown).

### 5.7 Honest accuracy (validated, 16y EGX)
| Band | AUC | Top-decile hit | Base rate | Lift |
|------|-----|----------------|-----------|------|
| +5% / 10d | 0.60 | 71.6% | 58.3% | 1.23× |
| **+10% / 10d** | 0.62 | 49.4% | 33.6% | **1.47×** |
| +15% / 20d | 0.59 | 46.1% | 35.6% | 1.29× |
| +20% / 20d | 0.58 | 32.6% | 25.2% | 1.30× |

AUC ~0.6 and ~1.3–1.5× lift is the realistic ceiling for real equity prediction. The edge is real but
modest; it is surfaced honestly rather than inflated.

---

## 6. API

Base path `/api`. Auth via `Authorization: Bearer <jwt>` (no cookies).

| Method & path | Auth | Purpose |
|---------------|------|---------|
| `GET /api/health` | – | liveness |
| `GET /api/status` | – | data freshness, counts, token-configured flag |
| `POST /api/auth/register` | invite code | create account (first user → admin) |
| `POST /api/auth/login` | – | email+password → JWT |
| `GET /api/auth/me` | JWT | identity + refreshed token |
| `GET /api/picks` | JWT | ranked recommendations (filters: signal, sector, min_score) |
| `GET /api/stocks/{ticker}` | JWT | detail: bars, latest pick, score breakdown, past calls |
| `POST/DELETE /api/watchlist/{ticker}` | JWT | star/unstar |
| `GET /api/track-record` | JWT | live win-rate, backtest table, model metrics, equity curve |

**Auth:** `auth.py` (bcrypt + PyJWT, HS256, 7-day expiry), `deps.py` (`get_current_user`,
`require_admin`). Registration is gated by `INVITE_CODE`; the very first registrant becomes admin.

---

## 7. Operations

### CLI (`python -m app.cli …`)
`initdb · seed · ingest · backtest · train · scan · grade · daily · demo · create-user EMAIL PW [role]`
- `daily` = ingest → grade → backtest → train → scan (the cloud job).
- `demo` = synthetic seed → backtest → train → scan (no token needed).

### Daily automation
`.github/workflows/daily-scan.yml` runs `app.cli daily` at 06:30 UTC Sun–Thu (before the 10:00 Cairo
open). Needs repo secrets `DATABASE_URL` and `EODHD_API_TOKEN`. Installs `requirements-engine.txt`.

### Config (env vars)
`EODHD_API_TOKEN`, `DATABASE_URL` (use `postgresql+psycopg://…` for Neon), `JWT_SECRET`,
`INVITE_CODE`, `CORS_ORIGINS`. Engine knobs: target bands, horizons, ATR multiplier, liquidity
thresholds (see `config.py`).

---

## 8. Deployment (current)

- **DB:** Neon Postgres. Tables via `initdb`; data bulk-loaded with
  `scripts/transfer_local_to_neon.py` (and refreshed daily by the Action).
- **API:** Vercel project, root `backend/`, `vercel.json` → `api/index.py` (ASGI). Env:
  `DATABASE_URL`, `JWT_SECRET`, `INVITE_CODE`, `CORS_ORIGINS`. Live: `sahm-eta.vercel.app`.
- **Frontend:** Vercel project, root `frontend/`, `VITE_API_URL` → API. Live: `sahmfe.vercel.app`.
- **Repo:** github.com/AhmedSamyAhmedAly/sahm (public; secrets only in service env, never committed).

---

## 9. Roadmap to push accuracy further (honestly)
- Add **fundamentals** (already available on the EODHD plan) and **relative strength vs EGX30** as
  features.
- **Monthly retrain** on accumulating graded outcomes; promote a new model only if it beats production
  on out-of-sample AUC.
- Sector/liquidity-aware thresholds; an LLM news-sentiment feature on the shortlist.
- A change-password flow + email-based onboarding.
