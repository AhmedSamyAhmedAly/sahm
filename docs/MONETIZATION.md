# Monetization — subscriptions (PayPal) + ads 💳

Two revenue paths, both switched on with environment variables on the backend
service. Nothing here needs a code change.

---

# 1. Subscriptions with PayPal

## The plans

| Plan | Markets | Monthly | Annual |
|---|---|---|---|
| **EGX** | Egyptian Exchange | **$5** | **$40** |
| **US** | US stocks | **$7** | **$60** |
| **EGX + US** | both | **$10** | **$90** |

Prices live in `backend/app/plans.py` — change them there and both the UI and the
API follow. (The PayPal plans must be recreated if you change a price; PayPal
plan amounts are immutable once created.)

## Step A — get API credentials

1. Sign in at [developer.paypal.com](https://developer.paypal.com/dashboard/) with your PayPal **business** account
   (a personal account can't take subscriptions — upgrade is free).
2. **Apps & Credentials** → choose **Sandbox** first → **Create App** → name it `Saeed`.
3. Copy the **Client ID** and **Secret**.

> Do all of Steps A–D in **Sandbox** first. When it works end to end, repeat in
> **Live** and swap the four values.

## Step B — create the six billing plans

PayPal needs a *Product* and then one *Plan* per (package × period).

**Easiest route — the dashboard:** **Pay & Get Paid → Subscriptions → Create plan**.
Create a product `Saeed signals`, then six plans:

| Plan name | Price | Cycle |
|---|---|---|
| Saeed EGX Monthly | $5 | every 1 month |
| Saeed EGX Annual | $40 | every 1 year |
| Saeed US Monthly | $7 | every 1 month |
| Saeed US Annual | $60 | every 1 year |
| Saeed Both Monthly | $10 | every 1 month |
| Saeed Both Annual | $90 | every 1 year |

Copy each **plan id** (looks like `P-5ML4271244454362XMQIZHI`).

## Step C — set the backend variables

Railway → **backend** service → **Variables**:

```
PAYPAL_ENV=sandbox                # then: live
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
PAYPAL_PLAN_EGX_MONTHLY=P-...
PAYPAL_PLAN_EGX_ANNUAL=P-...
PAYPAL_PLAN_US_MONTHLY=P-...
PAYPAL_PLAN_US_ANNUAL=P-...
PAYPAL_PLAN_BOTH_MONTHLY=P-...
PAYPAL_PLAN_BOTH_ANNUAL=P-...
```

Until these are set, `/subscribe` politely says payments aren't switched on yet —
so you can keep granting access by hand in the meantime.

## Step D — the webhook (this is what keeps renewals working)

1. PayPal dashboard → your app → **Webhooks → Add webhook**
2. URL: `https://<your-backend>.up.railway.app/api/billing/webhook`
3. Subscribe to these events:
   - `PAYMENT.SALE.COMPLETED` ← the monthly/annual renewal
   - `PAYMENT.SALE.DENIED`
   - `BILLING.SUBSCRIPTION.ACTIVATED`
   - `BILLING.SUBSCRIPTION.CANCELLED`
   - `BILLING.SUBSCRIPTION.EXPIRED`
   - `BILLING.SUBSCRIPTION.SUSPENDED`
4. Copy the **Webhook ID** → set `PAYPAL_WEBHOOK_ID=...` on the backend.

⚠️ **Without the webhook, renewals never extend anyone's access** — the first
payment works and then everyone silently expires after a month.

## Step E — test it

1. PayPal → **Testing Tools → Sandbox accounts** — use the generated *personal*
   buyer account to pay.
2. On the site: register → pick a plan → pay → you should land back with access.
3. Check **Admin → Users**: the account shows the plan and expiry.

## How access is decided

- `admin` and `staff` **always** have both markets and never pay.
  (`staff` = full access, no admin panel — for friends/testers.)
- Everyone else needs `plan_until` in the future, and the plan must include the
  market they're viewing.
- The API returns **HTTP 402** for a market you haven't paid for; the app turns
  that into the subscribe page. **Blocking happens server-side**, so it can't be
  bypassed from the browser.
- Cancelling stops renewal but keeps access until the paid period ends.

## Granting access by hand

**Admin → Users → 💳 Plan** — type `egx` / `us` / `both` (or `none` to revoke)
and a number of days. Days are *added* to any time already remaining. Every grant
is written to `subscription_events` with your email against it.

Set someone to **staff** (Role button) for permanent free access without a plan.

## Optional free trial

`TRIAL_DAYS=7` on the backend gives every new account 7 days of their chosen plan
before payment. Default `0` (off).

---

# 2. Ads

Ad slots are already placed on the landing page, dashboard (top + bottom), stock
detail, and positions. They render **nothing** until you configure a network, and
they are **automatically hidden from paying subscribers**.

## Wiring any network

Railway → **backend** → Variables:

```
ADS_ENABLED=true
ADS_HEAD_SNIPPET=<the <script> tag your network gives you>
ADS_SLOT_HTML=<the per-placement markup, using {slot} where useful>
```

`{slot}` is replaced with the placement name: `landing-hero`, `dashboard-top`,
`dashboard-bottom`, `stock-mid`, `positions-mid`.

### Google AdSense example
```
ADS_ENABLED=true
ADS_HEAD_SNIPPET=<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXX" crossorigin="anonymous"></script>
ADS_SLOT_HTML=<ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-XXXXXXXXXXXX" data-ad-slot="1234567890" data-ad-format="auto" data-full-width-responsive="true"></ins><script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
```

Switching to Ezoic / Media.net / AdThrive later is just editing these two
variables — no redeploy of the frontend.

## Which network pays most?

Honestly: **it depends on your traffic, and you can't know until you have some.**
Rough guidance:

- **AdSense** — easiest to get approved, works at any traffic level. Start here.
- **Ezoic** — usually beats AdSense, needs ~10k monthly visits.
- **Mediavine / AdThrive** — best rates, but need ~50k / ~100k monthly sessions.

⚠️ **A real tension worth thinking about:** ads and a paid product pull against
each other. Ads on a page where you're asking for $10/month cheapen the product,
and finance ads are exactly the kind users distrust. The code hides ads from
subscribers — I'd suggest also keeping them **off the logged-in pages** entirely
(landing page only) unless the ad revenue proves material.

To disable ads anywhere, set `ADS_ENABLED=false`.

---

# 3. Getting paid

Money lands in the **PayPal business account** whose credentials you configured.
Withdraw to your bank from PayPal as usual. Ad networks pay separately on their
own schedules (AdSense: monthly, ~$100 minimum).

**Tax/legal is on you** — subscription revenue is income, and depending on where
your customers are you may owe VAT. Worth an accountant's hour before you scale.
