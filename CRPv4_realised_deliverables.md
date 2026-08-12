# CRP v4 — Realised Deliverables

**Date:** 2026-06-06  
**Version:** 4.0.0  
**Purpose:** Honest mapping of what CRP v4 actually ships today vs what the specs describe. Use this to keep marketing, documentation, and implementation aligned.

---

## Executive Summary

CRP v4.0.0 is **released and live on PyPI**. The core protocol, SDK, safety systems, and benchmarking are implemented and tested. The ecosystem products (Comply, Gateway, Scan) have varying levels of completion — some are production-ready, others are scaffolded and need finishing.

| Category | Status |
|----------|--------|
| Core Protocol (specs 001–011) | ✅ Fully implemented |
| Advanced Context (specs 024–031) | ✅ Fully implemented |
| Safety & Governance (specs 033–034) | ✅ Fully implemented |
| SDK (L0, L1, L2) | ✅ Implemented |
| CLI (`crp scan`, `crp serve`, etc.) | ✅ Core commands implemented |
| Gateway runtime | ✅ Implemented in `crp.gateway` |
| Scan engine | ✅ Implemented in `crp.scan` |
| CRP Comply backend | 🟡 Partial — billing/auth works, no-code scaffolded, Gateway swap deferred |
| CRP Comply frontend | 🟡 Partial — dashboard works, no-code basic, repo connection stubbed |
| GitHub App Marketplace | 🔴 Not yet published |
| VS Code Extension | 🟡 Scaffolded, v0.2.0, not yet published |

---

## Core Protocol — SHIPPED ✅

### SPEC-001: Core Protocol
**What it says:** Session model, 4 axioms (coherence, relevance, parsimony, privacy), dispatch loop.

**What's real:**
- `crp.core.orchestrator.CRPOrchestrator` implements the full lifecycle
- 4 axioms are enforced in envelope construction and dispatch
- Session state persists across windows

**Evidence:** `crp/core/orchestrator.py`, `tests/test_orchestrator.py`

### SPEC-002: Headers
**What it says:** 58 CRP HTTP headers for context governance and safety signalling.

**What's real:**
- Header emission in `crp/envelope/builder.py`
- HTTP 451 halt mechanism implemented
- `X-CRP-*` and `CRP-*` headers generated on every dispatch

**Evidence:** `crp/envelope/builder.py`, `crp/_headers.py`

### SPEC-003: Context Envelope
**What it says:** 6-phase envelope builder with CKF gate.

**What's real:**
- `EnvelopeBuilder` with 6 phases: init, CKF query, ranking, compression, assembly, validation
- Saturation tracking
- `EnvelopePreview` for cost estimation

**Evidence:** `crp/envelope/builder.py`, `tests/test_envelope.py`

### SPEC-004: Continuation
**What it says:** Multi-window continuation with gap analysis and stitching.

**What's real:**
- `ContinuationManager` handles window boundaries
- Automatic continuation when output is truncated
- Gap analysis across windows

**Evidence:** `crp/continuation/`, `tests/test_continuation.py`

### SPEC-005: Decision Provenance Engine (DPE)
**What it says:** 13-stage hallucination & risk analysis pipeline.

**What's real:**
- 13-stage pipeline implemented in `crp/security/dpe.py`
- Classifies claims as `CONTEXT_GROUNDED`, `PARAMETRIC`, `MIXED`, `UNCERTAIN`
- Risk scoring per window

**Evidence:** `crp/security/dpe.py`, `tests/test_dpe.py`

### SPEC-006: Safety Policy
**What it says:** Configurable safety policy grammar with profiles and enforcement.

**What's real:**
- `SafetyPolicy` class with JSON/YAML parsing
- Profiles: balanced, strict, medical, financial
- Halt levels and HTTP 451 enforcement

**Evidence:** `crp/security/policy.py`, `tests/test_safety_policy.py`

### SPEC-007: Session Token
**What it says:** HKDF-derived session tokens with encrypted payload.

**What's real:**
- HKDF key derivation
- AES-256-GCM encrypted payload
- Tamper-evident structure

**Evidence:** `crp/security/session_token.py`

