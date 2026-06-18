# سهم Sahm — EGX Stock Signals

A shared web dashboard that scans the **Egyptian Exchange (EGX)** every trading day and ranks the
stocks with the strongest setups — each shown with an **honest, backtested success rate** and a clear
**buy / target / stop** plan. Built for a small group (invite-only login).

> **Not financial advice.** Sahm produces transparent, algorithmic *estimates*. The "Success %" is a
> historical, backtested hit-rate — **not a guarantee**. Trading carries risk of loss. You review and
> execute every trade yourself.

---

## What it does

1. **Ingests** EGX symbols + full daily price history from [EODHD](https://eodhd.com).
2. **Scores** every liquid stock 0–100 from transparent technical rules (trend, momentum, volume,
   breakout, volatility) — every point tied to a human-readable reason.
3. **Backtests** the rules over years of history to get the honest probability:
   *"stocks in this score band hit +10% within 10 days 62% of the time (n=340)."*
4. **Recommends** with ATR-based entry / target / stop and expected hold time.
5. **Grades** past calls as their horizons elapse → a live track record.
6. **Serves** it all through a login-protected dashboard.

## Architecture

```
backend/   FastAPI + SQLAlchemy + pandas (engine, backtester, API, auth)
frontend/  React + Vite (Dashboard, Stock detail, Track record, Login)
```
- **DB:** SQLite locally, **Neon Postgres** in production (same code, portable types).
- **Deploy:** API on **Render**, site on **Vercel**, daily scan on **GitHub Actions**.

---

## Run locally (no EODHD token needed — uses synthetic data)

```bash
# backend
cd backend
python -m venv .venv && . .venv/Scripts/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-engine.txt                 # full deps (API + ML engine)
python -m app.cli demo                                 # seed -> backtest -> scan
uvicorn app.main:app --reload --port 8077

# frontend (new terminal)
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```
Open http://localhost:5173, click **Register with invite** (default code `sahm-invite`), and the
first account becomes admin.

### With real EGX data
Set `EODHD_API_TOKEN` (and optionally `DATABASE_URL`) in `backend/.env`, then:
```bash
python scripts/spike_eodhd.py     # verify token + history depth
python -m app.cli daily           # ingest -> grade -> backtest -> scan
```

---

## Deploy (public link for friends) — all free, no card

Two Vercel projects (frontend + API) + Neon. (A `render.yaml` is also included if you
prefer Render for the API.)

1. **GitHub** — push this repo (public). Secrets stay out (only `.env.example`).
2. **Neon** — create a free Postgres project; connection string as
   `postgresql+psycopg://USER:PASS@HOST/DB?sslmode=require`.
3. **API on Vercel** — New Project ➜ **root `backend/`** (uses `backend/vercel.json`, serverless
   Python). Env vars: `DATABASE_URL`, `JWT_SECRET`, `INVITE_CODE`, `CORS_ORIGINS`. Note the API URL.
4. **Frontend on Vercel** — New Project ➜ **root `frontend/`** ➜ set `VITE_API_URL` to the API URL.
   **This Vercel URL is the public link.** Then set the API project's `CORS_ORIGINS` to this URL.
5. **GitHub Actions** — add repo secrets `DATABASE_URL` + `EODHD_API_TOKEN`; the daily scan
   (`.github/workflows/daily-scan.yml`) refreshes picks automatically (Sun–Thu).

One-time DB init / first data load (locally pointing at Neon, or via the Action):
```bash
DATABASE_URL=<neon-url> EODHD_API_TOKEN=<token> python -m app.cli daily
```

---

## CLI reference
```
python -m app.cli initdb     # create tables
python -m app.cli seed       # synthetic data (no token)
python -m app.cli ingest     # real EGX data (needs token)
python -m app.cli backtest   # compute Success %
python -m app.cli scan       # produce today's recommendations
python -m app.cli grade      # grade matured past calls
python -m app.cli daily      # ingest -> grade -> backtest -> scan (cloud job)
python -m app.cli demo       # seed -> backtest -> scan (local demo)
```

## Configuration (env)
| Var | Purpose |
|-----|---------|
| `EODHD_API_TOKEN` | EODHD API token (plan must cover EGX) |
| `DATABASE_URL` | SQLite (default) or Neon Postgres |
| `JWT_SECRET` | sign login tokens (random in prod) |
| `INVITE_CODE` | code friends use to register |
| `CORS_ORIGINS` | comma-separated allowed site origins |
