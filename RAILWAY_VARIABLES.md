# Railway Variables — CRP Scribe & CRP Comply

Complete reference for every Railway environment variable.  
Paste these directly into Railway → Service → Variables → **Raw Editor**.

> **DO NOT set `PORT`** — Railway injects it automatically as `8080`.  
> Your Dockerfiles already use `${PORT:-8500}` / `${PORT:-8400}`, so they pick it up correctly.

---

## CRP Scribe — Railway Variables

### Build Variable (toggle "Available at build time" ON in Railway UI)

| Variable | Value |
|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | `<YOUR_CLERK_PUBLISHABLE_KEY>` |

### Runtime Variables (paste into Raw Editor)

```
CLERK_ISSUER=https://clerk.scribe.crprotocol.io
CLERK_SECRET_KEY=<YOUR_CLERK_SECRET_KEY>
STRIPE_SECRET_KEY=<YOUR_STRIPE_SECRET_KEY>
STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>
STRIPE_SCRIBE_PRO_PRICE_ID=price_1TMSB5GRBK524I7zhmUgLmfm
STRIPE_SCRIBE_ENTERPRISE_PRICE_ID=price_1TMSB5GRBK524I7zCIU71YN6
CRP_SCRIBE_JWT_SECRET=<generate-your-own-random-secret>
CRP_SCRIBE_DATA_DIR=/app/data
CRP_SCRIBE_FRONTEND_DIR=/app/frontend/dist
CRP_SCRIBE_BASE_URL=https://scribe.crprotocol.io
CRP_SCRIBE_CORS_ORIGINS=https://scribe.crprotocol.io
PYTHONUNBUFFERED=1
```

> **NEVER commit real secret values to this file.** Pull the actual values from
> your local `.env` / secrets manager and paste them directly into Railway's
> Variables UI -- never into a git-tracked file. This file documents variable
> *names* and *shape* only.

### All Scribe Variables at a Glance

| Variable | Value | Build-time? |
|---|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | `<YOUR_CLERK_PUBLISHABLE_KEY>` | **YES — toggle ON** |
| `CLERK_ISSUER` | `https://clerk.scribe.crprotocol.io` | No |
| `CLERK_SECRET_KEY` | `<YOUR_CLERK_SECRET_KEY>` (see Clerk dashboard) | No |
| `STRIPE_SECRET_KEY` | `<YOUR_STRIPE_SECRET_KEY>` (see Stripe dashboard) | No |
| `STRIPE_WEBHOOK_SECRET` | `<YOUR_STRIPE_WEBHOOK_SECRET>` (see Stripe webhook config) | No |
| `STRIPE_SCRIBE_PRO_PRICE_ID` | `price_1TMSB5GRBK524I7zhmUgLmfm` | No |
| `STRIPE_SCRIBE_ENTERPRISE_PRICE_ID` | `price_1TMSB5GRBK524I7zCIU71YN6` | No |
| `CRP_SCRIBE_JWT_SECRET` | `<generate-your-own-random-secret>` | No |
| `CRP_SCRIBE_DATA_DIR` | `/app/data` | No |
| `CRP_SCRIBE_FRONTEND_DIR` | `/app/frontend/dist` | No |
| `CRP_SCRIBE_BASE_URL` | `https://scribe.crprotocol.io` | No |
| `CRP_SCRIBE_CORS_ORIGINS` | `https://scribe.crprotocol.io` | No |
| `PYTHONUNBUFFERED` | `1` | No |

---

## CRP Comply — Railway Variables

### Build Variable (toggle "Available at build time" ON in Railway UI)

| Variable | Value |
|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | `<YOUR_CLERK_PUBLISHABLE_KEY>` |

### Runtime Variables (paste into Raw Editor)

```
CLERK_ISSUER=https://clerk.comply.crprotocol.io
CLERK_SECRET_KEY=<YOUR_CLERK_SECRET_KEY>
STRIPE_SECRET_KEY=<YOUR_STRIPE_SECRET_KEY>
STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>
STRIPE_COMPLY_PRO_PRICE_ID=price_1TMSGAGRBK524I7zvSYEwg9S
STRIPE_COMPLY_ENTERPRISE_PRICE_ID=price_1TMSGAGRBK524I7z9ebppShK
STRIPE_COMPLY_CLOUD_PRICE_ID=price_1TMSGAGRBK524I7zaSuQMMzb
CRP_COMPLY_JWT_SECRET=<generate-your-own-random-secret>
CRP_COMPLY_DATA_DIR=/app/data
CRP_COMPLY_FRONTEND_DIR=/app/frontend/dist
CRP_COMPLY_BASE_URL=https://comply.crprotocol.io
CRP_COMPLY_CORS_ORIGINS=https://comply.crprotocol.io
PYTHONUNBUFFERED=1
```

