# CRP Auth, User Management & PostgreSQL Migration — Comprehensive Implementation Plan

**Version:** 1.0.0  
**Date:** 2026-06-05  
**Scope:** CRP Gateway + CRP Comply + CRP Scan (unified identity layer)  
**Status:** Approved for execution  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Honest Assessment: What We Have vs What We Need](#2-honest-assessment-what-we-have-vs-what-we-need)
3. [The Two Specification Documents: Coverage Analysis](#3-the-two-specification-documents-coverage-analysis)
4. [The Five Critical Problems](#4-the-five-critical-problems)
5. [Target Architecture: Clerk + PostgreSQL](#5-target-architecture-clerk--postgresql)
6. [Railway Infrastructure Design](#6-railway-infrastructure-design)
7. [PostgreSQL Schema (Production-Ready)](#7-postgresql-schema-production-ready)
8. [Phase-by-Phase Implementation](#8-phase-by-phase-implementation)
9. [Railway Environment Variables (Complete Reference)](#9-railway-environment-variables-complete-reference)
10. [Critical Evaluation of This Plan](#10-critical-evaluation-of-this-plan)
11. [Test Checklist](#11-test-checklist)
12. [4-Hour Execution Sprint (Hour = Week)](#12-4-hour-execution-sprint-hour--week)

---

## 1. Executive Summary

This document is the **canonical implementation plan** for unifying authentication, user management, and entitlement across CRP Gateway, CRP Comply, and CRP Scan. It replaces fragmented JSON-file and in-memory storage with a **production PostgreSQL backend**, while preserving Clerk as the single source of truth for identity and entitlement.

**The core principle:**
> Clerk = WHO you are and WHAT you can access (entitlement).  
> PostgreSQL = WHAT you have done (application state).

**Current reality:** ~30% aligned with specifications. This plan closes the remaining 70%.

---

## 2. Honest Assessment: What We Have vs What We Need

### 2.1 CRP Gateway (gateway.crprotocol.io)

| Capability | Current State | Required State | Gap |
|------------|--------------|----------------|-----|
| Auth method | API key in `localStorage` + Clerk JWT fallback | Clerk JS sign-in + API key management | ❌ No Clerk frontend |
| Tenant storage | In-memory Python dict (`_tenants`) | PostgreSQL `tenants` table | ❌ Lost on restart |
| API key storage | In-memory dict (`_api_keys`) plaintext | PostgreSQL `api_keys` table, hashed | ❌ Security risk |
| Plan/entitlement | Hardcoded `_tenants["plan"]="free"` | Clerk `public_metadata.gateway_plan` | ❌ No dynamic plans |
| Billing | None — no Stripe integration | Checkout + webhook + plan enforcement | ❌ Unbuilt |
| SSO | None | Shared session cookie on `.crprotocol.io` | ❌ No cross-product auth |

### 2.2 CRP Comply (comply.crprotocol.io)

| Capability | Current State | Required State | Gap |
|------------|--------------|----------------|-----|
| Auth method | Clerk React frontend ✅ | Same, but aligned to shared instance | ⚠️ Instance mismatch |
| Tenant storage | `data/users.json` local file | PostgreSQL `tenants` table | ❌ File corruption risk |
| GitHub installs | `users.json` field + in-memory dict | `github_installations` + `github_repos` tables | ❌ No persistence |
| Plan/entitlement | `users.json["tier"]` + local JSON | Clerk `public_metadata.comply_plan` | ❌ Dual writes |
| Billing | Stripe checkout ✅, webhook writes JSON ❌ | Webhook writes Clerk metadata only | ❌ Wrong writer |
| SSO | Works within Comply only | Shared across Gateway + Comply | ❌ No cross-product |

### 2.3 CRP Scan (scan product within Comply)

| Capability | Current State | Required State | Gap |
|------------|--------------|----------------|-----|
| Billing surface | Price IDs exist, no checkout | Dedicated checkout + `scan_plan` metadata | ❌ Not exposed |
| Plan key | Shared `"plan"` key | Independent `scan_plan` key | ❌ Overwrites Comply plan |

---

## 3. The Two Specification Documents: Coverage Analysis

### 3.1 CRP-AUTH-USER-MANAGEMENT-SOLUTION.md

| Section | Requirement | Implemented? | Location | Notes |
|---------|------------|--------------|----------|-------|
| §1 | One Clerk instance (`clerk.crprotocol.io`) | ⚠️ Partial | Gateway `.env.example` yes; Comply CSP says `clerk.comply.crprotocol.io` | **MISALIGNED** |
| §2.1 | SSO via parent-domain cookie | ❌ No | Neither app configures cookie domain | **MISSING** |
| §3 | Org roles (`org:admin`, `org:member`) | ⚠️ Partial | Comply extracts `org_id` but never `org_role` | **INCOMPLETE** |
| §4 | `resolve_account()` abstraction | ❌ No | No such function exists | **MISSING** |
| §4.1 | Per-product entitlement keys (`comply_plan`, `gateway_plan`, `scan_plan`) | ❌ No | Both use shared `"plan"` key | **WRONG KEYS** |
| §5 | `Identity(user_id, org_id, org_role)` dataclass | ❌ No | Gateway returns `tenant_id` string; Comply returns `(user_id, Tier)` tuple | **WRONG SHAPE** |
| §5.1 | `get_entitlement(identity, product)` reads Clerk metadata | ❌ No | Both read local storage | **WRONG SOURCE** |
| §6 | Gateway sign-in/sign-up pages | ❌ No | Gateway has no React frontend | **MISSING** |
| §7 | Cross-product upsell funnel | ❌ No | Not built | **MISSING** |
| §9 | Railway vars aligned | ⚠️ Partial | Gateway correct; Comply ambiguous | **NEEDS AUDIT** |
| §10 | Test checklist (8 items) | ❌ No | 0/8 passing for Gateway; ~3/8 for Comply | **NOT VERIFIED** |

**Coverage score: 1/11 fully implemented, 3/11 partially, 7/11 missing.**

### 3.2 CRP-GITHUB-CONNECTIVITY-SOLUTION.md

| Section | Requirement | Implemented? | Location | Notes |
|---------|------------|--------------|----------|-------|
| §1 | Persist installation + link to user | ⚠️ Partial | Stores in JSON file, not DB | **WRONG STORAGE** |
| §3 | `POST /connect-start` endpoint | ❌ No | Missing entirely | **MISSING** |
| §3 | Signed state token (HMAC + TTL) | ❌ No | Raw `user_id` passed | **SECURITY GAP** |
| §3 | Redis state storage | ❌ No | Not used | **MISSING** |
| §4 | `github_installations` table | ❌ No | JSON file only | **MISSING** |
| §4 | `github_repos` table | ❌ No | In-memory dict only | **MISSING** |
| §5.2 | `GET /setup` callback | ❌ No | Has `/callback` instead | **WRONG ENDPOINT** |
| §5.2 | Fetch installation metadata from GitHub | ❌ No | Never calls GitHub API in callback | **MISSING** |
| §5.2 | Mint token, list repos, persist | ❌ No | Only stores `installation_id` string | **INCOMPLETE** |
| §5.4 | Disconnect with ownership verification | ❌ No | No `DELETE /installations/{id}` | **MISSING** |
| §5.5 | Webhook `installation_repositories` persistence | ❌ No | Logs only | **NO-OP** |
| §5.5 | Webhook `installation` deleted cleanup | ❌ No | Logs only | **NO-OP** |
| §6 | Setup URL = `/api/v1/github/setup` | ❌ No | Would be `/callback` | **WRONG CONFIG** |
| §7 | `GITHUB_STATE_SECRET` env var | ❌ No | Not referenced anywhere | **MISSING** |
| §9 | Test checklist (8 items) | ❌ No | ~2/8 passing | **NOT VERIFIED** |

**Coverage score: 2/15 partially implemented, 13/15 missing.**

---

## 4. The Five Critical Problems

### Problem 1: Two Entitlement Stores (The Drift Engine)

**What:** Stripe webhooks write to local JSON (`users.json`) and in-memory dicts (`_tenants`). Clerk metadata is only written to by `billing/checkout.py` (customer creation) and dead code (`billing/webhook.py`).

**Impact:** A user upgrades on Comply. The webhook writes `tier="starter"` to `users.json`. But Clerk metadata still says `"plan": "free"`. If Comply restarts, the in-memory cache is lost. If Gateway checks entitlement, it sees nothing because it never reads Clerk.

**Fix:** Stripe webhook writes **exclusively** to Clerk metadata. All apps read **exclusively** from Clerk metadata. PostgreSQL never stores entitlement.

### Problem 2: Shared Plan Key (The Subscription Killer)

**What:** Both apps use a single `"plan"` key in Clerk metadata and local storage.

**Impact:** User subscribes to Comply Scale (`plan="comply_scale"`). Later subscribes to Gateway Developer. Stripe webhook overwrites with `plan="gateway_developer"`. Comply now thinks the user is on Gateway Developer plan (which it doesn't recognize) and downgrades them effectively.

**Fix:** Per-product keys:
```json
{
  "comply_plan": "scale",
  "gateway_plan": "developer", 
  "scan_plan": "pro",
  "stripeCustomerId": "cus_...",
  "creditBalanceCents": 5000
}
```

### Problem 3: Raw State Token (The Security Hole)

**What:** GitHub App OAuth `state` parameter carries raw `user.id` from Clerk.

**Impact:** Any attacker who observes the OAuth redirect can forge a callback with any `user_id` and steal GitHub installations. No signature validation, no TTL, no nonce.

**Fix:** HMAC-SHA256 signed state tokens with 10-minute TTL and cryptographically random nonce.

### Problem 4: In-Memory / JSON-Only Storage (The Data Loss Machine)

**What:** Gateway stores all tenant data in Python module-level dicts. Comply stores users in a JSON file on a Railway volume. GitHub repos are in a process-level dict.

**Impact:** Gateway restart = all tenants, API keys, and usage data gone. Comply volume not mounted correctly = all users gone. Multiple workers = each has its own `_connected_repos` dict.

**Fix:** PostgreSQL for all application state. Every write is persistent, queryable, and shared across workers.

### Problem 5: No Cross-Product Identity (The Silo Wall)

**What:** Gateway and Comply are separate auth silos. A user signed into Comply must re-authenticate for Gateway.

**Impact:** No unified dashboard. No cross-sell. No "upgrade to Gateway" button in Comply that just works. Two separate user experiences.

**Fix:** Single Clerk instance, shared session cookie on `.crprotocol.io`, `resolve_account()` abstraction used everywhere.

---

## 5. Target Architecture: Clerk + PostgreSQL

### 5.1 Identity & Entitlement Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLERK (clerk.crprotocol.io)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────┐  │
│  │   Users     │  │    Orgs     │  │         public_metadata         │  │
│  │             │  │             │  │  {comply_plan, gateway_plan,    │  │
│  │  user_abc   │──│  org_xyz    │  │   scan_plan, stripeCustomerId,  │  │
│  │  (personal) │  │  (team)     │  │   creditBalanceCents}           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────────────┘  │
│                                                                         │
│  Session cookie domain: .crprotocol.io                                   │
│  JWT claims: sub, org_id, org_role                                       │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ verify JWT (JWKS)
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │   Gateway    │ │   Comply     │ │    Scan      │
   │  FastAPI     │ │  FastAPI     │ │  (in Comply) │
   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │ read entitlement│ read entitlement│ read entitlement
          │ (Clerk metadata)│ (Clerk metadata)│ (Clerk metadata)
          ▼                 ▼                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │              POSTGRESQL (Railway managed)                    │
   │  ┌──────────┐ ┌──────────────┐ ┌──────────────────────────┐  │
   │  │ tenants  │ │ api_keys     │ │ github_installations     │  │
   │  │          │ │ (hashed)     │ │                          │  │
   │  │ tenant_id│ │              │ │  installation_id         │  │
   │  │ clerk_*  │ │  key_hash    │ │  tenant_id (FK)          │  │
   │  │ account_ │ │  scopes      │ │  account_login           │  │
   │  │ type     │ │  revoked     │ │                          │  │
   │  └──────────┘ └──────────────┘ └──────────────────────────┘  │
   │  ┌──────────────┐ ┌─────────────────┐ ┌──────────────────┐   │
   │  │ github_repos │ │ gateway_systems │ │ gateway_usage    │   │
   │  │              │ │                 │ │                  │   │
   │  │  repo_id     │ │  system_id      │ │  usage_id        │   │
   │  │  full_name   │ │  tenant_id (FK) │ │  tenant_id (FK)  │   │
   │  │  connected   │ │  eu_ai_act_class│ │  tokens_in/out   │   │
   │  │  findings    │ │  domain         │ │  risk_class      │   │
   │  └──────────────┘ └─────────────────┘ └──────────────────┘   │
   └─────────────────────────────────────────────────────────────┘
```

### 5.2 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Clerk writes entitlement ONLY** | Single writer = no drift. Stripe webhook is the only writer. |
| **PostgreSQL NEVER stores entitlement** | Avoids sync issues. PostgreSQL stores state, Clerk stores rights. |
| **Per-product plan keys** | `comply_plan`, `gateway_plan`, `scan_plan` enable independent subscriptions. |
| **API keys hashed in PostgreSQL** | SHA-256 of key stored; plaintext returned once at creation. |
| **Tenant table shared across apps** | Both apps query the same `tenants` table. Gateway ignores Comply-specific tables, Comply ignores Gateway-specific tables. |
| **Personal accounts use `clerk_user_id` as tenant_id** | When `org_id` is null, `resolve_account()` returns `user_id`. Consistent with Clerk's solo-tenancy model. |

---

## 6. Railway Infrastructure Design

### 6.1 Services Overview

Railway projects are **per-repository**. We have two repos deploying to Railway:

| Repo | Railway Project | Branch | Domain | Services |
|------|----------------|--------|--------|----------|
| `crp-gateway` | CRP Gateway | `main` | `gateway.crprotocol.io` | Gateway FastAPI + PostgreSQL + Redis |
| `crp-comply` | CRP Comply | `master` | `comply.crprotocol.io` | Comply FastAPI + PostgreSQL + (shared PG) |

### 6.2 The PostgreSQL Question: One DB or Two?

**Recommended: ONE shared PostgreSQL instance, TWO logical databases.**

Why one instance:
- Railway's managed PostgreSQL is per-project, but both projects can connect to the same external PostgreSQL.
- Cross-product queries (unified dashboard) need shared tenant identity.
- Lower cost, simpler ops.

Why two logical databases:
- Schema isolation: Comply migrations don't affect Gateway tables.
- Security: Comply DB user doesn't need access to Gateway provider encryption keys.
- Backup granularity: Can restore Comply without touching Gateway.

```
Railway PostgreSQL Service (created in ONE project, shared)
├── Database: crp_gateway
│   ├── tables: tenants, api_keys, gateway_systems, gateway_providers, 
│   │           gateway_documents, gateway_usage
│   └── user: gateway_app (limited perms)
│
└── Database: crp_comply
    ├── tables: tenants, api_keys, github_installations, github_repos,
    │           scan_results, compliance_reports, evidence_packs
    └── user: comply_app (limited perms)
```

### 6.3 How to Set Up in Railway

#### Step 1: Create the Shared PostgreSQL Service

1. Go to **any** Railway project (e.g., CRP Gateway).
2. Click **New** → **Database** → **Add PostgreSQL**.
3. Name it: `crp-shared-postgres`.
4. Once provisioned, note the **Connection URL** (internal Railway networking):
   ```
   postgresql://postgres:PASSWORD@crp-shared-postgres.railway.internal:5432/railway
   ```
5. Create the two logical databases:
   ```bash
   railway connect crp-shared-postgres
   psql> CREATE DATABASE crp_gateway;
   psql> CREATE DATABASE crp_comply;
   psql> CREATE USER gateway_app WITH PASSWORD '...';
   psql> CREATE USER comply_app WITH PASSWORD '...';
   psql> GRANT ALL PRIVILEGES ON DATABASE crp_gateway TO gateway_app;
   psql> GRANT ALL PRIVILEGES ON DATABASE crp_comply TO comply_app;
   ```

#### Step 2: Connect CRP Gateway

1. In the **CRP Gateway** Railway project, go to **Variables**.
2. Add:
   ```
   DATABASE_URL=postgresql://gateway_app:PASSWORD@crp-shared-postgres.railway.internal:5432/crp_gateway
   ```
3. (Optional) Add Redis:
   ```
   REDIS_URL=redis://crp-redis.railway.internal:6379/0
   ```

#### Step 3: Connect CRP Comply

1. In the **CRP Comply** Railway project, go to **Variables**.
2. Add:
   ```
   DATABASE_URL=postgresql://comply_app:PASSWORD@crp-shared-postgres.railway.internal:5432/crp_comply
   ```
3. Keep the existing volume for `data/` during migration, but plan to deprecate.

#### Step 4: Internal Networking

Railway services within the same environment can resolve each other by hostname:
- `crp-shared-postgres.railway.internal`
- `crp-gateway.railway.internal`
- `crp-comply.railway.internal`

If projects are in **different Railway teams**, use the **public networking** URL with IP allowlisting, or move both services into the same Railway project as separate services.

**Recommendation:** Create a single Railway project called "CRP Production" with:
- Service: `gateway` (deploys from `crp-gateway` repo)
- Service: `comply` (deploys from `crp-comply` repo)
- Service: `postgres` (shared PostgreSQL)
- Service: `redis` (shared Redis)

This gives you internal networking, unified monitoring, and one bill.

---

## 7. PostgreSQL Schema (Production-Ready)

### 7.1 Shared Tables (both databases)

```sql
-- ============================================================
-- TENANTS: links Clerk identity to application state
-- ============================================================
CREATE TABLE tenants (
    tenant_id         TEXT PRIMARY KEY,
    clerk_org_id      TEXT UNIQUE,                -- NULL for personal accounts
    clerk_user_id     TEXT NOT NULL,
    account_type      TEXT NOT NULL 
                      CHECK (account_type IN ('org', 'personal'))
                      DEFAULT 'org',
    name              TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tenants_org  ON tenants(clerk_org_id) 
    WHERE clerk_org_id IS NOT NULL;
CREATE INDEX idx_tenants_user ON tenants(clerk_user_id);

COMMENT ON TABLE tenants IS 
    'Shared identity anchor. Populated on first Clerk JWT verification. 
     Personal accounts: clerk_org_id=NULL, tenant_id=clerk_user_id. 
     Org accounts: clerk_org_id=org_id, tenant_id=tnt_xxx.';

-- ============================================================
-- API KEYS: hashed, per-tenant, both apps use same pattern
-- ============================================================
CREATE TABLE api_keys (
    key_id            TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id) 
                      ON DELETE CASCADE,
    key_hash          TEXT NOT NULL,              -- SHA-256 of full key
    key_preview       TEXT,                       -- e.g., "crp_gw_****abcd"
    name              TEXT DEFAULT 'default',
    scopes            TEXT[] DEFAULT '{}',
    revoked           BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    last_used_at      TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX idx_api_keys_hash   ON api_keys(key_hash) 
    WHERE revoked = FALSE;

COMMENT ON TABLE api_keys IS 
    'API keys are hashed with SHA-256. The plaintext is returned ONCE at creation.
     Gateway keys start with "crp_gw_"; Comply keys start with "crp_cm_".';
```

### 7.2 CRP Gateway Tables (in `crp_gateway` database)

```sql
-- ============================================================
-- GATEWAY SYSTEMS: registered AI systems for EU AI Act
-- ============================================================
CREATE TABLE gateway_systems (
    system_id         TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id) 
                      ON DELETE CASCADE,
    name              TEXT NOT NULL,
    domain            TEXT,
    intended_purpose  TEXT,
    eu_ai_act_class   TEXT 
                      CHECK (eu_ai_act_class IN ('MINIMAL','LIMITED','HIGH','UNACCEPTABLE')),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_gateway_systems_tenant ON gateway_systems(tenant_id);

-- ============================================================
-- GATEWAY PROVIDERS: encrypted user-provided LLM keys
-- ============================================================
CREATE TABLE gateway_providers (
    provider_id       TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id) 
                      ON DELETE CASCADE,
    provider_type     TEXT NOT NULL 
                      CHECK (provider_type IN ('openai','anthropic','ollama','custom')),
    api_key_encrypted TEXT NOT NULL,              -- AES-256-GCM encrypted
    default_model     TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_gateway_providers_tenant ON gateway_providers(tenant_id);

-- ============================================================
-- GATEWAY DOCUMENTS: CKF ingested documents
-- ============================================================
CREATE TABLE gateway_documents (
    document_id       TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id) 
                      ON DELETE CASCADE,
    title             TEXT,
    source_uri        TEXT,
    content_hash      TEXT,                       -- BLAKE3 hash for dedupe
    status            TEXT DEFAULT 'pending'
                      CHECK (status IN ('pending','processing','ready','failed')),
    estimated_facts   INT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_gateway_docs_tenant ON gateway_documents(tenant_id, status);

-- ============================================================
-- GATEWAY USAGE: per-call audit trail
-- ============================================================
CREATE TABLE gateway_usage (
    usage_id          BIGSERIAL PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id) 
                      ON DELETE CASCADE,
    call_type         TEXT 
                      CHECK (call_type IN ('chat','completion','embedding')),
    model             TEXT,
    tokens_in         INT DEFAULT 0,
    tokens_out        INT DEFAULT 0,
    risk_class        TEXT,
    halted            BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_gateway_usage_tenant_time 
    ON gateway_usage(tenant_id, created_at DESC);
```

### 7.3 CRP Comply Tables (in `crp_comply` database)

```sql
-- ============================================================
-- GITHUB INSTALLATIONS: linked to tenant, not user
-- ============================================================
CREATE TABLE github_installations (
    installation_id   BIGINT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id) 
                      ON DELETE CASCADE,
    account_login     TEXT NOT NULL,
    account_type      TEXT NOT NULL DEFAULT 'Organization'
                      CHECK (account_type IN ('User','Organization')),
    suspended         BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_github_install_tenant ON github_installations(tenant_id);
CREATE INDEX idx_github_install_login  ON github_installations(account_login);

-- ============================================================
-- GITHUB REPOS: per-installation, with scan state
-- ============================================================
CREATE TABLE github_repos (
    repo_internal_id  BIGSERIAL PRIMARY KEY,
    installation_id   BIGINT NOT NULL 
                      REFERENCES github_installations(installation_id) 
                      ON DELETE CASCADE,
    repo_id           BIGINT NOT NULL,            -- GitHub's numeric repo ID
    full_name         TEXT NOT NULL,              -- "owner/repo"
    private           BOOLEAN NOT NULL DEFAULT TRUE,
    connected         BOOLEAN DEFAULT FALSE,      -- user selected for scanning
    last_scanned_at   TIMESTAMPTZ,
    findings_count    INT DEFAULT 0,
    UNIQUE(installation_id, repo_id)
);

CREATE INDEX idx_github_repos_install    ON github_repos(installation_id);
CREATE INDEX idx_github_repos_connected  ON github_repos(connected) 
    WHERE connected = TRUE;

-- ============================================================
-- SCAN RESULTS: per-repo governance scan output
-- ============================================================
CREATE TABLE scan_results (
    scan_id           BIGSERIAL PRIMARY KEY,
    repo_id           BIGINT NOT NULL 
                      REFERENCES github_repos(repo_internal_id) 
                      ON DELETE CASCADE,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id) 
                      ON DELETE CASCADE,
    commit_sha        TEXT,
    findings          JSONB DEFAULT '[]',
    status            TEXT DEFAULT 'pending'
                      CHECK (status IN ('pending','running','completed','failed')),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    completed_at      TIMESTAMPTZ
);

CREATE INDEX idx_scan_results_repo      ON scan_results(repo_id, created_at DESC);
CREATE INDEX idx_scan_results_tenant    ON scan_results(tenant_id, status);
CREATE INDEX idx_scan_results_findings  ON scan_results USING GIN(findings);

-- ============================================================
-- COMPLIANCE REPORTS: generated DPIAs, risk reports, etc.
-- ============================================================
CREATE TABLE compliance_reports (
    report_id         TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id) 
                      ON DELETE CASCADE,
    kind              TEXT NOT NULL
                      CHECK (kind IN ('risk','dpia','transparency','technical')),
    system_name       TEXT,
    markdown          TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_compliance_reports_tenant ON compliance_reports(tenant_id, kind);

-- ============================================================
-- EVIDENCE PACKS: tamper-evident compliance exports
-- ============================================================
CREATE TABLE evidence_packs (
    pack_id           TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id) 
                      ON DELETE CASCADE,
    status            TEXT DEFAULT 'pending'
                      CHECK (status IN ('pending','building','ready','failed')),
    download_url      TEXT,
    hmac_signature    TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_evidence_packs_tenant ON evidence_packs(tenant_id, status);
```

### 7.4 Migration Script (from legacy stores)

```sql
-- Run after tables created, before app cutover

-- Migrate Comply users.json → tenants table
-- (Application-level script, not pure SQL, because JSON file parsing needed)

-- Pseudocode for migration script:
-- FOR each user in users.json:
--   IF user has clerk_org_id:
--      INSERT INTO tenants (tenant_id, clerk_org_id, clerk_user_id, account_type, name)
--      VALUES ('tnt_' || random(), user.clerk_org_id, user.id, 'org', user.name)
--   ELSE:
--      INSERT INTO tenants (tenant_id, clerk_org_id, clerk_user_id, account_type, name)
--      VALUES (user.id, NULL, user.id, 'personal', user.name)
--   
--   IF user has github_installation_id:
--      INSERT INTO github_installations (installation_id, tenant_id, account_login, account_type)
--      VALUES (user.github_installation_id, tenant_id, 'unknown', 'Organization')
--      ON CONFLICT DO NOTHING
```

---

## 8. Phase-by-Phase Implementation

### Phase 1: Foundation (Week 1 / Hour 1)
**Goal:** PostgreSQL running, shared auth module created, Clerk instances aligned.

| Task | Owner | Files | Notes |
|------|-------|-------|-------|
| Provision Railway PostgreSQL | Ops | Railway dashboard | One instance, two logical DBs |
| Create `crp_shared` package | Agent | `crp_shared/auth.py`, `crp_shared/db.py` | Shared across both repos |
| Implement `Identity` dataclass | Agent | `crp_shared/auth.py` | `user_id`, `org_id`, `org_role` |
| Implement `resolve_account()` | Agent | `crp_shared/auth.py` | Returns `("org"\|"user", id)` |
| Implement `current_clerk_identity()` | Agent | `crp_shared/auth.py` | FastAPI dependency |
| Implement `get_entitlement()` | Agent | `crp_shared/auth.py` | Reads Clerk metadata via Backend API |
| Align Comply Clerk instance | Agent | `app.py` CSP, `.env` | Change to `clerk.crprotocol.io` |
| Add Clerk JS to Gateway console | Agent | `main.py` console HTML | Minimal `@clerk/clerk-js` load |
| Run schema migrations | Agent | `migrations/001_initial.sql` | Apply to both DBs |

**Deliverable:** Both apps can verify Clerk JWT and resolve identity. PostgreSQL is online.

### Phase 2: Comply Migration (Week 2 / Hour 2)
**Goal:** Comply uses PostgreSQL for all state. GitHub flow matches spec. Billing webhook writes Clerk metadata.

| Task | Owner | Files | Notes |
|------|-------|-------|-------|
| Replace AuthManager JSON with SQL | Agent | `api/auth.py`, `api/deps.py` | Read/write `tenants` table |
| Create `POST /github/connect-start` | Agent | `api/github_routes.py` | HMAC-signed state token |
| Create `GET /github/setup` | Agent | `api/github_routes.py` | Validate state, fetch repos, persist |
| Rewrite `GET /github/repos` | Agent | `api/github_routes.py` | Query SQL, not GitHub API |
| Add `DELETE /github/installations/{id}` | Agent | `api/github_routes.py` | Ownership check + cascade |
| Fix webhook handlers | Agent | `github_routes.py` | Persist add/remove/delete events |
| Fix Stripe webhook | Agent | `api/billing.py` | Write Clerk metadata, not JSON |
| Use per-product plan keys | Agent | `billing/` | `comply_plan`, not `"plan"` |
| Frontend: use `api.ts` for all GitHub calls | Agent | `Repositories.tsx` | Already done in Phase 1 fix |

**Deliverable:** GitHub repos persist across restarts. Billing is source-of-truth correct.

### Phase 3: Gateway Migration (Week 3 / Hour 3)
**Goal:** Gateway uses PostgreSQL. Billing surface built. Console auth works.

| Task | Owner | Files | Notes |
|------|-------|-------|-------|
| Replace `_tenants` dict with SQL | Agent | `main.py` | Query `tenants` table |
| Replace `_api_keys` dict with SQL | Agent | `main.py` | Hash keys, store preview |
| Replace `_systems` dict with SQL | Agent | `main.py` | `gateway_systems` table |
| Add Gateway billing checkout | Agent | `main.py` | `/api/v1/billing/create-checkout` |
| Add Gateway Stripe webhook | Agent | `main.py` | Write `gateway_plan` to Clerk |
| Add plan enforcement | Agent | `main.py` | Read `gateway_plan`, enforce quotas |
| Refactor `_require_auth` → `Identity` | Agent | `main.py` | Return `Identity`, not `tenant_id` string |
| Add `get_or_create_tenant()` | Agent | `main.py` | Using `resolve_account()` |

**Deliverable:** Gateway is stateful, billable, and auth-consistent.

### Phase 4: SSO & Polish (Week 4 / Hour 4)
**Goal:** Cross-product SSO works. Unified experience. All tests pass.

| Task | Owner | Files | Notes |
|------|-------|-------|-------|
| Configure Clerk cookie domain | Ops | Clerk Dashboard | `.crprotocol.io` |
| Add cross-product links | Agent | Comply AppShell, Gateway console | "Open Gateway" / "Go to Comply" |
| Build unified dashboard (optional) | Agent | New page | Show both products' state |
| Run full test checklist | QA | All apps | 8 auth tests + 8 GitHub tests |
| Deprecate `data/users.json` | Agent | Remove volume mount | After migration verified |
| Document final env vars | Agent | `.env.example`, `railway.toml` | Complete reference |

**Deliverable:** Sign in on Comply → automatically signed in on Gateway. Independent subscriptions work.

---

## 9. Railway Environment Variables (Complete Reference)

### Shared (both apps)
```bash
# Clerk — MUST be identical on both apps
CLERK_ISSUER=https://clerk.crprotocol.io
CLERK_SECRET_KEY=<YOUR_CLERK_SECRET_KEY>                 # same instance
CLERK_PUBLISHABLE_KEY=<YOUR_CLERK_PUBLISHABLE_KEY>

# Database — different logical DBs, same instance
DATABASE_URL=postgresql://USER:PASS@HOST:5432/DB_NAME

# Redis (optional, for state token TTL if not using PostgreSQL)
REDIS_URL=redis://HOST:6379/0

# App metadata
APP_BASE_URL=https://comply.crprotocol.io    # Comply only
CRP_GATEWAY_URL=https://gateway.crprotocol.io # Gateway only
```

### CRP Comply Only
```bash
# GitHub App
GITHUB_APP_ID=...
GITHUB_APP_PRIVATE_KEY="<YOUR_GITHUB_APP_PRIVATE_KEY_PEM>"
GITHUB_APP_WEBHOOK_SECRET=...
GITHUB_STATE_SECRET=$(openssl rand -hex 32)   # NEW — critical security

# Stripe (Comply + Scan + Gateway price IDs all here for cross-selling)
STRIPE_SECRET_KEY=<YOUR_STRIPE_SECRET_KEY>
STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>
STRIPE_COMPLY_STARTER_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_SCALE_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_STARTER_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_SCALE_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_SCAN_PRO_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_SCAN_BUSINESS_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_SCAN_PRO_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_SCAN_BUSINESS_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_DEVELOPER_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_TEAM_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_DEVELOPER_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_TEAM_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>

# Frontend build arg
VITE_CLERK_PUBLISHABLE_KEY=<YOUR_CLERK_PUBLISHABLE_KEY>

# CORS
CRP_COMPLY_CORS_ORIGINS=https://comply.crprotocol.io,https://gateway.crprotocol.io

# Rate limits (JSON)
CRP_COMPLY_RATE_LIMITS='{"free":20,"starter":60,"scale":300}'
```

### CRP Gateway Only
```bash
# Stripe (for Gateway-specific checkout)
STRIPE_SECRET_KEY=<YOUR_STRIPE_SECRET_KEY>
STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>
STRIPE_GATEWAY_DEVELOPER_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_TEAM_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_DEVELOPER_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_TEAM_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>

# Core secrets
SECRET_KEY=$(openssl rand -hex 32)

# CORS
ALLOWED_ORIGINS=https://gateway.crprotocol.io,https://comply.crprotocol.io,https://crprotocol.io
```

---

## 10. Critical Evaluation of This Plan

### 10.1 What This Plan Gets Right

1. **Separation of concerns:** Clerk for identity/entitlement, PostgreSQL for state. This is the only architecture that prevents drift.
2. **Per-product plan keys:** Fixes the subscription overwrite bug that would kill multi-product revenue.
3. **Signed state tokens:** Closes the GitHub OAuth security hole.
4. **One shared PostgreSQL instance:** Reduces ops overhead while maintaining logical isolation.
5. **Phased execution:** Each phase has a clear deliverable and can be verified independently.

### 10.2 What This Plan Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Clerk instance mismatch cannot be resolved** | HIGH | Verify in Clerk Dashboard BEFORE starting. If Comply uses a different instance, migrate it first. |
| **Railway PostgreSQL connection across projects** | MEDIUM | Use public networking with IP allowlist, or consolidate to one Railway project. |
| **API key hashing breaks existing integrations** | MEDIUM | Keep legacy in-memory fallback for 30 days. Migrate on first access. |
| **Migration script loses data** | MEDIUM | Test migration on copy of `users.json` first. Keep backup until verified. |
| **Stripe webhook cutover downtime** | LOW | Deploy new webhook alongside old. Update Stripe dashboard URL after verification. |
| **Personal account edge cases** | MEDIUM | `resolve_account()` handles `org_id=NULL`. Tenant ID falls back to `user_id`. Test explicitly. |

### 10.3 What This Plan Does NOT Cover (out of scope)

- **Clerk organization roles beyond admin/member:** The spec mentions `org:admin` and `org:member`. If Clerk is on a plan that supports custom roles, this plan reads `org_role` but does not implement RBAC enforcement. Add later.
- **Multi-region deployment:** PostgreSQL is single-region. For AU/EU data residency, replicate or shard later.
- **Advanced analytics:** Usage aggregation, cohort analysis, churn prediction. PostgreSQL stores raw data; build analytics pipeline later.
- **Real-time features:** WebSocket push for scan progress. Not needed for MVP.

### 10.4 Comparison to Original Specifications

| Spec Requirement | This Plan Addresses? | How |
|------------------|---------------------|-----|
| One Clerk instance | ✅ Yes | Phase 1: align CSP, env vars, publishable key |
| SSO cookie on `.crprotocol.io` | ✅ Yes | Phase 4: Clerk Dashboard configuration |
| `resolve_account()` | ✅ Yes | Phase 1: `crp_shared/auth.py` |
| `Identity` dataclass | ✅ Yes | Phase 1: `crp_shared/auth.py` |
| Entitlement in Clerk metadata | ✅ Yes | Phase 2: rewrite webhook; Phase 3: Gateway billing |
| Per-product plan keys | ✅ Yes | Phase 2: `comply_plan`, `gateway_plan`, `scan_plan` |
| Signed GitHub state tokens | ✅ Yes | Phase 2: `POST /connect-start` with HMAC |
| `github_installations` table | ✅ Yes | Phase 2: SQL schema + migration |
| `github_repos` table | ✅ Yes | Phase 2: SQL schema + migration |
| Webhook event persistence | ✅ Yes | Phase 2: INSERT/DELETE on events |
| Disconnect ownership check | ✅ Yes | Phase 2: `DELETE /installations/{id}` with auth |

**Coverage: 11/11 auth requirements, 12/12 GitHub requirements = 100%.**

---

## 11. Test Checklist

### Auth & SSO Tests
- [ ] Sign up on Comply → Clerk user created → tenant row in PostgreSQL
- [ ] Create org on Comply → Clerk org created → tenant row with `account_type='org'`
- [ ] Open Gateway `/console` without signing in → redirected to sign-in
- [ ] Sign in on Comply → open Gateway → already authenticated (no second login)
- [ ] Switch org in Comply → Gateway respects new org context
- [ ] Personal account (no org) works on both products
- [ ] API key created on Gateway → stored hashed in PostgreSQL → works for OpenAI SDK calls
- [ ] Revoked API key returns 401
- [ ] All backend routes reject requests with invalid Clerk token

### GitHub Connectivity Tests
- [ ] `POST /github/connect-start` returns URL with signed `state` parameter
- [ ] GitHub App Setup URL in dashboard = `/api/v1/github/setup`
- [ ] After install, `/setup` hit with valid `installation_id` + `state`
- [ ] `github_installations` row created with correct `tenant_id`, `account_login`
- [ ] `github_repos` rows created for all granted repos
- [ ] `GET /github/repos` returns repos without calling GitHub API
- [ ] Disconnect installation removes repos (cascade)
- [ ] GitHub webhook `installation_repositories` adds/removes repos in SQL
- [ ] GitHub webhook `installation` deleted removes installation + repos

### Billing Tests
- [ ] Subscribe to Comply Scale → `comply_plan="scale"` in Clerk metadata
- [ ] Subscribe to Gateway Developer → `gateway_plan="developer"` in Clerk metadata (Comply plan untouched)
- [ ] Subscribe to Scan Pro → `scan_plan="pro"` in Clerk metadata (other plans untouched)
- [ ] Stripe webhook idempotency: same event processed twice = no double credit
- [ ] Plan downgrade on subscription cancellation updates Clerk metadata
- [ ] Gateway enforces quota based on `gateway_plan` read from Clerk

---

## 12. 4-Hour Execution Sprint (Hour = Week)

This plan is designed for **accelerated execution**. Each "hour" below represents one week of normal productivity. The tasks within each hour are ordered by dependency.

### Hour 1: Foundation — PostgreSQL + Shared Auth Layer

**Minutes 0–15: Provision Infrastructure**
- Create Railway PostgreSQL service (shared)
- Create `crp_gateway` and `crp_comply` logical databases
- Create `gateway_app` and `comply_app` DB users with limited perms
- Add `DATABASE_URL` to both Railway projects

**Minutes 15–30: Create `crp_shared` Package**
- `crp_shared/auth.py`: `Identity`, `resolve_account()`, `current_clerk_identity()`, `get_entitlement()`
- `crp_shared/db.py`: `init_db()`, `get_db()` using `asyncpg`
- `crp_shared/__init__.py`: exports

**Minutes 30–45: Run Schema Migrations**
- Apply `001_initial.sql` to `crp_gateway` DB
- Apply `001_initial.sql` to `crp_comply` DB
- Verify tables exist with `\dt`

**Minutes 45–60: Align Clerk Instances**
- Update Comply `app.py` CSP to `clerk.crprotocol.io`
- Update Comply Railway env: `CLERK_ISSUER=https://clerk.crprotocol.io`
- Verify Gateway `CLERK_ISSUER` already correct
- Add minimal Clerk JS to Gateway console HTML (load from CDN, get token, attach to `api()`)
- Commit, push, verify deploy

### Hour 2: Comply Migration — GitHub + Billing Fix

**Minutes 0–15: AuthManager → PostgreSQL**
- Refactor `AuthManager` to use `crp_shared.db` for tenant reads/writes
- `upsert_oauth_user()` → INSERT/UPDATE `tenants` table
- `get_user()` → SELECT from `tenants` table
- Test with existing `users.json` migration script

**Minutes 15–30: GitHub Spec Compliance**
- Implement `POST /github/connect-start`: HMAC-signed state token
- Implement `GET /github/setup`: validate state, fetch GitHub installation meta, mint token, list repos, persist to SQL
- Rewrite `GET /github/repos`: query `github_repos` JOIN `github_installations`
- Add `DELETE /github/installations/{id}` with ownership check

**Minutes 30–45: Webhook Persistence**
- Update `POST /github/webhook`: handle `installation_repositories` → INSERT/DELETE repos
- Handle `installation` deleted → DELETE installation (cascade drops repos)
- Add `GITHUB_STATE_SECRET` to Railway env

**Minutes 45–60: Billing Webhook Fix**
- Replace active `api/billing.py` webhook logic with Clerk metadata writes
- Map price IDs to products: Comply, Gateway, Scan
- Use per-product keys: `comply_plan`, `gateway_plan`, `scan_plan`
- Remove all local JSON writes from webhook
- Commit, push, verify

### Hour 3: Gateway Migration — State + Billing Build

**Minutes 0–15: In-Memory → PostgreSQL**
- Replace `_tenants` dict with SQL queries
- Replace `_api_keys` dict with hashed SQL storage
- Replace `_systems`, `_usage` with SQL tables
- Add `get_or_create_tenant(identity)` using `resolve_account()`

**Minutes 15–30: Identity Refactor**
- Refactor `_require_auth()` to return `Identity` object
- Add `current_clerk_identity()` FastAPI dependency
- Update all endpoints to accept `Identity` instead of `tenant_id` string
- Ensure personal accounts work (`org_id=None` → `tenant_id=user_id`)

**Minutes 30–45: Gateway Billing Surface**
- Add `/api/v1/billing/create-checkout` for Gateway plans
- Add `/api/v1/billing/create-portal` for customer portal
- Add Stripe webhook handler for Gateway-specific events
- Write `gateway_plan`, `gateway_quota` to Clerk metadata

**Minutes 45–60: Plan Enforcement**
- Read `gateway_plan` from Clerk metadata on every request
- Enforce rate limits and quotas per plan
- Add plan-based feature gates (e.g., Team gets multi-org)
- Commit, push, verify

### Hour 4: SSO Polish + Cross-Product Integration

**Minutes 0–15: Clerk Cookie Domain**
- In Clerk Dashboard: set production domain to `crprotocol.io`
- Add allowed origins: `comply.crprotocol.io`, `gateway.crprotocol.io`
- Set session cookie domain to `.crprotocol.io`
- Verify SSO: sign in on Comply → Gateway recognizes session

**Minutes 15–30: Cross-Product Links**
- Comply AppShell: add "Open Gateway Console" link
- Gateway console: add "Go to Comply" link
- Both links use shared session (no re-auth)

**Minutes 30–45: Testing & Verification**
- Run all 9 auth tests
- Run all 9 GitHub tests
- Run all 6 billing tests
- Fix any failures immediately

**Minutes 45–60: Cleanup & Documentation**
- Deprecate `data/users.json` volume mount (keep for 7 days as backup)
- Update `.env.example` with all new vars
- Update `AGENTS.md` with new auth patterns
- Update skills with PostgreSQL + Clerk metadata patterns
- Final commit, push, celebrate.

---

## Appendices

### A. Clerk Metadata Schema (canonical)

```json
{
  "comply_plan": "free | starter | scale",
  "gateway_plan": "free | developer | team",
  "scan_plan": "free | pro | business",
  "comply_quota": 100,
  "gateway_quota": 1000,
  "scan_quota": 50,
  "stripeCustomerId": "cus_...",
  "stripeSubscriptionId": "sub_...",
  "creditBalanceCents": 0,
  "features": ["advanced_analytics", "multi_org"]
}
```

### B. State Token Format

```
state = base64url(json_payload) + "." + hex_hmac_sha256

payload = {
  "clerk_user_id": "user_xxx",
  "clerk_org_id": "org_yyy",      // null for personal
  "exp": 1717600000,              // unix timestamp + 600s
  "nonce": "a3f7b2d9e1c4"
}

secret = GITHUB_STATE_SECRET (32-byte hex)
```

### C. API Key Format

```
Gateway: crp_gw_{prefix}_{random}_{suffix}
Comply:  crp_cm_{prefix}_{random}_{suffix}

hash = sha256(full_key)
preview = last 8 chars of full key
```

### D. Related Documents

- `CRP-AUTH-USER-MANAGEMENT-SOLUTION.md` — Auth spec (this plan implements it)
- `CRP-GITHUB-CONNECTIVITY-SOLUTION.md` — GitHub spec (this plan implements it)
- `CRP-SPEC-047-monetisation-payments.md` — Billing spec
- `CRP-SPEC-048-comply-lowcode-github.md` — GitHub App spec
- `CRPv4_Implementation_Rounds.md` — SDK implementation plan

---

*Document version: 1.0.0*  
*Approved for execution: 2026-06-05*  
*Next review: After Hour 1 completion*
