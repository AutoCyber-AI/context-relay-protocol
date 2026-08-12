<!-- SPDX-License-Identifier: CC-BY-4.0 -->
<!-- Copyright 2025-2026 AutoCyber AI Pty Ltd / Constantinos Vidiniotis -->

# CRP v3.0 — FINAL Implementation Plan

**Document:** CRP-V3-IMPLEMENTATION-PLAN
**Version:** 2.0 (supersedes the header-only draft)
**Date:** 2026-05-29
**Current codebase:** `crp` v2.3.2 → **Target:** v3.0.0
**Source:** Full cross-reference of SPEC-001 … SPEC-017 against the `crp/` Python package.

---

## 0. Executive Summary

The v2 codebase is **algorithmically rich but protocol-silent**. It computes nearly all the
hard things (claim attribution, fabrication/distortion/entailment, hallucination scoring,
CKF + HNSW + Leiden, HMAC fact chains, EU AI Act / ISO 42001 classification) but it does
**not speak the protocol**: it emits no CRP HTTP headers, has no declarative Safety Policy,
no safety budget, no session-token relay, no ETag/conditional dispatch, no HTTP 451 halt, no
Zero-CKF onboarding mode, and no conformance test suite.

**v3 is therefore NOT mostly "header plumbing".** It is several genuinely new *architectural*
subsystems plus a header surface over the existing engine:

| # | New subsystem | Spec | v2 status |
|---|---------------|------|-----------|
| A | **Protocol surface** — 58 headers + session-token relay + ETag/304 + HTTP 451 | 002, 007 | MISSING |
| B | **Safety Policy engine** — CSP-style directive parser + enforcer + profiles + inheritance | 006 | MISSING |
| C | **Safety Budget + Multi-Agent safety** — budget depletion, circuit breaker, propagation | 012 | MISSING |
| D | **Progressive activation (Zero/Partial/Full-CKF) + onboarding** | 017 | MISSING |
| E | **RQA + regulatory amplifiers** (extends existing DPE) | 005 | PARTIAL |
| F | **Window DAG / fan-in HMAC / continuation transfer types / audit export** | 004, 011 | PARTIAL |
| G | **Conformance test suite + test vectors** | 014 | MISSING |
| H | **crp-scan GitHub Action (SARIF)** — separate product | 013 | MISSING |
| I | **CRP Gateway managed service** — separate product | 016 | MISSING |

**Approximate v3 readiness today: ~30%.** The engine exists; the protocol does not.

---

## 1. What v2 ALREADY Has (reuse — do not rewrite)

These map almost 1:1 to spec requirements and only need to be *wired to the header surface*:

| Capability | Spec | v2 location |
|------------|------|-------------|
| Claim segmentation (FACTUAL/OPINION/PROCEDURAL/META) | 005 §3 | `provenance/claim_detector.py` |
| Attribution / grounding % | 005 §4 | `provenance/attribution_scorer.py` |
| Fabrication detection | 005 §5.2 | `provenance/fabrication_detector.py` |
| Distortion detection (6 types) | 005 §5.3 | `provenance/distortion_detector.py` |
| Intra-window contradiction | 005 §5.4 | `provenance/contradiction_detector.py` |
| NLI entailment scoring | 005 §6 | `provenance/entailment_verifier.py` |
| Per-claim hallucination risk + base composite | 005 §7,§16 | `provenance/hallucination_scorer.py` |
| Omission detection | 005 §12 | `provenance/omission_analyzer.py` |
| DPE report generation | 005 §13 | `provenance/report_generator.py` |
| Envelope packing (greedy + bookend) | 003 | `envelope/packer.py`, `builder.py`, `scoring.py` |
| Quality tier S/A/B/C/D | 002,003 | `core/dispatch_router.py::_classify_quality_tier` |
| CKF fabric, HNSW, Leiden communities, state hash | 009 | `ckf/fabric.py`, `community.py`, `semantic.py` |
| Fact integrity HMAC chain | 011,015 | `security/integrity.py` |
| Compliance audit trail (HMAC, ~15 event types) | 011 | `security/audit_trail.py` |
| EU AI Act / NIST / ISO 42001 classification | 010 | `security/compliance.py` |
| PII detection | 015 | `security/privacy.py` |
| Dispatch strategies (push/batch/hierarchical/parallel) | 008 | `core/dispatch_router.py`, `core/batch.py`, `advanced/parallel.py`, `hierarchical.py` |
| TaskIntent | 008 §2 | `core/task_intent.py` |
| Continuation / flow / completion / stitch | 004,005 | `continuation/*.py` |
| Session binding + encryption + HKDF primitives | 007,015 | `security/binding.py`, `encryption.py` |

