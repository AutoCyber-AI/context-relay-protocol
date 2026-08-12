# AGENTS.md — Context Relay Protocol (CRP) v4/v6 Implementation

> This file is for AI coding agents. Read it before modifying any code.
> The project uses English for all comments, docstrings, and documentation.
> **Current role:** Agent B — Safety Surface, SDK, Config, Products (Gateway, Comply, Scan)
>
> **Branch note:** The active `crpv6-agent-sdk` branch has implemented CRP v6 specs
> SPEC-049 through SPEC-057 and the Agent SDK (SPEC-059). The v4 roadmap below
> is retained for historical context; for the current operational picture see
> `docs/CRPv6_Operational_Readiness_Report.md`.

---

## Project Overview

**Context Relay Protocol (CRP) for Agentic AI** is an open Python SDK and protocol specification for agentic context and tool orchestration across LLM invocations. It acts as a middleware layer that wraps existing LLM calls and structures the surrounding agentic ecosystem to provide:

- **Unbounded context** — auto-ingests documents larger than any model's context window
- **Unbounded generation** — automatic continuation when output hits physical limits
- **Amplified reasoning** — meta-learning scaffolds for small models

**Current version:** 3.1.1 (`crp/_version.py`) — **v4.0.0 target in progress**  
**Package name on PyPI:** `crprotocol`  
**License:** Elastic License 2.0 (code) / CC BY-SA 4.0 (specification documents)

The core value proposition: instead of one shared context window where everything competes for token budget, CRP gives each LLM call its own dedicated window with a curated "envelope" of relevant historical facts, selected tools, and operation goals extracted from prior windows.

**v4 adds:** the quality layer (CDR/CDGR/CSO), the positioning layer (STL), and the product revenue loop (Gateway visual console, Comply upgrade, Scan remediation + payments).

---

## CRPv6 Launch Readiness Checklist

Canonical status of the CRPv6 launch push.  Items marked ✅ are verified in this
branch; items marked ⬜ are the remaining Wave 2 / Wave 3 work.  Update this section
after every material change.

### Wave 1 — ML-first foundation (DONE)
- ✅ All three Phase A models published on Hugging Face `AutoCyberAI/`:
  - `crp-intent-setfit` (0.934 held-out accuracy)
  - `crp-prm-deberta-v1` (AUC 0.793 — advisory scorer)
  - `crp-safety-deberta-v1` (12/12 adversarial pass)
- ✅ `crp/ml/manifest.json` lists all four default models with SHA-256 hashes.
- ✅ `crp/ml/registry.py` manages lazy, budgeted, fallback-safe loading.
- ✅ Safety classifier registered under `crp.security.safety` and wired into
  `crp/security/injection.py` via `ModelManager`.
- ✅ `crp download-models` CLI command exists.
- ✅ GLiNER replaced by default on Windows; rule-based + DSLiM NER fallback.

### Wave 2 — Protocol finalised and provable (IN PROGRESS)
- ✅ Reference agent examples in `examples/agents/`:
  - `weather_agent.py` (original)
  - `rag_agent.py` (search → read, CSO carry-forward)
  - `gdpr_dsr_agent.py` (read vs delete with token gate)
  - `report_agent.py` (scan → summarize → report)
- ✅ Reproducible benchmark harness in `AutoCyber AI Agentic AI research with CRP/benchmark_harness.py`
  with per-attack-class ASR, pass^k reliability panel, and utility/latency/cost panel.
- ✅ Standards Landscape report (`AutoCyber AI Agentic AI research with CRP/CRP_Standards_Landscape.md`)
  comparing CRP with MCP, A2A, and OpenAI Agents SDK.
- 🔄 Spec/reference consistency pass across `docs/`, `site-docs/`, research corpus.
- ⬜ `crp download-models` end-to-end verification on a clean machine.
- ⬜ Live-public-benchmark reproduction by an independent party (AgentDojo/AgentHarm).

### Wave 3 — Hosted product + money funnel (NOT STARTED)
- ⬜ Extract `frontend/agent-console/` and build CDN asset pipeline.
- ⬜ Gateway production hardening: auth, key vault, rate limits, quota.
- ⬜ Stripe + Clerk webhook entitlement wiring.
- ⬜ Redis/S3/Postgres defaults + `docker-compose.ci.yml`.
- ⬜ Comply evidence-pack automation from `crp_sessions/` audit data.
- ⬜ Self-serve Scan → Gateway → Comply funnel documentation and pricing page.
- ⬜ OpenTelemetry + cost accounting.

### Quality gates
- ✅ Full non-live test suite passes: `3232 passed, 3 skipped` (Windows,
  `CRP_GLINER_DISABLED=1`), ~3 min 47 s.
- ✅ `ruff check` / `mypy` pass on all files changed in Wave 2 (training scripts,
  intent/PRM wiring, downloader, CLI, docs).
- 🔄 Whole-repo `ruff check crp/ tests/` and `mypy crp/ --ignore-missing-imports`
  are currently **not clean** — a large set of pre-existing import-order, unused-import,
  whitespace and typing issues was surfaced when the check was widened. These are
  auto-fixable and must be resolved before claiming a fully lint-clean release,
  but they do not affect the 3232-test functional gate.
- ⬜ Live benchmark reproduction by an independent party.
- ⬜ `pip install crprotocol[full]` smoke test on clean Windows/macOS/Linux.
- ⬜ Gateway live smoke test on `gateway.crprotocol.io`.

---

## Related Repositories

| Repo | Local Path | GitHub | Visibility | State |
|------|-----------|--------|-----------|-------|
| **context-relay-protocol** | `C:\Users\User\Desktop\context-relay-protocol` | `AutoCyber-AI/context-relay-protocol` | Private | **v3.1.1 verified, v4 WIP** — main SDK + protocol |
| **crprotocol-specs** | `C:\Users\User\Desktop\crprotocol-specs` | `AutoCyber-AI/crprotocol-specs` | Public | v3 specs only (001–017), **v4 specs live in `SPECS_5_06_2026_CRP_v4/` of main repo** |
| **crp-comply** | `C:\Users\User\Desktop\crp-comply` | — | Private (planned) | **Bespoke compliance proxy** — FastAPI + React. To be upgraded to Gateway-consumer (SPEC-042). See `CRP_COMPLY_REASSESSMENT.md` in the local `crp-comply` project |
| **crp-scribe** | `C:\Users\User\Desktop\crp-scribe` | — | Private | Documentation/scribe tool |
| **crp-sidecar** | `C:\Users\User\Desktop\crp-sidecar` | — | Private | HTTP sidecar (inter-LLM sharing) |
| **crp-scan** | — (GitHub only) | `AutoCyber-AI/crp-scan` | Public | GitHub Action for static AI-governance scanning. **Not cloned locally.** |
| **crp-gateway** | **Does NOT exist as separate repo** | — | — | Lives inside `context-relay-protocol/crp/gateway/` — **to be extracted as standalone service repo in Round 3** for Railway deployment |