### SPEC-008: Dispatch Strategies
**What it says:** Multiple dispatch variants (basic, tools, reflexive, progressive, stream-augmented, agentic).

**What's real:**
- All 6 dispatch variants implemented in `CRPOrchestrator`
- Provider adapter pattern (OpenAI, Anthropic, Gemini, Bedrock, Custom)

**Evidence:** `crp/core/orchestrator.py`, `crp/providers/`

### SPEC-009: CKF (Contextual Knowledge Fabric)
**What it says:** Graph-based knowledge fabric with HNSW, Leiden clustering, semantic fallback.

**What's real:**
- CKF graph in `crp/ckf/`
- HNSW index for semantic retrieval
- Leiden community detection
- Fact confidence tracking

**Evidence:** `crp/ckf/`, `tests/test_ckf.py`

### SPEC-010: Regulatory Mapping
**What it says:** EU AI Act / GDPR / ISO / NIST mapping.

**What's real:**
- Regulatory framework mapping in compliance reports
- Article-by-article coverage matrix
- EU AI Act Art. 6–17 mapped

**Evidence:** `crp/compliance/`, `site-docs/compliance/`

### SPEC-011: Audit Trail
**What it says:** HMAC-SHA256 tamper-evident audit chain.

**What's real:**
- Per-window HMAC chain
- 30+ event types
- Integrity verification API

**Evidence:** `crp/security/audit.py`, `tests/test_audit.py`

---

## Advanced Context Systems — SHIPPED ✅

### SPEC-024: Coverage-Differential Retrieval (CDR)
- Novelty-weighted fact ranking
- Ensures new information gets through token budget

### SPEC-025: Cognitive-Driven Graph Retrieval (CDGR)
- Multi-hop graph walk for complex reasoning
- Integrates with CKF

### SPEC-027: Retrieval Integrity
- Contradiction detection
- Repetition detection
- Source drift monitoring

### SPEC-028: Conversational Context
- Multi-horizon context: persistent, conversational, ephemeral
- Turn log management

### SPEC-029: Ephemeral Tool Context
- Scratch buffer for tool outputs
- Automatic compaction

### SPEC-030: Cognitive State Relay (CSO)
- Session memory across windows and restarts
- `relay_cso()` primitive

### SPEC-031: Semantic Task Layer (STL)
- Task positioning instead of injection
- Focused task handling with fewer tokens

### SPEC-035: Context Lifecycle
- 5-primitive storage engine
- Ingest → rank → select → compact → persist

---

## Safety & Governance — SHIPPED ✅

### SPEC-033: Safety Control Plane
- `crp.security.control_plane.SafetyControlPlane`
- Capability registry
- Surface map for dashboards
- Gate management

### SPEC-034: Safety Coverage
- Coverage map of all safety capabilities
- Per-tier capability availability
- Addable rules registration

---

## SDK — SHIPPED ✅

### SPEC-032: Developer Experience
**L0:** One-line `base_url` change  
**L1:** `client.ingest()` + `client.ask()`  
**L2:** `depth`, `@tool`, `how_it_was_built` controls

**Evidence:** `crp/sdk/client.py`, `site-docs/guides/sdk.md`

---

## CLI — SHIPPED ✅

Commands implemented:
- `crp init` — create session
- `crp dispatch` — run task
- `crp ingest` — add knowledge
- `crp status` — session status
- `crp preview` — envelope preview
- `crp serve` — HTTP sidecar (SPEC-038)
- `crp scan` — source code governance scanner (NEW in this round)

---

## Gateway — SHIPPED ✅ (Runtime) / 🟡 (Deployment)

### SPEC-016: Gateway Service
- `crp.gateway.GatewayRequestLifecycle` — 22-step lifecycle
- OpenAI-compatible `/v1/chat/completions`
- Tenant provisioning, billing, usage tracking

### SPEC-043: Gateway Runtime Product
- Productised as "CRP Gateway"
- Pricing: Developer $29/mo, Team $199/mo

### crp-gateway repo
- FastAPI deployment wrapper around `crp.gateway`
- Railway-ready with `railway.json`
- Dockerfile, docker-compose, README

**Gap:** Not yet deployed to `gateway.crprotocol.io`. Redis needed for multi-replica state.

---