---

## 2. The Gaps — Organised into Workstreams

### WORKSTREAM A — Protocol Surface (SPEC-002, SPEC-007)

**A1. Header module `crp/headers/`** (NEW)
- `names.py` — 58 header-name constants (the 10 IANA-priority first).
- `emit.py` — `HeaderEmitter`: maps `DPE_Report` + `QualityReport` + session state → `dict[str,str]`.
- `parse.py` — `parse_request_headers()`: reads inbound CRP headers (policy, accept-quality, accept-strategy, accept-risk, if-match, cache, grounding-mode, session-token, data-residency, reproducibility-seed).
- `middleware.py` — ASGI/WSGI middleware (FastAPI/Starlette) that runs dispatch and injects response headers.
- **Header families to emit:** `CRP-Context-*` (tier, saturation, facts-used, tokens-used, strategy, window, session-id, etag, cache-status, protocol-version), `CRP-Safety-*` (hallucination-risk/score, attribution, grounding-pct, fabrications, distortions, contradictions, omissions, entailment-score, oversight-mode, retry-after), `CRP-Provenance-*` (hmac, window-hmac, dag-root, chain-integrity, claim-count, attribution-score, fidelity-score, window-lineage, report-uri), `CRP-Compliance-*` (eu-ai-act, nist-tier, gdpr-pii, iso-42001, audit-trail-id/uri, controls-met, data-residency), `CRP-Agent-*` (phase, loop-depth, safety-budget, tool-calls, session-parent, revision-round), `CRP-Memory-*` (tier-hit, ckf-hits, ckf-community, knowledge-age), `CRP-Quality-*` (repetition, completeness, flow, score).

**A2. Axiom-4 header stripping** (NEW — SPEC-015, SPEC-014 TV-002)
- Allowlist filter in the provider call path (`providers/`, `adapters.py`): **no** `CRP-*` header may reach the LLM. Add explicit test.

**A3. ETag + conditional dispatch (HTTP 304)** (NEW — SPEC-002 §4.8-4.11, SPEC-003 §11)
- `CRP-Context-ETag` = SHA-256 of sorted `fact_id:content_hash` set (reuse `ckf/fabric.py` state hash).
- `CRP-Context-If-Match` → if match, return 304, skip envelope rebuild.
- `CRP-Context-Cache` directives: `no-store`, `no-cache`, `reuse-ckf`, `only-if-ckf` (424), `max-age`.

**A4. HTTP 451 halt response** (NEW — SPEC-001 §4.2, SPEC-006 §3.2)
- Halt body: `crp_halt_reason`, `session_id`, `audit_trail_uri`, `retry_condition`; sets `CRP-Safety-Retry-After`.

**A5. Session token v3 (SPEC-007)** — extend `security/binding.py`
- Payload: `v, sid, win, qh[], sb, ct, cid, dag, str, pol, ckf, scope, iat, exp, nonce` (≤4KB base64url).
- Signing: `HKDF-SHA256(master_key, salt=sid, info="crp-session-sign-v3", L=32)` → `HMAC-SHA256`.
- `CRP-Set-Session` / `CRP-Session-Token` headers; refresh every response.
- Validation: signature (constant-time), expiry→401, **chain-tip→409**, scope→403, **policy-hash tightening→403**, **nonce→400**.
- Dual master-key rotation (`kv` field); store chain tips in KV (Redis/DynamoDB) for multi-instance relay.

---

### WORKSTREAM B — Safety Policy Engine (SPEC-006) — *entirely new*

**B1. `crp/policy/` module** (NEW)
- `grammar.py` — ABNF parser (RFC 5234) → `SafetyPolicy` dataclass; reject malformed.
- `model.py` — directives: `default-src`, `halt-on`, `warn-on`, `require-grounding`, `require-entailment`, `require-quality`, `require-flow`★, `require-completeness`★, `block-ungrounded`, `block-pii`, `block-fabrication`, `block-repetition`★, `max-repetition`★, `upgrade-on-risk`, `oversight`, `report-uri`.
- `enforce.py` — `enforce_policy(policy, dpe_report) → PASS|WARN|HALT|UPGRADE|REDISPATCH`; "most restrictive wins" precedence.
- `profiles.py` — `medical`, `financial`, `developer`, `public-facing` named profiles (§6).
- `mode.py` — `CRP-Safety-Mode` shorthand (`strict`/`warn`/`permissive`) + `CRP-Safety-Policy-Report-Only`.
- `report.py` — POST violation JSON to `report-uri`.
- `nonce.py` — `CRP-Safety-Nonce` bound to policy hash (replay defence).