### crp-comply Current Architecture (to be upgraded in R3)
- **Backend:** FastAPI (`src/crp_comply/api/`) with auth, billing, credits, provider routing, evidence signing
- **Agent:** RAG-based compliance agent (`src/crp_comply/agent/`) with corpus ingestion, loop runtime, reflector
- **Frontend:** React/Vite (`frontend/src/`) — dashboard UI
- **Search:** SearXNG integration (`services/crp-comply-searxng/`, `services/crp-comply-search/`)
- **SDK:** Separate small SDK (`sdk/`) for client integration
- **Current proxy model:** Bespoke proxy (`provider.py`) forwards to OpenAI/Anthropic with compliance scanning
- **R3 target:** Retire bespoke proxy → consume Gateway runtime evidence (SPEC-042)

### crp-gateway Current State
- Exists as `crp/gateway/` in main repo
- Currently minimal (`__pycache__` only, no substantial code yet)
- **R3 target:** Full 22-step OpenAI-compatible lifecycle (SPEC-016), provider router, key vault

---

## v4 Implementation Plan (4 Rounds, 2 Agents)

**Source:** `CRPv4_Implementation_Rounds.md` (canonical — updated 2026-06-05)

### CRITICAL GATE
> **The SQB benchmark (SPEC-026) is the single gate that separates specification from proven system.**
> CRP v4.0.0 must prove: **Factual F1 ≥ v3 baseline AND LLM-as-judge usefulness score ≥ v3 baseline.**
> **Tier 2 (STL/Positioning) does NOT begin until Tier 1 passes SQB.** This is non-negotiable.

### Work Split
| Agent | Owns |
|-------|------|
| **Agent-A** | Core Protocol quality layer: CDR, CDGR, CSO, Storage Engine, SQB |
| **Agent-B** | Safety Surface, SDK, Config, Products: Gateway, Comply, Scan upgrades |

---

## ROUND 1 — Core Quality Foundation + Safety Surface
**Version target:** `4.0.0-alpha.1`  
**Gate:** All 1537 existing tests pass. CDR integration test runs without error.

### Agent-A Deliverables (context only — Agent-B does not touch)
- A1.1 CKF Graph Edges (`crp/ckf/graph_edges.py`) — SPEC-025 prerequisite
- A1.2 Coverage Set (`crp/state/coverage_set.py`) — SPEC-024 §2.1
- A1.3 CDR Formula (`crp/envelope/cdr.py`) — SPEC-024 §7.1
- A1.4 CDGR Graph Walk (`crp/ckf/cdgr.py`) — SPEC-025
- A1.5 Residual Task Anchor (`crp/continuation/flow.py`) — SPEC-004 amendment
- A1.6 5-Primitive Storage Engine (`crp/state/storage/`) — SPEC-035
- A1.7 SQB Benchmark Harness (`examples/crp_demos/sqb_benchmark.py`) — SPEC-026 — **THE GATE**

### Agent-B Deliverables (YOUR WORK)
- **B1.1 — Safety Control Plane (`crp/security/control_plane.py`)** — SPEC-033
  - `SafetyControlPlane` class: registry, manifest, tune, register_rule, get_surface_map
  - Registry entries: hallucination_risk_scoring, fabrication_detection, distortion_detection, grounding_verification, contradiction_detection, repetition_detection, pii_detection, prompt_injection_shield, safety_budget_multiagent, compliance_classification, tamper_evident_audit, http_451_halt, human_oversight
  - Also create `crp/security/safety_manifest.py`

- **B1.2 — Checkpoint Primitive (`crp/security/checkpoint.py`)** — SPEC-033/034
  - Inline human-in-the-loop mechanism
  - `Checkpoint` class with trigger, timeout, on_timeout, on_reject
  - `CheckpointResolution` with approve/reject/edit actions
  - Webhook interface for async resolution
  - HMAC audit chain integration (SPEC-011)

- **B1.3 — Safety Coverage Map (`crp/security/coverage.py`)** — SPEC-034
  - Addable rules registry: jailbreak_detection, toxicity_classification, secrets_detection, copyright_detection, agency_boundary, semantic_drift
  - `SafetyCoverageMap` with capabilities + explicit out-of-scope list

- **B1.4 — Unified Config (`crp/config.py`, `crp/config_schema.py`)** — SPEC-037
  - `crp.config.yaml` optional single-file governance
  - `CRPConfig.load()`, `get_config_hash()`, `layer_override()`
  - Sections: version, model, safety, knowledge, context, audit, gateway
  - 5-layer hierarchy: defaults → env vars → config file → init kwargs → runtime `configure()`

- **B1.5 — Progressive SDK Level 0 + 1 (`crp/sdk/client.py`, `crp/sdk/response.py`)** — SPEC-032
  - Level 0: `crp.Client()` drop-in governance — `client.complete("...")` → `r.crp.risk`, `r.crp.grounded`, `r.crp.fabrications`, `r.crp.chain_valid`, `r.crp.audit_url`
  - Level 1: `client.ingest("./docs/")`, `client.ask("...")` → `a.quality`, `a.sources`, `a.complete`

- **B1.6 — Pluggable Storage Backends (`crp/state/backends/`)** — SPEC-038
  - `StorageBackend` ABC: get, set, delete
  - `InMemoryBackend`, `SQLiteBackend`, `RedisBackend`, `S3Backend`
  - Visibility API: `client.storage.overview()`, `client.knowledge.location`

---

## ROUND 2 — CSO + SQB Gate + Positioning Layer
**Version target:** `4.0.0-alpha.2`  
**Hard prerequisite:** Round 1 complete and integrated  
**GATE: SQB must pass all 5 criteria before Tier 2 (STL) begins**

### Agent-A Deliverables
- A2.1 Cognitive State Object (`crp/state/cso.py`) — SPEC-030
- A2.2 CSO-aware Session Token — SPEC-007 amendment
- A2.3 **RUN SQB — THE GATE**
- A2.4 Formal Loop Exit Rules (`crp/continuation/flow.py`) — SPEC-004 amendment

### Agent-B Deliverables (YOUR WORK)
- **B2.1 — Multi-Horizon Context (`crp/state/horizons.py`)** — SPEC-028
  - `ContextTier`: PERSISTENT, CONVERSATIONAL, EPHEMERAL
  - `MultiHorizonContext.blend_for_operation()`, `classify_intent()`, `resolve_reference()`

- **B2.2 — Ephemeral Tool Context + Scratch Buffer (`crp/state/scratch_buffer.py`)** — SPEC-029
  - Pointer-based large working data
  - Structure-aware (tabular, JSON, code, text)
  - Freshness-gated TTL
  - `TOOL_GROUNDED` provenance

- **B2.3 — Semantic Task Layer (`crp/stl/`)** — SPEC-031 — **THE POSITIONING LAYER**
  - 8 operations: RETRIEVE, COMPARE, ANALYSE, SYNTHESISE, GENERATE, VERIFY, CLARIFY, REVISE
  - `crp/stl/classifier.py` — classify_operations()
  - `crp/stl/depth_model.py` — D1–D5 depth negotiation
  - `crp/stl/frame_builder.py` — build_operation_frame()
  - `crp/stl/goal_compass.py` — anchored goal-compass
  - `crp/stl/orchestrator.py` — stl_execute()
  - **Token target:** < 30% of injection equivalent (SPEC-031 §1)

- **B2.4 — Retrieval Integrity (`crp/envelope/retrieval_integrity.py`)** — SPEC-027
  - Recency decay, contradiction detection, parallel coverage isolation

