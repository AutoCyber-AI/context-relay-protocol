# CRP Comply — Comprehensive Upgrade Report

**Date:** 2026-06-05  
**Scope:** Local LLM, Knowledge Base / CKF, Recipes, Onboarding, Session Management, Notifications, Security  
**Audited by:** Kimi Code CLI (harsh critic mode)

---

## Executive Summary

CRP Comply has a **sophisticated but incomplete** foundation. The CKF is real, the agent loop is functional, and the recipe engine is declarative and powerful. However, **11 security vulnerabilities** exist in the local LLM worker path, **billing notifications silently fail** due to a missing function, **sessions last 7 days with no idle timeout**, and the **recipe UX is confusing** because two disconnected surfaces (Workspace + Agent Chat) compete for the same user mental model.

| Area | Grade | Status |
|------|-------|--------|
| Local LLM Security | D+ | 11 vulnerabilities, including key leakage and no Origin validation |
| Knowledge Base / CKF | B+ | CKF is real and active, but CRP dispatch backbone is bypassed |
| Recipes | C | Powerful backend, confusing frontend, no scheduling, no multi-stakeholder |
| Onboarding | C+ | System-centric flow, stale marketing copy, missing compliance-officer workflow |
| Session Management | D | 7-day sessions, no idle timeout, no step-up auth, no revocation |
| Notifications | D+ | Dispatcher exists but `emit_notification` is missing; email only for free assessment |
| Cryptographic Storage | C | API keys hashed (BLAKE3), but JWT audit trail falls back to "dev" key |

---

## 1. Local LLM Connection — Security Audit

### Architecture (Correct)
The SDK worker uses an **outbound WebSocket over `wss://`** to the hosted backend. The local LLM (LM Studio / Ollama) binds to `localhost` by default. This is the right architecture for NAT traversal — no inbound firewall holes.

### 11 Security Vulnerabilities

| # | Severity | Vulnerability | Location | Fix |
|---|----------|---------------|----------|-----|
| 1 | **CRITICAL** | Query-string `?api_key=` leaks keys to reverse-proxy logs (Railway, Cloudflare, nginx) | `worker_ws.py:60` | Remove query-string auth; header-only |
| 2 | **CRITICAL** | No WebSocket `Origin` validation. Malicious web page can open WS to relay. | `worker_ws.py` | Add `Origin` whitelist check |
| 3 | **HIGH** | No rate limiting on `/agent/worker`. Unbounded connections per user/IP. | `worker_ws.py` | Add per-user max 2 workers, per-IP rate limit |
| 4 | **HIGH** | In-process registry breaks multi-replica. Worker on Replica A, dispatch on Replica B = fail. | `worker_registry.py:34` | Redis-backed registry for production |
| 5 | **HIGH** | Streaming queue silently drops chunks when full (`maxsize=4096`). | `worker_registry.py:246` | Add back-pressure / pause worker read |
| 6 | **HIGH** | Worker downloads entire response before size cap check. OOM possible. | `sdk/worker.py:240` | Use `httpx` streaming limits |
| 7 | **MEDIUM** | Injection scan only checks last tool message; swallows all exceptions. | `worker_adapter.py:176` | Scan ALL messages; fail open on scan error |
| 8 | **MEDIUM** | `ProviderStore` JSON file has no locking. Concurrent writes corrupt file. | `provider.py:143` | Atomic write (temp + `os.replace`) |
| 9 | **MEDIUM** | Audit trail JWT signed with `"dev"` if env var missing. Silent swallow on failure. | `worker_ws.py:133` | Fail closed; require secret; log at ERROR |
| 10 | **MEDIUM** | Stolen API key = full impersonation. No mTLS, device fingerprint, or HMAC per-session. | — | Add per-session HMAC + device fingerprint |
| 11 | **LOW** | WS streaming timeout race: chunk every 9s bypasses deadline indefinitely. | `worker_registry.py:369` | Track absolute elapsed time, not just poll timeout |

### Is the Local LLM Isolated from the Public Internet?

**Yes, but with caveats:**
- The **worker→backend** path is encrypted (`wss://`) and authenticated (API key).
- The **backend→worker** path has no per-session HMAC, so a stolen key allows prompt injection.
- The **worker→local LLM** path is `http://localhost` (unencrypted but loopback-only). If user configures LM Studio on `0.0.0.0`, LAN hosts can reach it directly.
- `--allow-lan` forwards to RFC1918 addresses without requiring HTTPS on the local segment.