**B2. Policy inheritance (multi-agent)** (NEW — SPEC-006 §5, SPEC-012 §4)
- Child policy MUST be ≥ restrictive than parent; relax → HTTP 403; emit `CRP-Safety-Policy-Applied`.

---

### WORKSTREAM C — Safety Budget + Multi-Agent Safety (SPEC-012) — *entirely new*

**C1. `crp/agent/budget.py`** (NEW)
- `AgentSafetyBudget`: start 1.0; decrement LOW 0.00 / MEDIUM 0.05 / HIGH 0.15 / CRITICAL 0.35; re-dispatch does **not** decrement (only final delivered response does); no recovery within session.
- Thresholds: >0.50 healthy; 0.25–0.50 caution (warning header); 0.10–0.24 force human-review; ≤0.10 HTTP 451; ≤0.00 halt session.
- Budget lives in the **signed** session token (anti-inflation).

**C2. Circuit breaker** (NEW) — CLOSED / HALF-OPEN (force reflexive, block new delegations) / OPEN (451).

**C3. Multi-agent orchestration** (NEW)
- Downstream propagation: budget, policy, session-parent, loop-depth, safety-mode, data-residency.
- Upstream propagation: budget, hallucination-risk, provenance-hmac, chain-integrity, audit-trail-uri, quality-score.
- `min()` budget merge on fan-in; loop-depth / `max_delegations` / `max_dag_nodes` limits (403 on exceed).
- Cross-agent HMAC linking (`SUB_AGENT_RESULT` event); cross-agent coherence/completeness (DPE §6/§8 across agents).
- Oversight token flow: `CRP-Oversight-Token: approved:sha256:<sig>` releases a halted response.

> **PRIVATE:** SPEC-012 internals are NOT published. Implement in the closed reference codebase only. Do not commit design docs to the public specs repo.

---

### WORKSTREAM D — Progressive Activation / Zero-CKF (SPEC-017) — *entirely new*

**D1. `crp/activation/mode.py`** (NEW)
- Mode detection from CKF fact count: **Zero** (0), **Partial** (1–999, quality capped at B), **Full** (1000+).
- Per-call coverage check in Partial: retrieve at relevance ≥0.60 → coverage ratio → cap tier or treat as zero for that call.
- Transition rules (sticky) + `MODE_TRANSITION` audit event + ETag invalidation.
- Zero-CKF DPE skip set: run Stages 1,2,5,6,7,8,9,11,12,13; Stage 3 limited, Stage 4 on-query, Stage 10 skipped; force PARAMETRIC grounding.
- Auto policy adjustment: `block-ungrounded`→`warn-ungrounded`, relax `default-src context`→`+parametric`, skip `require-grounding`; keep `halt-on`, `block-pii` active.

**D2. Onboarding overlay (14-day, time-based)** (NEW)
- Headers: `CRP-Context-Mode`, `CRP-Context-Mode-Transition`, `CRP-Activation-Status`, `CRP-Activation-Features`, `CRP-Context-Coverage`, `CRP-Onboarding-Active/Days-Remaining/Next-Action/Hint`, `CRP-Safety-Policy-Adjustment` (10 new headers).
- Progressive feature cascade: 0→safety-only; 1+→attribution; 50+→community; 100+→tier B; 500+→tier A; 1000+→tier S.

---

### WORKSTREAM E — DPE completion: RQA + amplifiers (SPEC-005) — *extends existing*

**E1. Regulatory amplifiers (§17)** — ❌ MISSING — add to `provenance/hallucination_scorer.py`:
GDPR-PII ×1.30, EU-AI-Act-HIGH ×1.25, financial/medical ×1.20, agentic depth>2 ×1.15, cross-window contradiction ×1.20, SEVERE repetition ×1.10; cap at 1.0.

**E2. RQA composite quality score (§18)** — ❌ MISSING — new:
`quality_score = 0.25·(1-repetition) + 0.35·completeness + 0.25·flow + 0.15·(1-contradiction)`; downgrade tier by score; emit `CRP-Quality-Score`.

