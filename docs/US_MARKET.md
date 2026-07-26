# Adding the US market 🇺🇸

Saaed is now **multi-market**. The same engine (features → score → backtested
probability → ML → levels → news) runs per **exchange**, with EGX and US kept fully
separate in the *same* database. This doc explains how it's wired and the steps to
turn the US market on.

## How separation works

- **One process = one market.** The active market is chosen by the `MARKET` env var
  (`EGX` default, or `US`) or the CLI `--market` flag:
  ```bash
  python -m app.cli --market US daily      # or:  MARKET=US python -m app.cli daily
  ```
- **Per-market config** lives in `app/config.py` → `MARKETS` (a `MarketProfile` each):
  exchange code, currency, liquidity floor, extra tickers, news language/region/sources,
  and (for the US virtual exchange) the sub-exchanges to keep (main boards only).
- **Data is namespaced.** Every `Asset` has an `exchange` column and tickers are
  suffixed (`COMI.EGX`, `AAPL.US`). `daily_bars` / `recommendations` follow the ticker.
- **Models & stats are namespaced.** `model_versions`, `backtest_stats` and
  `pipeline_runs` carry an `exchange` column. A US retrain only ever replaces US rows;
  an EGX scan only ever scores with EGX models. Nothing clobbers the other market.
- **The schema self-migrates.** `init_db()` adds the `exchange` columns to an existing
  DB automatically (Postgres in place; the disposable SQLite cache is rebuilt), so no
  manual migration is needed on deploy.

## The website switcher

The nav has a **Markets** dropdown (`EGX ▾` → EGX / US). It's persisted in
`localStorage` and passed to the API as `?market=`. The `/api/picks` endpoint filters
by exchange. Until US data exists, the US tab shows a clean **"US Stocks — coming
soon"** card (no empty tables, no errors).

## Turn US on — checklist

1. **EODHD plan.** Confirm your EODHD token covers **US EOD** (`AAPL.US`, and the
   `exchange-symbol-list/US` endpoint). The All-World / EOD plans do; verify with:
   ```bash
   MARKET=US EODHD_API_TOKEN=... python -m app.cli --market US   # prints a ping line
   ```
2. **GitHub secrets.** The US workflows reuse the *existing* secrets — `EODHD_API_TOKEN`,
   `DATABASE_URL`, `OPENAI_API_TOKEN` / `ANTHROPIC_API_TOKEN`. Nothing new to add.
3. **Bootstrap the US history + models — in resumable chunks.** The full US universe
   is far too big to ingest-and-train in one free-runner job (it runs out of
   memory/time), so use the dedicated **US bootstrap (chunked ingest)** workflow
   (Actions → *US bootstrap (chunked ingest)* → *Run workflow*):
   - Each run ingests the next `batch_size` not-yet-fetched tickers into the
     persistent `sahm-us.db` cache and prints `remaining=N` in its run summary.
   - **Re-run it until the summary shows `remaining=0`.** On that final run it
     automatically retrains the models, runs the first scan, and pushes US results to
     Neon — the US tab then goes live.
   - `batch_size` defaults to 1500; lower it (e.g. 500) if a run gets close to the
     time limit, raise it to finish in fewer runs. It's fully idempotent — a failed or
     interrupted run just resumes from the cache on the next click.

   (The scheduled *Daily US scan* skips cleanly until this bootstrap has built the
   cache, so it won't fail in the meantime.)
4. **Verify.** Open the site → **Markets → US**. The US universe and suggestions should
   appear. Check `pipeline_runs` / `model_versions` in Neon show `exchange = 'US'` rows.
5. **Let it run.** From then on the schedules take over:
   - **Daily US scan** — pre-open (Mon–Fri), light top-up + grade + scan.
   - **US intraday news refresh** — during/after US hours.
   - **US weekly retrain** — Saturday (US closed weekends).

## Tuning the US universe

`MarketProfile("US", ...)` in `app/config.py`:
- `min_avg_value_traded` (default **$5M/day**) — the liquidity floor. Raise it for a
  tighter, more-liquid set (fewer names, faster/cheaper); lower it for broader coverage.
- `symbol_exchanges` — which sub-exchanges to keep (default main boards; drops OTC /
  pink-sheets). Narrow this to shrink the bootstrap further.
- `news_trusted_sources` — the US trusted-publisher whitelist for the news overlay.

## Adding a *third* market later

1. Add a `MarketProfile` to `MARKETS` in `app/config.py`.
2. Add it to the frontend `MARKETS` list in `frontend/src/market.jsx`.
3. Copy the three `us-*.yml` workflows, swapping `MARKET`, the cache key, the
   `LOCAL_DB_URL` filename, and the cron to that market's pre-open time.
