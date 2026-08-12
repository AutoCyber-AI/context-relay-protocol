# CRP SDK Context & AI Safety Implementation Gap Report

**Scope:** `crp/` Python SDK vs. CRPv4 / CRPv3 specs (SPEC-001–048).  
**Focus:** context-management primitives, AI-safety enforcement, and user-visible surfaces.  
**Generated:** 2026-06-15 during v4.1 hardening and SDK reference rebuild.

---

## Executive summary

The CRP codebase contains **far more capability than is exposed or wired end-to-end**. Many context-management and AI-safety modules are implemented as standalone libraries but are not integrated into the live request path (`crp.gateway.GatewayRequestLifecycle` / `examples/crp_demos/v4/server.py`) or the progressive SDK (`crp.sdk.CRPClient`). The result is a large surface of **hidden features** that solve real governance problems but are not enforceable or visible to users today.

This report is the basis for closing those gaps.

---

## 1. Hidden context-management capabilities

The following modules are implemented in `crp/` but are **not used by the v4 demo server or the progressive SDK**.

| Capability | Where implemented | Why it matters | Current state |
|------------|-------------------|----------------|---------------|
| **Semantic Task Layer (STL)** | `crp.stl.*` | Classifies operations, negotiates depth, builds goal compass | Scaffold; `stl_execute()` simulates calls |
| **Context Differential Retrieval (CDR)** | `crp.envelope.cdr.py` | Coverage-differential ranking; prevents redundant context | Implemented, not called by envelope builder |
| **Context Differential Graph Retrieval (CDGR)** | `crp.ckf.cdgr.py` | Multi-hop graph retrieval across documents | Implemented, not integrated |
| **Retrieval integrity** | `crp.envelope.retrieval_integrity.py` | Recency decay, contradiction detection, parallel coverage isolation | Implemented, not invoked |
| **Multi-horizon context** | `crp.state.horizons.py` | PERSISTENT / CONVERSATIONAL / EPHEMERAL tier blending | Implemented, not wired to SDK |
| **Scratch buffer** | `crp.state.scratch_buffer.py` | Ephemeral tool context with TTL | Implemented, not wired to `@client.tool` |
| **CSO relay** | `crp.state.cso.py` | Carries decisions/facts across continuation windows | Implemented; Gateway logs but does not call `relay_cso()` |
| **Continuation manager** | `crp.continuation.manager.py` | Formal continuation loop, residual anchors, exit rules | Implemented; Gateway does not drive it |
| **Extraction pipeline** | `crp.extraction.pipeline.py` | 6-stage fact extraction | Implemented; demo uses simple splitting |
| **Pluggable storage backends** | `crp.state.backends.*` | SQLite/Redis/S3 backends | Memory + SQLite present; Redis/S3 lazy |
| **Advanced strategies** | `crp.advanced.*` | Hierarchical, parallel, meta-learning, source grounding | Implemented, not exposed |

### User-visible outcome gap

A user calling `client.ask(...)` today does **not** benefit from CDR/CDGR, STL depth negotiation, multi-horizon context, scratch buffers, CSO relay, or the full extraction pipeline. The response may still be good, but the documented governance pipeline is not fully exercised.

---

## 2. Hidden AI-safety capabilities

The following safety features are implemented but **not consistently enforced** in the live request path.

