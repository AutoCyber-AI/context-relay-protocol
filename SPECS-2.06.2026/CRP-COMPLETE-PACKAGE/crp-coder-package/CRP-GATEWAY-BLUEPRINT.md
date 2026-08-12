# CRP Gateway — Implementation Blueprint

**Companion to:** CRP-SPEC-016 (Gateway Service contract)
**Purpose:** SPEC-016 defines WHAT the Gateway offers (endpoints, quotas,
onboarding). This document defines HOW to build it — the architecture,
request lifecycle, components, data stores, and deployment. Hand both to
the team building the hosted Gateway.

**What the Gateway is, in one line:** the hosted reverse proxy that turns
"point your app at our URL" into full CRP governance + positioning on
every AI call — the Cloudflare-for-AI-governance layer.

---

## 1. THE REQUEST LIFECYCLE (the heart of the Gateway)

Every request flows through this pipeline. This is the single most
important diagram for the implementer.

```
┌─ INBOUND ────────────────────────────────────────────────────────┐
│ 1. TLS termination                                               │
│ 2. Authenticate API key → resolve tenant + plan + scopes         │
│ 3. Rate-limit check (per-key, SPEC-016 §13) → 429 if exceeded    │
│ 4. Quota check (daily/monthly, plan tier) → 402 if exhausted     │
│ 5. Parse request: extract CRP-* request headers + the LLM payload │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─ GOVERNANCE PREP (Core, <50ms) ──────────────────────────────────┐
│ 6. Resolve session token → load session state (CSO, Coverage Set,│
│    Turn Log, Scratch Buffer) OR create new session                │
│ 7. Resolve Safety Policy (request header > key > system > tier)   │
│ 8. Determine context mode (zero-ckf / partial / full, SPEC-017)   │
│ 9. Injection-attack scan on inputs (SPEC-015)                     │
└──────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │  STL active?  (ask vs complete) │
              └───────────────┬───────────────┘
         NO (complete)        │        YES (ask)
              │               │               │
┌─ SINGLE CALL ─┐    ┌─ POSITIONED EXECUTION (STL, SPEC-031) ──────┐
│ 10a. Build    │    │ 10b. Classify task → operations             │
│   envelope    │    │ 10c. Propose depth                          │
│   (CDR/CDGR)  │    │ 10d. For each operation:                    │
│ 11a. Strip    │    │       build Operation Frame (minimal)       │
│   CRP headers │    │       position model (1 focused call)       │
│ 12a. Dispatch │    │       verify (DPE) → integrate (CSO)        │
│   to provider │    │       renegotiate depth if needed           │
│               │    │ 10e. Assemble final response                │
└───────┬───────┘    └──────────────────┬──────────────────────────┘
        └───────────────┬───────────────┘
                        │
┌─ GOVERNANCE ANALYSIS (Core, <50ms) ──────────────────────────────┐
│ 13. DPE 13-stage analysis on output (SPEC-005)                    │
│ 14. Safety Policy enforcement:                                    │
│       PASS → continue                                            │
│       HALT → HTTP 451 + halt body + audit event (STOP HERE)      │
│ 15. Update CSO (preservation-verified, SPEC-030)                  │
│ 16. Extend HMAC audit chain (SPEC-011)                            │
│ 17. Update Coverage Set / Turn Log / Scratch Buffer               │
│ 18. Decrement safety budget (multi-agent, SPEC-012)               │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─ OUTBOUND ───────────────────────────────────────────────────────┐
│ 19. Emit all CRP-* response headers (SPEC-002)                    │
│ 20. Stream audit event to CRP Comply (if connected)              │
│ 21. Re-issue session token (CRP-Set-Session)                     │
│ 22. Return response to caller                                    │
└──────────────────────────────────────────────────────────────────┘
```

**Critical invariant:** Step 11 (strip CRP headers before provider) is
Axiom 4. NO CRP-* header may reach the LLM provider. Build this as a
hard allowlist filter on the outbound provider request.

---

## 2. COMPONENT ARCHITECTURE