- **B2.5 — SDK Level 2 Controls (`crp/sdk/client.py`)** — SPEC-032
  - Depth: `client.ask("...", depth="thorough")`
  - Tools: `@client.tool` decorator
  - Safety fine-grained: `crp.Client(safety={"halt_on": "CRITICAL", "require_grounding": 0.80})`
  - Inspect reasoning: `a.decisions`, `a.how_it_was_built`, `a.open_questions`

---

## ROUND 3 — Products: Gateway + Comply Upgrade + Scan Remediation
**Version target:** `4.0.0-beta.1`  
**Hard prerequisite:** Round 2 SQB gate passed  
**This is where the revenue layer connects.**

### Agent-A Deliverables
- A3.1 Gateway OpenAI-compatible Endpoint (`crp/gateway/api.py`) — SPEC-016
- A3.2 Provider Router + Key Vault — SPEC-016 §8
- A3.3 Semantic Code Ingestion for Scan (`crp/scan/semantic_ingestion.py`) — SPEC-039
- A3.4 Scan Remediation Engine (`crp/scan/remediation.py`) — SPEC-036

### Agent-B Deliverables (YOUR WORK)
- **B3.1 — Comply Gateway Swap (`crp/comply/gateway_client.py`)** — SPEC-042
  - Replace Comply's bespoke proxy with Gateway consumption
  - `ComplyGatewayClient.subscribe_to_audit_stream()`, `get_evidence_pack()`, `map_to_regulation()`
  - This is the most important product change

- **B3.2 — Stripe + Clerk Entitlement Webhook (`crp/monetisation/webhook.py`, `crp/monetisation/entitlement.py`)** — SPEC-047
  - `EntitlementChecker`: plan, quota, features, credit balance
  - Stripe webhook handler: `checkout.session.completed`, `customer.subscription.deleted`
  - Clerk org.publicMetadata writes
  - **NEVER grant on success page — only on verified webhook**

- **B3.3 — GitHub App Connection (`crp/scan/github_app.py`)** — SPEC-048
  - Installation token minting (~1h, never persist)
  - `open_remediation_pr()` — always PR to dedicated branch, NEVER direct commit to main

- **B3.4 — No-Code Governance Loop (`crp/comply/no_code.py`)** — SPEC-048
  - Scan→Comply→Fix funnel with zero code writing
  - `express_requirement()`, `generate_config()`, `generate_code_change()`

---

## ROUND 4 — Conformance, Quality Benchmark Final, PyPI Publish
**Version target:** `4.0.0`  
**Gate: SQB final run + conformance suite clean + all invariants verified**

### Agent-A Deliverables
- A4.1 Run FINAL SQB — SPEC-026
- A4.2 Conformance Suite — SPEC-014
- A4.3 BENCHMARKS.md update
- A4.4 Version bump + build

### Agent-B Deliverables (YOUR WORK)
- **B4.1 — Full Test Suite:** `pytest tests/ -v --tb=short` — all 1537+ tests pass
- **B4.2 — CHANGELOG.md:** Document all v4.0.0 changes with SQB numbers
- **B4.3 — PyPI Publish:** ONLY after A4.1 SQB passes all criteria
- **B4.4 — GitHub Push:** Tag `v4.0.0`, push to origin

---

## ROUND 5 — Frontier Capabilities (deferred to v4.1+)
**Build ONLY when Tier 1+2 proven, and only when a customer needs it**

| Spec | What | Build Condition |
|------|------|----------------|
| SPEC-018 AIR | Error quarantine feedback loop | Customer has < 7B local model |
| SPEC-019 CQR | Cognitive failure detection (C1–C6) | On request only |
| SPEC-020 CLD | Cognitive load distribution | Weak local models, async only |
| SPEC-021 ROS | Consensus / self-consistency | Customer explicitly requests multi-pass |
| SPEC-022 PEF | Parallel execution fabric | Only if 020/021 built |
| SPEC-044 ADA | Authoritative Domain Agent | After Gateway + Comply proven |
| SPEC-045 | Knowledge Learning | Frontier; explicit weight boundary needed |
| SPEC-046 | User-Defined Cognition | Frontier |
| SPEC-041 | Framework adapters (LangChain, LlamaIndex, Haystack) | Adoption demand emerges |

**RULE:** Tier 4 features are NEVER in Core. NEVER default. ALWAYS declare cost upfront. ALWAYS warn on strong models.

---

## NON-NEGOTIABLE INVARIANTS

1. **< 50ms overhead on any single call.** CDR < 1ms. CDGR < 2ms. CSO ops < tens of ms.
2. **Model-agnostic.** Identical governance contract on GPT-5, Claude, 70B, 1B local.
3. **Axiom 4 — STRIP BEFORE FORWARDING.** NO `CRP-*` header ever reaches the LLM provider. Hard allowlist filter. Dedicated security test.
4. **Positioning not injection (Tier 2+).** Operation Frames built UP from operation requirements, not trimmed DOWN from everything.
5. **Embedding consistency.** Coverage Set, Turn Log, CKF facts MUST use same embedding model. Record model id in session token. Reject mismatched updates.
6. **State relay verified.** CSO preservation guarantee — every still-valid prior fact survives relay or is repaired. No silent state loss.
7. **HMAC chain unbroken.** Every window/operation extends chain. Tampering surfaces as `CRP-Provenance-Chain-Integrity: BROKEN`.
8. **Amplification is opt-in.** Tier 4 is OFF by default, async-only, declares cost upfront.
9. **Right storage primitive per access.** Never force everything through one vector index.
10. **Checkpoints never leave end user with raw error.** On timeout or reject, provide graceful fallback.
11. **Remediations are always proposals (PRs), never auto-commits.** NEVER commit to protected branches.
12. **Config optional and provenanced.** `crp.config.yaml` is optional. Emit `CRP-Config-Hash` when loaded.

---

## Complete Spec Index (v4 — 49 Specifications)

All v4 specs are in `SPECS_5_06_2026_CRP_v4/specs/` (main repo). v3 specs are in `crprotocol-specs/` (separate repo).