| Capability | Where implemented | Spec | Enforcement gap |
|------------|-------------------|------|-----------------|
| **Safety policy engine** | `crp.policy.enforce.py` | SPEC-006 | Full engine exists; Gateway does not call `enforce_policy()` |
| **Agent safety budget** | `crp.agent.budget.py` | SPEC-012 | Gateway uses ad-hoc `0.05/0.02` decrement; no `DEPLETED` circuit breaker |
| **Checkpoints / HITL** | `crp.security.checkpoint.py` | SPEC-033/034 | Checkpoint object created but never waits for resolution |
| **Full DPE** | `crp.provenance.*` | SPEC-005 | Gateway uses lightweight heuristic DPE only |
| **Canonical window HMAC chain** | `crp.provenance.window_chain.py` | SPEC-011 | Gateway uses its own SHA-256 tip; header not verifiable |
| **Input validator** | `crp.security.validation.py` | SPEC-033 | Exposed via demo endpoint but not consistently wired |
| **Injection detector** | `crp.security.injection.py` | SPEC-033 | Exposed via demo endpoint but not consistently wired |
| **PII scanner** | `crp.security.privacy.py` | SPEC-033/034 | Exposed via demo endpoint but not consistently wired |
| **Safety coverage map** | `crp.security.coverage.py` | SPEC-034 | Configurable but not surfaced in SDK responses |
| **Embedding defense** | `crp.security.embedding_defense.py` | SPEC-015 | Implemented, not wired |

### Score → enforcement mapping

| Header / score | Produced by | Enforced in Gateway? | Visible? |
|----------------|-------------|----------------------|----------|
| `CRP-Safety-Hallucination-Risk` | `crp/provenance/hallucination_scorer.py` | Partial (policy engine not called) | Yes, header emitted |
| `CRP-Agent-Safety-Budget` | `crp/agent/budget.py` | **No** — ad-hoc decrement | Header emitted |
| `CRP-Context-Quality-Tier` | `crp/headers/emit.py` | **No** — accept-quality not parsed | Header emitted |
| `CRP-Quality-Score` / `Flow` / `Completeness` | RQA modules | **No** — not consumed by continuation loop | Header emitted |
| `CRP-Safety-Grounding-Pct` | `crp/provenance/attribution_scorer.py` | Partial | Yes |
| `CRP-Provenance-Chain-Integrity` | `crp/provenance/window_chain.py` | Header only | Yes |
| `CRP-Context-Mode` / `Mode-Transition` | `crp/activation/mode.py` | **No** — `ModeState` not used | Header emitted |

**Bottom line:** many safety signals are emitted as headers but the deterministic gating layer is incomplete.

---

## 3. SDK visibility gaps

The progressive SDK (`crp.sdk.CRPClient`) has the right shape but several visibility APIs are stubs.

| SDK member | Status | Note |
|------------|--------|------|
| `client.complete()` | Partial | Works for basic calls; lacks streaming/policy integration |
| `client.ask()` | Partial | Does not invoke CDR/CDGR/STL/continuation as documented |
| `client.session()` | Partial | No chat object with multi-thread support |
| `client.tool()` | Stub | Decorator registers functions but no tool-calling dispatch |
| `client.knowledge.*` | Stub | `_KnowledgeProxy` does not reflect real CKF |
| `client.storage.overview()` | Stub | `_StorageProxy` placeholder |
| `client.audit.*` | Partial | Export methods exist but are not integrated with Gateway audit |
| `client.compliance.*` | Partial | Evidence generation exists but no live Comply stream |
| `client.agent()` | Stub | Multi-agent budget not enforced |

---

## 4. Recommended closure order

To make the SDK cohesive and complete, tackle these in order:

1. **End-to-end safety wiring** — Make `GatewayRequestLifecycle` consume `RequestDirectives` and call `crp.policy.enforce.enforce_policy()`. Map every `EnforcementAction` to the correct HTTP status/body.
2. **Agent safety budget enforcement** — Replace ad-hoc decrement with `AgentSafetyBudget.account()` and halt on `DEPLETED`.
3. **Checkpoint gating** — Wait for checkpoint resolution before returning a HIGH/CRITICAL response.
4. **Envelope integration** — Replace stub `_step10_build_envelope` with real CDR/CDGR/retrieval-integrity pipeline backed by session CKF.
5. **CSO relay** — Call `relay_cso()` after each window and emit canonical chain headers.
6. **Continuation loop** — Drive `ContinuationManager` from Gateway for `depth="exhaustive"` and long tasks.
7. **Progressive SDK wiring** — Implement `client.ask()` to orchestrate CDR/CDGR/STL/continuation/DPE end-to-end.
8. **Visibility APIs** — Replace `_KnowledgeProxy` and `_StorageProxy` stubs with real CKF/storage introspection.
9. **Generated API docs** — Add `mkdocstrings` so docstrings become site pages.
10. **Parity tests** — Add tests that prove each score header maps to a deterministic enforcement action.

