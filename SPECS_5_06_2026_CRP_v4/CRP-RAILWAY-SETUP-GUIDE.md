# CRP Railway Setup Guide — PostgreSQL, Redis & Environment Variables


# 13.06.2026 - User feedback on what's been attempted:


For connecting via public url...there will be egress costs...hence, connecting privately, I believe you can implement what you have stated via first connecting, Connect to Postgres:

Private Network
Public Network
1
Create a new variable in the service you want to connect to this database.

2
Assign it the following value:

 ${{ Postgres.DATABASE_URL }}

3
Use the variable in your application code.


Connect and create the dbs. I have added the variables:
All clerk variables including authorised parties

Gateway specific:
all stripe variables, Db url

Comply-specific:
db url, all stripe, all github specifically:
GITHUB_APP_CLIENT_ID
*******
GITHUB_APP_CLIENT_SECRET
*******
GITHUB_APP_ID
*******
GITHUB_APP_PRIVATE_KEY
*******
GITHUB_APP_WEBHOOK_SECRET
*******


SO YOUR JOB IS TO CREATE THE DB INTERNALLY OR EVEN CONNECTING TO IT AND ENSURING THE DATABASES ARE SETUP PROPERLY!



## Overview

Both **CRP Gateway** and **CRP Comply** connect to:
- **ONE PostgreSQL instance** → two logical databases (`crp_gateway`, `crp_comply`)
- **ONE Redis instance** → namespaced keys (`gw:*` for Gateway, `cmp:*` for Comply)

This guide assumes you have a Railway project with both services deployed.

---

## 1. Provision PostgreSQL

### Option A: Railway-managed PostgreSQL (Recommended)
1. In your Railway project dashboard → **New** → **Database** → **Add PostgreSQL**
2. Wait for provisioning. Railway will provide a `DATABASE_URL` like:
   ```
   postgresql://user:password@host.railway.internal:5432/railway
   ```
3. **Create the two logical databases** using Railway's shell or `psql`:

```bash
# Connect to the default "railway" database first
psql $DATABASE_URL

# Inside psql:
CREATE DATABASE crp_gateway;
CREATE DATABASE crp_comply;
\q
```

### Option B: External PostgreSQL (e.g. Supabase, Neon)
If using an external provider, create the two databases there and note the connection strings.

---

## 2. Apply SQL Schemas

The schema file is at `context-relay-protocol/migrations/001_initial.sql`.

### Apply to Gateway DB
```bash
# Replace with your actual Gateway DB connection string
export GATEWAY_DB_URL="postgresql://user:password@host:5432/crp_gateway"
psql $GATEWAY_DB_URL -f migrations/001_initial.sql
```

### Apply to Comply DB
```bash
# Replace with your actual Comply DB connection string
export COMPLY_DB_URL="postgresql://user:password@host:5432/crp_comply"
psql $COMPLY_DB_URL -f migrations/001_initial.sql
```

> **Note:** Both schemas are identical. The application code only touches the tables it needs. Gateway ignores `github_installations`, `compliance_reports`, etc. Comply ignores `gateway_systems`, `gateway_usage`, etc.

---

## 3. Provision Redis

1. Railway dashboard → **New** → **Database** → **Add Redis**
2. Railway provides `REDIS_URL` like:
   ```
   redis://default:password@host.railway.internal:6379
   ```
3. Both services share this single Redis instance. Key namespacing prevents collisions:
   - Gateway uses `gw:*` prefix (not yet implemented — currently in-memory)
   - Comply uses `cmp:*` prefix (not yet implemented — currently in-memory)

---

## 4. Environment Variables

