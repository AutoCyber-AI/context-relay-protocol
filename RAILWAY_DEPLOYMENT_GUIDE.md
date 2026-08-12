# Railway Deployment Guide — CRP Scribe & CRP Comply

**Railway plan:** Hobby — $5 USD/month minimum (includes $5 of usage credits).  
**Architecture:** Each product = 1 Railway project, 1 service, 1 persistent volume.

---

## BLOCKERS — Fix Before Deploying

### ✅ Clerk — Production Instances Ready

Both Clerk production instances are live:
- **Scribe:** `clerk.scribe.crprotocol.io` — `<YOUR_CLERK_PUBLISHABLE_KEY>`
- **Comply:** `clerk.comply.crprotocol.io` — `<YOUR_CLERK_PUBLISHABLE_KEY>`

GitHub Actions secrets have been updated with the production keys.

### ✅ Stripe Is Already Production

Both products use `sk_live_` keys — Stripe is production-ready. The only post-deploy task is updating the webhook URLs.

---

## STEP 1 — Create Railway Projects

Do this twice — once for Scribe, once for Comply.

1. Go to [https://railway.app](https://railway.app) → **New Project**
2. Choose **"Deploy from GitHub repo"**
3. Authorize Railway if needed, then select:
   - Scribe: `Constantinos-uni/crp-scribe`
   - Comply: `Constantinos-uni/crp-comply`
4. Railway detects the `Dockerfile` automatically → **Deploy now**
5. The first build will likely **fail** — that is expected until Variables are set in Step 3

---

## STEP 2 — Add Persistent Volume

Data (users, API keys, audit records) is stored in `/app/data`. Without a volume, all data is wiped on every redeploy.

1. Inside the Railway project → click your service
2. Click **Volumes** tab → **"Add Volume"**
3. Set mount path: `/app/data`
4. Size: **1 GB** (start here — upgradeable later, max 5 GB on Hobby)
5. Click **Create**

---

## STEP 3 — Set Environment Variables

In the Railway project → click your service → **Variables** tab → **"New Variable"** (or **"Raw Editor"** to paste all at once).

### CRP Scribe — Railway Variables

> **Do NOT add a `PORT` variable.** Railway injects `PORT=8080` automatically. Your CMD uses `${PORT:-8500}` and correctly picks up 8080. When adding a custom domain, enter **8080** as the target port.

```
# ── Clerk ────────────────────────────────────────────────────────
CLERK_ISSUER=https://clerk.scribe.crprotocol.io
CLERK_SECRET_KEY=<YOUR_CLERK_SECRET_KEY>

# ── Stripe ──────────────────────────────────────────────────────────
# NEVER commit real values here. Pull from your local .env / secrets manager
# and paste directly into Railway's Variables UI -- never into this file.
STRIPE_SECRET_KEY=<value from your .env file>
STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>
STRIPE_SCRIBE_PRO_PRICE_ID=price_1TMSB5GRBK524I7zhmUgLmfm
STRIPE_SCRIBE_ENTERPRISE_PRICE_ID=price_1TMSB5GRBK524I7zCIU71YN6

# ── App ───────────────────────────────────────────────────────────
CRP_SCRIBE_DATA_DIR=/app/data
CRP_SCRIBE_FRONTEND_DIR=/app/frontend/dist
# Set this after Railway assigns your domain:
CRP_SCRIBE_BASE_URL=https://scribe.crprotocol.io
CRP_SCRIBE_CORS_ORIGINS=https://scribe.crprotocol.io

# ── Python ────────────────────────────────────────────────────────
PYTHONUNBUFFERED=1
```

**Build Variable** (Railway Variables panel → set as "Build Variable" toggle ON):

```
VITE_CLERK_PUBLISHABLE_KEY=<YOUR_CLERK_PUBLISHABLE_KEY>
```

> This is a **build-time** variable — it must be toggled as "Available at build time" in Railway so it gets passed as a Docker `ARG` when Vite compiles the frontend bundle.

### CRP Comply — Railway Variables

> **Do NOT add a `PORT` variable.** Railway injects `PORT=8080` automatically. Your CMD uses `${PORT:-8400}` and correctly picks up 8080. When adding a custom domain, enter **8080** as the target port.

```
# ── Clerk ────────────────────────────────────────────────────────
CLERK_ISSUER=https://clerk.comply.crprotocol.io
CLERK_SECRET_KEY=<YOUR_CLERK_SECRET_KEY>

# ── Stripe ──────────────────────────────────────────────────────────
STRIPE_SECRET_KEY=<value from your .env file>
STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>
STRIPE_COMPLY_PRO_PRICE_ID=price_1TMSGAGRBK524I7zvSYEwg9S
STRIPE_COMPLY_ENTERPRISE_PRICE_ID=price_1TMSGAGRBK524I7z9ebppShK
STRIPE_COMPLY_CLOUD_PRICE_ID=price_1TMSGAGRBK524I7zaSuQMMzb

# ── App ───────────────────────────────────────────────────────────
CRP_COMPLY_DATA_DIR=/app/data
CRP_COMPLY_FRONTEND_DIR=/app/frontend/dist
# Set this after Railway assigns your domain:
CRP_COMPLY_BASE_URL=https://comply.crprotocol.io
CRP_COMPLY_CORS_ORIGINS=https://comply.crprotocol.io

# ── Python ────────────────────────────────────────────────────────
PYTHONUNBUFFERED=1
```

**Build Variable** (toggle "Available at build time" ON):

```
VITE_CLERK_PUBLISHABLE_KEY=<YOUR_CLERK_PUBLISHABLE_KEY>
```

---

## STEP 4 — Configure Build Variable Toggle

Railway must pass `VITE_CLERK_PUBLISHABLE_KEY` as a Docker `ARG` during the build, not just as a runtime env var. Without this toggle, the Clerk key is never baked into the Vite bundle and all users see "Clerk: Missing publishable key".

1. In Variables tab, find `VITE_CLERK_PUBLISHABLE_KEY`
2. Click the variable → toggle **"Available at build time"** to ON
3. Trigger a new deploy (Railway → **Redeploy**)

---

## STEP 5 — Set Custom Domain

1. Railway project → Settings → **Domains**
2. Click **"Add custom domain"**
3. Enter your domain:
   - Scribe: `scribe.crprotocol.io`
   - Comply: `comply.crprotocol.io`
4. Railway shows a **CNAME record** to add in your DNS provider
5. Add the CNAME at your DNS provider (e.g., Cloudflare: Type=CNAME, Name=`scribe`, Target=`<railway-provided-value>`)
6. Wait for DNS propagation (5–30 minutes typically)
7. Railway will auto-issue an SSL certificate once DNS resolves

> **Note:** Hobby plan allows 2 custom domains — one per product fits exactly.

---

## STEP 6 — Update Clerk Production Instance Domains

After your domain is live:

1. Clerk Dashboard → your production instance → **Domains**
2. Set **Home URL** to `https://scribe.crprotocol.io` (or comply)
3. Add `https://scribe.crprotocol.io` to **Allowed redirect URLs**
4. Update **CLERK_ISSUER** Railway Variable if the issuer URL changed

---

## STEP 7 — Update Stripe Webhook URLs

The Stripe webhook secrets are already set correctly. You just need to point the webhook endpoint at the live Railway URL.

1. Go to [https://dashboard.stripe.com/webhooks](https://dashboard.stripe.com/webhooks)
2. Find the existing webhook endpoint for each product (currently likely `http://localhost:...`)
3. Click **Update endpoint** → set URL to:
   - Scribe: `https://scribe.crprotocol.io/api/v1/stripe/webhook`
   - Comply: `https://comply.crprotocol.io/api/v1/stripe/webhook`
4. Ensure these events are enabled:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. The webhook secret (`<YOUR_STRIPE_WEBHOOK_SECRET>`) stays the same — no change needed in Railway Variables

---

## STEP 8 — Update GitHub Actions Secrets (for CI)

After creating production Clerk instances, update the CI secrets so the Docker build step in CI uses the live keys:

```bash
# CRP Scribe
gh secret set VITE_CLERK_PUBLISHABLE_KEY \
  --repo Constantinos-uni/crp-scribe \
  --body "<YOUR_CLERK_PUBLISHABLE_KEY>"

# CRP Comply
gh secret set VITE_CLERK_PUBLISHABLE_KEY \
  --repo Constantinos-uni/crp-comply \
  --body "<YOUR_CLERK_PUBLISHABLE_KEY>"
```

> These Clerk publishable keys (`pk_live_`) are safe to store as GitHub Actions secrets — they are public-facing keys designed to be embedded in browser JavaScript bundles. They grant no privileged access.  
> **NEVER** put `STRIPE_SECRET_KEY` (`sk_live_`) or `CLERK_SECRET_KEY` in GitHub secrets; they belong only in Railway Variables.

---

## STEP 9 — Hardware & Scaling Settings

Railway Hobby resources per service:

| Setting | Value |
|---|---|
| vCPU | Up to 48 vCPU shared (burst) |
| RAM | Up to 48 GB shared (burst) |
| Estimated baseline | ~0.5 vCPU / 512 MB at idle |
| Volume storage | 5 GB max (we use 1 GB) |
| Sleep on inactivity | **Disabled on Hobby** (apps stay awake) |

No manual resource allocation needed — Railway auto-scales within plan limits.

**Healthcheck** (already configured in both Dockerfiles):
- Interval: 30s
- Timeout: 5s
- Retries: 3
- Path: `GET /api/v1/health`

Railway will automatically restart the container if healthchecks fail.

---

## STEP 10 — Verify Deployment

After both apps are deployed and custom domains resolve:

| Check | Expected |
|---|---|
| `GET https://scribe.crprotocol.io/api/v1/health` | `{"status": "ok"}` |
| `GET https://comply.crprotocol.io/api/v1/health` | `{"status": "ok"}` |
| Open `https://scribe.crprotocol.io` in browser | Clerk sign-in loads (not "Missing publishable key") |
| Open `https://comply.crprotocol.io` in browser | Clerk sign-in loads |
| Sign in with a test account | Dashboard accessible |
| Stripe test purchase | Webhook fires (check Stripe dashboard → Webhooks → Recent deliveries) |

---

## Summary — Deployment Checklist

- [ ] Create production Clerk instances for both products (BLOCKER 1)
- [ ] Create Railway project for CRP Scribe → deploy from GitHub
- [ ] Add Railway Volume at `/app/data` (1 GB)
- [ ] Set all Scribe Railway Variables (including Build Variable toggle for VITE key)
- [ ] Create Railway project for CRP Comply → deploy from GitHub
- [ ] Add Railway Volume at `/app/data` (1 GB)
- [ ] Set all Comply Railway Variables (including Build Variable toggle for VITE key)
- [ ] Add custom domain `scribe.crprotocol.io` + DNS CNAME
- [ ] Add custom domain `comply.crprotocol.io` + DNS CNAME
- [ ] Update Stripe webhook URLs for both products
- [ ] Update Clerk production instance allowed domains
- [ ] Update GitHub Actions secrets with `pk_live_` keys
- [ ] Verify healthcheck endpoints return `{"status": "ok"}`
- [ ] Confirm Clerk sign-in loads (no missing key error)
- [ ] Confirm Stripe test purchase triggers webhook

---

## Cost Estimate

| Component | Cost |
|---|---|
| Railway Hobby base | $5.00 USD/month (includes $5 usage credits) |
| 2 services at ~$0.50 idle each | ~$1.00/month usage |
| 2 × 1 GB volumes | ~$0.25/month each = $0.50/month |
| **Total (light traffic)** | **~$5.00 USD/month** (covered by base credit) |
| **Total (moderate traffic)** | **~$8–12 USD/month** |

Volumes and CPU/RAM above the base $5 credit are billed at Railway's usage rates. Monitor usage in Railway Dashboard → Usage tab.