> **NEVER commit real secret values to this file.** Pull the actual values from
> your local `.env` / secrets manager and paste them directly into Railway's
> Variables UI -- never into a git-tracked file. This file documents variable
> *names* and *shape* only.

### All Comply Variables at a Glance

| Variable | Value | Build-time? |
|---|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | `<YOUR_CLERK_PUBLISHABLE_KEY>` | **YES — toggle ON** |
| `CLERK_ISSUER` | `https://clerk.comply.crprotocol.io` | No |
| `CLERK_SECRET_KEY` | `<YOUR_CLERK_SECRET_KEY>` (see Clerk dashboard) | No |
| `STRIPE_SECRET_KEY` | `<YOUR_STRIPE_SECRET_KEY>` (see Stripe dashboard) | No |
| `STRIPE_WEBHOOK_SECRET` | `<YOUR_STRIPE_WEBHOOK_SECRET>` (see Stripe webhook config) | No |
| `STRIPE_COMPLY_PRO_PRICE_ID` | `price_1TMSGAGRBK524I7zvSYEwg9S` | No |
| `STRIPE_COMPLY_ENTERPRISE_PRICE_ID` | `price_1TMSGAGRBK524I7z9ebppShK` | No |
| `STRIPE_COMPLY_CLOUD_PRICE_ID` | `price_1TMSGAGRBK524I7zaSuQMMzb` | No |
| `CRP_COMPLY_JWT_SECRET` | `<generate-your-own-random-secret>` | No |
| `CRP_COMPLY_DATA_DIR` | `/app/data` | No |
| `CRP_COMPLY_FRONTEND_DIR` | `/app/frontend/dist` | No |
| `CRP_COMPLY_BASE_URL` | `https://comply.crprotocol.io` | No |
| `CRP_COMPLY_CORS_ORIGINS` | `https://comply.crprotocol.io` | No |
| `PYTHONUNBUFFERED` | `1` | No |

---

## How to Enter Variables in Railway

### Option A — Raw Editor (fastest for bulk paste)

1. Service → **Variables** tab → **Raw Editor** button (top right)
2. Paste the runtime block above
3. Click **Update Variables**
4. Then add `VITE_CLERK_PUBLISHABLE_KEY` separately and toggle "Available at build time" ON

### Option B — New Variable (one at a time)

1. Service → **Variables** → **New Variable**
2. Enter name and value
3. For `VITE_CLERK_PUBLISHABLE_KEY` specifically: after saving, click the variable → toggle **"Available at build time"** to ON

---

## How to Add the Volume (it's on the canvas, not in settings)

Railway Volumes are NOT inside the service settings panel. Find them on the project canvas:

1. Go back to the **project view** (click your project name at the top)
2. You'll see your service as a card on a canvas
3. Click the **"+"** button (usually top-right of the canvas, or right-click canvas)
4. Select **"Volume"**
5. Railway asks:
   - **Mount path:** `/app/data`
   - **Service to attach:** select your service (crp-scribe or crp-comply)
   - **Size:** 1 GB
6. Click **Create**

Do this for both Scribe and Comply projects.

---

## What the Port 8080 Means

When adding a custom domain Railway asks "Target port your app is listening on" and shows **8080**.

**8080 is correct — leave it.**

Railway automatically injects `PORT=8080` into your container at runtime.  
Your Dockerfile CMD (`${PORT:-8500}` / `${PORT:-8400}`) resolves to 8080 because Railway's `$PORT` overrides the default.  
Railway then routes `comply.crprotocol.io → container:8080` automatically.

**Do NOT add `PORT` as a Railway Variable.** Railway owns that value.

---

## Post-Deploy Checklist

- [ ] Scribe: set `VITE_CLERK_PUBLISHABLE_KEY` → toggle "Available at build time" ON → redeploy
- [ ] Comply: same as above
- [ ] Scribe: Volume attached at `/app/data`
- [ ] Comply: Volume attached at `/app/data`
- [ ] Scribe: Custom domain `scribe.crprotocol.io` — Target port **8080**
- [ ] Comply: Custom domain `comply.crprotocol.io` — Target port **8080**
- [ ] Add DNS CNAME records at your DNS provider (Railway shows you the target value)
- [ ] Stripe → Webhooks — update endpoint URL to `https://scribe.crprotocol.io/api/v1/stripe/webhook`
- [ ] Stripe → Webhooks — update endpoint URL to `https://comply.crprotocol.io/api/v1/stripe/webhook`
- [ ] Clerk dashboard → both production instances → set Home URL and allowed redirect URLs to Railway domains
- [ ] Verify: `GET https://scribe.crprotocol.io/api/v1/health` → `{"status": "ok"}`
- [ ] Verify: `GET https://comply.crprotocol.io/api/v1/health` → `{"status": "ok"}`
