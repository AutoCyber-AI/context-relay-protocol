# CRP Auth Migration Sprint — 4-Hour Summary

**Date:** 2026-06-05  
**Sprint Goal:** Migrate CRP Gateway and CRP Comply from legacy API-key auth to Clerk SSO with shared PostgreSQL backend.

---

## ✅ Completed

### Hour 0 — Stop the Bleeding (Deployed)
- **Comply GitHub auth fix**: `Repositories.tsx` uses `api.ts` client with Clerk token injection
- **Comply webhook 405 fix**: Added `@app.post("/api/github/webhook")` delegating to handler
- **Comply callback singleton fix**: `AuthManager()` → `get_auth()` in legacy callback
- **Gateway console API key auth**: Added API key input bar to `/console` with localStorage persistence

### Hour 1 — Foundation
- **Gateway startup bug fixed**: `crprotocol>=4.0.0` in `requirements.txt`, `__init__.py` added, graceful `ImportError` fallback
- **`crp_shared` package created in BOTH repos**:
  - `auth.py`: `Identity`, `resolve_account()`, `current_clerk_identity()`, `get_entitlement()`, `get_clerk_org_metadata()`, `update_clerk_org_metadata()`
  - `db.py`: `init_db()`, `get_db()` using `asyncpg`
- **Comply `deps.py` updated**: Added `current_clerk_identity` dependency
- **Signed GitHub state tokens**: HMAC-SHA256 in `github_state.py` (self-validating, no DB needed)
- **Comply GitHub routes updated**: `POST /github/connect-start`, `GET /github/setup` with state validation

### Hour 2 — Comply Billing Webhook Rewrite
- **Rewrote `api/billing.py` webhook handlers** to write Clerk org metadata:
  - `_update_clerk_metadata()` helper
  - `_price_to_product_plan()` mapping for `comply`, `gateway`, `scan` products
  - Handlers updated: `checkout.session.completed`, `subscription.created`, `subscription.updated`, `subscription.deleted`
  - Per-product plan keys: `comply_plan`, `gateway_plan`, `scan_plan`
  - Backward compat: still writes local JSON during cutover
- **Checkout session creation** now passes `crp_org_id` in metadata from Clerk claims

### Hour 2.5 — Security Hardening
- **`authorizedParties` enforcement** in `crp_shared/auth.py` (both repos):
  - Validates `azp` claim against `CLERK_AUTHORIZED_PARTIES` env var
  - Falls back to `Origin`/`Referer` header check
  - Strict mode in production; lenient in development

### Hour 3 — Gateway Billing + SQL Layer
- **`crp_gateway/billing.py`**: `/billing/checkout`, `/billing/portal`, `/billing/webhook`
  - Webhook writes `gateway_plan` to Clerk org metadata
- **`crp_gateway/db.py`**: Async PostgreSQL repository layer
  - `tenants`, `api_keys`, `usage`, `systems` tables
  - Falls back to in-memory when `DATABASE_URL` not set

### Hour 4 — Gateway Clerk Sign-In
- **Console Clerk integration**:
  - Sign In / Sign Out buttons in auth bar
  - Clerk JS loaded from CDN
  - Session token used for API calls when no API key set
  - `clerk-publishable-key` meta tag in console HTML

---

## ⏳ Remaining (Post-Sprint)

### P0 — PostgreSQL Provisioning
- **Railway**: Provision ONE PostgreSQL service in consolidated project
- **Logical DBs**: Create `crp_gateway` and `crp_comply` databases
- **Schemas**: Apply `001_initial.sql` for both logical DBs
- **Gateway migration**: Switch `main.py` from in-memory dicts to `crp_gateway/db.py` repository calls

### P0 — Idempotency Table
- Replace file-based idempotency (`/tmp/crp_webhook_events.json`) with PostgreSQL `webhook_events` table with 24h TTL

### P1 — Entitlement Backfill
- One-off script to write existing active subscriptions to Clerk metadata for all orgs

### P1 — Gateway State Migration
- `_tenants`, `_api_keys`, `_usage`, `_systems` still accessed directly as dicts in `main.py`
- Need to async-ify handlers and await repository calls

### P2 — Clerk Frontend API Key
- Console uses placeholder `<YOUR_CLERK_PUBLISHABLE_KEY>` — replace with real publishable key

### P2 — Gateway `/docs` Auth
- Swagger UI should support Bearer token input for testing Clerk-authenticated endpoints

---

## Commits

### crp-gateway (`main`)
1. `bffc42e` — Shared auth layer, Identity model, startup robustness
2. `8d4baa5` — authorizedParties validation
3. `336900a` — Billing endpoints + SQL repository layer
4. `eaafff8` — Clerk sign-in on console

### crp-comply (`master`)
1. `04f754e` — Shared auth layer, Identity model, current_clerk_identity
2. `6d822ef` — Signed state tokens, connect-start endpoint, setup callback
3. `9ca415a` — Billing webhook rewrite (Clerk metadata)
4. `ee45a04` — authorizedParties validation