**E3. Upgrade existing PARTIAL stages to v3 thresholds:**
- Stage 6 cross-window: severity classification + NLI re-check + ×1.20 amplifier (`advanced/cross_window.py`).
- Stage 7 repetition: n-gram ratio + semantic cosine (SEVERE >30% n-gram / >50% semantic) (`advanced/cqs.py`).
- Stage 8 completeness: sub-query decomposition + auto-continuation trigger (`continuation/completion.py`).
- Stage 9 flow: 4-signal score (opening/topic/register/transition) + stitch insertion <0.30 (`continuation/flow.py` + `stitch.py`).
- Re-dispatch protocol (§19): temp 0.2, strategy upgrade, new seed, max 2 per window.

**E4. New quality headers:** `CRP-Quality-Repetition`, `-Completeness`, `-Flow`, `-Score`.

---

### WORKSTREAM F — Window DAG + Audit (SPEC-004, SPEC-011) — *extends existing*

**F1. Formal DAG edges** (`core/window.py`) — `transfer_type` (FULL_CONTEXT/SUMMARY/FACTS_ONLY/RESULT_ONLY), `transferred_tokens`, `summary_hash`; invariant validation.
**F2. Window-level HMAC** — `HMAC(session_id‖window_number‖ts‖response_hash‖dpe_report_hash‖prev_window_hmac, key)` → `CRP-Provenance-HMAC`.
**F3. Fan-in HMAC merge** — sort parent HMACs, concat, hash.
**F4. Continuation lifecycle** — 4-step protocol, transfer-type selection under budget pressure, context summarisation (non-billable LLM call, fidelity >0.80).
**F5. Quality-history degradation detection** in session token (`qh[]`).
**F6. Audit trail completion** — add ~22 missing event types; `verify_chain()` → VALID/BROKEN/PARTIAL/UNVERIFIED → `CRP-Provenance-Chain-Integrity`; **NDJSON / OCSF / SARIF** export methods.
**F7. Envelope refinements** — primacy-recency "sandwich" (replace bookend), 3 grounding modes with weight adjustments, ETag computation.
**F8. CKF additions** — Fact Quarantine (§8.4), cache directives `only-if-ckf`/`max-age`, GDPR 30-day erasure timeline + audit event.

---

### WORKSTREAM G — Conformance Suite (SPEC-014) — *new deliverable*

- `tests/conformance/` with JSON **test vectors** TV-001…TV-051+ (basic header set, Axiom-4 stripping, 451 on CRITICAL, 304 ETag, DPE detections, policy parse/inheritance, HMAC chain valid/broken, session token sig/expiry, budget depletion).
- Test runner executable against any CRP endpoint.
- Conformance levels: **CRP-Basic** (7 mandatory headers), **CRP-Standard** (58 headers + policy + compliance), **CRP-Full** (9 strategies + multi-agent + streaming + OCSF + Comply).
- Publish to `AutoCyber-AI/crprotocol-conformance-tests` (separate public repo).

---

### WORKSTREAM H — crp-scan GitHub Action (SPEC-013) — *separate product*

- New repo `AutoCyber-AI/crp-scan`: `action.yml` (Docker), Python detection engine (LLM SDKs + agent frameworks + raw HTTP + prompt patterns), confidence levels, gap analysis, **SARIF v2.1.0** output (rules CRP001-CRP005) → GitHub Security tab, remediation + Comply signup funnel, CLI mode. Marketplace listing.

---

### WORKSTREAM I — CRP Gateway service (SPEC-016) — *separate product, later*

Managed multi-region service: OpenAI-compatible + CRP-native endpoints, ingestion API, admin API, tiers/quotas/rate-limits, onboarding, BYOK, well-known discovery. Largely out of scope for the v3.0 *library* release; tracked separately as the commercial product. The existing `cli/sidecar.py` is the seed.

---

## 3. Build Order (phased)