```
┌──────────────────────────────────────────────────────────────────┐
│                      CRP GATEWAY                                  │
│                                                                   │
│  ┌────────────────┐   API FRONTEND (stateless, horizontally       │
│  │ API Frontend   │   scalable)                                   │
│  │ - TLS, auth    │   - OpenAI-compatible + CRP-native endpoints  │
│  │ - rate/quota   │   - request parsing, header handling          │
│  │ - routing      │                                               │
│  └───────┬────────┘                                               │
│          │                                                        │
│  ┌───────▼────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Governance     │  │ STL Engine   │  │ Provider Router      │ │
│  │ Core           │  │ (positioning)│  │ + Key Vault          │ │
│  │ - DPE workers  │  │ - classify   │  │ - OpenAI/Anthropic/  │ │
│  │ - Safety Policy│  │ - depth      │  │   Gemini/Bedrock/    │ │
│  │ - CSO manager  │  │ - frames     │  │   local              │ │
│  │ - HMAC chain   │  │ - assemble   │  │ - failover           │ │
│  └───────┬────────┘  └──────┬───────┘  └──────────┬───────────┘ │
│          │                  │                     │             │
│  ┌───────▼──────────────────▼─────────────────────▼───────────┐ │
│  │ STATE LAYER (per-tenant isolated)                          │ │
│  │  - CKF: vector index (HNSW) + graph + fact store          │ │
│  │  - Session store: CSO, Coverage Set, Turn Log, Scratch     │ │
│  │  - Audit store: append-only HMAC-chained event log        │ │
│  │  - Provider key vault (encrypted, per-tenant)             │ │
│  └────────────────────────────────────────────────────────────┘ │
│          │                                                        │
│  ┌───────▼────────┐  ┌──────────────┐                            │
│  │ Comply Webhook │  │ Metrics /    │                            │
│  │ Dispatcher     │  │ Billing      │                            │
│  └────────────────┘  └──────────────┘                            │
└──────────────────────────────────────────────────────────────────┘
```

### Component responsibilities

| Component | Owns | Scaling |
|-----------|------|---------|
| API Frontend | auth, routing, rate/quota, header I/O | stateless, scale horizontally |
| Governance Core | DPE, Safety Policy, CSO, HMAC | stateless workers; CPU-bound (embeddings/NLI) |
| STL Engine | task classification, positioning, assembly | stateless; orchestrates provider calls |
| Provider Router | provider selection, key vault, failover | stateless |
| State Layer | CKF, sessions, audit, keys | stateful, per-tenant partitioned |
| Comply Dispatcher | stream audit → CRP Comply | async queue |
| Metrics/Billing | usage counting, quota enforcement | async aggregation |

---

## 3. THE STATE LAYER (most important to get right)

### 3.1 Per-tenant isolation (hard requirement, SPEC-016 §4)

Every store is partitioned by tenant. No query ever crosses tenants.
HNSW indexes are per-tenant. Audit HMAC keys are per-tenant. Provider
keys are per-tenant encrypted. This is architectural, not a filter.

### 3.2 The four session-scoped stores

These live together, keyed by session_id, loaded at step 6 of the
lifecycle:

```
SessionState {
  cso:            CognitiveStateObject    # SPEC-030 — the relay primitive
  coverage_set:   CoverageEntry[]         # SPEC-024 — what's been covered
  turn_log:       Turn[]                  # SPEC-028 — conversation history
  scratch_buffer: ScratchEntry[]          # SPEC-029 — tool outputs
  safety_budget:  float                   # SPEC-012 — multi-agent
  ngram_blacklist: set                    # SPEC-024 §5 — output guard
  embedding_model_id: string              # SPEC-027 §2.5 — consistency
}
```

The session token (SPEC-007) carries a signed reference to this state
(or the compact state itself for stateless relay). The Gateway loads it
on each request and re-issues it on response.

### 3.3 The CKF (persistent, per-tenant)

```
- Vector index: HNSW (per-tenant)
- Graph: similarity edges + Leiden communities (for CDGR, SPEC-025)
- Fact store: fact nodes with provenance, recency, importance
- Source registry: ingested documents
```

Document ingestion (SPEC-016 §9) runs async: upload → chunk → extract →
embed → index → community-detect. The CKF state hash drives the ETag
(SPEC-003 conditional dispatch).

### 3.4 The audit store (append-only)

HMAC-chained event log, per-tenant, write-once. Never updated in place.
Streams to CRP Comply via the webhook dispatcher. Retention per plan
tier (SPEC-011 §5.3).

---

## 4. ENDPOINTS TO BUILD (from SPEC-016 §2)

### Inference (OpenAI-compatible — the drop-in path)
```
POST /v1/chat/completions      ← Level 0 governance (complete)
POST /v1/completions
POST /v1/embeddings            ← pass-through + audit only
GET  /v1/models
```

### CRP-native (the full power)
```
POST /crp/v3/ask               ← Level 1 — STL positioning pipeline
POST /crp/v3/dispatch          ← explicit strategy control
GET  /crp/v3/session/{id}
DELETE /crp/v3/session/{id}
POST /crp/v3/verify-chain      ← audit integrity
```

### Knowledge
```
POST /crp/v3/ckf/documents     ← ingest
GET  /crp/v3/ckf/documents
DELETE /crp/v3/ckf/documents/{id}   ← GDPR erasure
GET  /crp/v3/ckf/state         ← ETag, stats, mode
```

### Admin
```
POST /crp/v3/admin/systems     ← register AI system (EU AI Act class)
POST /crp/v3/admin/keys
PUT  /crp/v3/admin/policies
GET  /crp/v3/admin/quotas
```

### Well-known / health
```
GET /.well-known/crp-gateway.json   ← capability advertisement
GET /health
```

---

## 5. THE THREE LATENCY BUDGETS (enforce these)