## Scan — SHIPPED ✅ (Engine) / 🟡 (Distribution)

### SPEC-036: Scan Remediation
- `crp.scan` module finds ungoverned AI calls
- Auto-remediation PR engine
- SARIF output support

### SPEC-039: Semantic Code Ingestion
- Parses Python, TS, JS, Java, Go, Rust
- Identifies exact call sites needing governance

### Distribution
- **GitHub Action:** Ready in `crp-scan` repo, NOT YET published to Marketplace
- **VS Code Extension:** v0.2.0 scaffolded, NOT YET published
- **CLI:** `crp scan` command works locally

---

## CRP Comply — 🟡 PARTIAL

### SPEC-040: CRP Comply Product
**What's shipped:**
- FastAPI backend with auth, billing, reports
- React dashboard with 9+ pages
- EU AI Act, ISO 42001, GDPR report generators
- Evidence pack export
- Session audit
- Stripe + Clerk integration

**What's stubbed or deferred:**
- Gateway swap (SPEC-042) — `gateway_proxy.py` exists but not mounted
- No-Code Governance Loop (SPEC-048) — basic form works, NOT scan-driven per spec
- GitHub App connection — install redirect works, repo listing/trigger are stubs

### SPEC-042: Comply Upgrade Integration
- `ComplyGatewayProxy` class implemented
- Not wired into live API path
- Dead code until Gateway is deployed

### SPEC-047: Monetisation
**What's shipped:**
- Stripe Checkout + webhook
- Clerk org metadata sync
- Tier enum: Free, Starter, Scale, Enterprise
- Rate limits per tier

**What's missing:**
- Annual price IDs in Stripe (monthly only currently)
- Webhook idempotency Redis backend (file-based workaround in place)

### SPEC-048: No-Code / GitHub / Signup
**Current state:**
- No-code form generates basic `crp.config.yaml`
- Capability mapping NOW FIXED (was completely broken)
- Public `/no-code` route REMOVED — only authenticated `/app/no-code`
- GitHub install redirect works
- Repo listing/trigger are stubs (return empty/ok)

**What SPEC-048 actually requires (not yet done):**
- Scan-driven per-finding governance cards
- Intent Translator as ADA over CRP spec corpus
- Plain-language confirmation echo
- PR opening via GitHub App
- Result-preserving anonymous token → claim on signup

---

## Testing & Quality — SHIPPED ✅

- **1,537 tests passing** (per homepage)
- **SQB Gate cleared** — recall 1.000 / 1.000 / 0.800
- Conformance suite: `tests/conformance/`
- Security tests: `tests/test_compliance_security.py`

---

## Documentation — 🟡 PARTIAL

**What's shipped:**
- 48 specification documents
- SDK guide
- Product pages (Gateway, Comply, Scan)
- Compliance mapping (EU AI Act, ISO 42001, GDPR, NIST)

**What's outdated or missing:**
- crprotocol.io homepage was not deploying due to mkdocs `--strict` warning (FIXED — manually deployed)
- Some product page anchors are broken (warning-level only)
- No-Code docs don't reflect current UI

---

## Honest Gaps (Do Not Market As Shipped)

1. **Gateway is not live at gateway.crprotocol.io**
2. **GitHub Action not in Marketplace**
3. **VS Code Extension not in Marketplace**
4. **CRP Comply no-code is not yet scan-driven per SPEC-048**
5. **CRP Comply repo connection lists no actual repos yet**
6. **CRP Comply Gateway swap is dead code**
7. **Redis not yet used for webhook idempotency / multi-replica state**
8. **Annual Stripe products not yet created**

---

## What This Means for Marketing

**Say:**
- "CRP v4.0.0 is released on PyPI with full protocol implementation"
- "Core safety, context, and compliance systems are production-ready"
- "Gateway, Scan, and Comply are in active beta"
- "Free tier available; paid tiers from $49/mo"

**Don't say:**
- "Gateway is live at gateway.crprotocol.io" (it's not)
- "One-click no-code setup from scan findings" (not yet scan-driven)
- "GitHub Action available in Marketplace" (not yet published)
- "VS Code extension in Marketplace" (not yet published)

---

*Maintained by the CRP core team. Update this document whenever a gap is closed.*