| Spec | Title | Tier | Status | Agent Owner |
|------|-------|------|--------|-------------|
| SPEC-001 | Core Protocol | Foundation | v3 ✅ | Shared |
| SPEC-002 | HTTP Headers | Foundation | v3 ✅ | Shared |
| SPEC-003 | Context Envelope | Foundation | v3 ✅ | Shared |
| SPEC-004 | Continuation & State Relay | Foundation | v3 ✅ | A (amend R1) |
| SPEC-005 | Decision Provenance Engine (DPE) | Foundation | v3 ✅ | Shared |
| SPEC-006 | Safety Policy | Foundation | v3 ✅ | B (unify R1) |
| SPEC-007 | Session Token | Foundation | v3 ✅ | A (amend R2) |
| SPEC-008 | Dispatch & Provider Adaptation | Foundation | v3 ✅ | Shared |
| SPEC-009 | Contextual Knowledge Fabric (CKF) | Foundation | v3 ✅ | A (amend R1) |
| SPEC-010 | Regulatory Mapping | Foundation | v3 ✅ | Shared |
| SPEC-011 | Audit Trail | Foundation | v3 ✅ | Shared |
| SPEC-012 | Multi-Agent Safety | Foundation | v3 ✅ | B (unify R1) |
| SPEC-013 | GitHub Action | Foundation | v3 ✅ | A (amend R3) |
| SPEC-014 | Conformance | Foundation | v3 ✅ | A (R4) |
| SPEC-015 | Security & Privacy | Foundation | v3 ✅ | B (unify R1) |
| SPEC-016 | Gateway Service | Product | **NEW v4** | A (R3) |
| SPEC-017 | Zero-CKF Mode | Foundation | v3 ✅ | Shared |
| SPEC-018 | AIR — Amplification Intelligence Relay | Frontier | **NEW v4** | Deferred (R5) |
| SPEC-019 | CQR — Cognitive Quality Recognition | Frontier | **NEW v4** | Deferred (R5) |
| SPEC-020 | CLD — Cognitive Load Distribution | Frontier | **NEW v4** | Deferred (R5) |
| SPEC-021 | ROS — Reasoning Orchestration & Synthesis | Frontier | **NEW v4** | Deferred (R5) |
| SPEC-022 | PEF — Parallel Execution Fabric | Frontier | **NEW v4** | Deferred (R5) |
| SPEC-023 | Amplification Boundary | Frontier | **NEW v4** | Deferred (R5) |
| SPEC-024 | Coverage Differential Retrieval (CDR) | **Tier 1** | **NEW v4** | A (R1) |
| SPEC-025 | Context Differential Graph Retrieval (CDGR) | **Tier 1** | **NEW v4** | A (R1) |
| SPEC-026 | Semantic Quality Benchmark (SQB) | **GATE** | **NEW v4** | A (R1/R2/R4) |
| SPEC-027 | Retrieval Integrity | Tier 2 | **NEW v4** | B (R2) |
| SPEC-028 | Conversational Context (Multi-Horizon) | Tier 2 | **NEW v4** | B (R2) |
| SPEC-029 | Ephemeral Tool Context & Scratch Buffer | Tier 2 | **NEW v4** | B (R2) |
| SPEC-030 | Cognitive State Object (CSO) | **Tier 1** | **NEW v4** | A (R2) |
| SPEC-031 | Semantic Task Layer (STL) | **Tier 2** | **NEW v4** | B (R2) |
| SPEC-032 | Developer Experience & Progressive SDK | Cross-cutting | **NEW v4** | B (R1/R2) |
| SPEC-033 | Safety Control Plane | **Tier 1** | **NEW v4** | B (R1) |
| SPEC-034 | Safety Coverage | **Tier 1** | **NEW v4** | B (R1) |
| SPEC-035 | Context Lifecycle & Storage Engine | **Tier 1** | **NEW v4** | A (R1) |
| SPEC-036 | Scan Remediation Engine | Product — Tier 3 | **NEW v4** | A (R3) |
| SPEC-037 | Unified Configuration | **Tier 1** | **NEW v4** | B (R1) |
| SPEC-038 | Pluggable Storage Backends | **Tier 1** | **NEW v4** | B (R1) |
| SPEC-039 | Semantic Code Ingestion | Product — Tier 3 | **NEW v4** | A (R3) |
| SPEC-040 | CRP Comply (Product) | Product | **NEW v4** | B (R3) |
| SPEC-041 | Adoption Ecosystem | Go-to-Market | **NEW v4** | Deferred (R5) |
| SPEC-042 | Comply Upgrade & Gateway Integration | Product — Tier 3 | **NEW v4** | B (R3) |
| SPEC-043 | Gateway Runtime Product | Product — Tier 3 | **NEW v4** | A (R3) |
| SPEC-044 | Authoritative Domain Agent (ADA) | Frontier | **NEW v4** | Deferred (R5) |
| SPEC-045 | Knowledge Learning | Frontier | **NEW v4** | Deferred (R5) |
| SPEC-046 | User-Defined Cognition | Frontier | **NEW v4** | Deferred (R5) |
| SPEC-047 | Monetisation & Payments | Revenue — Tier 3 | **NEW v4** | B (R3) |
| SPEC-048 | Comply Low-Code + GitHub App | Product — Tier 3 | **NEW v4** | B (R3) |
| SPEC-049 | SLM Agent Execution Profile | Cross-cutting — Agentic Execution | **NEW v4.1** | B (R3+) |
| SPEC-050 | Tool Capability Fabric & Operation Orchestration | Cross-cutting — Agentic Execution | **NEW v4.1** | B (R3+) |

**Additional v4 documents in `SPECS_5_06_2026_CRP_v4/`:**
- `CRP-BUILD-PROMPT.md` — Build instructions
- `CRP-CODER-BRIEF.md` — Coder brief with gap analysis
- `CRP-ECOSYSTEM-BOUNDARIES.md` — Ecosystem boundaries
- `CRP-GATEWAY-BLUEPRINT.md` — 22-step Gateway lifecycle blueprint
- `CRP-GITHUB-APP-GUIDE.md` — GitHub App implementation guide
- `CRP-MARKET-STRATEGY.md` — Market strategy
- `CRP-MASTER-INDEX.md` — Master index of all specs
- `CRP-SDK-REFERENCE.md` — SDK reference
- `CRP-STRIPE-SETUP-GUIDE.md` — Stripe setup guide
- `CRP-V4-UPGRADE-PROMPT.md` — v4 upgrade prompt
- `CRP-FEASIBILITY.md`, `CRP-IANA-RESPONSE-STRATEGY.md`, `CRP-IETF-EMAIL-TEMPLATES.md`, `CRP-PUBLIC-CHECKLIST.md`, `CRP-SITE-STRATEGY.md`, `CRP-SUBMISSION-GUIDE.md`

---

## File Structure After All Rounds