**Recommendation:** The local LLM connection is architecturally sound but needs the 11 fixes above before it can be marketed as "securely isolated."

---

## 2. Knowledge Base, CKF & CRP Architecture

### What Exists (The Good)

| Component | Status | Evidence |
|-----------|--------|----------|
| **CKF Graph** | ✅ Active | `ckf_corpus.py` — HNSW + Leiden community detection, 50k facts |
| **RAG Retrieval** | ✅ Active | `rag/index.py` — SQLite + NumPy brute-force cosine, BAAI/bge-small-en |
| **Federated Fabric** | ✅ Active | `federated_fabric.py` — parallel tenant + corpus CKF queries |
| **Extraction Pipeline** | ✅ Active | 6-stage: regex → statistical → NER → UIE → RST → LLM-assisted |
| **Contradiction Detection** | ✅ Active | `crp_integration.py:165-211` |
| **Compliance Tools** | ✅ Active | 10+ tools: `query_regulation`, `classify_ai_act_risk`, `recall_facts`, etc. |
| **Reflector Quality Gate** | ✅ Active | `reflector.py` — citation verification, confidence floor 0.6 |

### What's Missing (The Bad)

| Gap | Severity | Description |
|-----|----------|-------------|
| **CRP dispatch backbone dormant** | **CRITICAL** | `crp.Client.dispatch()` is bypassed on the hot path. The bespoke iterative loop handles all LLM calls. CRP's auto-ingest, envelope negotiation, continuation manager, and unbounded-context engine are never reached. |
| **No 5-primitive storage engine** | HIGH | SPEC-035 defines rolling log, hot cache, inverted index, scratch buffer, and graph. Only the graph (CKF) exists. |
| **No CDGR / CDR in agent loop** | HIGH | Coverage Differential Retrieval (SPEC-024) and Graph Walk Retrieval (SPEC-025) are defined but not used in the agent loop. |
| **Bespoke ledger duplicates CKF** | MEDIUM | `CrpMessageLedger` manually implements warm-store fact extraction instead of using `crp.ckf.ContextualKnowledgeFabric` natively. |
| **ISO content surrogate-only** | MEDIUM | ISO 42001/22989 chunks are copyright-redacted to title+clause ID. The LLM must rely on parametric knowledge rather than retrieved text. |
| **No specialized document agents** | HIGH | There is no "DPIA Agent", "Risk Assessment Agent", or "Annex IV Agent" — just one `ComplianceAgent` with tools. Each deliverable type should have a dedicated sub-agent with domain-specific retrieval and analysis. |

### What Should Be Built: AI Governance Expert System

The current system is a **single agent with tools**. It should become a **multi-agent system**:

```
┌─────────────────────────────────────────────┐
│         AI Governance Orchestrator           │
│  (routes tasks, manages session state)       │
└─────────────┬───────────────────────────────┘
              │
    ┌─────────┼─────────┬──────────┬──────────┐
    ▼         ▼         ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌─────────┐
│DPIA   │ │Risk   │ │Annex  │ │Conform│ │Evidence │
│Agent   │ │Agent  │ │IV     │ │ity    │ │Pack     │
│        │ │       │ │Agent  │ │Agent  │ │Agent    │
└───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └────┬────┘
    │         │         │         │          │
    └─────────┴─────────┴─────────┴──────────┘
                          │
              ┌───────────▼────────────┐
              │  Shared Knowledge Layer │
              │  (CKF + CDR + CDGR)     │
              └─────────────────────────┘
```

Each agent:
- Has its own system prompt tailored to the deliverable type
- Uses domain-specific retrieval (e.g., Annex IV agent queries only Annex IV corpus + technical docs)
- Can dispatch as a CRP sub-agent with isolated context
- Returns structured output to the orchestrator

### Migration Path
1. **Phase 1:** Make `crp.Client.dispatch*()` the sole LLM entry point (retire bespoke loop)
2. **Phase 2:** Implement 5-primitive storage engine (Redis for hot cache, S3 for scratch)
3. **Phase 3:** Add pluggable CKF backends (pgvector, Qdrant)
4. **Phase 4:** Build specialized deliverable agents as CRP sub-agents

---

## 3. Recipes System

