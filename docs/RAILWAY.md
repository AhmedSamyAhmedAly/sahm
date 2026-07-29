# Deploying Saeed on Railway 🚂

Everything (database + API + website) runs in one Railway project. Expect
**~$10–12/month** on the **Hobby** plan (the Free plan's $1/month credit can't keep an
always-on app running).

The repo is already configured: each service has a `Dockerfile` + `railway.json`, so
Railway only needs to know which folder each service lives in.

---

## 1. Create the project + database

1. [railway.app](https://railway.app) → **New Project** → **Provision PostgreSQL**.
2. Open the Postgres service → **Variables**. You need two URLs:
   - `DATABASE_URL` — internal (`*.railway.internal`). **Fast, free egress — use this
     for the backend service.**
   - `DATABASE_PUBLIC_URL` — public proxy. **GitHub Actions and your laptop must use
     this one**; the internal host is unreachable from outside Railway.

## 2. Backend service (API)

**New** → **GitHub Repo** → this repo → then in **Settings**:

| Setting | Value |
|---|---|
| Root Directory | `backend` |
| Builder | Dockerfile (auto-detected via `railway.json`) |

**Variables:**
```
DATABASE_URL=${{Postgres.DATABASE_URL}}     # reference — keeps it internal
JWT_SECRET=<a long random string>
EODHD_API_TOKEN=<your token>
ADMIN_EMAIL=<your email>                    # this account is the admin
INVITE_CODE=saeed-invite
CORS_ORIGINS=https://<your-frontend-domain>
OPENAI_API_TOKEN=       # optional
ANTHROPIC_API_TOKEN=    # optional
```
Then **Settings → Networking → Generate Domain** and note the API URL.

> The app normalizes `postgres://` / `postgresql://` to the psycopg-3 driver
> automatically (`normalize_db_url`), so Railway's connection string works as-is.
> The schema is created on startup — no migration step.

## 3. Frontend service (website)

**New** → **GitHub Repo** → same repo → **Settings**:

| Setting | Value |
|---|---|
| Root Directory | `frontend` |

**Variables:**
```
VITE_API_URL=https://<your-backend-domain>
```
⚠️ Vite inlines this at **build** time — after changing it you must **redeploy**, not
just restart. Then **Generate Domain**, and put that domain into the backend's
`CORS_ORIGINS` (step 2) so the browser is allowed to call the API.

## 4. Load the data

From your machine (uses the local caches — nothing is re-downloaded):

```bash
cd backend
NEW_DATABASE_URL="<DATABASE_PUBLIC_URL>" \
OLD_DATABASE_URL="<old Neon URL>" \
LOCAL_DB_URL="sqlite:///./sahm-us.db" MARKET=US \
    python scripts/migrate_to_new_db.py
```

It creates the schema, copies users/assets/models/EGX picks from the old database,
then loads the US market from the local cache — trimming charts to ~1 year for
tradeable stocks (`CHART_DAYS`) and ~45 days for the rest, tradeable names first.
Re-running tops up rather than duplicating.

## 5. Point the scheduled jobs at Railway

In the GitHub repo → **Settings → Secrets and variables → Actions**, set
`DATABASE_URL` to the **`DATABASE_PUBLIC_URL`** (not the internal one), and make sure
`EODHD_API_TOKEN` and the LLM keys are present. The workflows are unchanged.

## 6. Verify

- `https://<backend>/api/health` → `{"status":"ok","service":"saeed"}`
- `https://<backend>/api/status` → shows the latest scan date and universe size
- Open the site, log in, switch **Markets → US** — suggestions should appear.

---

## Keeping the bill down

- **RAM is the cost** ($10/GB/month); disk is cheap ($0.15/GB/month), so a big price
  history is nearly free — the storage wall that forced this move is gone.
- The frontend is served by **nginx** (~10 MB RAM) rather than a Node server (~100 MB).
- The heavy work (backtest, training) runs on **GitHub Actions**, never on Railway.
- Watch the project's **Usage** tab for the first week to confirm the real number.