```
crp/
├── sdk/                    ← NEW (SPEC-032) — progressive SDK Level 0–3
│   ├── client.py           ← crp.Client(), the steering wheel
│   └── response.py         ← CRPResponse with .crp governance summary
├── state/
│   ├── coverage_set.py     ← NEW (SPEC-024) — Coverage Set [Agent-A]
│   ├── cso.py              ← NEW (SPEC-030) — Cognitive State Object [Agent-A]
│   ├── horizons.py         ← NEW (SPEC-028) — Multi-horizon context [Agent-B]
│   ├── scratch_buffer.py   ← NEW (SPEC-029) — Ephemeral tool context [Agent-B]
│   ├── memory_authority.py ← NEW (SPEC-045) — write-authority lattice for governed memory [Agent-B]
│   └── storage/            ← NEW (SPEC-035) — 5-primitive storage engine [Agent-A]
│       ├── router.py
│       ├── rolling_log.py
│       ├── hot_cache.py
│       ├── inverted_index.py
│       └── ephemeral_store.py
│   └── backends/           ← NEW (SPEC-038) — Pluggable storage backends [Agent-B]
│       ├── __init__.py
│       ├── memory.py       # InMemoryBackend
│       ├── sqlite.py       # SQLiteBackend
│       ├── redis.py        # RedisBackend
│       └── s3.py           # S3Backend
├── envelope/
│   ├── cdr.py              ← NEW (SPEC-024) — CDR formula [Agent-A]
│   └── retrieval_integrity.py ← NEW (SPEC-027) [Agent-B]
├── ckf/
│   ├── graph_edges.py      ← NEW (SPEC-025 prerequisite) [Agent-A]
│   └── cdgr.py             ← NEW (SPEC-025) — CDGR graph walk [Agent-A]
├── stl/                    ← NEW (SPEC-031) — Semantic Task Layer [Agent-B]
│   ├── __init__.py
│   ├── classifier.py
│   ├── depth_model.py
│   ├── frame_builder.py
│   ├── goal_compass.py
│   ├── operation_state.py  ← NEW (SPEC-050) — operation state machine
│   ├── tool_positioner.py  ← NEW (SPEC-050) — build Tool Positioning Frame
│   └── orchestrator.py
├── security/
│   ├── control_plane.py    ← NEW (SPEC-033) [Agent-B]
│   ├── safety_manifest.py  ← NEW (SPEC-033) [Agent-B]
│   ├── checkpoint.py       ← NEW (SPEC-033/034) [Agent-B]
│   ├── coverage.py         ← NEW (SPEC-034) [Agent-B]
│   ├── kill_switch.py      ← NEW (SPEC-033 §3.4) — emergency stop + incident recorder [Agent-B]
│   └── trust_monitor.py    ← NEW (SPEC-033 §3.5) — runtime trust decay + IoC detection [Agent-B]
├── agent/
│   ├── budget.py           — Safety budget + circuit breaker (SPEC-012)
│   ├── chain.py            — Cross-agent provenance linking (SPEC-012)
│   ├── oversight.py        — Oversight token flow (SPEC-012)
│   ├── propagation.py      — Header propagation + delegation limits (SPEC-012)
│   ├── autonomy.py         ← NEW (SPEC-026) — ASR/pass^k → autonomy tier [Agent-B]
│   └── runtime_governance.py ← NEW — Wave-2 runtime bridge: PP/EP/BTF/autonomy/trust/memory [Agent-B]
├── gateway/
│   ├── api.py              ← EXTEND (22-step lifecycle) [Agent-A]
│   ├── router.py           ← NEW (SPEC-016) [Agent-A]
│   ├── key_vault.py        ← NEW (SPEC-016) [Agent-A]
│   └── capability_router.py ← NEW (SPEC-049/050) — capability-profile mapper & structured-output translation [Agent-B]
├── tools/                  ← NEW (SPEC-050) — Tool Capability Fabric
│   ├── __init__.py
│   ├── capability_fabric.py # TCF registry and retrieval
│   ├── descriptor.py        # CapabilityDescriptor + validation
│   └── executor.py          # tool-call execution and observation storage
├── scan/
│   ├── semantic_ingestion.py ← NEW (SPEC-039) [Agent-A]
│   ├── remediation.py      ← NEW (SPEC-036) [Agent-A]
│   ├── github_app.py       ← NEW (SPEC-048) [Agent-B]
│   └── templates/          ← remediation PR templates [Agent-A]
├── comply/
│   ├── gateway_client.py   ← NEW (SPEC-042) — replaces bespoke proxy [Agent-B]
│   └── no_code.py          ← NEW (SPEC-048) [Agent-B]
├── monetisation/           ← NEW (SPEC-047) [Agent-B]
│   ├── __init__.py
│   ├── webhook.py
│   └── entitlement.py
├── config.py               ← NEW (SPEC-037) — unified config [Agent-B]
└── config_schema.py        ← NEW (SPEC-037) [Agent-B]
```

---

## Technology Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.10+ |
| Build system | Hatchling (`pyproject.toml`) |
| Linting | Ruff (target py310, line length 100) |
| Type checking | mypy (strict subset) |
| Testing | pytest + pytest-asyncio + pytest-cov |
| Docs site | MkDocs Material |
| CLI framework | Click (optional extra) |

**Core dependencies:** None (zero-dependency core for maximum portability).

**Optional dependency groups:**
- `[full]` — all features (sentence-transformers, hnswlib, spacy, gliner, blake3, cryptography, httpx, openai, anthropic, leidenalg, igraph, prometheus-client, click)
- `[nlp]` — NLP extraction stages (sentence-transformers, hnswlib, spacy, gliner)
- `[security]` — cryptographic integrity/encryption (blake3, cryptography)
- `[cli]` — command-line interface (click)
- `[dev]` — development tooling (pytest, pytest-asyncio, pytest-cov, ruff, mypy, pip-audit)

---

## Build, Test, and Development Commands

### Installation

```bash
# Development install
pip install -e ".[dev]"

# Full feature install
pip install -e ".[full]"

# NLP-only install
pip install -e ".[nlp]"
```

### Linting and Type Checking

```bash
ruff check crp/ tests/          # Linting
mypy crp/ --ignore-missing-imports  # Type checking
```

### Testing

```bash
# Run all tests with coverage (80% minimum required)
pytest tests/ -v --tb=short --cov=crp --cov-report=term-missing --cov-fail-under=80

# Run a specific test file
pytest tests/test_smoke.py -v

# Windows GLiNER/torch mitigation
# On Windows the full suite can hit an OpenMP duplicate-runtime crash inside GLiNER.
# Set the following before running tests until the upstream issue is resolved:
export CRP_GLINER_DISABLED=1   # skips GLiNER entirely; rule-based extraction still runs

# Exclude live-LLM tests unless a local endpoint is running
python -m pytest tests/ -q --tb=short \
  --ignore=tests/test_gap_fixes_live.py \
  --ignore=tests/test_live_comprehensive.py \
  --ignore=tests/test_live_full_capture.py \
  --ignore=tests/test_live_long_generation.py \
  --ignore=tests/test_live_verification.py

# Perf threshold tests (test_benchmarks.py) are calibrated for Linux CI.
# On Windows they scale 1.5x by default (OpenMP hardening + background load);
# override with CRP_PERF_SCALE=<float>.
```

### Dependency Audit

```bash
pip-audit --strict --desc on
```

### CLI Usage