```
PHASE 1 — Protocol surface MVP  (Workstream A, parts of E)
  crp/headers/{names,emit,parse,middleware}.py
  Axiom-4 stripping + test
  Wire the 10 IANA headers from existing DPE/quality/HMAC outputs
  Regulatory amplifiers (E1) + RQA score (E2) so safety headers are spec-correct
  → Deliverable: every dispatch returns correct CRP headers. CRP-Basic level reachable.

PHASE 2 — Safety Policy engine  (Workstream B)
  crp/policy/* (parser, enforce, profiles, mode, report, nonce)
  HTTP 451 halt (A4) + Safety-Retry-After
  → Deliverable: halt-on / require-* / block-* enforced; profiles work.

PHASE 3 — Session token v3 + ETag/304  (A3, A5, F2)
  Extend security/binding.py to v3 payload + HKDF + chain-tip/policy/nonce validation
  ETag + conditional dispatch + cache directives
  Window-level HMAC + chain-integrity header
  → Deliverable: stateless relay, 304 caching, tamper-evident window chain. CRP-Standard reachable.

PHASE 4 — Safety budget + multi-agent  (Workstream C)  [PRIVATE]
  crp/agent/budget.py + circuit breaker + propagation + inheritance + oversight token
  → Deliverable: multi-agent safety. CRP-Full reachable.

PHASE 5 — Progressive activation / Zero-CKF  (Workstream D)
  crp/activation/* + 10 onboarding headers + feature cascade
  → Deliverable: day-one UX, graceful empty-CKF behaviour.

PHASE 6 — DAG/audit completion + RQA stage upgrades  (F, E3)
  transfer types, fan-in HMAC, summarisation, 22 audit events, NDJSON/OCSF/SARIF export
  Stage 6/7/8/9 v3 thresholds + re-dispatch protocol

PHASE 7 — Conformance suite + release  (Workstream G)
  tests/conformance/ + runner + conformance-tests repo
  pyproject version → 3.0.0, PyPI publish, GitHub release, update homepage stats

PHASE 8 — crp-scan Action  (Workstream H)  [separate repo, parallelisable from Phase 1]

PHASE 9 — Gateway service  (Workstream I)  [commercial product, post-3.0]
```

---

## 4. Testing Strategy & Test Applications

- **Unit:** every new module (`headers/`, `policy/`, `agent/`, `activation/`) gets a dedicated `tests/test_*.py`. **Never run the full suite in parallel** (PC crashes — repo rule).
- **Conformance vectors:** `tests/conformance/` JSON TVs assert exact header values for known inputs.
- **Integration test app:** `examples/v3_demo.py` — FastAPI app with `CRPHeaderMiddleware` + `CRP-Safety-Policy` request → verify headers, 451 halt, 304 caching, Zero-CKF onboarding headers end-to-end.
- **Second implementation (IETF interop):** a minimal Node or Go client that consumes/echoes session tokens — required for Proposed Standard. Can be a thin reference, not a full engine.
- **Provider compatibility:** matrix tests against OpenAI/Anthropic/Ollama verifying Axiom-4 stripping + tokenizer selection.

---

## 5. What Stays Private / Out of Scope for the public spec + v3.0 library

- **SPEC-012 multi-agent internals** and **Stop-Inject** mechanism — implement closed-source only; never publish.
- **SPEC-007 §3 exact key-derivation hardening details** beyond the published HKDF info string.
- **SPEC-016 Gateway** and **SPEC-013 scan Pro features** — commercial products, separate repos, post-3.0.
- **Exact DPE weights / amplifier values** — keep symbolic in the public spec (already scrubbed).

---

## 6. Readiness Scorecard (today)

| Spec | Engine exists | Protocol surface | Net v3 readiness |
|------|--------------|------------------|------------------|
| 001 Core | ✅ | ❌ 451/conformance levels | ~40% |
| 002 Headers | ✅ (values) | ❌ emission | ~15% |
| 003 Envelope | ✅ | ⚠️ sandwich/ETag/modes | ~60% |
| 004 Continuation | ⚠️ | ❌ DAG edges/fan-in HMAC | ~50% |
| 005 DPE | ✅ | ⚠️ amplifiers/RQA | ~70% |
| 006 Safety Policy | ❌ | ❌ | ~5% |
| 007 Session token | ⚠️ | ❌ v3 payload | ~35% |
| 008 Dispatch | ✅ | ⚠️ matrix/headers | ~60% |
| 009 CKF | ✅ | ⚠️ quarantine/cache | ~73% |
| 010 Regulatory | ⚠️ | ❌ headers | ~40% |
| 011 Audit | ✅ | ⚠️ events/export/window HMAC | ~60% |
| 012 Multi-agent | ❌ | ❌ | 0% |
| 013 GitHub Action | ❌ | ❌ | 0% |
| 014 Conformance | ❌ | ❌ | 0% |
| 015 Security | ⚠️ | ⚠️ | ~50% |
| 016 Gateway | ❌ | ❌ | ~2% |
| 017 Zero-CKF | ❌ | ❌ | 0% |

**Critical path to a credible v3.0 library release:** Phases 1→2→3→7 (protocol surface, policy, token/ETag, conformance). Phases 4–6 raise it to CRP-Full. Phases 8–9 are separate products.

---

_End of plan._