### CRP Gateway (`crp-gateway` service)

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | **Yes** | `postgresql://user:pass@host:5432/crp_gateway` | PostgreSQL connection for Gateway logical DB |
| `REDIS_URL` | No | `redis://default:pass@host:6379` | Shared Redis (future use) |
| `CLERK_ISSUER` | **Yes** | `https://clerk.crprotocol.io` | Clerk instance URL |
| `CLERK_SECRET_KEY` | **Yes** | `<YOUR_CLERK_SECRET_KEY>` | Clerk Backend API key |
| `CLERK_PUBLISHABLE_KEY` | **Yes** | `<YOUR_CLERK_PUBLISHABLE_KEY>` | Clerk Frontend API key (for console JS) |
| `CLERK_AUTHORIZED_PARTIES` | **Yes** | `https://comply.crprotocol.io,https://gateway.crprotocol.io` | Allowed token origins |
| `STRIPE_SECRET_KEY` | **Yes** | `<YOUR_STRIPE_SECRET_KEY>` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | **Yes** | `<YOUR_STRIPE_WEBHOOK_SECRET>` | Stripe webhook endpoint secret |
| `STRIPE_GATEWAY_DEVELOPER_PRICE_ID` | **Yes** | `<YOUR_STRIPE_PRICE_ID>` | Stripe price ID for Developer plan |
| `STRIPE_GATEWAY_TEAM_PRICE_ID` | **Yes** | `<YOUR_STRIPE_PRICE_ID>` | Stripe price ID for Team plan |
| `SECRET_KEY` | No | `random-string` | For internal HMAC/signing |
| `PORT` | Auto | `8100` | Railway injects this automatically |
| `CRP_GATEWAY_BASE_URL` | No | `https://gateway.crprotocol.io` | Used in checkout redirect URLs |

### CRP Comply (`crp-comply` service)

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | **Yes** | `postgresql://user:pass@host:5432/crp_comply` | PostgreSQL connection for Comply logical DB |
| `REDIS_URL` | No | `redis://default:pass@host:6379` | Shared Redis (future use) |
| `CLERK_ISSUER` | **Yes** | `https://clerk.crprotocol.io` | Same Clerk instance as Gateway |
| `CLERK_SECRET_KEY` | **Yes** | `<YOUR_CLERK_SECRET_KEY>` | Same Clerk Backend API key |
| `CLERK_PUBLISHABLE_KEY` | **Yes** | `<YOUR_CLERK_PUBLISHABLE_KEY>` | Same Clerk Frontend API key |
| `CLERK_AUTHORIZED_PARTIES` | **Yes** | `https://comply.crprotocol.io,https://gateway.crprotocol.io` | Same allowed origins |
| `STRIPE_SECRET_KEY` | **Yes** | `<YOUR_STRIPE_SECRET_KEY>` | Same Stripe account |
| `STRIPE_WEBHOOK_SECRET` | **Yes** | `<YOUR_STRIPE_WEBHOOK_SECRET>` | Stripe webhook endpoint secret |
| `STRIPE_COMPLY_STARTER_PRICE_ID` | **Yes** | `<YOUR_STRIPE_PRICE_ID>` | Comply Starter tier |
| `STRIPE_COMPLY_SCALE_PRICE_ID` | **Yes** | `<YOUR_STRIPE_PRICE_ID>` | Comply Scale tier |
| `STRIPE_COMPLY_PROFESSIONAL_PRICE_ID` | **Yes** | `<YOUR_STRIPE_PRICE_ID>` | Comply Pro tier |
| `STRIPE_COMPLY_ENTERPRISE_PRICE_ID` | No | `<YOUR_STRIPE_PRICE_ID>` | Comply Enterprise tier |
| `STRIPE_COMPLY_CLOUD_PRICE_ID` | No | `<YOUR_STRIPE_PRICE_ID>` | Comply Cloud tier |
| `GITHUB_APP_ID` | **Yes** | `123456` | GitHub App ID |
| `GITHUB_PRIVATE_KEY` | **Yes** | `<YOUR_GITHUB_PRIVATE_KEY_PEM>` | GitHub App private key |
| `GITHUB_CLIENT_ID` | **Yes** | `Iv1.abc...` | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | **Yes** | `<YOUR_GITHUB_CLIENT_SECRET>` | GitHub OAuth App client secret |
| `GITHUB_WEBHOOK_SECRET` | **Yes** | `<YOUR_GITHUB_WEBHOOK_SECRET>` | GitHub App webhook secret |
| `GITHUB_STATE_SECRET` | No | `random-string` | HMAC secret for state tokens (auto-generated if not set) |
| `CRP_COMPLY_BASE_URL` | **Yes** | `https://comply.crprotocol.io` | Used in checkout/success redirects |
| `CRP_COMPLY_DATA_DIR` | No | `/app/data` | Volume mount for file storage |
| `PORT` | Auto | `8400` | Railway injects this automatically |