```bash
crp init                       # Create session
crp dispatch --task "..."      # Dispatch task
crp ingest --session <id>      # Ingest text
crp status --session <id>      # Session status
crp preview --session <id>     # Preview envelope
crp serve                      # HTTP sidecar (inter-LLM sharing)
crp scan                       # Static AI-governance scanner
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

Hooks run automatically on commit: trailing-whitespace, end-of-file-fixer, check-yaml, check-json, check-added-large-files (max 500KB), check-merge-conflict, detect-private-key, ruff --fix, mypy.

---

## Code Organization (Existing v3.1.1)

The main package is `crp/` with ~179 Python files across 25 submodules.

| Module | Purpose |
|--------|---------|
| `crp/core/` | Orchestrator, config, errors, session types, task intent, window DAG, dispatch router, extraction facade, security manager, circuit breaker |
| `crp/providers/` | LLM provider adapters (OpenAI, Anthropic, Ollama, llama.cpp, Custom, base ABC, discovery, manager) |
| `crp/extraction/` | 6-stage graduated extraction pipeline (regex → statistical → GLiNER NER → UIE relations → RST discourse → LLM-assisted) |
| `crp/envelope/` | Envelope builder (6-phase: decompose → score → rerank → pack → bookend → CKF gate) |
| `crp/ckf/` | Contextual Knowledge Fabric — graph walk, pattern query, semantic fallback, community detection, pub/sub, merge, GC |
| `crp/continuation/` | Continuation manager, completion detection, gap analysis, stitching, voice profile, document map, quality monitor |
| `crp/state/` | Warm state store, cold storage, fact graph, event log, snapshots, serialization, compaction, cleanup, multi-horizon context, scratch buffer, CDR Coverage Set, CSO, memory write-authority lattice |
| `crp/security/` | 13+ subsystems: input validation, injection detection, session binding, RBAC, integrity chain, encryption, quarantine, embedding defense, PII scanner, retention, erasure, consent, oversight, audit trail, compliance reporter, safety control plane, kill-switch, trust monitor |
| `crp/provenance/` | Decision Provenance Engine — claim detection, fabrication, hallucination scoring, contradiction, omission, entailment, RQA, window HMAC chain |
| `crp/observability/` | Events, metrics, telemetry, structured logging, audit, quality tracking |
| `crp/advanced/` | Source grounding, meta-learning (ORC/ICML/RTL), CQS detector, cross-window validator, feedback loop, parallel fan-out, review cycle, scale mode selector, hierarchical processing, auto-ingest, curator |
| `crp/policy/` | Safety policy grammar, enforcement, inheritance, profiles, nonce, report |
| `crp/headers/` | CRP HTTP headers (conditional, emit, halt, middleware, names, parse) |
| `crp/agent/` | Budget, chain, oversight, propagation, autonomy-by-measurement, runtime governance bridge |
| `crp/activation/` | Activation modes, onboarding, policy adjustment, stages |
| `crp/resources/` | Resource manager, adaptive allocator, overhead manager, cost model |
| `crp/integrations/` | LangChain hooks, OpenAI/Anthropic hooks |
| `crp/cli/` | CLI main entry point, sidecar HTTP server, startup |
| `crp/schemas/` | JSON Schema loader |
| `crp/gateway/` | Gateway components (minimal — to be built in R3) |
| `crp/scan/` | Static AI-governance scanner (CRP001–CRP006 rules) |
| `crp/ml/` | Managed-model registry, manifest.json, `download-models` downloader (CRPv6 Phase A) |
| `crp/eval/` | Evaluation statistics: pass^k, bootstrap CI, McNemar (CRPv6) |
| `crp/security/audit_merkle.py` / `audit_anchor.py` | Merkle inclusion proofs + Ed25519 receipts + external anchoring for the audit chain (CRPv6) |
| `crp/gateway/gbnf.py` / `constrained.py` / `tel_stream.py` | GBNF grammar compiler, per-provider constrained decoding, TEL SSE endpoint (CRPv6 SPEC-054/056) |
| `crp/security/kill_switch.py` / `trust_monitor.py` | Emergency kill-switch + incident recorder, runtime trust-decay monitor (CRPv6 SPEC-033 §3.4–3.5) |
| `crp/agent/autonomy.py` / `runtime_governance.py` | Autonomy-by-measurement (ASR/pass^k → tier), runtime bridge wiring PP/EP/BTF/trust/memory (CRPv6 Wave 2) |
| `crp/state/memory_authority.py` | Memory write-authority lattice: governed recall/remember with conflict resolution (CRPv6 SPEC-045) |

**CRPv6 ML models (Hugging Face `AutoCyberAI`):** `crp-intent-setfit` (intent, 0.934 held-out), `crp-safety-deberta-v1` (safety, 12/12 adversarial), `crp-prm-deberta-v1` (PRM, advisory: AUC 0.793). Training/eval scripts in `scripts/train_crp_*.py` / `scripts/eval_crp_*.py`. Model loaders restore torch thread parallelism after load on Windows (the `OMP_NUM_THREADS=1` cap in `crp/__init__.py` is a load-time crash guard only).

**Key architectural patterns:**
- **Mixin pattern:** `CRPOrchestrator` inherits from `DispatchMixin` + `ExtractionMixin`
- **Lazy imports:** Heavy subsystems deferred to avoid circular dependencies and slow imports
- **5-layer config hierarchy:** defaults → env vars → config files → init kwargs → runtime `configure()`
- **Facade pattern:** `SecurityManager` groups multiple security subsystems
- **Event-driven:** `EventEmitter` pub/sub bus for all pipeline stages
- **Thread-safe:** `RLock` guards all mutable orchestrator state

---

## Code Style Guidelines

### Mandatory File Header

Every Python file MUST start with:

```python
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Module docstring with spec section references (e.g., §3.2, §7.14)."""

from __future__ import annotations
```

### Ruff Configuration (from `pyproject.toml`)

- Target Python 3.10
- Line length: 100
- Selected rules: E, F, W, I, UP, B, SIM
- Ignored: E501 (line too long), E731 (lambda assignment), SIM102, SIM105, SIM108, SIM114, B905
- Per-file ignores for `tests/*`: F401, E402, F841, B007

### mypy Configuration

- `check_untyped_defs = true`
- `disallow_incomplete_defs = true`
- `no_implicit_optional = true`
- `warn_redundant_casts = true`
- `strict_equality = true`
- `warn_unused_configs = true`

### Common Conventions

- Use `from __future__ import annotations` in every module
- Use type hints throughout
- Use `logger = logging.getLogger(__name__)` pattern
- Use deferred/lazy imports to avoid circular dependencies
- Docstrings should reference specification sections (e.g., `§3.2`, `§7.14.3`)
- Use dataclasses for configuration and data types
- Prefer explicit over implicit; every public API should have type annotations

---

## Testing Strategy

**Framework:** pytest with pytest-asyncio and pytest-cov

**Coverage requirement:** 80% minimum (`--cov-fail-under=80`)

**Test files:** 37+ test modules in `tests/`

| Test Category | Files |
|---------------|-------|
| Smoke | `test_smoke.py` |
| Integration | `test_integration.py` |
| Phased feature tests | `test_phase1.py` through `test_phase9.py` |
| Live LLM integration | `test_live_*.py` (requires real API keys) |
| Security/compliance | `test_compliance_security.py`, `test_compliance_wiring.py` |
| Provenance engine | `test_decision_provenance*.py` |
| Adversarial testing | `test_adversarial_provenance.py` |
| Agentic dispatch | `test_agentic.py` |
| Benchmarks | `test_benchmarks.py` |
| Relay strategies | `test_relay_strategies.py` |
| Resource management | `test_resource_manager.py`, `test_adaptive_allocator.py` |
| Security modules | `test_security_modules.py` |
| Context enforcement | `test_context_enforcer.py`, `test_context_source.py` |
| Ledger | `test_manifest_ledger.py` |
| Conformance | `tests/conformance/` |
| Stress/diagnostic | `tests/killer_test/` |

**Mock provider pattern:** Tests use `CustomProvider` with fixed `generate_fn` — no external APIs required for most tests.

**Fixtures:** Shared fixtures are in `tests/conftest.py` (sample_task_intent, sample_system_prompt, sample_task_input).

---

## CI/CD

GitHub Actions workflows in `.github/workflows/`:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | push/PR to `main` | Lint (ruff), type check (mypy), test (pytest with coverage), dependency audit (pip-audit) across Python 3.10–3.13 |
| `docs.yml` | push to `main` when `site-docs/**` or `mkdocs.yml` changes | Build and deploy MkDocs site via `mkdocs gh-deploy` |
| `validate-schemas.yml` | push/PR when `schemas/**` changes | Validate JSON Schemas with ajv-cli (Node.js) |
| `link-check.yml` | push/PR to `main` | Check markdown internal links |

---

## Deployment and Distribution

**PyPI package:** `crprotocol` (wheels in `dist/`)

**Docker:** Single `Dockerfile` for HTTP sidecar
- Base: `python:3.13-slim`
- Non-root user (`crp`)
- Exposes port 8900
- Health check via HTTP to `/health`
- Installs `[cli]` + `[security]` extras only (no dev deps)
- Volume mount for `crp_sessions/`

**Distribution modes:**
1. **Embedded library** (primary): `pip install crprotocol` — zero deployment overhead
2. **HTTP sidecar** (optional): `crp serve` — inter-LLM context sharing, never auto-started
3. **Docker container**: For containerized deployments behind TLS reverse proxy

**Docs site:** MkDocs Material (`mkdocs.yml`) deployed to GitHub Pages

---

## Security Considerations

- **License guard:** `crp/license_guard.py` runs on import for advisory IP protection checks. `crp/__init__.py` calls `_license_startup_check()`.
- **Input validation:** Layer 1, cannot be disabled.
- **Injection detection:** Layer 2, advisory only (does not block).
- **Session binding:** HMAC-SHA256 key derivation.
- **Integrity chain:** BLAKE3 hash + HMAC per window.
- **Encryption at rest:** AES-256-GCM.
- **RBAC + rate limiting:** Built into sidecar and core.
- **Embedding defense:** SQ8 quantization + XOR salting.
- **Privacy:** Data classification, PII detection, retention policies, GDPR Art. 17 erasure.
- **Audit trail:** Tamper-evident HMAC-signed compliance audit trail.
- **Compliance framework:** EU AI Act + ISO 42001 aligned.

---

## Special Conventions

### Specification-driven Development

Every module references spec sections (e.g., `§3.2`, `§7.14.3`). There are 9 formal specification documents in `specification/` (~19,200 lines) plus 48 v4 specs in `SPECS_5_06_2026_CRP_v4/specs/`. RFC process for breaking changes is in `rfcs/`.

### Provider Abstraction

All LLM providers must implement `LLMProvider` ABC with 3 methods:
- `generate_chat(messages, **kwargs) -> tuple[str, str]`
- `count_tokens(text) -> int`
- `context_window_size -> int`

Built-in adapters: OpenAI, Anthropic, Ollama, llama.cpp. `CustomProvider` wraps any LLM in 3 lines.

### Quality Tiers

Every dispatch returns a `QualityReport` with tier `S/A/B/C/D` based on facts extracted, continuation count, saturation, finish reason, and output length.

### Zero In-window Overhead

CRP operates entirely outside the LLM's context window. No protocol tokens, no function call schemas, no memory management instructions inside the window.

### Dual Licensing

- Specification/docs: CC BY-SA 4.0
- Code: Elastic License 2.0 (prohibits "CRP-as-a-Service" without enterprise license)

---

## Authentication, User Management & PostgreSQL Migration

**Canonical plan:** `SPECS_5_06_2026_CRP_v4/CRP-AUTH-POSTGRESQL-MIGRATION-PLAN.md`

This section governs how CRP Gateway, CRP Comply, and CRP Scan share identity, entitlement, and persistent state. Read this BEFORE modifying any auth, billing, user, or database code.

### Core Principle

> **Clerk = WHO you are and WHAT you can access (entitlement).**  
> **PostgreSQL = WHAT you have done (application state).**

Never store entitlement in PostgreSQL. Never store application state in Clerk metadata.

### The Five Critical Rules

1. **Clerk is the single entitlement writer.** Stripe webhooks write to Clerk `public_metadata` ONLY. Apps read from Clerk metadata ONLY. PostgreSQL never stores plans, tiers, or quotas.
2. **Per-product plan keys.** Use `comply_plan`, `gateway_plan`, `scan_plan` — never a shared `"plan"` key. This enables independent subscriptions.
3. **API keys are hashed.** Store SHA-256 in PostgreSQL. Return plaintext ONCE at creation. Never log plaintext keys.
4. **Signed state tokens for OAuth.** GitHub App `state` parameters must be HMAC-SHA256 signed with 10-min TTL. Never pass raw `user_id`.
5. **`resolve_account()` everywhere.** Use `Identity(user_id, org_id, org_role)` → `resolve_account()` → `("org", org_id)` or `("user", user_id)`. Personal accounts work when `org_id` is null.

### Shared Code (`crp_shared/`)

Both repos import from a shared package:

```python
from crp_shared.auth import Identity, resolve_account, current_clerk_identity, get_entitlement
from crp_shared.db import init_db, get_db
```

**Identity dataclass:**
```python
@dataclass(frozen=True)
class Identity:
    user_id: str      # Clerk sub claim
    org_id: str | None   # Clerk org_id claim (null for personal)
    org_role: str | None # Clerk org_role claim
```

** resolve_account:**
```python
def resolve_account(identity: Identity) -> tuple[str, str]:
    if identity.org_id:
        return ("org", identity.org_id)
    return ("user", identity.user_id)
```

**get_entitlement:**
```python
async def get_entitlement(identity: Identity, product: str) -> dict:
    # Reads from Clerk metadata via Backend API
    # product = "comply" | "gateway" | "scan"
    # Returns {"plan": "...", "quota": N, "credits": N, "stripe_customer_id": "..."}
```

### Clerk Metadata Schema (canonical)

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

### PostgreSQL Schema Overview

**Shared instance, two logical databases:** `crp_gateway` and `crp_comply`.

**Shared tables (both DBs):**
- `tenants` — links Clerk identity to app state
- `api_keys` — hashed API keys with scopes

**Gateway-specific tables (`crp_gateway`):**
- `gateway_systems` — registered AI systems
- `gateway_providers` — encrypted LLM provider keys
- `gateway_documents` — CKF ingested docs
- `gateway_usage` — per-call audit trail

**Comply-specific tables (`crp_comply`):**
- `github_installations` — GitHub App installations
- `github_repos` — connected repositories
- `scan_results` — governance scan outputs
- `compliance_reports` — generated reports
- `evidence_packs` — tamper-evident exports

### Railway Setup

**Recommended:** One Railway project "CRP Production" with:
- Service: `gateway` (from `crp-gateway` repo, `main` branch)
- Service: `comply` (from `crp-comply` repo, `master` branch)
- Service: `postgres` (shared PostgreSQL)
- Service: `redis` (shared Redis, optional)

**Database URLs:**
```
Gateway: postgresql://gateway_app:PASS@postgres.railway.internal:5432/crp_gateway
Comply:  postgresql://comply_app:PASS@postgres.railway.internal:5432/crp_comply
```

**Clerk configuration:**
- Production domain: `crprotocol.io` (parent)
- Allowed origins: `https://comply.crprotocol.io`, `https://gateway.crprotocol.io`
- Session cookie domain: `.crprotocol.io` (enables SSO)
- Both apps use **identical** `CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY`

### Migration from Legacy Stores

**Comply `data/users.json` → PostgreSQL:**
```python
# Run once at startup during transition period
for user in auth_manager._users.values():
    tenant_id = user.get("clerk_org_id") or user["id"]
    account_type = "org" if user.get("clerk_org_id") else "personal"
    await db.execute("""
        INSERT INTO tenants (tenant_id, clerk_org_id, clerk_user_id, account_type, name)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (tenant_id) DO NOTHING
    """, tenant_id, user.get("clerk_org_id"), user["id"], account_type, user.get("name"))
```

**Gateway in-memory `_tenants` → PostgreSQL:**
```python
# Lazy migration: on first lookup miss, check legacy dict and migrate
async def get_tenant(tenant_id: str) -> dict | None:
    row = await db.fetchrow("SELECT * FROM tenants WHERE tenant_id = $1", tenant_id)
    if row:
        return dict(row)
    # Fallback to legacy in-memory store during transition
    legacy = _tenants.get(tenant_id)
    if legacy:
        await migrate_legacy_tenant(legacy)
        return legacy
    return None
```

### Environment Variables

The canonical per-service variable checklist has been moved out of the public
repository. It is shared with Enterprise and white-label customers under NDA.
When deploying CRP Gateway or CRP Comply, configure:

- A PostgreSQL logical database per service.
- Redis for distributed rate-limiting and idempotency (multi-replica Gateway).
- Identity-provider and billing-provider credentials in a secrets manager.
- Service `APP_BASE_URL` and inter-service URLs.
- Per-tenant LLM provider keys; never set global provider keys unless in dev.

### Dead Code to Remove After Migration

| Module | Why Dead | Action After Migration |
|--------|----------|----------------------|
| `AuthManager._users` (JSON file) | Replaced by `tenants` table | Remove volume mount, delete `data/users.json` |
| `AuthManager._api_keys` (JSON file) | Replaced by `api_keys` table | Remove file, use SQL only |
| `_tenants` in-memory dict (Gateway) | Replaced by `tenants` table | Remove module-level dict |
| `_connected_repos` in-memory dict | Replaced by `github_repos` table | Remove from `github_routes.py` |
| `billing/webhook.py` (dead code) | Replaced by live webhook | Delete or archive |

---

## Quick Reference for Agents

**Before editing any file:**
1. Check if the file has a spec section reference in its docstring — read that section for context.
2. Ensure the copyright header and `from __future__ import annotations` are present.
3. Run `ruff check crp/ tests/` and `mypy crp/ --ignore-missing-imports` before committing.
4. Run `pytest tests/ -v --tb=short --cov=crp --cov-report=term-missing --cov-fail-under=80` to ensure tests pass.
5. If adding new public API, add it to `crp/__init__.py` and `__all__`.
6. If adding lazy-loaded types, register them in `crp/__init__.__getattr__`.

**When adding tests:**
- Use `CustomProvider` with a mock `generate_fn` to avoid external API calls.
- Place tests in `tests/test_<feature>.py`.
- Use fixtures from `conftest.py` where applicable.

**When modifying schemas:**
- Update the corresponding JSON Schema in `schemas/`.
- The `validate-schemas.yml` workflow will validate it automatically.

**When implementing Agent-B deliverables:**
- Read the corresponding spec in `SPECS_5_06_2026_CRP_v4/specs/` FIRST.
- Follow the `CRPv4_Implementation_Rounds.md` pseudocode closely — it is canonical.
- Ensure Checkpoint resolution NEVER leaves user with raw error — always graceful fallback.
- NEVER let `CRP-*` headers reach LLM providers (Axiom 4).
- SDK methods must be invisible by default — progressive disclosure (SPEC-032 §1).
- Comply upgrade (SPEC-042) is the most important product change in R3.
- Stripe webhook MUST verify HMAC and NEVER grant on success page alone.
- GitHub App tokens are ~1h, NEVER persist, use immediately and discard.

**When modifying auth / user management / billing:**
- Read `SPECS_5_06_2026_CRP_v4/CRP-AUTH-POSTGRESQL-MIGRATION-PLAN.md` FIRST.
- Use `Identity` + `resolve_account()` for all tenant resolution.
- Write entitlement to Clerk metadata ONLY (Stripe webhook).
- Read entitlement from Clerk metadata ONLY (`get_entitlement()`).
- Store application state in PostgreSQL ONLY (never in-memory or JSON).
- Use per-product plan keys: `comply_plan`, `gateway_plan`, `scan_plan`.
- Hash all API keys with SHA-256 before storage.


---

## Site Documentation & Publishing

The public site at `https://crprotocol.io` is built with **MkDocs Material** from the `site-docs/` directory.

### Local build and quality checks

```bash
# 1. Strict build
.venv/Scripts/python -m mkdocs build --strict

# 2. Automated audit (catches formatting issues, leaks, dead refs)
.venv/Scripts/python scripts/audit_docs.py
```

You MUST get a clean exit from both before pushing. The audit script returns a non-zero exit code for ERROR-level findings (unclosed fences, broken tables, dead references, confidential leaks). Fix every error; triage warnings using `docs/DOCS_QUALITY_STRATEGY.md`.

### Deploy

Do **not** run `mkdocs gh-deploy` locally. Deployment is handled automatically by GitHub Actions:

- Workflow: `.github/workflows/docs.yml`
- Trigger: push to `main` that changes `site-docs/**`, `mkdocs.yml`, `.github/workflows/docs.yml`, or `pyproject.toml`
- Dependencies: installed from the `docs` extra in `pyproject.toml` (`pip install -e ".[docs]"`)
- Action: `mkdocs gh-deploy --force --strict` publishes the `site/` directory to the `gh-pages` branch
- Live URL: `https://crprotocol.io`

After pushing, monitor the run:

```bash
gh run list --workflow=docs.yml --limit 5
gh run view <run-id> --log
gh run watch <run-id>
```

If the run fails, read the log, fix the strict-mode warning or dependency error, and push again. Recent failures were caused by an invalid package name (`pymdownx-extensions`) in the workflow; the workflow now installs the documented `docs` extra from `pyproject.toml`.

### What to keep in sync

- **Value propositions** on the homepage (`site-docs/index.md`), `why-crp.md`, `who-is-it-for.md`, and every product page must match the actual capabilities in `crp/`.
- **SDK surface** in `site-docs/sdk/` and `site-docs/guides/sdk.md` must reflect the real `CRPClient` API. After adding an SDK method, document it and add a code example.
- **Product pages** (`products/gateway.md`, `products/comply.md`, etc.) must
  reflect the actual managed-cloud status: CRP Gateway and CRP Comply managed
  cloud are live at `gateway.crprotocol.io` and `comply.crprotocol.io`. Say
  "managed cloud live; self-host and white-label available" for live products,
  and "coming soon" only for products that are genuinely not yet released.
- **Railway / deployment docs** must not expose environment variable names,
  third-party integration fields, or live payment-provider identifiers on the
  public site. The public self-hosting guide is `site-docs/guides/gateway-railway.md`;
  the canonical internal variable checklist is maintained outside the public
  repository and shared with Enterprise customers under NDA.

### Pages that should always be reviewed after SDK changes

- `site-docs/index.md` — hero + value props
- `site-docs/why-crp.md`
- `site-docs/who-is-it-for.md`
- `site-docs/getting-started/quickstart.md`
- `site-docs/guides/sdk.md`
- `site-docs/sdk/index.md`
- `site-docs/sdk/context-management.md`
- `site-docs/sdk/ai-safety.md`
- `site-docs/sdk/configuration.md`
- `site-docs/products/gateway.md`
- `site-docs/products/comply.md`
- `site-docs/products/visualise.md`
- `site-docs/products/scan.md`

### Adding a new docs page

1. Create the `.md` file under `site-docs/`.
2. Add it to the `nav:` section in `mkdocs.yml`.
3. Run `mkdocs build --strict` locally.
4. Push to `main`; the site updates within ~1 minute of the workflow completing.