---

## 6. Hardening update (2026-06-05)

A focused scoring-hardening pass closed several of the gaps above:

- **`tests/test_scoring_robustness.py`** now exercises attribution, hallucination risk, CDR, safety-budget, policy enforcement, gateway DPE proxy, header emission, and boundedness properties. It runs against Meta Llama 3.1 8B Instruct on LM Studio when available and passes with deterministic scorers when offline.
- **`AgentSafetyBudget.account()` is now used by the gateway** (`crp/gateway/api.py` Step 18). The ad-hoc `0.05/0.02` decrement was replaced with the formal LOW/MEDIUM/HIGH/CRITICAL decrements from SPEC-012, eliminating the budget-accounting divergence.
- **`block-ungrounded` no longer counts MIXED claims as ungrounded**. A new `block-mixed` directive was added to `SafetyPolicy` / grammar / enforcement so operators can choose to block partially-grounded claims explicitly rather than having `block-ungrounded` over-reach.
- **`CDRScoredFact.components`** exposes the raw scoring signals (`relevance`, `novelty`, `residual_pull`, `effective_relevance`, `importance`, `cdr_score`) for introspection and calibration.
- **Policy violation type `MIXED_CONTENT`** added; `SafetySignals` now carries `mixed_count` separately from `ungrounded_count`.
- **Calibration harnesses added** in `crp/provenance/calibration.py` for attribution and hallucination risk, exposing AUC, precision/recall, FPR/FNR, and best-F1 thresholds so hard-coded constants can be tuned against labelled data.

Remaining larger gaps now closed in this pass:

- **`GatewayRequestLifecycle` now calls `enforce_policy()`** and maps `HALT`/`WARN`/`REDISPATCH` actions to the correct audit events and safety-halt responses.
- **Checkpoint gating is wired end-to-end**: HIGH/CRITICAL responses wait for `Checkpoint.wait_for_resolution()`; rejection promotes the response to a 451 safety halt.
- **CSO relay is invoked after every window** via `relay_cso()`, and the returned CSO ID is persisted in the session token.
- **`_step10_build_envelope` is no longer a stub**: it runs CDR ranking, CDGR multi-hop connector expansion, and retrieval-integrity contradiction resolution when a CKF is attached to the router or cached on the session.
- **SDK graceful fallback is fixed**: `CRPClient.complete()` and `ask()` return `finish_reason="error"` when orchestrator dispatch fails or no real provider is configured.
- **SDK visibility proxies now reflect real orchestrator state** (`warm_store` and `ckf`) instead of returning placeholder data.
- **`mkdocstrings` is installed and configured** for auto-generated API docs, with a `docs` optional-dependency group in `pyproject.toml`.

Small residual items: full DPE engine as the default gateway scorer (the lightweight DPE proxy remains the fast path), and driving `ContinuationManager` from the Gateway for `depth="exhaustive"` (currently exercised through the SDK only).

---

## 5. SDK reference pages created

To expose what **is** available today, the following site pages were added:

- `site-docs/sdk/index.md` — complete method map and Level 0–3 reference
- `site-docs/sdk/context-management.md` — every context primitive, visible fields, and enforcement table
- `site-docs/sdk/ai-safety.md` — every safety layer, visible fields, and enforcement table
- `site-docs/sdk/configuration.md` — full `crp.config.yaml` schema
- `site-docs/sdk/async.md` — async mirror of sync methods
- `site-docs/sdk/errors.md` — exception hierarchy and error codes
- `mkdocs.yml` updated with a top-level **SDK Reference** section