### What Exists (The Good)
- **30 built-in YAML recipes** covering EU AI Act, GDPR, ISO 42001, NIST AI RMF
- **Declarative pipeline:** YAML → tailoring → human inputs → LLM drafting → markdown + JSON + derivation manifest
- **Interview branches:** Conditional Socratic question trees in YAML
- **Citation extraction:** Deterministic regex extracts `Article N`, `Annex N`, `Clause N`
- **Provenance:** Every paragraph has `chunk_id` and derivation manifest

### What's Confusing (The Bad)

| Problem | Evidence | Impact |
|---------|----------|--------|
| **Two modes for same output** | `Draft.tsx` has Workspace (deterministic) + Agent Chat (conversational) tabs | Users don't know which to use |
| **Fake streaming** | `Workspace.tsx:118-123` — client-side animation, backend is blocking | Users think real-time drafting is happening |
| **Dead "Save to vault" button** | `Workspace.tsx:614-626` — tooltip says backend endpoint not ready | Deliverables aren't persisted automatically |
| **Human inputs scattered** | `required_inputs`, `ask_when_unknown`, `interview_branches` all render as form fields in left rail | User can't tell why a question is being asked |
| **No unified interview bot** | Agent Chat is seeded with a prompt; it doesn't consume YAML branch definitions | The LLM improvises instead of following the recipe script |
| **No scheduling** | No "remind me in 2 days" or "interview due before deployment" | Compliance deadlines are missed |
| **No multi-stakeholder** | No role-based routing (DPO, Legal, Engineering) | One person answers everything |

### Ideal Flow

```
1. User selects recipe
   → System shows applicability verdict + skipped sections rationale
   
2. Unified Interview (conversational, not form-based)
   → Recipe-driven bot consumes YAML interview_branches directly
   → One question at a time, cites the regulation article
   → Answers persisted to CKF (never ask twice across recipes)
   → Multi-stakeholder: assigns questions to roles
   
3. One-Click Drafting
   → Auto-runs when all questions resolved
   → Server-side SSE streaming (real, not fake)
   → Sections appear in binder as they complete
   
4. Vault Persistence + Review
   → Auto-saves to ReportStore
   → Stakeholder review workflow: assign, sign-off, version
   → Staleness detection when profile/corpus changes
   
5. Notifications & Scheduling
   → Schedule interviews (e.g., "FRIA review due Aug 15")
   → Reminders for unanswered questions
   → Escalation for high-priority items (Art 5 prohibited practice)
```

---

## 4. Onboarding

### Current Flow (System-Centric)
1. Describe your business → AI pre-fill
2. Your role (provider/deployer/etc.)
3. Where you operate (jurisdictions)
4. What you build (system category, Annex III row)
5. Data & modalities (9 boolean toggles)
6. Certifications (ISO 42001, ISO 27001, SOC 2)

### Problems
- **Missing audit context:** No "when is your conformity assessment date?" or "which notified body?"
- **Missing team discovery:** No "do you have a DPO?" or "existing risk register format?"
- **Missing evidence inventory:** Can't upload existing policies, pen-test reports, model cards
- **Missing gap assessment:** Doesn't show a checklist of required deliverables for user's actual context
- **Stale marketing copy:** Product page claims "byte-for-byte reproducible" (false), "continuous scraper fleet" (overstated), pricing in `index.html` doesn't match `Pricing.tsx`

### Ideal Flow (Compliance-Officer-Centric)
1. **Audit context:** Assessment date, notified body, auditor contact
2. **Team & process:** DPO? Existing ISO 27001? Risk register format?
3. **Evidence inventory:** Upload existing policies, pen-tests, model cards
4. **Gap assessment:** Checklist of required deliverables for actor + jurisdiction + audit date
5. **LLM setup with privacy guardrails:** Default to local LM Studio with data-residency notice
6. **Human-in-the-loop checkpoint:** Mandatory review before generating legal drafts

---

## 5. Session Management

### Current State
- **Clerk session cookie:** 7 days (default Clerk behavior)
- **No `sessionOptions`:** `ClerkProvider` in `main.tsx` has no duration override
- **No idle timeout:** No application-level timer
- **No step-up auth:** Billing checkout, API key creation, tier changes use same token
- **No revocation list:** Backend checks signature and expiry but not `jti` or revocation store
- **No device binding:** No IP, User-Agent, or fingerprint checks
- **`verify_aud` disabled:** `crp_shared/auth.py` skips audience verification