### Shared / Derived Variables

Both services should share these values:

```bash
# Clerk (same instance)
CLERK_ISSUER=https://clerk.crprotocol.io
CLERK_SECRET_KEY=<YOUR_CLERK_SECRET_KEY>
CLERK_PUBLISHABLE_KEY=<YOUR_CLERK_PUBLISHABLE_KEY>
CLERK_AUTHORIZED_PARTIES=https://comply.crprotocol.io,https://gateway.crprotocol.io

# Stripe (same account)
STRIPE_SECRET_KEY=<YOUR_STRIPE_SECRET_KEY>
STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>

# PostgreSQL (same instance, different DB names)
# Gateway service:
DATABASE_URL=postgresql://user:pass@postgres.railway.internal:5432/crp_gateway
# Comply service:
DATABASE_URL=postgresql://user:pass@postgres.railway.internal:5432/crp_comply

# Redis (same instance)
REDIS_URL=redis://default:pass@redis.railway.internal:6379
```

---

## 5. Stripe Webhook Configuration

You need **two webhook endpoints** pointing to the same Stripe account:

### Gateway Webhook
- **URL:** `https://gateway.crprotocol.io/billing/webhook`
- **Events:** `checkout.session.completed`, `customer.subscription.deleted`

### Comply Webhook
- **URL:** `https://comply.crprotocol.io/api/billing/webhook`
- **Events:** `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `payment_intent.succeeded`

Each endpoint gets its own `STRIPE_WEBHOOK_SECRET`.

---

## 6. Railway Variable Inheritance

If both services are in the **same Railway project**, you can use **shared variables**:

1. Railway dashboard → Project Settings → **Shared Variables**
2. Add shared vars: `CLERK_ISSUER`, `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`
3. Service-specific vars override shared vars:
   - Gateway service: `DATABASE_URL` → `crp_gateway`
   - Comply service: `DATABASE_URL` → `crp_comply`

---

## 7. Verification Checklist

After setting variables and deploying:

- [ ] `curl https://gateway.crprotocol.io/health` → `{"status":"ok"}`
- [ ] `curl https://comply.crprotocol.io/api/v1/health` → `{"status":"ok"}`
- [ ] Gateway `/console` loads with Sign In button
- [ ] Comply frontend loads and can sign in via Clerk
- [ ] Stripe checkout session creates successfully on both services
- [ ] Webhook events write Clerk metadata (check org public_metadata in Clerk Dashboard)
- [ ] PostgreSQL tables populated (`SELECT * FROM tenants;` in both DBs)

---

## 8. Troubleshooting

### "asyncpg not found" on deploy
- Gateway: `asyncpg` and `stripe` added to `requirements.txt` ✅
- Comply: `asyncpg` added to `pyproject.toml` ✅
- **Action:** Trigger a fresh deploy (Railway rebuilds from commit)

### "DB pool not initialized"
- `DATABASE_URL` is missing or malformed
- Check Railway service variables → ensure `DATABASE_URL` is set

### "Clerk JWT verification failed"
- `CLERK_ISSUER` must match your Clerk instance URL exactly
- `CLERK_SECRET_KEY` must be the **Backend** API key, not the publishable key

### "Unauthorized party" 401 errors
- `CLERK_AUTHORIZED_PARTIES` must include both origins exactly as the browser sends them
- Check browser Network tab → `Origin` header value