| Path | Budget | What runs |
|------|--------|-----------|
| **Core governance** (`/v1/*`, complete) | < 50ms overhead | envelope build (CDR <1ms, CDGR <2ms) + DPE (embeddings/NLI) + policy + HMAC. NO extra inference. |
| **STL positioning** (`/crp/v3/ask`) | sum of N operation calls | one focused model call per operation; total is task-dependent but each call is small/fast |
| **Amplification** (opt-in only) | seconds–minutes, async | multi-pass; ONLY with CRP-Amplification-Mode; never on Core path |

The Core path budget is sacred. Profile it. If DPE exceeds 50ms, the
embeddings/NLI models are too large — use distilled cross-encoders.

---

## 6. PROVIDER ROUTING & KEY VAULT (SPEC-016 §10)

```
Request model "gpt-4o"     → OpenAI
Request model "claude-*"   → Anthropic
Request model "gemini-*"   → Google
Request model "local:*"    → tenant's configured local endpoint
No model specified         → tenant default
Provider 5xx/timeout       → failover provider
```

Two key modes:
- **Vaulted:** provider key encrypted per-tenant (AES-256-GCM), Gateway
  uses it. Developer never re-sends it.
- **BYOK:** developer sends provider key per-request in `CRP-Provider-Key`
  header; Gateway uses it, never stores it. (SPEC-016 §10.3)

---

## 7. ONBOARDING (the day-one funnel, SPEC-016 §3 + SPEC-017)

The conversion-critical flow. Build it as a < 5-minute path:

```
1. Sign up (email/OAuth) → tenant provisioned (SPEC-016 §4.2)
2. Region selected → data residency set
3. Provider key pasted OR "BYOK in code" chosen
4. AI system named + domain picked → EU AI Act auto-classified
5. crp_gw_ key issued + code snippet shown
6. First call works in zero-CKF mode (safety active immediately)
   → CRP-Context-Mode: zero-ckf + CRP-Onboarding-Hint emitted
7. "Ingest documents to unlock context features" CTA
```

Pre-populate from GitHub Scan referrals (`?source=github-scan`): provider,
framework, finding count already filled (SPEC-016 §3.3). Turns signup from
"start from scratch" into "confirm what we know."

---

## 8. DEPLOYMENT

### 8.1 Multi-region (SPEC-016 §1.1)
```
gateway.crprotocol.io        → geo-routed to nearest
  ├── eu.gateway...  (Frankfurt + Dublin)   ← EU AI Act data residency
  ├── au.gateway...  (Sydney + Melbourne)   ← home region
  ├── us.gateway...  (Virginia + Oregon)
  └── uk.gateway...  (London)
```

### 8.2 What scales how
- API Frontend, Governance Core, STL Engine, Provider Router: **stateless**,
  autoscale on CPU/request load.
- State Layer: **stateful**, per-tenant partitioned; scale by sharding
  tenants across nodes. CKF vector indexes are the memory-heavy part.
- DPE workers: CPU-bound (embeddings + NLI). The likely bottleneck.
  Pool them; use distilled models; cache embeddings.

### 8.3 Free tier on cheap infra
Free tier (100 calls/day) can run DPE on CPU. Paid tiers get GPU-backed
DPE worker pools for lower latency. This keeps free-tier cost near zero
while funding the funnel.

---

## 9. BUILD ORDER FOR THE GATEWAY

```
Phase 1 — Minimum viable governed proxy:
  API Frontend (auth, /v1/chat/completions) + Provider Router
  + Governance Core (DPE + Safety Policy + HMAC) + audit store
  → delivers Level 0 governance. THE revenue-critical MVP.

Phase 2 — Knowledge + quality:
  State Layer CKF (HNSW + graph) + ingestion + CDR/CDGR
  + session stores (CSO, Coverage Set)
  → delivers Level 1 quality via /crp/v3/ask (basic, no STL yet)

Phase 3 — Positioning:
  STL Engine (classify, depth, frames, assemble)
  + multi-horizon (Turn Log, Scratch Buffer)
  → delivers the full positioning experience

Phase 4 — Scale + products:
  Multi-region, Comply webhook streaming, tiering/billing,
  amplification workers (opt-in, isolated)
```

Phase 1 alone is a sellable product (governed AI proxy). Ship it, get
the first customers, then build Phase 2+ on real usage.

---

## 10. RELATIONSHIP TO THE SDK

The SDK (CRP-SDK-REFERENCE) is the client; the Gateway is the server.

```
client.complete()  → POST /v1/chat/completions   (Level 0)
client.ask()       → POST /crp/v3/ask             (Level 1, STL)
client.ingest()    → POST /crp/v3/ckf/documents
client.audit.*     → /crp/v3/verify-chain etc.
client.compliance.*→ /crp/v3/admin + Comply
```

The SDK can also run **fully local** (no Gateway) using the same protocol
internally — the Gateway is the hosted, scaled, multi-tenant deployment of
the same engine. Self-hosted = SDK does it all in-process; hosted = SDK
talks to the Gateway. Same protocol, two deployment modes.

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*