### Security Implications
| Risk | Likelihood | Impact |
|------|-----------|--------|
| Shared workstation left logged in | High | Unauthorized access to compliance data |
| Stolen token replayed from any device | Medium | Full account takeover until Clerk expiry |
| No anomaly detection | Medium | Compromise goes unnoticed |
| `localStorage` API key storage | Medium | XSS could exfiltrate key |

### Required Fixes
1. Add Clerk `sessionOptions` with shorter lifetime (e.g., 24 hours)
2. Add idle timeout (30 minutes) with warning at 25 minutes
3. Add step-up auth for sensitive actions (billing, API key creation)
4. Enable `verify_aud` with proper audience claim
5. Add device fingerprinting and anomaly logging
6. Move API key from `localStorage` to `httpOnly` cookie or secure storage

---

## 6. Notifications

### Current State
| Channel | Status |
|---------|--------|
| In-app inbox | ✅ Working |
| Email | ⚠️ Stub in dispatcher; real send only in free-assessment endpoint |
| SMS | ❌ Pure stub |
| Webhook | ⚠️ Stub in dispatcher; signed outbound harness exists |

### Critical Bug
`emit_notification` is **imported but does not exist**:
- `src/crp_comply/api/billing.py:580` — billing action required
- `src/crp_comply/api/billing.py:668` — credits granted

These notifications **silently fail** with `ImportError` swallowed by `except Exception: pass`.

### Missing Infrastructure
- No notification preferences in Settings UI
- No Clerk webhook endpoint (`user.created`, `organization.created`, etc.)
- No retry / dead-letter for failed deliveries
- No notification database table (all file-based)

### Recommended MVP
1. Wire existing Resend/SMTP email code into `EmailChannel`
2. Add `emit_notification()` helper function
3. Add Notification Preferences tab to Settings
4. Add Clerk webhook endpoint for user lifecycle events

---

## 7. Cryptographic Mechanisms

### What's Secure
| Mechanism | Implementation | Status |
|-----------|---------------|--------|
| API key hashing | BLAKE3 hash + prefix stored | ✅ Good |
| Clerk JWT verification | RS256, JWKS cached, issuer verified | ✅ Good |
| WebSocket encryption | `wss://` in production | ✅ Good |
| HSTS | `max-age=31536000; includeSubDomains; preload` | ✅ Good |
| X-Frame-Options | `DENY` | ✅ Good |

### What's Insecure
| Mechanism | Problem | Location |
|-----------|---------|----------|
| JWT audit trail signing | Falls back to `"dev"` key | `worker_ws.py:133` |
| `verify_aud` disabled | Skips audience verification | `crp_shared/auth.py:125` |
| ProviderStore JSON | No file locking, race condition | `provider.py:143` |
| API key in `localStorage` | XSS exfiltration risk | `lib/api.ts:16` |
| Admin secret in `localStorage` | XSS exfiltration risk | `lib/api.ts:636` |
| Query-string API key | Leaked to proxy logs | `worker_ws.py:60` |
| No per-session HMAC | Stolen key = full impersonation | — |

---

## 8. Action Plan (Prioritized)

### P0 — Critical Security (Do First)
1. Remove query-string auth from worker WebSocket
2. Add WebSocket Origin validation
3. Add `emit_notification()` and wire email sender
4. Fix ProviderStore atomic writes
5. Fix audit trail JWT to require secret (no "dev" fallback)
6. Enable `verify_aud` in Clerk JWT verification
7. Add idle timeout + session hardening

### P1 — High Impact
8. Add per-user worker connection limit + rate limiting
9. Add Redis-backed worker registry for multi-replica
10. Fix streaming queue backpressure
11. Add notification preferences UI
12. Add Clerk webhook endpoint
13. Fix stale marketing copy (Product, How It Works, index.html)

### P2 — Architecture
14. Make `crp.Client.dispatch*()` the sole LLM entry point
15. Build specialized deliverable agents (DPIA, Risk, Annex IV, etc.)
16. Implement 5-primitive storage engine
17. Unify recipe interview into conversational bot consuming YAML branches
18. Add multi-stakeholder routing to recipe questions
19. Add scheduling + reminders for compliance deadlines

### P3 — Polish
20. Fix fake streaming in Workspace (replace with SSE)
21. Wire "Save to vault" to actual backend endpoint
22. Full dark mode on public pages
23. Card-view alternative for mobile tables

---

*Report generated by Kimi Code CLI, 2026-06-05.*
