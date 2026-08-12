# CRPv6 Research Corpus — Complete Document Analysis

**Date:** 2026-07-31 · **Corpus:** `AutoCyber AI Agentic AI research with CRP/` (20 documents + 2 benchmark scripts + 6 diagrams)
**Method:** 11 parallel deep analyses; every document read in full and every concrete demand gap-checked against the live `crpv6-agent-sdk` repo state (IMPLEMENTED / PARTIAL / MISSING with file evidence).
**Synthesis:** the prioritized outcome of this analysis is the approved CRPv6 completion plan (session plan of 2026-07-31): Waves 1-3 below mirror its sequencing; Phase A operational detail lives in `docs/CRPv6_PhaseA_Action_Plan.md`.

## Cross-corpus synthesis (what MUST be done for a complete CRPv6)

Convergent gaps (demanded by multiple independent documents):

| Gap | Demanded by | Status |
|---|---|---|
| Governed-vs-bare ASR benchmark in repo + CI (governed ASR == 0 sweep) | Security Ch.32, Evaluation Ch.9/28/37, Collateral, Compendium, Economics | MISSING |
| Stats toolkit: pass^k + bootstrap CI + McNemar | Evaluation, Economics, Compendium | MISSING |
| Egress/information-flow taint rule (labels -> approved sinks) | Tool Use, Security, Benchmark harness | MISSING |
| LiveModel adapter + public attack dataset (AgentDojo/InjecAgent) | Benchmark bundle, Collateral | MISSING |
| Audit-chain hardening: Merkle proofs + external anchoring + Ed25519 | Provenance capstone, Compendium, Collateral | PARTIAL (HMAC chain only) |
| TEL: real SSE endpoint (heartbeats+replay), NLI-backed faithful narration, real-chain provenance | Transparency, Tool Use | PARTIAL (library, no wire) |
| XGrammar/GBNF real constrained decoding at Gateway (SPEC-054) | Impl. Spec, Tool Use T3, Voice, Economics | PARTIAL (post-hoc validate+repair) |
| Wire inert built code: SPEC-051 PP, SPEC-055 EP, SPEC-057 BTF as_of, QSR ladder | Impl. Spec, Grounding | PARTIAL (built, never called) |
| Kill-switch + runtime detection/trust decay | Security Ch.19/24/33 | MISSING |
| Memory write-authority lattice + governed recall/remember + memory eval | Memory Ch.13/17/19 | MISSING |
| Autonomy-by-measurement (ASR/pass^k -> tier -> enforced autonomy) | Evaluation Ch.16 | MISSING |
| SPEC-058 Governed Delegation | Security, Evaluation, Compendium, Memory | MISSING (only spec with zero code) |
| MCP supply-chain gateway hardening | Security Ch.23/30 | MISSING |
| Reference agents (voice/compliance/pentest) + quickstart + funnel proof | Voice, Report Engine, SDK Completion, Developer Brief | MISSING |
| Publish SPEC-049-059 docs to site-docs/spec (catalogue stops at 048) + correction log | Developer Brief, SDK Completion | MISSING |

Explicitly deferred by the corpus itself: SPEC-045 session learning, long-horizon world models beyond `crp/pp`, ontology-grounded CKF, parametric continual learning.

---

## Per-document analyses


<!-- ==================== Architecture_of_Tool_Use_source.md and Architecture_of_Transparency_source.md ==================== -->
Analysis complete. Both documents read in full (Tool Use: 1,516 lines; Transparency: 1,440 lines), and every demand was checked against the live `crp/` tree (TEL, tools/TCF, agent_sdk, gateway, vr, qsr, ep, clr, frontend).

---

# Document 1 — `Architecture_of_Tool_Use_source.md`

## 1. What it is

Second volume of the AutoCyber series (July 2026). Thesis: "tool use" is not one capability but a **nine-stage inner loop** (select → parameterise → validate → execute → capture → parse → verify/interpret → contextualise, wrapped by narration), and correctness/governance must be enforced *structurally*: the model expresses **bounded intent** (intent-compiler pattern), a deterministic policy gate disposes, and everything is provenance-chained. Scores CRP v5.1 per stage (Ch. 28) and proposes a six-item CRP roadmap **T1–T6** (Ch. 29), a 7-point tool-use standard (Ch. 30), and honestly-open problems (Ch. 31).

## 2. Concrete demands on CRPv6

From the §29 roadmap (sequencing: T1 → T2+T3 → T4 → T5 → T6) and §30 standard:

- **T1 — Typed Tool Manifest & Parameter Catalog (keystone spec):** machine-readable manifest per tool with `when_to_use`/`when_not_to_use`, typed **intent model**, declared **effect** (read_only/idempotent/irreversible), **safety class** (auto/gated/hitl), `requires_privilege`, worked **examples**, pointer to a **compiler** (schema sketch in Appendix C).
- **T2 — Intent-compiler convention** (§8.8, Template 5): model fills a small safe `ScanIntent`-style typed intent under constrained decoding; a **deterministic, versioned, unit-tested compiler** emits the real invocation + provenance. Model never emits raw flags.
- **T3 — Constrained Dispatch at the Gateway:** schema/grammar-constrained decoding enforced **at the proxy** (Outlines/XGrammar/GBNF/`response_format` strict), so structural validity is a property of infrastructure, not the model.
- **T4 — Tool-Result Envelope:** `{invocation, outcome, parsed_result, parse_confidence, raw_ref, provenance}` — parsed structure in-window, raw out-of-window by reference, timeout/partial as first-class outcomes, dedupable via CDR, hashed into the audit chain.
- **T5 — Selection-as-retrieval over the CKF:** index T1 manifests, retrieve top-k via CDR/CDGR, log selections to the quality-tier flywheel so tool routing self-improves.
- **T6 — Narration Faithfulness Contract:** NLI-entailment-check every narrated claim against the Tool-Result Envelope/trace before display (Templates 9/11).
- Supporting demands: deterministic **scope/CIDR gate** the model cannot bypass (§9, Template 6); **Z3/SMT validation** of combinatorial flag legality (§8.6, Template 6); **structured-first parsing** with verified LLM fallback (§11); **grounding verification of tool outputs** — point DPE at captures (§12); **environment grounding** of parameter values (§8.9); **loop avoidance** (`already_tried`) + hard budgets + replanning (§13); explicit **recovery ladder** retry→reflect→replan→escalate→abstain (§35); **clarification as a first-class selection branch** (§7C); **eval harness** with per-stage metrics where `scope_safety_rate` is a gate, not a score (§36); **concurrency + transient-only retry + call/time budgets over the gate** (Part V hardening, tied to SPEC-026/033).

## 3. Explicit TODOs stated in the document

- Build order: T1 first, then T2+T3, T4, T5, T6 (§29).
- [OPEN] items (§31): auto-derive safe intent+compiler from man pages/OpenAPI; general output parsing without per-tool parsers; detecting deceptive/degraded tool output; long-horizon tool planning; **learned parameter priors from quality-tier telemetry** (flagged as a research-paper thread); safe autonomous exploration in adversarial environments.
- §36: build a DIY safety+faithfulness eval harness (public benchmarks don't encode engagement scope).

## 4. Gap check

| Demand | Status | Evidence |
|---|---|---|
| T1 manifest | **PARTIAL** | `crp/tools/descriptor.py` (SPEC-050) has kind, operation_types, schemas, safety_class, mutual exclusions, residency, embeddings + `schemas/capability-descriptor.json`. Missing: `when_to_use`/`when_not_to_use`, effect class, `requires_privilege`, examples, intent-model/compiler pointer. |
| T2 intent-compiler | **MISSING** (as the report means it) | `crp/agent_sdk/intent_compiler.py` is a *registration* compiler (Python callable → ToolSpec/descriptor), not the safe-intent → deterministic-argv pattern. The model still fills raw tool arguments, validated post-hoc by the executor. |
| T3 constrained dispatch | **PARTIAL** | `crp/gateway/router.py:235` passes `response_format` through to the provider; `CapabilityRouter` validates args against `input_schema` with `allow_repair`. No gateway-side grammar/GBNF/XGrammar enforcement. |
| T4 Tool-Result Envelope | **PARTIAL→mostly** | `ToolObservation` (`crp/tools/executor.py`) is typed, provenanced, has `invocation_id` + `scratch_ref` (raw-by-reference); `ResultEnvelope` in `tool_manifest.py`. Missing: `parse_confidence`, `timeout`/`partial` outcome classes (only ok/validation_failed/error/not_registered). |
| T5 selection-as-retrieval | **IMPLEMENTED** (over TCF, not CKF) | `crp/tools/capability_fabric.py`: registry + embedding/lexical retrieval, policy pre-filter, dependency/mutual-exclusion resolution, profile-bounded top-K. Not indexed in CKF via CDR/CDGR; selection-telemetry→tool-routing flywheel not closed (QSR harvests the audit chain for *model* routing only). |
| T6 narration faithfulness | **PARTIAL** | `crp/tel/faithful.py` implements `entailment_check`/`filter_faithful` but as a word-subset approximation ("production implementation may swap in an NLI model") and **nothing calls it** — `Agent.run_tel()` streams text unfiltered. |
| Scope/CIDR gate | **MISSING** | No cidr/scope primitive anywhere in `crp/`; generic policy gating exists (`crp/policy`, TCF `PolicyContext`). |
| Z3 flag-legality | **PARTIAL** | `crp/vr/z3_verifier.py` (SPEC-049) proves arithmetic/constraint *reasoning claims*, not pre-execution tool-flag legality. |
| Grounding verification of tool outputs | **PARTIAL** | Per-tool `ToolResultExtractor` parsing pattern exists; DPE/VR verify claims vs sources/reasoning, not parsed values vs raw captures. |
| Loop avoidance + budgets | **PARTIAL** | `max_operations` hard cap in `crp/agent_sdk/agent.py:120`; no `already_tried` triple-tracking or no-progress detection. |
| Recovery ladder | **PARTIAL** | `crp/qsr/escalation.py` is a model-escalation ladder, not the §35 per-stage failure taxonomy in the agent loop. |
| Clarification branch | **IMPLEMENTED** | `crp/clr` (SPEC-053) + `agent._maybe_clarify` + `CLARIFICATION_REQUESTED` → TEL `INTERRUPT`. |
| Safety-gate eval harness | **MISSING** | No `scope_safety_rate`-style harness; unit tests only. |
| Concurrency/resilience/budgets | **PARTIAL** | v3 `crp/advanced/` has parallel fan-out; agent_sdk executor has no async fan-out or transient-vs-permanent retry distinction. |

## 5. Priority picks

1. **T2 intent-compiler as a first-class ToolSpec field** (add `intent_model` + `compiler` to SPEC-050/059 manifests) — the report's headline recommendation; converts CRP's worst scorecard gap (parameterisation) into the "provably safe tool use" differentiator, and it's a contained schema+convention change.
2. **T6 wired, NLI-backed narration faithfulness** — `faithful.py` already exists; connecting it to `run_tel`'s text stream and swapping the word-subset check for the DeBERTa/NLI machinery already in `crp/provenance` is small effort for the "provably faithful narration" claim no competitor makes. Both documents converge on this.
3. **T3 constrained decoding enforced at the Gateway** (strict `json_schema` for capability args; GBNF path for local SLMs) — makes structural validity an infrastructure property, which is the core of the SLM-first story and the highest-leverage reliability fix for small models.

---

# Document 2 — `Architecture_of_Transparency_source.md`

## 1. What it is

Third volume of the series (July 2026). Thesis: **display is the product and faithfulness is the contract** — stream a standard (AG-UI-compatible), tiered (casual→auditor), entailment-checked account of what the agent actually did, because transparency is the precondition for governance, audit, and trust. Twelve templates cover the event model, SSE server, session bus, state sync, HITL interrupts, faithful narration, progress, renderers, and a CRP bridge; Part V gives the **CRP v5.1 display scorecard** (§25) and the **D1–D6 roadmap** (§26).

## 2. Concrete demands on CRPv6

From §26 (sequencing D1 → D2+D3 → D4 → D5 → D6) and the §27 seven-point display standard:

- **D1 — CRP→AG-UI event mapping (keystone):** emit standard `RUN_*`, `STEP_*`, `TEXT_MESSAGE_*`, `REASONING_*`, `TOOL_CALL_*`, `STATE_SNAPSHOT/DELTA` from the CRP runtime (Template 12) so any AG-UI frontend renders a CRP agent.
- **D2 — Governance event vocabulary:** namespaced `CUSTOM` events `crp.safety_scan`, `crp.policy`, `crp.risk`, `crp.retrieval`, `crp.quality` (+`crp.progress`, `crp.continuation`, `crp.provenance` per Appendix C), with a **published schema**.
- **D3 — Faithful Narration Contract:** every `TEXT_MESSAGE_CONTENT` summary sentence NLI-entailment-checked against the event trace before streaming; shipped as a guarantee (Template 7).
- **D4 — Live Provenance Layer:** stream the **HMAC audit chain link-by-link** so clients verify tamper-evidence themselves; define an **A2UI provenance-viewer component**.
- **D5 — Quality & confidence streaming:** tier + calibrated confidence as an always-visible casual badge (counters over-trust).
- **D6 — Resumable transparency:** snapshot+delta + `Last-Event-ID` replay backed by a **Redis stream**, so a CSO-relayed engagement can be left and resumed with full transparency.
- Supporting demands: **SSE transport with heartbeats, replay, per-session isolation** (§5.1, Template 2); **WebSocket HITL interrupt back-channel** that fails closed on timeout (Template 6); **honest progress/ETA with confidence labels** (Template 8); **braided narrative+structure on one stream**; **four-tier progressive disclosure** frontends (Templates 10–11, Mission-Control layout §21); **A2UI declarative generative UI** — never executable agent markup (§22); **OpenTelemetry GenAI-convention operator tracing** linked to user sessions via a `crp.trace` event (§31); **stream security**: losable-vs-unlosable backpressure policy, auth-bound subscription, JSON-Patch `__proto__` hardening, run budgets (§32).

## 3. Explicit TODOs stated in the document

- Build order D1 → D2+D3 → D4 → D5 → D6 (§26).
- Publish the CRP display-event schema (Appendix C) and **lead the missing cross-vendor governance-event vocabulary standard** (§28 [OPEN]).
- [OPEN] (§28): faithful narration at production latency; provenance UIs non-experts understand; honest ETAs for nondeterministic agents; empirically-optimised disclosure tiers; cross-session resumable transparency (CRP is positioned to own this).

## 4. Gap check

| Demand | Status | Evidence |
|---|---|---|
| D1 AG-UI mapping | **IMPLEMENTED** | `crp/tel/events.py` (SPEC-056 §8.3.1) has the full ~16-event vocabulary incl. `STATE_*`, `MESSAGES_SNAPSHOT`, `INTERRUPT`, `CUSTOM`; `crp/tel/adapter.py::map_agent_event` maps internal agent events; `Agent.run_tel()` (`agent.py:503`) yields the stream. Tests: `test_tel.py`, `test_tel_sse.py`. |
| D2 governance vocabulary | **IMPLEMENTED** (minor gaps) | Adapter emits `crp.safety_scan`, `crp.verification`, `crp.quality`, `crp.retrieval`, `crp.prediction`, `crp.provenance`, `crp.policy`, `crp.progress`, `crp.intent`, `crp.run_complete`. Missing: standalone `crp.risk`, `crp.continuation`; no published JSON schema for display events in `schemas/` (only `stream-event.json` base). |
| D3 faithful narration | **PARTIAL** | `crp/tel/faithful.py` exists but is a word-subset approximation, and **it is not wired into the stream** — `run_tel` emits narrative deltas unfiltered. No NLI backing. |
| D4 live provenance | **PARTIAL** | `crp.provenance` event + `crp/tel/report.py` exist, but `run_tel` emits a placeholder sha256 (`prev="0"*64`, session-payload hash), **not the real HMAC window chain** from `crp/provenance`. No client-verification protocol, no A2UI viewer. |
| D5 quality streaming | **IMPLEMENTED** | `crp.quality` events with tier/confidence; optional semantic-entropy field backed by `crp/ep/semantic_entropy.py`. |
| D6 resumable transparency | **PARTIAL** | `SessionBus` has a replay buffer + `replay_after`; `stream_events(last_event_id=...)` implements resume. Missing: Redis/durable backing (in-memory only), cross-session persistence, and — critically — **no HTTP SSE server exists**; `crp/frontend/console.py` points at `/v1/chat/stream`, which no gateway route implements. `heartbeat_interval` is accepted by `stream_events` but never used. |
| INTERRUPT + HITL back-channel | **PARTIAL** | `INTERRUPT` type, constructor, and clarification→interrupt mapping exist; there is **no WebSocket/POST-back approval channel or await-decision/resume mechanism** (no websocket code in `crp/`). Fail-closed timeout semantics absent. |
| Honest progress/ETA | **PARTIAL** | `crp.progress` event carries percent/eta/confidence; no ETA computation from step telemetry in the agent. |
| Four-tier disclosure frontend | **PARTIAL** | `crp/frontend/console.py` is a single-page chat console with a raw event panel — no casual/power/developer/auditor tiering, no Mission-Control layout, no auditor verify button. |
| A2UI generative UI | **MISSING** | No A2UI references in `crp/`. |
| OTel GenAI observability | **PARTIAL/MISSING** | `crp/observability/metrics.py` has an OTLP-JSON envelope (zero-dep) but not OTel GenAI semantic-convention spans, no `crp.trace` event linking stream↔trace. |
| Stream security hardening | **PARTIAL** | Subscriber queues bounded (maxsize 256) but no losable/unlosable drop policy; no auth-bound subscription (library-level only); JSON-Patch client hardening N/A (no official JS client). |

## 5. Priority picks

1. **Serve the stream: a real SSE endpoint with heartbeats + replay** (FastAPI/sse-starlette at the Gateway, backed by `SessionBus`/`stream_events`) — TEL is currently a library with a working event model but no wire; the shipped console's `/v1/chat/stream` is a dead URL. This converts D1/D6 from code to product and is mostly plumbing.
2. **D3 done properly: faithful narration wired and NLI-backed** — same pick as the Tool-Use volume (their T6 ≡ this D3); gate `TEXT_MESSAGE_CONTENT` through `filter_faithful` backed by the existing DeBERTa entailment stack. Cheapest available "nobody else ships this" claim.
3. **D4 real-chain provenance** — replace the placeholder hash in `run_tel` with links from the actual HMAC audit chain (`crp/provenance` window chain) so the auditor tier verifies something real; the A2UI viewer can wait, the chain cannot.

---

## Cross-document note

The two volumes are deliberately convergent: **T6 = D3** (faithful narration), **T4 envelope = D6's resumable evidence**, **T1 manifest ↔ D2 schema** (both are "publish a typed artefact" moves). The single highest-value shared work item is the **faithfulness pipeline** (one NLI verifier serving tool-output grounding §12, narration gating T6/D3, and the DPE), followed by **serving TEL over HTTP SSE** and the **T1/T2 manifest+intent-compiler** upgrade. Nothing in either roadmap contradicts the current SPEC-049–059 architecture — both docs explicitly frame their roadmaps as extensions of machinery CRP already has, and the repo state confirms the foundations (TCF retrieval, TEL event model, policy layer, audit chain) are in place.

<!-- ==================== Architecture_of_Understanding_source.md and AutoCyber_CRP_Collateral_Pack_source.md ==================== -->
Analysis complete. Both documents fully read (Understanding: 1,616 lines; Collateral Pack: 99 lines) and gap-checked against the `crpv6-agent-sdk` branch.

---

# Document 1 — `Architecture_of_Understanding_source.md`

### 1. What it is
A 4-part technical report (July 2026) on what constitutes machine "understanding" in agentic AI, proposing a ten-component model (syntax → semantics → pragmatics → knowledge → reasoning → memory → world-modelling → meta-cognition → normativity → routing) with runnable local-SLM Python templates for each. Its core thesis: in SLM-first systems components 3–10 live *outside the model* in the protocol layer — which is CRP's architecture — and it audits CRP v5.1 against the model, ending in a five-item spec-shaped roadmap (R1–R5). It explicitly flags epistemic tiers [SHIPPED]/[RESEARCH]/[OPEN] and lists what honestly doesn't exist.

### 2. Concrete demands on CRPv6
The scorecard (Part IV) and Appendix B reduce to five roadmap specs plus standing requirements:

- **R1 — Verification Relay ("highest impact", the #1 gap):** a 14th DPE stage for *step-level* reasoning verification (PRM-style judge, depth-gated to thorough/exhaustive); symbolic verifiers as first-class dispatch targets (sandboxed Python/PAL, SymPy, Z3, datalog-over-CKF, graph-constrained decoding) — LLM-Modulo natively in the protocol; wire self-consistency/semantic-entropy divergence into quality tiers and risk; verifier-scored, self-curating RTL (traces stored with PRM scores, pruned by outcome).
- **R2 — Quality-Tier-Supervised Routing ("highest leverage, low effort"):** train operation/model/depth router on CRP's own logged (task, decision, quality-tier) triple; per-model capability profiles measured by SQB (SPEC-026); `escalate-on quality<B` / `escalate-on confidence<0.5` as **Safety Policy Directive verbs**; per-profile schema-simplification transform (flat SLM-friendly schemas, Kim et al. 2025); Gateway-enforced grammar-constrained decoding (Outlines/XGrammar/llguidance).
- **R3 — Predictive Positioning ("frontier-credible"):** rule induction over the event-sourced action log (state-pattern, action → outcome, p-success); rules stored as `causal=True` intervention-grade CKF edges; pre-dispatch rule check; simulate-before-act gating on HIGH/CRITICAL feeding the existing checkpoint HITL (anticipatory EU-AI-Act Art. 14 oversight).
- **R4 — Interpretation Layer ("low effort, standards wedge"):** pre-envelope intent/speech-act tagging (sub-500M classifier, ~10 ms, tag travels as envelope metadata); session-scoped coreference rewriting against an entity registry *before* retrieval ("resolution precedes retrieval"); a structured **`CRP-Clarification-Required`** response type with options, confidence, and resumption semantics — explicitly absent from MCP/A2A, a first-mover standardisation opportunity.
- **R5 — Epistemic Profiles ("trust dividend"):** per-model, per-task-type calibration curves accumulated from DPE-verified outcomes; positioning consumes them (stricter thresholds for measured-overconfident models); exportable as evidence; **bi-temporal validity intervals** on CKF facts (valid-from/valid-to vs recorded-at).
- **Standing/other:** ontology-grounding option over CKF types for domain agents (Wave 3, OG-RAG +55% recall, ties to SPEC-044); CKF already judged leading (CDR/CDGR/event-sourcing, bookends, CSO relay — "keep"); private contamination-resistant benchmark with unanswerable/ambiguous items, per-kind accuracy + selective accuracy + calibration gap (ECE); abstention as a routing outcome with provenance; honest-claims discipline (never claim strong comprehension, general causal discovery, ToM, unified calibration, on-device continual learning).

### 3. Explicit TODOs in the document
- **This month:** deploy intent+coref interpretation layer in front of retrieval; enforce grammar-constrained tool calls at Gateway; start logging the routing-supervision triple; add `escalate-on` to the policy language.
- **This quarter:** ship Verification Relay (distil step judge to ≤2B verifier; SymPy/Z3/sandbox dispatch targets); wire consistency-divergence into quality tiers; train first quality-tier-supervised router from telemetry; add bi-temporal validity to CKF facts.
- **This year:** Predictive Positioning + accompanying arXiv paper ("agent action logs as intervention data"); epistemic profiles as exportable evidence; clarification-semantics draft into IETF conversation.
- Sequencing: R2/R4 weeks-scale; R1 the quality headline; R3 the research story; R5 rides R1's verification data.

### 4. Gap check (vs. branch `crpv6-agent-sdk`)
| Demand | Status | Evidence |
|---|---|---|
| R1 Verification Relay (DPE stage-14, LLM-Modulo loop, tier cap/risk floor) | **IMPLEMENTED** | `crp/vr/` (SPEC-049): `relay.py` (generate-critique-repair loop, caps quality tier, raises risk floor), `prm.py`, `extract.py` |
| R1 symbolic verifiers as dispatch targets | **IMPLEMENTED** | `crp/vr/z3_verifier.py`, `crp/vr/exec_verifier.py` (datalog-over-CKF/graph-constrained decoding not confirmed — **PARTIAL** tail) |
| R1 distilled ≤2B PRM step-verifier | **PARTIAL** | `crp/vr/prm.py` wired; model training in progress on GPU (Phase A), not yet published |
| R1 consistency-divergence → tiers/risk | **IMPLEMENTED** | `crp/ep/semantic_entropy.py` (SPEC-055) + relay tier-capping |
| R2 learned router on quality tiers + telemetry harvest | **IMPLEMENTED** | `crp/qsr/router.py` (SPEC-050 §2.3.3, learned classifier w/ cold-start), `harvest.py`, `profiles.py` (capability profiles) |
| R2 schema simplification per model profile | **IMPLEMENTED** | `crp/qsr/schema_adapt.py`; also `crp/gateway/capability_router.py` |
| R2 grammar-constrained decoding | **IMPLEMENTED** | `crp/extraction/structured_output.py` (Outlines FSM, GBNF, logit masking, JSON repair) |
| R2 `escalate-on` as **policy grammar verb** | **PARTIAL** | `crp/qsr/escalation.py` exists, but `crp/policy/grammar.py` only shows `halt-on`-class verbs — no escalate verb in SPDL grammar |
| R3 Predictive Positioning (world model, rule induction, simulate-before-act, causal edges) | **IMPLEMENTED** | `crp/pp/` (SPEC-051): `world_model.py`, `induction.py`, `simulate.py`, `causal_ckf.py` |
| R4 intent/speech-act pre-envelope layer | **IMPLEMENTED** | `crp/isa/intent.py` + SetFit model trained/published (Phase A); `crp/isa/position.py` |
| R4 session coreference rewriting before retrieval | **IMPLEMENTED** | `crp/isa/coref.py` (SPEC-052 §4.3.2, rule-based + lazy fastcoref via `crp.ml`) |
| R4 `CRP-Clarification-Required` primitive | **IMPLEMENTED** | `crp/clr/` (SPEC-053): `response.py` (Interpretation/options/confidence), `trigger.py`, `handler.py`; also `crp/security/clarify.py` |
| R5 epistemic profiles (calibration curves as evidence) | **IMPLEMENTED** | `crp/ep/calibration.py` (SPEC-055 §7.3.2, per-(model, task-kind) reliability curves), `apply.py` |
| R5 bi-temporal CKF validity | **IMPLEMENTED** | `crp/btf/temporal.py` (SPEC-057, `BiTemporalFact` valid-from/valid-to vs recorded-at) |
| Ontology-grounding option over CKF (Wave 3) | **MISSING** | No ontology module; tied to deferred SPEC-044 (frontier) |
| Verifier-scored self-curating RTL | **PARTIAL/UNKNOWN** | RTL exists from v3 (`crp/advanced`); PRM-score pruning of traces not confirmed |
| Hardware-aware local resource management | **MISSING** | Doc itself flags as [OPEN, adjacent] — no demand to build now |

The R1–R5 roadmap has been executed almost 1:1 as v6 SPECs (049–057): R1→vr, R2→qsr, R3→pp, R4→isa+clr, R5→ep+btf. Remaining true gaps are thin: the PRM model finishing, the `escalate-on` policy verb, ontology layer.

### 5. Priority picks
1. **Finish + publish the PRM step-verifier and make `crp/vr` depth-gated default in the agent loop.** R1 is the doc's "#1 gap" and quality headline; it's the only roadmap item whose code exists but whose model artifact is still in flight.
2. **Add `escalate-on` verbs to the SPDL policy grammar** (one-line-per-rule link between normative layer and `crp/qsr`). R2 is rated "highest leverage / low effort"; everything else for it is built — this is the missing wire.
3. **Ontology-grounding option over CKF types.** The one knowledge-stack wave with no v6 module; strong empirical case (+55% fact recall, OG-RAG) and it converts SPEC-044's domain-agent story from retrieval to validity — but it's frontier-tier, so sequence it after 1–2.

---

# Document 2 — `AutoCyber_CRP_Collateral_Pack_source.md`

### 1. What it is
A marketing/sales derivative pack condensing the whole research series into four audience-facing pieces: an investor one-pager, a buyer FAQ, a regulator-facing obligations brief, and a 14-slide pitch-deck outline. Its unified thesis: SLM-first + local + a deterministic policy gate outside the model simultaneously fixes agentic AI's security, cost, and compliance problems, and the governance byproduct (tamper-evident evidence) is the revenue product (Comply > Gateway > Scan-funnel).

### 2. Concrete demands on CRPv6
Every load-bearing product claim the pack makes, which the code must back:

- **Deterministic policy gate outside the model** — model proposes, gate disposes; blocks out-of-scope/exfiltration/irreversible-without-approval actions; measured **~0.24 µs/action** overhead (§2 FAQ, §4 slide 9).
- **Governed-vs-bare benchmark as the proof artifact** — attack success ~15% → 0%, zero utility cost, holds at 5× model injectability (§1 "The proof", slide 9; flagged as "mechanism illustration").
- **Tamper-evident audit chain** — "hash-chained, **Merkle-proofed, externally anchored, and signed**"; separates encrypted content from hash-only events to honour erasure rights (§2 "Isn't this just logging?").
- **Six-framework evidence at control level** — EU AI Act (Art. 12 logging, 14 oversight, 15 robustness, 72 post-market monitoring, 73 incident reporting in 15 days), DORA (Art. 6/17/24 TLPT/28–31), HIPAA §164.312(b), NIST AI RMF, ISO 42001 Annex A, **AIUC-1 all 51 controls** incl. B6/D3/E15 (§3).
- **Verification relay** as part of the Art. 15 story (§3).
- **Safety control plane with approval gates + kill-switch** for Art. 14 human oversight (§3).
- **Continuous runtime monitoring + incident detection** with timestamped tamper-evident record (Art. 72/73) (§3).
- **On-device/local inference** so PHI/financial data never leaves boundary (§2, §3 HIPAA).
- **Configurable, tunable policies** with audit visibility of what was blocked and why ("governance is a dial") (§2).
- **Model- and infra-agnostic operation** over existing stacks (§2).
- **Product trio:** CRP Scan (free VS Code funnel that "finds governance gaps in your agent codebase"), CRP Gateway (governed runtime), CRP Comply (audit-ready evidence, main revenue) (§1, §2, slide 12).
- **SLM-first economics** — 1–2 orders cheaper/token, "~84% cheaper at scale" (slide 10).

### 3. Explicit TODOs in the document
This is collateral, not a roadmap; its stated next steps are:
- "All regulatory and pricing facts are 2026-current directional; **verify primary sources before external use**" (repeated 3× — EUR-Lex, ESAs, HHS/OCR, NIST, ISO).
- Keep appendix slides in reserve (seven-pillar map, sector deep-dives, pentest economics, AIUC-1 control mapping).
- Standing honesty disclaimer: CRP produces evidence and enforcement, **is not itself a certification** — accredited auditor certifies.
- Implicit: the "how do I start" funnel (Scan → Gateway → Comply) must actually work as described for the deck to be true.

### 4. Gap check
| Demand | Status | Evidence |
|---|---|---|
| Deterministic policy gate outside model | **IMPLEMENTED** | `crp/policy/` (grammar/enforcement), `crp/agent_sdk/policy.py`, safety control plane (v4 SPEC-033); the 0.24 µs figure comes from the research harness |
| Governed-vs-bare benchmark reproducible | **PARTIAL** | Exists only as `benchmark_harness.py` + `benchmark_sweep.py` inside the research folder (untracked `??` dir) and `Governed_vs_Bare_Benchmark_source.md` — not in `scripts/`, `tests/`, or CI, so the headline proof isn't independently rerunnable from the repo |
| HMAC hash-chained signed audit | **IMPLEMENTED** | v3 integrity chain (BLAKE3+HMAC/window), `crp/security`, SPEC-011; sessions show `.audit.jsonl` artifacts |
| **Merkle proofs + external anchoring** | **MISSING** | Zero `merkle` matches in `crp/`; no external anchoring code — public collateral currently *over-claims* relative to code |
| Encrypted-content vs hash-only event separation (erasure) | **IMPLEMENTED** | v3 security stack: AES-256-GCM encryption, retention, GDPR Art. 17 erasure modules (per AGENTS.md) |
| Verification relay (Art. 15) | **IMPLEMENTED** | `crp/vr/` (SPEC-049); PRM model training in progress (**PARTIAL** on the artifact) |
| Safety control plane, approval gates, kill-switch (Art. 14) | **IMPLEMENTED** | `crp/security/control_plane.py`, `checkpoint.py` (SPEC-033/034); anticipatory gating via `crp/pp/simulate.py` |
| Post-market monitoring / incident detection (Art. 72/73) | **PARTIAL** | Observability/audit/monitoring exist; no dedicated serious-incident detection + 15-day reporting workflow found |
| On-device/local inference | **IMPLEMENTED** | Ollama/llama.cpp providers; `crp/ml` model registry/downloader for local scaffolds |
| Six-framework compliance mapping incl. AIUC-1 51 controls | **PARTIAL** | Compliance reporter + docs pages (`site-docs/aiuc-1.md`, `control-evidence.md`) exist; a machine-readable control→evidence map driving Comply evidence packs is not evident in `crp/` |
| Product trio | **PARTIAL** | Scan rules in `crp/scan`; Gateway managed cloud reportedly live but in-repo `crp/gateway` still thin; Comply is a separate repo consuming Gateway (R3/SPEC-042 in progress) |
| SLM-first routing economics | **IMPLEMENTED** | `crp/qsr` learned router + escalation ladder + capability profiles |

### 5. Priority picks
1. **Merkle-proofing + external anchoring of the audit chain.** The regulator brief and FAQ publicly claim "Merkle-proofed, externally anchored" — code delivers neither. This is either a small build (Merkle tree over the existing HMAC chain + anchor export) or a credibility/compliance risk in writing; fix the code or the claim.
2. **Promote the governed-vs-bare benchmark into the repo** (`scripts/` + CI-rerunable). The entire pitch's "proof" slide rests on it; today it's an ad-hoc script in an untracked research folder — skeptics, auditors, and AIUC-1 assessors will ask to rerun it.
3. **Machine-readable AIUC-1/framework control→evidence mapping** feeding Comply evidence packs. The 51-control mapping is the revenue claim ("a fraction of running six framework programs separately"); it currently lives in docs, not in the evidence pipeline.

---

## Cross-document note
The Understanding report's R1–R5 roadmap is effectively the *design source* for the v6 branch — SPEC-049 (vr), 050 (qsr), 051 (pp), 052/053 (isa/clr), 055 (ep), 057 (btf) map 1:1 and are implemented. Its residual asks (PRM artifact, `escalate-on` verb, ontology layer) plus the Collateral Pack's over-claims (Merkle/anchoring, rerunnable benchmark, control-level evidence map) form a coherent, small "complete CRPv6" tail. One ambiguity to flag to you: the Understanding doc audits "CRP v5.1" while the branch is v6 — the v6 specs appear to be its roadmap executed, so I've treated its demands as v6 requirements rather than v5 bug reports.

<!-- ==================== AutoCyber_Report_Engine.md and AutoCyber_Voice_Stack.md ==================== -->
Analysis complete. Both documents fully read and cross-checked against the repo.

---

# Document 1: `AutoCyber_Report_Engine.md`

## 1. What it is
A meta-document for the AutoCyber research-report series, in three parts: **Part A** is a prioritized roadmap of ~17 reports worth writing next (grouped in 6 themes, each tagged HIGH/MED/LOW and mapped to CRP specs it "advances"); **Part B** is a reusable master prompt encoding the series' house style (dual-register teaching, real-library code, honesty rule, CRP v6 spec tie-in, APA-7, 50–80 pages); **Part C** gives three pre-filled prompts for the top picks (Agent Security, Provenance & Audit, Compliance Crosswalk). It is a **content-production playbook, not a code spec** — its demands on CRPv6 are that the referenced specs/products actually exist so the reports can truthfully tie into them.

## 2. Concrete demands on CRPv6
Every spec/capability the document says reports will lean on (i.e., must be real):
- **SPEC-045** session/persistent learning + **SPEC-030 CSO** — for the Memory report (Theme 1)
- **SPEC-049** verification relay + **SPEC-026** quality tiers / SQB — for the Evaluation report
- **SPEC-051** predictive positioning — for Grounding/World-Models (flag as research-stage)
- **SPEC-033** safety control plane, **SPEC-012** multi-agent safety, **SPEC-006** SPDL, **SPEC-027** retrieval integrity, **SPEC-059** intent-compiler-as-privilege-boundary, **SPEC-011/029** audit — for the Agent Security report (§C.1)
- **SPEC-011** HMAC audit, **SPEC-029** Tier-E action log, **SPEC-016** Gateway, **SPEC-056** transparency emission, **SPEC-048** no-code governance — for the Provenance & Audit report (§C.2); "faithful narration" as evidence
- **SPEC-048 + 016 + 011/029** — for the Compliance Crosswalk: control-by-control runtime-evidence mapping to **EU AI Act, ISO 42001, NIST AI RMF, GDPR**, auto-generated and kept current (§C.3)
- **SPEC-027** — agentic RAG/knowledge freshness report
- **SPEC-014** conformance/interoperability — "what CRP-compliant means" report
- Positioning vs **MCP / A2A / AG-UI** standards-landscape story (IETF thread)
- **CRP Cookbook**: worked end-to-end reference apps — voice agent, compliance-evidence agent, pentest agent (Theme 6)
- Marketing discipline: "Comply on the compliance budget line; security/positioning as Gateway/protocol story" — docs must not drift this (Part B house style)

## 3. Explicit TODOs in the document
- Recommended launch-month sequence: **(1) Agent Security report → (2) Provenance & Audit → (3) Compliance Crosswalk** (Part A, §52)
- Full Part A backlog: Memory/Continual Learning [HIGH], Evaluation [HIGH], Grounding/World Models [MED], Sandboxing/Least-Privilege [MED], Economics of SLM-First [MED], On-Device Fine-Tuning [MED], Multimodal On-Device [MED], NPU-Native Agent [MED], Local RAG [LOW], Standards Landscape [MED], Conformance Report [LOW], CRP Cookbook [MED]

## 4. Gap check (report status + underlying CRP capability)
| Demand | Report written? | CRP capability status |
|---|---|---|
| SPEC-049 VR / SPEC-026 SQB | ✅ `The_Architecture_of_Evaluation_in_Agentic_AI_source.md` | IMPLEMENTED (`crp/vr/`, `examples/crp_demos/sqb_benchmark.py`) |
| SPEC-030 CSO / memory | ✅ `The_Architecture_of_Memory_in_Agentic_AI_source.md` | IMPLEMENTED (`crp/state/cso.py`); **SPEC-045 learning MISSING** (deferred frontier, zero refs in `crp/`) |
| SPEC-051 predictive positioning | ✅ `...Grounding_and_World_Models_source.md` | IMPLEMENTED (`crp/pp/` — WorldModel, induction, guarded_dispatch) |
| SPEC-033/012/006/027/059 security surface | ✅ `The_Architecture_of_Agent_Security_source.md` | IMPLEMENTED modules (`crp/security/control_plane.py`, `crp/agent/`, `crp/policy/`, `crp/envelope/retrieval_integrity.py`, `crp/agent_sdk/intent_compiler.py`); OS-level sandboxing not in `crp/` (report content, not SDK) |
| SPEC-011/029/016/056 provenance/audit | ✅ `The_Architecture_of_Provenance_and_Audit_source.md` | IMPLEMENTED: HMAC chain (v3), Tier-E store (`crp/state/scratch_buffer.py:69`), TEL/faithful narration (`crp/tel/faithful.py`), Gateway |
| SPEC-048 compliance crosswalk | ✅ `The_Compliance_Crosswalk_source.md` | PARTIAL: `crp/comply/no_code.py` + `gateway_client.map_to_regulation()` exist; v3 compliance reporter covers EU AI Act/ISO 42001; NIST RMF/GDPR auto-crosswalk depth unverified |
| Economics of SLM-first | ✅ `The_Economics_of_SLM-First_Agentic_AI_source.md` | n/a (business doc) |
| Standards landscape (MCP/A2A/AG-UI) | ❌ not in folder | PARTIAL: `crp_mcp/` server + `crp/tel` AG-UI adapter exist; no A2A interop |
| Conformance report (SPEC-014) | ❌ not in folder | IMPLEMENTED: `tests/conformance/` with vectors (agent, hmac, session, dpe, headers, safety_policy) |
| CRP Cookbook reference apps | ❌ | MISSING: only `examples/comply_demo.py`; no voice-agent or pentest-agent worked apps |
| On-device fine-tuning / multimodal / NPU-native / local RAG / sandboxing reports | ❌ not in folder | mixed (n/a to SDK) |

**Bottom line:** all three launch-sequence reports (C.1–C.3) plus the HIGH Theme-1 reports are already written. Remaining document TODOs are the MED/LOW backlog reports + the Cookbook apps.

## 5. Priority picks
1. **CRP Cookbook reference apps (voice agent, compliance-evidence agent, pentest agent)** — the only HIGH-leverage item that's both unwritten and requires real code; it's the adoption accelerant and demo vehicle.
2. **SPEC-045 session/persistent learning** — the one referenced spec with zero implementation; the Memory report already ties to it, so the code is behind the collateral.
3. **Deepen the auto-generated compliance crosswalk (NIST AI RMF/GDPR control-level, kept current)** — it is literally the Comply sales asset; verify `map_to_regulation()` covers all four frameworks at obligation granularity.

---

# Document 2: `AutoCyber_Voice_Stack.md`

## 1. What it is
An opinionated design spec for a **sub-400 ms felt-latency, fully on-device voice agent** (SLM + STT + TTS) built on CRP v6. Its flagship thesis: **Speculative Positioning** — run CRP's positioning step (tool selection, prompt prefix-warming, tool/RAG prefetch, grammar pre-compile) on *stable partial transcripts while the user is still speaking*, so positioning hides inside the speaking window instead of sitting on the critical path. Backed by a concurrency design (per-unit lane assignment to avoid DDR bandwidth contention), named model stacks per device tier, a 12-lever speed playbook, and a latency budget (~360 ms vs ~560 ms vanilla).

## 2. Concrete demands on CRPv6
- **`Agent.position_async(partial, warm_prefix=True, prefetch_tools=True, compile_grammar=True)`** returning a prepared-state object (§2.3) — the flagship primitive
- **`agent.generate_from_prepared(prepared, final)`** with `prepared.matches(final_transcript)` speculation validation + fallback to `agent.stream()` (§2.3)
- **`agent.stt.set_agent_context(expected_intent)`** — feed positioned intent back to STT for ~10% WER cut (§2.2 item 5, §5 lever 9)
- **SPEC-050 routing** — tool selection on partial intent, manifest scoped to 1–3 tools (§2.2)
- **SPEC-030 CSO** — warm, relayed positioned state = prefix-cache + carried context, not re-stuffed window (§7)
- **SPEC-054 structured decoding** — grammar *pre-compiled* during speech; zero-retry tool calls (§2.2, §7)
- **SPEC-027 retrieval integrity** — provenance-tracked predictive tool/RAG prefetch (§2.2 item 3)
- **SPEC-059 Agent SDK** — the whole `position_async`/`generate_from_prepared` surface (§7)
- **SPEC-032 depth="quick"** — voice path runs shallow verification with safety gate kept (§7)
- **SPEC-033 safety control plane** — HITL gate for dangerous tools positioned ahead of endpoint, zero added turn latency (§7)
- **SPEC-011/029 audit** — signed record of spoken actions (Comply deliverable) (§7)
- **Partial debouncing (~100–200 ms stability gate)** before forwarding partials downstream (§3.3, §5 lever 8) — implied SDK-side or app-side helper
- Benchmarkable demo: **~360 ms speculative vs ~560 ms vanilla preemptive loop, same 4B model/hardware** (§7, §8)

## 3. Explicit TODOs in the document
- §8 "What to Build First" — one move: **implement `Agent.position_async()` with `warm_prefix=True` and wire it to stable STT partials**; then demo the 360 ms vs 560 ms benchmark
- §5 playbook levers 1, 2, 4 flagged as the differentiators (Speculative Positioning, heterogeneous lane scheduling, neural turn-taking); rest = "table stakes" in the companion report's templates

## 4. Gap check
| Demand | Status | Evidence |
|---|---|---|
| `Agent.position_async()` w/ warm_prefix/prefetch/compile_grammar | **MISSING** | grep across `crp/`: zero hits for `position_async`, `generate_from_prepared`, `speculative`; `crp/agent_sdk/agent.py` exposes only `run/ask/run_stream/run_tel` |
| `generate_from_prepared` + `matches()` + stream fallback | **MISSING** | same as above |
| STT integration / `set_agent_context` | **MISSING** | no STT/TTS/Moonshine/Whisper code in `crp/` (`crp/continuation/voice.py` is writing-style voice profile, unrelated) |
| SPEC-050 tool routing / positioning core | IMPLEMENTED | `crp/tools/capability_fabric.py`, `crp/isa/position.py`, `crp/stl/` |
| SPEC-030 CSO warm relayed state | PARTIAL | `crp/state/cso.py` implements logical state relay; no KV-prefix-cache warming binding to providers |
| SPEC-054 structured decoding | PARTIAL | `crp/gateway/structured_decoder.py`, `tool_adapter.py`, `capability_router.py` implement it; no "pre-compile grammar ahead of turn" async API |
| SPEC-027 retrieval-integrity provenance for prefetch | IMPLEMENTED (module) / MISSING (prefetch wiring) | `crp/envelope/retrieval_integrity.py` exists; no predictive-prefetch consumer |
| SPEC-059 Agent SDK | IMPLEMENTED | `crp/agent_sdk/` (Agent, intent compiler, events) |
| SPEC-032 depth="quick" | IMPLEMENTED | `crp/sdk/client.py:311` (`quick\|standard\|thorough\|exhaustive`); Agent SDK has depth-gated `verify=` override |
| SPEC-033 HITL gate | IMPLEMENTED | `crp/security/control_plane.py`, `crp/security/checkpoint.py` (7 SPEC-033 refs) |
| SPEC-011/029 signed audit of actions | IMPLEMENTED | v3 HMAC chain; Tier-E store `crp/state/scratch_buffer.py:69` |
| Partial debouncing helper | MISSING | nothing in `crp/` |
| Lane scheduling / NPU placement / TTS producer-consumer | Out of scope (app layer) | doc assigns these to the voice app + Pipecat, not CRP core — but no CRP-side hooks exist either |
| 360 ms vs 560 ms benchmark demo | MISSING | no voice example in `examples/` |

## 5. Priority picks
1. **`Agent.position_async()` + prepared-state object (the §8 "one move")** — the doc's own explicit first build; it is the only primitive no competitor can ship (positioning as a callable, speculatively-runnable step) and it unlocks the prefix-cache win and the on-stage benchmark.
2. **Prepared-state validation + fallback path (`matches()` → `generate_from_prepared()` / `stream()`)** — makes speculation safe and shippable rather than a demo hack; small incremental surface on `crp/agent_sdk`.
3. **Minimal audio-facing adapter seam in the Agent SDK** (partial-in/final-out turn API + debounce hook, STT/TTS-agnostic) — CRP doesn't need to own Moonshine/Kokoro, but without a defined seam the voice stack can't wire into positioning at all; also directly produces the missing Cookbook voice-agent app from the Report Engine.

---

## Cross-document synthesis
Both documents converge on the same gap: the collateral (reports, stack specs, spec mappings) is ahead of the code in exactly one place — **a speculative/async positioning surface on `crp.Agent` with a warm, validated, prepared state**. Building `position_async()` + prepared-state lifecycle simultaneously (a) fulfills the Voice Stack's §8 directive, (b) produces the Cookbook voice-agent app the Report Engine lists as its key unwritten adoption asset, and (c) exercises already-implemented modules (SPEC-050/030/054/027/032/033) end-to-end for the first time in a latency-critical, benchmarkable setting. Secondary shared gap: **SPEC-045 learning** (referenced by reports, zero code) and the **Cookbook app trio** (only 1 of 3 exists).

<!-- ==================== AutoCyber_Series_Roadmap_TODO_source.md and The_AutoCyber_Agentic_AI_Compendium_source.md ==================== -->
Analysis complete. Both documents were read in full (106 + 284 lines) and every named spec/capability was verified against the repo with targeted greps.

---

# Document 1 — `AutoCyber_Series_Roadmap_TODO_source.md`

## 1. What it is
The living tracker for the AutoCyber agentic-AI research series and the CRP Comply launch: what has shipped (7 pillars + 2 capstones + Compendium + CRP v6 spec), this cycle's work orders (T-1…T-7, all marked ✅), the full backlog, and the recommended sequence to launch. It is almost entirely a **research-collateral / go-to-market tracker**, not an SDK spec — its code-relevant content is concentrated in §3.2 ("turning claims into measured evidence").

## 2. Concrete demands on CRPv6
- **T-3 (§3.2, ✅ claimed done):** a runnable governed-vs-bare benchmark harness (`harness.py` + `sweep.py`) — identical agent run through an AgentDojo/AgentHarm-style indirect-injection + tool-misuse suite, bare vs CRP-gated, measuring ASR, utility, and overhead deterministically, with honesty caveats. Claimed results: bare ASR 14.85% → governed 0.00%, utility unchanged, ~0.24 µs/action overhead.
- **(§3.2, ⬜):** wire the same governed/bare wrapper to the **real AgentDojo / AgentHarm / InjecAgent** datasets for externally comparable numbers.
- **(§3.2, ⬜):** add a **reliability (pass^k) and utility-cost panel** — pair the security number with latency/token cost.
- **T-4 (§3.3, ✅):** AIUC-1 **control-level mapping** — 51 controls, domains A–F, each mapped to CRP evidence/spec, as Crosswalk Appendix E; chain CRP evidence through AIUC-1's own official crosswalks (EU AI Act, ISO 42001, NIST, MITRE ATLAS, OWASP Agentic Top 10).
- **(§3.3, ⬜):** map the **AutoCyber Voice Stack to AIUC-1 voice-agent requirements** (ElevenLabs/Stanford/Gray Swan).
- **(§3.3, 🔁):** re-verify the AIUC-1 mapping **quarterly** (Q2-2026 focus: MCP security, agent permissions, third-party risk).
- **(§3.1, ⬜):** corpus-wide **SPEC-0xx number / cross-reference consistency pass**.
- **(§3.6, ⬜):** new reports — **CRP & the Standards Landscape (vs MCP/A2A)** (P1), CRP Cookbook (P2), On-Device Fine-Tuning (P2), Multimodal On-Device Agents (P3), NPU-Native Agent (P3).
- **(§3.7, ⬜):** sector crosswalks — finance (DORA + model-risk), healthcare (HIPAA + medical-device), US state-law deepening (Colorado, NYC, California).
- **(§3.8, 🔁):** recurring primary-source legal verification (EU AI Act articles/dates, Digital Omnibus, Colorado AI Act) and quarterly security-fact refresh (OWASP Agentic Top 10, MCP CVEs).

## 3. Explicit TODOs / sequence (§4)
1. **Done this cycle:** T-2 hardening, T-3 benchmark, T-4 AIUC-1 mapping, T-5 Economics report (P0), T-6 diagrams, T-7 collateral.
2. **Next up (stated in §2):** the **CRP & Standards Landscape report (vs MCP/A2A)**, sector crosswalks, and the recurring legal-verification pass.
3. **Ongoing:** §3.8 legal/security-fact verification + AIUC-1 quarterly re-mapping.
4. Stated highest-return pre-launch items: Economics report (done), measured benchmark (done), diagrams + collateral (done) — i.e., the launch-blocking substance gaps are closed per the doc itself.

## 4. Gap check (repo-verified)
| Demand | Status | Evidence |
|---|---|---|
| Governed-vs-bare harness (T-3) | **IMPLEMENTED** (as research collateral, not in repo test suite) | `AutoCyber AI Agentic AI research with CRP/benchmark_harness.py` + `benchmark_sweep.py` exist; no equivalent in `tests/` or `examples/` |
| Real AgentDojo/AgentHarm/InjecAgent wiring | **MISSING** | Names appear only in research `.md`/harness files; no dataset integration anywhere in `crp/` or `tests/` |
| pass^k reliability + utility-cost panel | **MISSING** | Zero matches for `pass^k`/`pass_at_k` in any `.py` in the repo |
| AIUC-1 51-control mapping (T-4) | **IMPLEMENTED (docs) / PARTIAL (site)** | Appendix E lives in research-dir Crosswalk; public site has `site-docs/aiuc-1.md` (principle-level, "51 requirements and 130 controls") and `site-docs/control-evidence.md` (framework-level table, ~23 rows) — control-by-control mapping not on the site |
| Voice Stack → AIUC-1 voice mapping | **MISSING** | No voice-agent stack in `crp/` (`crp/continuation/voice.py` is writing-style voice profiles, unrelated); the Voice Stack is a separate earlier report |
| Standards Landscape report (vs MCP/A2A) | **MISSING** | No such doc in research dir or `site-docs/` |
| Sector crosswalks (DORA/HIPAA/US-state) | **PARTIAL** | Economics report Part XVIII has DORA/HIPAA/TLPT deep-dives; dedicated crosswalk reports not present |
| SPEC-number consistency pass | N/A (docs process) | — |
| Legal/security-fact refresh | N/A (recurring process) | — |

## 5. Priority picks
1. **pass^k + utility-cost measurement in the SDK/eval surface** — the only *code-level* gap in this doc; it turns SPEC-049/026 governance claims into the reliability numbers enterprise buyers and AIUC-1's testing model demand.
2. **Promote the governed-vs-bare harness into the repo (tests/examples) and wire one real public dataset (AgentDojo or InjecAgent)** — converts marketing claims into externally checkable evidence; currently the harness sits outside the repo as loose collateral.
3. **CRP & Standards Landscape report (vs MCP/A2A)** — the doc's own stated "next up" P1; pure positioning asset, no code cost.

---

# Document 2 — `The_AutoCyber_Agentic_AI_Compendium_source.md`

## 1. What it is
The consolidation/study guide for the seven-pillar series (Understanding, Tool Use, Transparency, Memory, Evaluation, Grounding & World Models, Agent Security) plus the two governance-evidence capstones (Provenance & Audit, Compliance Crosswalk). Its thesis: **trustworthy agent = capability × governance, and governance must be enforced outside the model** ("a prompt is a suggestion; a policy is an enforceable rule"). Its most actionable artifact is **§8.3, the complete CRP v6 spec map** tying every pillar's governance gap to a named spec.

## 2. Concrete demands on CRPv6 (§8.3 spec map + pillar tie-ins)
- **Positioning** — bounded reasoning + task-scoped capability (Pillars 1, 2, 7).
- **SPEC-006 (SPDL)** — the deterministic policy mediating actions (7, 2, 4).
- **SPEC-033 (safety control plane)** — action mediation, HITL, **kill-switch** (7, 2).
- **SPEC-027 (retrieval integrity)** — provenance / information-flow labels (4, 7).
- **SPEC-045 (session/persistent learning)** — governed memory (4, 6).
- **SPEC-030 (CSO)** — carried state, runtime detection (4, 7).
- **SPEC-049 (verification relay)** — verify results *and* predictions at runtime (5, 6, 2).
- **SPEC-026 (quality tiers)** — autonomy gated by measured reliability (5, 6, 7).
- **SPEC-011/029 (audit chain, Tier-E log)** — tamper-evident record under all pillars.
- **SPEC-056 (transparency emission)** — faithful narration (3, 5).
- **SPEC-012 (multi-agent safety)** — scope isolation, conflict resolution (7, 4).
- **SPEC-058 (governed delegation)** — attenuated delegation (7, multi-agent).
- **SPEC-016 (Gateway)** — MCP/tool supply-chain enforcement (7, 2).
- **SPEC-059 (intent compiler)** — tool-execution privilege boundary (2, 7).
- **SPEC-051 (predictive positioning)** — governed prediction, explicitly flagged *research-stage* (6).
- **SPEC-048 (no-code governance)** — evidence → compliance deliverables.
- Plus named mechanisms the pillars say CRP gives you: the **`CRPGovernedAgent`** control-plane wrapper ("the single most important template", §7.3); **structured/constrained decoding** for schema-valid tool calls (§2); the **authority lattice** INGESTED<AGENT<HUMAN<POLICY (§4); **constraint pinning** so compaction can't erase safety constraints (§4); **pass^k** reliability measurement (§5); the **governed-vs-bare head-to-head** (§5); a **hash-chained + Merkle + CT-style-anchored + WORM** audit trail with **Ed25519** non-repudiation and **content/events separation** (§9.1); **OpenTelemetry** tracing (§3); **MCP description-pinning** for supply-chain vetting (§7); five-framework compliance evidence packs (EU AI Act × NIST AI RMF × ISO 42001 × SOC 2 × GDPR) (§9.2).

## 3. Explicit TODOs / open items stated in the document
- **SPEC-051 is flagged research-stage** — "the report teaches you what *not* to build yet"; predictions must stay governed hypotheses (low authority, verified before costly action, tier-gated).
- The **symbol grounding problem** is marked unsolved/[OPEN] (§6.1).
- §10.1 ("what was strengthened") is retrospective; the doc defers forward work to the Roadmap/TODO tracker. No other explicit build TODOs — it is a map, not a backlog.

## 4. Gap check (repo-verified)
| Demand | Status | Evidence |
|---|---|---|
| Positioning | **IMPLEMENTED** | `crp/envelope/`, `crp/stl/positioned.py`, `crp/isa/position.py` |
| SPEC-006 SPDL | **IMPLEMENTED** | `crp/policy/` (grammar, enforce, inheritance, profiles, nonce, report) |
| SPEC-033 control plane | **IMPLEMENTED** | `crp/security/control_plane.py` — 13+ capabilities incl. `http_451_halt`, `human_oversight`; HITL via `checkpoint.py` |
| — kill-switch sub-item | **MISSING** | No `kill.?switch` match anywhere in `crp/`; halt exists, agent kill-switch does not |
| SPEC-027 retrieval integrity | **IMPLEMENTED / PARTIAL** | `crp/envelope/retrieval_integrity.py` with `resolve_fact_authority()`; full information-flow control (Biba/taint) not present |
| SPEC-045 governed memory / knowledge learning | **MISSING (deliberately deferred)** | Listed Frontier Tier-4 in `AGENTS.md`/Rounds; no code. Session/persistent memory itself exists (`crp/state/`), so the *governed-memory* substrate is partial cover |
| SPEC-030 CSO | **IMPLEMENTED** | `crp/state/cso.py` |
| SPEC-049 verification relay | **IMPLEMENTED** | `crp/vr/` (relay, prm, exec_verifier, z3_verifier, extract) |
| SPEC-026 quality tiers | **IMPLEMENTED** | `QualityReport` S–D tiers in core; `examples/crp_demos/sqb_benchmark.py` harness |
| SPEC-011/029 audit chain + Tier-E log | **PARTIAL** | HMAC-SHA256 chained trail in `crp/security/audit_trail.py` ✅; `scratch_buffer.py` Tier-E ✅. **Merkle trees, external CT-style anchoring, WORM storage, Ed25519 signatures: all MISSING** (zero matches in `crp/`) |
| SPEC-056 TEL / faithful narration | **IMPLEMENTED** | `crp/tel/` (emitter, faithful.py, sse, adapter, report) |
| SPEC-012 multi-agent safety | **IMPLEMENTED** | `crp/agent/` (budget, chain, oversight, propagation) |
| SPEC-058 governed delegation | **MISSING** | No code matches; Developer Brief lists it "Draft/preview — Roadmap (Wave 4)" |
| SPEC-016 Gateway | **IMPLEMENTED** | `crp/gateway/` (api, router, key_vault, capability_router, structured_decoder) |
| — MCP description-pinning / supply-chain vetting | **MISSING** | No `description.?pin`/`supply.?chain`/`tool.?poison` matches in `crp/` |
| SPEC-059 intent compiler + governed agent wrapper | **IMPLEMENTED** | `crp/agent_sdk/` (`agent.py` crp.Agent, `intent_compiler.py`, `policy.py` with block/allow_only/domain/residency/safety) — this functionally realizes the Compendium's `CRPGovernedAgent` template under the SPEC-059 API; the literal name exists only in research docs |
| SPEC-051 predictive positioning | **IMPLEMENTED (research-stage, as specified)** | `crp/pp/` (world_model, simulate, causal_ckf, induction) — matches the "flagged research-stage" framing |
| SPEC-048 no-code governance | **PARTIAL** | `crp/comply/no_code.py` exists, but `CRPv4_realised_deliverables.md` states it is "basic form… NOT scan-driven per spec" |
| Constrained/structured decoding | **IMPLEMENTED** | `crp/gateway/structured_decoder.py`, `crp/extraction/structured_output.py`, `crp/stl/tool_positioner.py` |
| Authority lattice (INGESTED<AGENT<HUMAN<POLICY) | **PARTIAL** | Authority *scoring* exists (`retrieval_integrity.py`, `gateway/api.py`); no explicit lattice type or write-gate by that name |
| Constraint pinning vs compaction | **PARTIAL** | `crp/state/critical_state.py` (Tier-0 "ALWAYS included in every envelope") + scratch-buffer `PINNED` give the mechanism; not exposed as a named safety-constraint-pinning API, and `compaction.py` has no pin/safety handling of its own |
| pass^k measurement | **MISSING** | No matches in any `.py` |
| Governed-vs-bare head-to-head | **IMPLEMENTED (research collateral)** | `benchmark_harness.py` + `benchmark_sweep.py` in research dir; not in repo tests |
| OpenTelemetry tracing | **PARTIAL** | Only `crp/observability/metrics.py` mentions OTel; TEL emits AG-UI events, not OTel span trees |
| Five-framework compliance evidence | **IMPLEMENTED** | `crp/security/compliance.py` (EU AI Act Art. 6/9–17, ISO 42001), `compliance reporter`, site `control-evidence.md` |

## 5. Priority picks
1. **SPEC-058 Governed Delegation (attenuated multi-agent delegation)** — the only spec in the Compendium's own v6 spec map with zero code; it completes the "CRP governs every step of a multi-agent action" story that the Security pillar calls the convergent architecture, and it's already specced as a draft preview.
2. **Harden the audit chain to the Provenance capstone's construction (Merkle inclusion proofs + external anchoring + Ed25519 signatures)** — the Compendium makes this "the technical core of Comply"; today only the HMAC hash-chain third exists, so the "court-defensible" claim outruns the code.
3. **pass^k reliability measurement wired into VR/quality tiers** — the Evaluation pillar's central metric and the natural quantitative output of SPEC-049/026; cheap to build, directly sellable as evidence.

---

## Cross-document note
The two docs agree on the same two code-level gaps: **pass^k reliability measurement** and **hardened/verifiable evidence** (benchmark harness in the Roadmap; Merkle/anchored audit in the Compendium). Both also rely on **SPEC-058** for the multi-agent story without noting it's unbuilt. Everything else the Compendium's §8.3 spec map demands is implemented in the current `crpv6-agent-sdk` branch, with SPEC-051 correctly implemented *as research-stage* and SPEC-045/SPEC-048 deliberately deferred/partial per the v4 plan.

<!-- ==================== CRP_v6_Agent_SDK_and_Launch_Completion_source.md and CRP_v6_Developer_Brief.md ==================== -->
Analysis complete. Here are the findings, one section per document.

---

# Document 1 — `CRP_v6_Agent_SDK_and_Launch_Completion_source.md`

## 1. What it is
The capstone research document (July 2026, AutoCyber AI). It maps the four research reports against the shipped spec catalogue (001–048 + v6 049–057) and finds one genuine gap: the Tool-Use roadmap's manifest / intent-compiler / result-envelope layer (T1, T2, T4). It then specifies that gap as SPEC-059 with runnable code, defines a `crp.Agent` builder SDK, and separates a one-month launch cut (SPEC-059 + Agent SDK + SPEC-054 + SPEC-056 D1–D3 + docs) from deferred roadmap (PRM judge, learned router, world model, calibration, bi-temporal).

## 2. Concrete demands on CRPv6
- **SPEC-059 — Agent Capability Layer** (§2.1):
  - T1 Typed Tool Manifest: `Intent` base (Pydantic) with ClassVar metadata — `name`, `description`, `when_to_use`, `when_not_to_use`, `effect` (READ_ONLY/IDEMPOTENT/IRREVERSIBLE), `safety_class` (AUTO/GATED/HITL), `requires_privilege`; `manifest()` indexed in the CKF for selection-as-retrieval (T5).
  - T2 Intent-Compiler: per-tool `compile()` — model fills a safe typed intent; deterministic, versioned transform emits the real invocation + provenance; model never touches raw argv.
  - T4 Tool-Result Envelope: `ToolResult` with `parsed` in-window, `raw_ref` out-of-window by reference, `parse_confidence`, `provenance_hash` into the SPEC-011 HMAC audit chain; `capture()` helper.
- **`crp.Agent` SDK** (§2.2): `Agent(model, tools, policy, memory="ckf", stream, depth)` composing positioned loop (STL/SPEC-031), grammar-constrained parameterisation (SPEC-054), safety-class gating/HITL (SPEC-006/033), sandboxed execute, envelope capture, DPE scan per step (SPEC-005), CKF/CSO memory, faithful narration (T6/D3), AG-UI streaming (SPEC-056).
- **Reuse proof** (§2.3): a second, unrelated agent (GDPR DSR) in ~15 lines on the unmodified loop.
- **SPEC-054**: XGrammar structured decoding wired into the Gateway generation path (§3.1).
- **SPEC-056 D1–D3 only**: AG-UI event emission, `crp.*` governance-event vocabulary, entailment-checked faithful narration; D4–D6 deferred (§3.1).
- **Docs + one reference agent**: copy-pasteable quickstart, manifest/compiler pattern documented (§3.1).
- **Scan → Gateway → Comply funnel wired and tested**; Comply generates an evidence pack from a real Agent-SDK run (§3.3 checklist).
- **Positioning demands** (Part 4): protocol keeps "agentic positioning layer for SLM-first AI" + adds reuse message; agent-security story lives at protocol/Gateway level; Comply stays on the compliance budget line with "evidence, not certification" framing; Scan stays free/unmonetised.

## 3. Explicit TODOs / next steps stated
- §3.1 Ship in the month: SPEC-059 + Agent SDK; SPEC-054; SPEC-056 D1–D3; docs + reference agent.
- §3.2 Defer (publish as roadmap): SPEC-049 PRM judge (symbolic-only may sneak in), SPEC-050 learned router (ship capability-profile fallback), SPEC-051, SPEC-053, SPEC-055 calibration, SPEC-057.
- §3.3 Launch-readiness checklist (6 items, quoted above in demands).
- §3.3: "Ship symbolic-only if you have time; defer the judge."

## 4. Gap check

| Demand | Status | Evidence |
|---|---|---|
| T1 Typed Tool Manifest (`Intent`, effect/safety_class metadata) | **IMPLEMENTED** | `crp/agent_sdk/tool_manifest.py` — `ToolSpec`, `ToolIntent`, `CompiledTool`, `ResultEnvelope` (docstring cites SPEC-059 §3) |
| T2 Intent-Compiler (`compile()` convention) | **IMPLEMENTED** | `crp/agent_sdk/intent_compiler.py` — `compile_tool()`, `compile_tools()`, schema extraction from callables/Pydantic |
| T4 Tool-Result Envelope (raw-by-ref, provenance hash) | **IMPLEMENTED** | `ResultEnvelope` in `tool_manifest.py`; raw-ref/provenance wiring referenced in `agent.py:543-546` |
| `crp.Agent` SDK (declaration-only loop) | **IMPLEMENTED** | `crp/agent_sdk/agent.py` — `Agent` with `run()`, `run_stream()`, `run_tel()`; `events.py`, `policy.py`; tests `test_agent_sdk.py`, `test_agent_sdk_structured.py` |
| Manifest indexed in CKF for selection-as-retrieval (T5) | **PARTIAL** | `crp/tools/capability_fabric.py` + `descriptor.py` (TCF registry/retrieval per SPEC-050) exist; CKF indexing of manifests as the doc literally describes is not directly verified |
| SPEC-054 structured decoding in Gateway | **IMPLEMENTED** | `crp/gateway/structured_decoder.py` (§4), `tool_adapter.py` (§3), `capability_router.py`; test `test_gateway_structured_decoder.py`. XGrammar backend choice unverified — decoder exists, engine integration unclear |
| SPEC-056 D1–D3 (AG-UI, governance vocab, faithful narration) | **IMPLEMENTED** | `crp/tel/` — `emitter.py`, `events.py`, `faithful.py`, `sse.py`, `adapter.py`; tests `test_tel.py`, `test_tel_sse.py` |
| Reuse proof: second agent in ~15 lines | **PARTIAL** | Tests exercise the SDK, but no `examples/*agent*` demo found; reuse proof lives in tests/docs, not as a shipped example |
| Docs + reference agent, copy-pasteable | **PARTIAL** | `site-docs/crpv6/agent-sdk-usage.md` + `docs/CRPv6_Agent_SDK_Usage_Guide.md` exist; no runnable end-to-end reference agent in `examples/` |
| Scan → Gateway → Comply funnel wired & tested | **PARTIAL** | `crp/comply/gateway_client.py` has `stream_audit_events`, `get_evidence_pack`, `map_to_regulation`; no test/doc found proving the end-to-end funnel |
| Evidence pack from a real Agent-SDK run | **MISSING (as proven path)** | `get_evidence_pack()` exists but takes tenant_id/period, not an agent run; no evidence of agent-run → evidence-pack closure |
| SPEC-049 symbolic-only verifier | **IMPLEMENTED+** | `crp/vr/` has `z3_verifier.py`, `exec_verifier.py`, `relay.py` — and the PRM judge (`prm.py`) is actually being trained now, ahead of the doc's deferral |
| SPEC-050 capability-profile fallback | **IMPLEMENTED** | `crp/gateway/capability_router.py` (per task context) |
| Deferred as roadmap: 051, 053, 055-calibration, 057 | **IMPLEMENTED (beyond ask)** | `crp/pp/`, `crp/clr/`, `crp/ep/`, `crp/btf/` all exist as modules — repo is ahead of this document's defer recommendations |
| Positioning: reuse message, Comply on compliance line, "evidence not certification" | **PARTIAL** | `site-docs/crpv6/` exists with v6 framing; whether the reuse message and exact Comply/Scan positioning landed on the live pages was not verified here |

## 5. Priority picks
1. **Evidence pack from a real Agent-SDK run (Scan→Gateway→Comply funnel proof)** — the only launch-checklist item with no code trace; it's the monetisation-path proof this document calls "the actual product."
2. **Runnable reference agent in `examples/` + quickstart** — adoption hinges on a copy-pasteable path; currently the reuse proof exists only in tests and markdown.
3. **Publish v6 spec documents 049–059 into the catalogue** — `site-docs/spec/` still ends at SPEC-048; the catalogue doesn't yet read 001…059 (see Document 2, where this is an explicit hard requirement).

---

# Document 2 — `CRP_v6_Developer_Brief.md`

## 1. What it is
The founder's work order to the lead engineer (or coding agent): verify the research corpus against the real repo ("the code wins"), correct it, bind SPEC-059/`crp.Agent` to the real API, write **all eleven** new spec documents (049–059) so the protocol is documentation-complete, and implement the one-month launch subset. It locks positioning (§3.1), reusability as north star (§3.2), and an honesty rule against claiming unbuilt capabilities (§3.3).

## 2. Concrete demands on CRPv6
- **§2.1 — Write a formal spec document for every one of SPEC-049…059** (incl. SPEC-058 Governed Delegation as Draft/preview), in house style, into the published catalogue; update master index to read 001…059; each labelled `implemented` or `roadmap`. "Nothing omitted from documentation, regardless of what is coded."
- **§4 Phase 0** — Traceability matrix: every R1–R5 / T1–T6 / D1–D6 item → spec → code module → status (shipped/partial/specced-only/gap).
- **§4 Phase 1** — Map inferred Agent SDK calls (`SDKClient.position`, `fill_intent`, `narrate_faithful`, `dpe`, `ckf.index_manifest`, `stream_sink`, `tokenizer_key`, `new_session`, `execute`) to real APIs; verify every spec claim "does X" against the repo; confirm integration-point spec numbers.
- **§4 Phase 2** — Implement T1 manifest + T2 compiler + T4 envelope against the real dispatch/CKF/audit substrate.
- **§4 Phase 3** — Launch build: SPEC-059 + `crp.Agent`; SPEC-054 (verify XGrammar compatibility with actual runtime — vLLM/SGLang/Ollama — or identify fallback); SPEC-056 D1–D3; one reference agent + quickstart; Scan→Gateway→Comply funnel wired and tested with evidence pack from an Agent-SDK run; all eleven spec docs published.
- **§4 Phase 4** — One PR per component; each PR demonstrates the reuse invariant (reference agent + second trivially-different agent on unmodified loop).
- **§4 Phase 5** — Feasibility verdicts per deferred spec (XGrammar, Z3, semantic entropy, WALL-E induction, RouteLLM, Graphiti currency as of mid-2026).
- **§5 deliverables** — correction log (5.1), traceability matrix (5.2), real-API-bound SPEC-059 + Agent SDK + reuse proof (5.3), gap list with severity × effort (5.4), launch PR plan (5.5), feasibility verdicts (5.6), eleven published spec docs (5.7).
- **§6 acceptance criteria** — declaration-only agent building; ~15-line second agent; structurally-valid SLM tool calls; AG-UI streaming + entailment-checked narration; Comply evidence pack from agent run + funnel conversion; docs match code; eleven specs published; positioning intact.
- **§3.3 honesty rule** — do not implement or let marketing claim: learned router (050), PRM judge (049), world model (051), calibration curves (055).

## 3. Explicit TODOs / next steps
The entire §4 phase list (0–5) is the TODO. Beyond that: §5.4 gap list with severity × effort and launch/roadmap/drop recommendation; §5.5 ordered launch PR plan with acceptance criteria; SPEC-053 clarification "pull forward if the reference-agent work finishes early" (§4 Phase 3).

## 4. Gap check

| Demand | Status | Evidence |
|---|---|---|
| Eleven spec docs (049–059) published into catalogue | **MISSING / PARTIAL** | `site-docs/spec/` ends at CRP-SPEC-048; `SPECS_5_06_2026_CRP_v4/specs/` has only 049/050 (v4-vintage SLM/TCF specs, different content). v6 specs live in `CRP_v6_Implementation_Specification_source.md` + `site-docs/crpv6/index.md` summary table (lists 049–057, 059 — **no SPEC-058 row**). No standalone house-style 049–059 spec documents published |
| SPEC-058 Governed Delegation (draft doc) | **MISSING** | No module, no spec doc, not in the `site-docs/crpv6/index.md` table |
| Phase 0 traceability matrix | **IMPLEMENTED** | `docs/CRPv6_TRACEABILITY_MATRIX.md` exists with launch-cut vs deferred and spec-numbering sections |
| Phase 1 correction log (§5.1) | **MISSING** | Grep for "correction log" finds only the brief itself and the matrix; no standalone correction-log document |
| Phase 1 real-API binding of Agent SDK | **IMPLEMENTED** | `crp/agent_sdk/` binds to real modules (`crp_emitter.provenance` in `agent.py:546`, tel, intent compiler) rather than the doc's inferred names |
| Phase 2 T1/T2/T4 implementation | **IMPLEMENTED** | `tool_manifest.py`, `intent_compiler.py`, `ResultEnvelope` (see Doc 1 gap check) |
| SPEC-054 runtime-compat verification (vLLM/SGLang/Ollama/XGrammar fallback) | **PARTIAL** | `crp/gateway/structured_decoder.py` exists with tests; no doc found recording the XGrammar-vs-runtime compatibility verdict the brief demands |
| SPEC-056 D1–D3 | **IMPLEMENTED** | `crp/tel/` full module + tests |
| Reference agent + quickstart | **PARTIAL** | Usage guides exist (`site-docs/crpv6/agent-sdk-usage.md`); no runnable `examples/` agent demo |
| Scan→Gateway→Comply funnel + evidence pack from agent run | **PARTIAL** | `crp/comply/gateway_client.py` (`get_evidence_pack`, `stream_audit_events`, `map_to_regulation`) exists; no end-to-end test/doc proving funnel conversion |
| §5.4 gap list (severity × effort) | **PARTIAL** | `docs/CRPv6_Completeness_Roadmap.md` likely serves this role (not opened in this pass) |
| §5.5 launch PR plan | **PARTIAL** | `docs/CRPv6_PhaseA_Action_Plan.md` is a phase plan but oriented at ML-first Phase A, not the brief's launch PR sequence |
| Phase 5 feasibility verdicts (library currency) | **MISSING** | No feasibility-verdict document found in `docs/` |
| §6 acceptance: second agent in ~15 lines | **PARTIAL** | `test_agent_sdk.py` exercises the SDK; no explicit two-agent reuse-proof artifact |
| Honesty rule (don't build/claim 049-PRM, 050-learned, 051, 055-calibration) | **DIVERGED (deliberately)** | Repo state is ahead of the brief: PRM is being trained now (`docs/CRPv6_RunPod_PRM_Runbook.md`, `crp/vr/prm.py`), and 051/053/055/057 all have modules. The brief's "roadmap, not code" deferral was superseded by the ML-first Phase A strategy — the honesty-rule *spirit* (don't claim what's not proven) is carried in `CRPv6_Operational_Readiness_Report.md` |
| Reusability invariant (§3.2) — agents inherit new specs for free | **IMPLEMENTED** | Agent SDK composes shared loop (`agent.py`); SPEC-049/050 additions ride the same modules |

## 5. Priority picks
1. **Write/publish the eleven spec documents (049–059) into `site-docs/spec/` with the index updated to 001…059** — this is the brief's most-emphasised hard requirement ("documentation-complete at launch", acceptance criterion §6) and is the clearest gap: the public catalogue still stops at 048.
2. **Correction log (§5.1) + XGrammar/runtime compatibility verdict** — the brief's trust mechanism for the whole corpus is unrecorded; without it nobody can tell which spec claims were verified against code.
3. **End-to-end funnel proof: reference agent run → Comply evidence pack** — the §6 monetisation acceptance criterion and the only launch item with no demonstrable artifact.

---

## Cross-document note
Both documents assume a code-first launch month with heavy ML specs deferred; the repo has since pivoted to an ML-first Phase A (SetFit intent, DeBERTa safety shipped; PRM training), so several "deferred" items (crp/pp, crp/clr, crp/ep, crp/btf, PRM) are already built or in flight. The durable unmet demands from both documents are the same three: **published 049–059 spec docs (incl. SPEC-058)**, **correction log / docs-match-code proof**, and **the Scan→Gateway→Comply evidence-pack funnel demonstrated from a real Agent SDK run**.

<!-- ==================== CRP_v6_Implementation_Specification_source.md ==================== -->
Analysis complete. Here is the full report.

---

# Document: `CRP_v6_Implementation_Specification_source.md`

*(1613 lines; identical copy also at repo root, tracked as modified in git. July 2026, AutoCyber AI — "capstone" volume of the Understanding / Tool Use / Transparency series.)*

## 1. What it is

The canonical CRPv6 build document: it converts the three prior analysis volumes plus the CRP v5.1 gap assessment into **nine numbered, coded specifications (CRP-SPEC-049 … 057)** that extend the existing SPEC-001…048 catalogue. It defines a three-wave build program (Wave 1: VR/SDE/TEL; Wave 2: QSR/EP/ISA; Wave 3: PP/CLR/BTF), a consolidated normative MUST-checklist (Appendix B), a reference integration tracing one request through all nine specs (Appendix A), a strategic synthesis (Part 10: three data flywheels = the moat), and a forward research agenda ending in a SPEC-058 "Governed Delegation" preview (Part 11). Its core thesis: CRP's remaining gaps are *verification, learning, prediction, and emission* gaps — not capability gaps — and each closes with a module that consumes data CRP already logs and writes into a control point CRP already owns.

## 2. Concrete demands on CRPv6

**SPEC-049 Verification Relay (`crp/vr/`)** — Part 1
- `Verifier` Protocol + `Verdict`/`VerificationResult`/`Claim` types (§1.3.1)
- Z3 SMT verifier — sound, confidence 1.0 (§1.3.2); sandboxed exec verifier — isolated `-I`, network-denied, resource-capped (§1.3.3)
- ProcessRewardVerifier as **DPE stage 14**, model `autocyber/crp-prm-deberta-v1` (§1.3.4)
- `VerificationRelay` LLM-Modulo generate-critique-repair loop, `max_repairs=2` (§1.3.5)
- Unrepaired INVALID **MUST cap quality tier at D** and raise risk floor to HIGH (§1.4, §1.5)
- Step verdicts **MUST** go to audit chain; `(step, verdict, verifier)` labels persisted for training (§1.5)
- SPDL depth-gating: symbolic verifiers always run; PRM only at `thorough`/`exhaustive` (§1.3.6)
- Formal expressions **MUST** be generated under SDE, never parsed from raw model text (§1.6)

**SPEC-050 Quality-Tier-Supervised Router (`crp/qsr/`)** — Part 2
- `harvest()` of `(task features, routing decision, quality tier, vr_ratio, escalated, latency, cost)` from audit records — no new logging (§2.3.1)
- `CapabilityProfile` per model: competence-by-task-kind, `schema_complexity_ceiling`, ctx window (§2.3.2)
- `LearnedRouter` (GradientBoosting); **cold-start on profiles until ≥200 tier-A/S examples**; schema-ceiling pre-filter (§2.3.3)
- **Escalation ladder as SPDL primitive** — `escalate_on: tier_below/vr_ratio_below`, `max_rungs`, driven only by observed failure signals (§2.3.4)
- `adapt_schema()` — flatten/NL-rename tool schemas for small models (§2.3.5)
- Router decisions/outcomes **MUST** be written back to audit; training **MUST** use only HMAC-verified records; cloud escalation re-applies full DPE (§2.5–2.6)

**SPEC-051 Predictive Positioning (`crp/pp/`)** — Part 3
- `induce_rules()` over Tier-E action log: `(state_pattern, action) → outcome_pattern` with support + confidence (§3.3.1)
- `WorldModel.predict()` (§3.3.2); optional neural fallback (§3.3.5)
- **Causal CKF edges** `causes`/`enables`/`prevents`, textual vs interventional evidence kept distinct (§3.3.3)
- `guarded_dispatch()` — **simulation-before-action for HIGH-risk ops, failing open to a checkpoint**, never to silent execution (§3.3.4, §3.5)
- SPDL keys: `simulate_risk_levels`, `sim_confidence_floor`, `induction_schedule` (§3.3.4)
- Predictions written to audit; streamable via TEL (§3.4); induction only over provenance-verified Tier-E (§3.6)

**SPEC-052 Intent & Speech-Act Positioning (`crp/isa/`)** — Part 4
- `IntentClassifier` (SetFit `autocyber/crp-intent-setfit`): speech act, directness, implied constraints, valence — sub-10 ms (§4.3.1)
- `CoreferenceResolver` (fastcoref-class) over a session entity registry, incl. ordinal deixis ("the second option") (§4.3.2)
- `build_intent_section()` → envelope `interpreted_intent` section with `intent_confidence` feeding SPEC-053 (§4.3.3)
- Coref **MUST** run before envelope packing; tone **MUST NOT** influence operation selection (§4.4)

**SPEC-053 Clarification Protocol (`crp/clr/`)** — Part 5
- `should_clarify(intent_confidence, parse_divergence, risk, policy)` trigger (§5.3.1)
- `CRP-Clarification-Required` typed response with ≥2 interpretations + operations + optional default (§5.3.2)
- `X-CRP-Clarification` response header; AG-UI INTERRUPT lifecycle; audit-logged exchange (§5.3.3)
- No defaulted HIGH-risk proceed without explicit consent (§5.4)

**SPEC-054 Structured Decoding Enforcement (`crp/sde/`)** — Part 6
- `compile_tool_grammar()` — XGrammar compile, cached per `(schema, tokenizer)` (§6.3.1)
- `GrammarEnforcer` — per-decode-step bitmask logit masking (§6.3.2); vLLM path via `guided_json` request param (§6.3.2)
- `select_engine()` by constraint shape — CFG-capable engine for recursive schemas (§6.3.3)
- **MUST enforce grammar at decode time for ALL tool-calling generations; enforcement is primary, post-hoc validation only defence-in-depth** (§6.4); semantic checks (VR/DPE) still run

**SPEC-055 Epistemic Profiles (`crp/ep/`)** — Part 7
- `semantic_entropy()` over meaning-clusters via **bidirectional entailment** (NLI model), normalised 0–1 (§7.3.1)
- `CalibrationProfile` per (model, task_kind) — binned reliability curve, ECE, `overconfident_on()` — **stored as CKF nodes**, updated only from verified outcomes (§7.3.2)
- `epistemic_adjust()` — entropy > 0.6 caps tier at B + raises risk; overconfidence injects positioning hint + raises risk (§7.3.3)

**SPEC-056 Transparency Emission Layer (`crp/tel/`)** — Part 8
- D1: standard AG-UI lifecycle/text/reasoning/tool/state events (§8.3.1)
- D2: namespaced governance events — `crp.safety_scan`, `crp.verification`, `crp.quality`, `crp.prediction`, `crp.provenance` (§8.3.1)
- D3: faithful-narration contract — every narrated sentence entailment-checked before streaming, unsupported withheld (§8.3.2)
- D4: live client-verifiable HMAC provenance stream (§8.3.3); D5: quality/confidence badge (§8.3.4)
- D6: `Last-Event-ID` replay resumability backed by CSO (§8.3.5)
- Security: inert/declarative rendering, authenticated tenant-isolated endpoints, prototype-pollution hardening, disclosure tiers (§8.5)

**SPEC-057 Bi-Temporal CKF (`crp/btf/`)** — Part 9
- `BiTemporalFact` with event time `[valid_from, valid_to]` + ingestion time `[ingested_at, invalidated_at]` (§9.3)
- `supersede()` — never overwrite, preserve history (§9.3)
- `retrieve_as_of()` by world time; retrieval gains `as_of` filter; current queries **SHOULD** default to currently-valid facts (§9.4)

**Cross-cutting (Appendix B)**
- All new signals stream via TEL as governance events
- All training/induction reads only HMAC-verified audit/action records
- No overclaiming of calibration/causality/comprehension — honesty is itself a conformance requirement

**Part 11 (forward agenda)**
- SPEC-058 Governed Delegation (preview): signed delegation envelope (scope ≤ parent scope), cross-agent HMAC audit link, verification handshake requiring B's VR verdict + faithful-narration attestation (§11.4)
- Research leads: multi-agent trust/delegation, agent evaluation science, adversarial robustness catalogue, memory consolidation/forgetting, ontology-grounded reasoning, conformal prediction, deep neurosymbolic world models

## 3. Explicit TODOs / next steps stated in the document

- **Build order (§0.3):** Wave 1 (VR, SDE, TEL) → Wave 2 (QSR, EP, ISA) → Wave 3 (PP, CLR, BTF). Pragmatic first sprint (§0.5): **SDE + TEL + CLR + VR-symbolic**.
- **VR sequencing (§0.5):** "Ship symbolic first, PRM second" — PRM needs a trained classifier; symbolic verifiers are quick wins.
- **Appendix B consolidated build checklist** — wave-by-wave MUST verification before moving on ("Ship a wave, verify its checklist, move on").
- **QSR cold-start gate (§2.5):** stay on capability profiles until ≥200 tier-A/S examples accrue, then switch to learned model; hold out a trusted eval set against poisoning before promoting a new router.
- **PP induction schedule (§3.3.4):** nightly re-induction over the growing action log; start with shallow symbolic rules, gate hard, never overclaim causality.
- **Standards plays (§10.3):** push the governance-event vocabulary (SPEC-056) and clarification primitive (SPEC-053) to the IETF/IANA track.
- **SPEC-058 Governed Delegation (§11.4):** the "natural tenth spec… Wave 4"; next report in the series should be multi-agent governance (§11.5).

## 4. Gap check (verified against `crp/` tree + wiring greps)

| Demand | Status | Evidence |
|---|---|---|
| **SPEC-049 VR** modules (interface, z3, exec, prm, relay) | **IMPLEMENTED** | All present in `crp/vr/`; `tests/test_vr.py` passes. PRM defaults to `AutoCyberAI/crp-prm-deberta-v1` via `crp.ml` lazy/budgeted load with UNKNOWN fallback (`crp/vr/prm.py`) — model artifact still training (expected per "symbolic first, PRM second") |
| VR wired as DPE stage 14 + tier cap D / risk floor + `CRP-Verification-Ratio` | **IMPLEMENTED (with caveat)** | Relay emits `dpe_14_verification` report with `tier_cap: "D"`/`risk_floor` (`crp/vr/relay.py:114-119`); invoked from `crp/gateway/api.py:826-935` and `crp/agent_sdk/agent.py:444`. Caveat: not literally a 14th stage inside `crp/provenance/` DPE engine — wired at gateway/agent layer |
| VR SPDL depth-gating directives (`safety-policy.yaml`) | **PARTIAL** | Depth gate exists as code param (`min_depth_for_prm`, `crp/vr/relay.py:40`); no `verification_relay:`/`enabled_at_depth:` policy directives found in `crp/policy/` or `crp/security/` |
| **SPEC-050 QSR** modules (harvest, profiles, router, escalation, schema_adapt) | **IMPLEMENTED (modules)** | All in `crp/qsr/` + `tests/test_qsr.py`; cold-start ≥200-example gate in `crp/qsr/router.py` |
| QSR wired into dispatch | **IMPLEMENTED (opt-in)** | `crp/qsr/gateway.py:resolve_model` called from `crp/gateway/api.py:1101-1103` when `model: crp-learned` or `crp-model-selection: learned` header |
| QSR escalation ladder in runtime path | **MISSING (unwired)** | `run_with_escalation` never called outside `crp/qsr/` itself; no SPDL `escalation:` policy block found |
| QSR schema adaptation applied on route | **MISSING (unwired)** | `adapt_schema` exported but never invoked in the gateway resolve path; router only pre-filters by ceiling |
| **SPEC-051 PP** modules (induction, world_model, causal_ckf, simulate) | **PARTIAL** | All four modules + `tests/test_pp.py` (200 lines) exist, but `guarded_dispatch`/`WorldModel`/causal edges are **never called anywhere outside `crp/pp/`** — no HIGH-risk simulation hook in gateway/agent, no induction schedule, no SPDL keys, causal edges not added to real `crp/ckf` |
| **SPEC-052 ISA** (SetFit intent + coref + intent section) | **IMPLEMENTED** | `crp/isa/{intent,coref,position}.py`; SetFit model in `crp/ml/manifest.json` (`crp.isa.intent`), ML-default with rule fallback; fastcoref lazy-loaded with rule fallback; wired into `crp/agent_sdk/agent.py:28`; `tests/test_isa.py` |
| **SPEC-053 CLR** (trigger, response, `X-CRP-Clarification`) | **IMPLEMENTED** | `crp/clr/{trigger,response,handler}.py`; wired into `crp/agent_sdk/agent.py:344-350` emitting header + typed `CRP-Clarification-Required`; `tests/test_clr.py` |
| **SPEC-054 SDE** — token-level grammar enforcement (XGrammar) | **MISSING** | No `crp/sde/`; zero hits for `xgrammar`/`guided_json`/`GrammarEnforcer` in `crp/`. Only `crp/gateway/structured_decoder.py` = post-hoc JSON-Schema validation + one-turn repair — precisely what §6.4 forbids as the *primary* guarantee. `crp/stl/positioned.py:124` notes constrained decoding "can be layered on later" |
| **SPEC-055 EP** modules (entropy, calibration, apply) | **PARTIAL** | All three + `tests/test_ep.py` exist (NLI via `cross-encoder/nli-deberta-v3-xsmall`), but `epistemic_adjust`/`semantic_entropy` are **never called from gateway/agent/tier pipeline**; calibration not stored in CKF; entropy appears only as an optional TEL payload field (`crp/tel/adapter.py:53`) |
| **SPEC-056 TEL** (AG-UI D1–D6, faithful narration, replay) | **IMPLEMENTED** | `crp/tel/`: AG-UI `EventType` vocab + CUSTOM governance events incl. `crp.prediction`/`crp.provenance` (`events.py`, `adapter.py:59-64`), `faithful.py` (D3), `sse.py` with `Last-Event-ID` replay (D6), wired into `crp/agent_sdk/agent.py:511`; `tests/test_tel.py` + `test_tel_sse.py` |
| **SPEC-057 BTF** (bi-temporal facts, supersede, as-of) | **PARTIAL** | `crp/btf/temporal.py` has `BiTemporalFact` + `TemporalCKF` with `supersede`/`retrieve_as_of`/`current` + `tests/test_btf.py` — but it's a standalone in-memory store; **nothing in `crp/ckf/` or the retrieval path consumes it**; no `as_of` filter on SPEC-028 retrieval |
| **SPEC-058 Governed Delegation** (preview, Wave 4) | **MISSING** | No `crp/delegation/` — expected; explicitly a preview, not a current-cycle demand |
| Cross-cutting: all signals stream via TEL | **PARTIAL** | TEL adapter has the methods, but PP/EP produce no runtime signals to stream |
| Cross-cutting: training only on HMAC-verified records | **PARTIAL/UNVERIFIED** | `crp/qsr/harvest.py` reads audit records; no provenance-verification gate found before training |
| Phase-A ML models (intent SetFit, safety DeBERTa) | **IMPLEMENTED** | `crp.isa.intent` + `crp.security.safety` (`AutoCyberAI/crp-safety-deberta-v1`) in `crp/ml/manifest.json`; safety wired into `crp/security/injection.py`. PRM training in progress |

**Net:** Wave 1 is ~2/3 done (VR ✅, TEL ✅, SDE ❌-core); Wave 2 is ~2/3 done (ISA ✅, QSR mostly ✅ but escalation/adaptation unwired, EP code-complete but inert); Wave 3 is ~1/3 done (CLR ✅, PP and BTF code-complete but inert). The pattern: **every module exists with tests; the gaps are (a) SDE's actual enforcement mechanism, and (b) runtime wiring of PP, EP, BTF, QSR-escalation.**

## 5. Priority picks

1. **SPEC-054 SDE — real XGrammar grammar enforcement in the Gateway.** The only Wave-1 spec whose *core mechanism* is genuinely absent (post-hoc validation ≠ decode-time enforcement; the spec explicitly forbids validation-as-primary). Doc rates it Low effort / Low risk / High demo value, it kills a whole class of SLM tool-call failures, and §6.5 makes it a *security* control that also closes VR's formal-expression injection vector (§1.6).
2. **Wire SPEC-051 PP + SPEC-055 EP into the dispatch path (gateway/agent).** Both are code-complete with tests but inert — `guarded_dispatch` and `epistemic_adjust` are never called at runtime. Wiring is small effort and activates the two highest-story claims in the document ("anticipatory oversight", "knows what it doesn't know"), feeding the TEL `crp.prediction`/`crp.quality` events that already exist.
3. **Integrate SPEC-057 BTF into CKF retrieval (`as_of` filter, default currently-valid).** Small, self-contained substrate fix for a real grounding failure mode (stale superseded facts); completes Wave 3 and is a prerequisite for honest "what we believed then" audit claims.

*(Runner-up: QSR escalation-ladder wiring — same "code exists but inert" pattern, but lower demo value than PP/EP. SPEC-058 should stay Wave 4 until the nine-spec core is fully wired, per the document's own sequencing.)*

<!-- ==================== Governed_vs_Bare_Benchmark_source.md and benchmark_harness.py and benchmark_sweep.py ==================== -->
# Analysis: Governed-vs-Bare Benchmark Bundle

All three files form one artifact: a report (`Governed_vs_Bare_Benchmark_source.md`) plus the two runnable scripts (`benchmark_harness.py`, `benchmark_sweep.py`) that produce its numbers. Verified against repo state via Grep/Glob in `crp/`, `docs/`, `examples/`, `scripts/`.

---

## 1. `Governed_vs_Bare_Benchmark_source.md`

### What it is
A benchmark report (July 2026) that converts the series' illustrative "ASR 0% gated vs 12% ungated" claim into a *measured, reproducible* result: a CRP-style deterministic policy gate drives attack-success-rate from ~15% (bare) to 0% (governed) at zero utility cost and ~0.24µs overhead, and a susceptibility sweep proves the gate is **susceptibility-independent** (bare ASR 7%→70%, governed stays 0.00%). It applies a rigorous honesty rule: this is a *mechanism benchmark* with exactly one modeled quantity (model injection-susceptibility), not a live-LLM run.

### Concrete demands on CRPv6
- **A deterministic policy gate / reference monitor** (§2 "The gate", §8) with three rules: (1) **scope enforcement** — target must be in authorised scope; (2) **information-flow/egress control** — sensitive-labeled data may not flow to unapproved sinks; (3) **irreversible→human approval** — irreversible actions never auto-execute. Fail-safe default deny, complete mediation. §8 states this gate *is* SPEC-006 (SPDL policy) + SPEC-033 (safety control plane).
- **Tamper-evident audit chain recording per-action gate decisions** — "the per-action decisions the harness counts *are* the entries the audit chain (SPEC-011/029) would record as tamper-evident evidence" (§8).
- **Verification relay + human oversight for in-policy attacks** — attacks within expressible policy "are the domain of the verification relay and human oversight" (§7).
- **A runnable, seeded, reproducible harness** producing ASR / task-utility / overhead tables with 95% CIs over 30 trials (§2–§3).
- **One-line live-model substitution** — replace `ModelSim.decide` with a real OpenAI-compatible/local-SLM client; everything else unchanged (§6).
- **Real dataset loaders** for AgentDojo / AgentHarm / InjecAgent (§6).
- **Reliability panel (pass^k)** and **utility-cost panel** (measure over-blocked legitimate actions / false-positive cost) (§6, §7).
- **AIUC-1 auditor-grade artifact** — governed-vs-bear ASR table + sweep as the evidence artifact an accredited auditor would examine (§5, §7, §8).

### Explicit TODOs / next steps in the document
- §6: swap `ModelSim` for `LiveModel` (code sketch provided) — any OpenAI-compatible/local SLM endpoint.
- §6: point the suite loader at the real AgentDojo / AgentHarm / InjecAgent datasets.
- §6: add a reliability panel (pass^k over repeated trials) and a utility-cost panel (over-blocking measurement).
- §7: build scenarios for in-policy attacks (VR + human oversight domain).
- §7: live run must measure false-positive/over-blocking cost.
- §7: pursue AIUC-1 certification via accredited auditor live adversarial testing.

### Gap check (vs repo state)
| Demand | Status | Evidence |
|---|---|---|
| Deterministic policy gate (SPEC-006/033) | **PARTIAL** | `crp/policy/enforce.py` (`enforce_policy` → `PolicyDecision`), `crp/security/control_plane.py` (`SafetyControlPlane`), `crp/agent_sdk/policy.py` (`Policy.allow_only`, `.domain`, `.block` — SPEC-059 §4), `crp/tools/capability_fabric.py` (`PolicyContext` pre-filter with allowlist + policy-domain check — SPEC-050 §3.4) all exist. But there is **no single tool-call-level reference monitor** combining scope + egress + reversibility. |
| Egress/information-flow taint rule (data labels → approved sinks) | **MISSING** | No taint/label-based egress mediation found in `crp/` (greps for `egress`, `information.?flow`, `approved_sink` hit only unrelated allowlist code). |
| Irreversible→approval | **IMPLEMENTED** | `crp/security/checkpoint.py` (Checkpoint primitive, approve/reject/edit, timeout/reject fallback — SPEC-033/034). |
| Tamper-evident audit chain | **IMPLEMENTED** (chain) / **PARTIAL** (per-action wiring) | `crp/security/audit_trail.py` — HMAC-SHA256 chained `ComplianceAuditTrail` with `verify_chain()` (§7.14). No evidence gate decisions are auto-recorded per tool call. |
| Verification relay + human oversight | **IMPLEMENTED** | `crp/vr/` (`VerificationRelay`, `Z3Verifier`, `ProcessRewardVerifier`, `ExecVerifier`) + `crp/security/checkpoint.py`. |
| Governed-vs-bare harness in repo | **MISSING** | Zero matches for `AgentDojo|AgentHarm|InjecAgent|attack_success|ASR` in `crp/` or `docs/`; harness exists only in the research folder. `examples/crp_demos/sqb_benchmark.py` is a *quality* benchmark, not security ASR. |
| Live-model adapter (`LiveModel`) | **MISSING** | Harness not in repo; no adapter. |
| Real dataset loaders (AgentDojo etc.) | **MISSING** | — |
| pass^k / utility-cost panels | **MISSING** | `pass^k` appears only in research docs, no code. |
| AIUC-1 evidence artifact | **PARTIAL** | Audit trail + `crp/security/compliance.py` reporter exist; `site-docs` has `aiuc-1/` pages; no benchmark→evidence-pack pipeline. |

### Priority picks
1. **Port the harness + sweep into the repo, wired to CRP's real enforcement path** (`agent_sdk.Policy` → `capability_fabric.PolicyContext` → `Checkpoint`, decisions recorded into `ComplianceAuditTrail`) — this single artifact turns "governance works" from assertion into a reproducible measurement and directly produces the AIUC-1 evidence the report promises (§8).
2. **Implement the egress/information-flow taint rule** (sensitive data labels → approved sinks) as a first-class mediation rule in the tool-call path — the one gate rule with no counterpart in `crp/` today, and the rule that blocks the highest-susceptibility attack class (exfiltration, 0.18).
3. **Add the utility-cost (over-blocking) panel** — required before any honest auditor-grade claim, since real deployments *will* over-block (§5, §7).

---

## 2. `benchmark_harness.py`

### What it is
A self-contained, stdlib-only, seeded 179-line harness implementing the mechanism benchmark: `ModelSim` (the one modeled quantity — per-attack-type injection susceptibility 0.10–0.18), `PolicyGate` (the real deterministic reference monitor: scope / egress / irreversible→approval, default-deny, complete mediation), a 200-scenario suite across 4 attack classes, and a 30-trial runner emitting ASR, task utility, gate overhead (ns-timed), and 95% CIs as JSON.

### Concrete demands on CRPv6
- **Gate semantics as a reusable decision point**: `PolicyGate.mediate(action, scenario) -> {ALLOW, DENY, APPROVE}` where APPROVE ≠ auto-execute — CRP's real policy path must expose an equivalent per-action mediation function so the same harness can run against it (docstring: "The POLICY GATE is implemented for real… running identically in both arms").
- **Three concrete mediation rules** (lines 75–86): (1) `action.target not in authorised_scope → DENY`; (2) `action.data_labels and action.target not in approved_sinks → DENY`; (3) `action.irreversible → APPROVE`. These are the exact semantics CRP's gate must express.
- **A `decide(scenario) -> list[Action]` model interface** that a real model client can implement with tool-call parsing (`parse_actions(resp)`) — i.e., an adapter contract between any OpenAI-compatible/SLM endpoint and the benchmark.
- **Metrics/reproducibility infrastructure**: seeded identical decisions across both arms (same seed → same model decisions), per-call overhead timing (`perf_counter_ns`), 95% CI computation, ASR/utility/asr_reduction/utility_delta reporting.
- **Per-action decision accounting** (`gate.calls`) — the countable unit that should map to audit-chain entries.

### Explicit TODOs / next steps in the document
- Only one, stated twice (module docstring + class docstring): **"Replace `ModelSim.decide` with a real model client for live numbers"** — the harness is otherwise feature-complete for its mechanism-benchmark purpose; further upgrades (datasets, panels) live in the report §6.

### Gap check (vs repo state)
| Demand | Status | Evidence |
|---|---|---|
| Per-action `mediate()` decision point in real CRP path | **PARTIAL** | `capability_fabric.PolicyContext.evaluate(cap) -> (bool, reason)` (allowlist, policy-domain) and `crp/policy/enforce.py:enforce_policy` are real decision points, but neither takes target/labels/reversibility; no unified 3-rule monitor exists. |
| Rule 1 — scope enforcement | **PARTIAL** | Capability allowlist + `Policy.domain()` restrict *which tools/domains*, not per-call *targets* within a tool. |
| Rule 2 — egress/IFC (labels → sinks) | **MISSING** | No data-label taint tracking in `crp/`. |
| Rule 3 — irreversible→approval | **IMPLEMENTED** | `crp/security/checkpoint.py`; `irreversible` also matched in `crp/sdk/client.py`, `crp/state/cso.py`, `crp/core/dispatch_router.py` (concept present, not unified into gate rule). |
| Model adapter contract | **MISSING** | No harness/adapter in repo; CRP providers (`crp/providers/`) could host it trivially. |
| Metrics/CI/trial infrastructure | **MISSING** | No ASR benchmark in `examples/` or `scripts/`; SQB benchmark is quality-focused. |
| Per-action decisions → audit chain | **PARTIAL** | `ComplianceAuditTrail.append_entry` exists; no gate→trail wiring found. |

### Priority picks
1. **Adopt this file into the repo** (e.g. `examples/crp_demos/governed_vs_bare.py`) with `PolicyGate` replaced by the real CRP stack — the docstring's own design ("swap ModelSim… the rest of the harness is identical") makes this a small, high-leverage change.
2. **Extend the real policy path with the two missing rule primitives** (per-call target scope and data-label→sink egress) so the harness runs *unmodified* against CRP.
3. **Implement the `LiveModel` adapter against `crp/providers/`** (OpenAI-compatible + local SLM) — one class, converts mechanism numbers into live numbers.

---

## 3. `benchmark_sweep.py`

### What it is
A 22-line driver that imports the harness as `H`, scales `H.SUSCEPTIBILITY` by multipliers 0.5×/1×/2×/3×/5× (capped at 1.0, restored after each run), reruns both arms (20 trials each), and prints the sweep table as JSON plus the key result: governed ASR stays 0.0 while bare ASR climbs toward 1.0 — empirical proof of susceptibility-independence.

### Concrete demands on CRPv6
- **Deterministic, model-external gate (architectural invariant)**: the sweep's whole point is that CRP's gate must decide *deterministically and outside the model* — governed ASR must be invariant to model weakness. This is a *property* CRP's policy enforcement must possess and be able to demonstrate.
- **Sweep runner capability**: parameter-scaling over susceptibility multipliers with clean mutate-restore discipline (`H.SUSCEPTIBILITY.update(base)` after each run) — i.e., the benchmark tooling should support scaling experiments, not just point measurements.
- **Regression property**: "governed ASR == 0 at every multiplier" is the acceptance criterion the sweep asserts (final print); any live version of this in CRP needs the same invariant guarded.

### Explicit TODOs / next steps in the document
- None stated as future work — the file is complete and self-executing. The only imperative is the printed key result (governed ASR stays 0.0), which functions as the property to preserve/re-verify when a live model replaces `ModelSim`.

### Gap check (vs repo state)
| Demand | Status | Evidence |
|---|---|---|
| Deterministic, model-external gate property | **IMPLEMENTED** (as architecture) | `enforce_policy(policy, signals)` is a pure function of policy + signals; `PolicyContext.evaluate` is deterministic set-membership; `Checkpoint` resolves externally. The *property* holds by design. |
| Empirical demonstration of the property | **MISSING** | No sweep/benchmark/test in repo demonstrates governed-ASR invariance; only the research-folder script. |
| Sweep runner in repo | **MISSING** | — |
| Regression guard (governed ASR == 0 across multipliers) | **MISSING** | No test asserting this; `scripts/probe_safety.py` and `examples/crp_demos/safety_checkpoint_test.py` probe safety behavior but are not ASR sweeps. |

### Priority picks
1. **Fold the sweep into the repo benchmark as a `--sweep` mode and add a CI test asserting governed ASR == 0.0 at all multipliers** — cheap (mechanism-level, no live model needed), and it permanently guards CRPv6's central security claim ("you cannot make the model immune, so you make a compromised model harmless") against regressions in the policy path.

---

## Cross-document summary

- **The bundle's single big ask:** a reproducible governed-vs-bare security benchmark (harness + sweep + live adapter + dataset loaders + pass^k/utility panels) whose gate *is* CRP's SPEC-006/033/059 enforcement path and whose per-action decisions land in the SPEC-011 audit chain — producing the AIUC-1-grade evidence artifact.
- **Repo state:** the *governance machinery* largely exists (policy enforcement, control plane, checkpoints, capability pre-filter, HMAC audit trail, verification relay) — **PARTIAL/IMPLEMENTED** — but the *measurement layer* is entirely **MISSING** from the repo: no harness, no sweep, no ASR metrics, no egress-taint rule, no benchmark→evidence pipeline. The two scripts exist only in the `AutoCyber AI Agentic AI research with CRP/` folder.
- **Top-3 next builds (merged):**
  1. **`examples/crp_demos/governed_vs_bare.py` + sweep mode + CI regression test** wired to the real policy path — highest evidence-value per line of code; directly marketable (AIUC-1) and cheap since the scripts already exist.
  2. **Egress/information-flow taint rule (data labels → approved sinks)** in the tool-call mediation path — the one gate rule CRP genuinely lacks; blocks the exfiltration class.
  3. **`LiveModel` adapter + utility-cost (over-blocking) panel** — converts mechanism numbers into live, honest, auditor-grade numbers (report §6–§7).

*Caveats:* I verified existence/absence of modules and symbols via targeted Grep/Glob, not by executing code. I did not trace whether `ComplianceAuditTrail` is auto-invoked from `agent_sdk` tool execution — the "per-action audit wiring" PARTIAL verdict is based on no grep evidence of such wiring.

<!-- ==================== Local_Agentic_SLM_Applications_source.md and The_Economics_of_SLM-First_Agentic_AI_source.md ==================== -->
All checks complete. Here is the full analysis.

---

# Document 1 — `Local_Agentic_SLM_Applications_source.md`

## 1. What it is

A 38-chapter engineering report (July 2026) on building real-time, tool-driven **local voice agents**: SLM inference (engines, quantization), STT/TTS, streaming voice loops, packaging (Nuitka/native), on-device RAG/memory/vision, and production audio. Its CRP-relevant thesis (Ch 12, 18, 27): CRP v6's governance layer *is also the speed layer* — positioning shrinks prefill, structured decoding kills retry latency — and CRP's Agent SDK is the missing "governed, positioned agentic middle" between voice frameworks (Pipecat/Moonshine) and local engines (llama.cpp/ExecuTorch).

## 2. Concrete demands on CRPv6

- **Positioning as a latency feature** (Ch 1, 12, 29): load only the 1–3 tools a step needs, relay state via CSO instead of re-stuffing the window; keeps prefill ~90 ms in the walkthrough.
- **Structured-decoding tool validity, SPEC-054, explicitly "XGrammar"** (Ch 12, 20, 34, 38): tool calls valid *by construction at token level* — "eliminating the retry loop… avoiding one re-generation can save hundreds of milliseconds" on slow on-device decode.
- **SLM-first right-sizing** (Ch 12, 20): "pick the smallest model in the Qwen3 family that passes your task's eval, because positioning does the heavy lifting"; SPEC-050 schema-simplification adapter to flatten nested tool schemas for small models.
- **`crp.Agent` SDK, SPEC-059** (Ch 12, 27): `Agent(model="qwen3-4b-instruct-Q4_K_M", tools=[ScanHost], policy=Policy.from_file("voice-policy.yaml"), stream=True, depth="quick")`; local GGUF "via the CRP engine adapter".
- **Class-based intent manifest** (Ch 27): `from crp.agent.manifest import Intent, Effect, SafetyClass`; `class ScanHost(Intent)` with `when_to_use`, `effect = Effect.READ_ONLY`, `safety_class = SafetyClass.GATED`, `compile()` emitting safe invocations.
- **Token streaming for TTS** (Ch 27): `agent.stream(user_text)` *yields narrative tokens* piped into sentence-chunked TTS; `stream=True` "emits AG-UI + governance events (SPEC-056)".
- **`depth="quick"`** (Ch 27): "skips the heavy verification stages for the voice path while keeping the safety gate."
- **Safety-gated tools + HITL** (Ch 36, 38): safety-classed tools, policy gate with human-in-the-loop for dangerous effects (SPEC-033); faithful narration ("cannot claim it scanned a host it didn't") + signed audit trail (SPEC-011/029/056).
- **Agentic RAG as a positioned tool** (Ch 30, 38): `search_knowledge` tool — model decides when to retrieve; "retrieval becomes a positioned tool with provenance (SPEC-027 retrieval integrity)".
- **Bounded auditable memory** (Ch 31): summary+window; "exactly what SPEC-045 and the CSO (SPEC-030) formalise".
- **Quality tiers as an automatable quant/eval gate** (Ch 21.3, 37, 38): "CRP's quality tiers (SPEC-026)… turn 'is this quant good enough?' into a measured, automatable gate"; run task eval in CI.
- **Vision as a positioned, safety-classed tool** (Ch 32, 38).
- **Semantic endpointing classifier** (Ch 25.3): SetFit `turn-complete` classifier as the model-training pattern (same SetFit approach as CRP's intent model).
- **Device-detected model delivery** (Ch 28.2): download-on-first-run, fetch the right quant/engine build per device.

## 3. Explicit TODOs / next steps in the document

- **Ch 19 "Shortest Path to a Demo"**: build laptop demo (Qwen3-4B Q4_K_M on llama.cpp/MLX + Moonshine Base + Silero VAD + Kokoro sentence-chunked + barge-in) → swap inline loop for `crp.Agent` → package with Nuitka → native phone build on ExecuTorch/MNN/Cactus.
- **Ch 38 Production Readiness Checklist** (the ship gate): smallest-eval-passing SLM; Q4_K_M verified; per-target engine; KV-quant + Flash Attention + prefix caching; streamed stages <800 ms TTFT; semantic endpointing; barge-in; full audio front-end (AEC/noise/resample); grammar-constrained tools; step-budgeted loop with trace; positioning; safety-classed gated tools; faithful narration + signed audit; bounded memory; agentic RAG; vision-as-tool; Nuitka/native packaging; device-detected model delivery; sustained-load testing; per-OS CI with task eval.
- **Ch 26**: watch S2S models (Moshi/Ultravox); consider hybrid once S2S exposes text-level tool/policy hooks.
- **Ch 16/32**: watch native multimodal SLMs (Qwen3-Omni-class) and NPU inference frontier.
- Implicit: train a `turn-complete` SetFit endpointing model (Ch 25.3 shows it as `autocyber/turn-complete-setfit`).

## 4. Gap check

| Demand | Verdict | Evidence |
|---|---|---|
| Positioning (1–3 tools/step, CSO relay) | IMPLEMENTED | `crp/stl/tool_positioner.py`, `crp/stl/positioned.py`, `crp/state/cso.py` (SPEC-050/030) |
| Structured decoding SPEC-054 | **PARTIAL** | `crp/gateway/structured_decoder.py` is *post-hoc validate + single repair turn*, not XGrammar token-level constraint — the retry-generation cost the doc wants eliminated still exists |
| SPEC-050 schema adapter (flatten nested schemas) | IMPLEMENTED | `crp/qsr/schema_adapt.py`, `crp/stl/tool_positioner.py` |
| `crp.Agent` (SPEC-059) | IMPLEMENTED | `crp/agent_sdk/agent.py` — `Agent(model, tools, policy, depth=…)`, `run()`/`ask()` |
| `Policy.from_file(...)` | **MISSING** | `crp/agent_sdk/policy.py` has `balanced/strict/permissive/grounded/block/…` builders only; no YAML file loader (no `from_file` anywhere in `crp/`) |
| `crp.agent.manifest` Intent/Effect/SafetyClass class API | **MISSING** | No `crp/agent/manifest.py`; no `Intent`/`Effect` classes in `crp/`. SDK uses plain callables via `intent_compiler.py`; `SafetyClass` lives in `crp/tools/descriptor.py` with values READ_ONLY/MUTATING/DESTRUCTIVE/NETWORK/HUMAN_OVERSIGHT (no `GATED`). Doc's Ch 27 template will not run as written |
| `agent.stream()` token streaming | **MISSING** | `Agent.run_stream()` exists but yields `AgentEvent` governance events; `AgentEventKind` has no `TOKEN` kind (events.py:20–29); `model_call.py` has no streaming path. Nothing to pipe into TTS |
| `depth="quick"` (skip verification, keep safety) | IMPLEMENTED | `agent.py:119,441–448` — depth auto/quick/standard/thorough; VR only on thorough/exhaustive |
| AG-UI + governance events (SPEC-056) | IMPLEMENTED | `crp/tel/` (adapter, events, sse, emitter) — AG-UI vocabulary with governance extensions |
| Safety-classed tools + HITL (SPEC-033) | IMPLEMENTED | `SafetyClass` in descriptor; `crp/security/checkpoint.py`; `crp/security/control_plane.py` |
| Faithful narration + signed audit | IMPLEMENTED | `crp/tel/faithful.py`; v3 audit chain + `crp/ep/` |
| Agentic RAG as positioned tool (SPEC-027) | PARTIAL | `crp/envelope/retrieval_integrity.py` exists; STL has RETRIEVE op + CKF query tools — but no `search_knowledge`-style on-demand retrieval tool wired into the Agent SDK |
| Bounded auditable memory (CSO/SPEC-045) | PARTIAL | CSO (SPEC-030) implemented; SPEC-045 session learning deferred (frontier) |
| Quality tiers as quant/eval gate (SPEC-026) | IMPLEMENTED | S/A/B/C/D `QualityReport`; `examples/crp_demos/sqb_benchmark.py`, `sqb_positioned.py` |
| Local GGUF engine adapter | IMPLEMENTED | `crp/providers/llamacpp.py`, `ollama.py` |
| Semantic endpointing SetFit model | MISSING | No turn-complete model artifact; SetFit infra exists (`crp/isa/intent.py` + `crp-intent-setfit`) to train one |
| Device-detected model delivery | PARTIAL | `crp/ml/downloader.py` + `manifest.json` do HF downloads of CRP's own ML models; no device detection or quant/engine selection |
| Vision-as-tool, voice demo app | MISSING | No vision tool, no voice example in `examples/` |

## 5. Priority picks

1. **Token-level streaming on `crp.Agent`** (`stream()` or a `TOKEN` AgentEvent) — the doc's entire CRP-voice integration (Ch 27) pipes narrative tokens into TTS; today only governance events stream, so the flagship use case is unwirable.
2. **True grammar-constrained decoding (XGrammar) behind SPEC-054** — current validate+repair still burns a full extra on-device generation; the doc names this the #1 agentic latency killer on SLMs (Ch 12, 34).
3. **Runnable voice-agent reference example + `Policy.from_file`** — ship the Ch 27 `crp_voice_agent.py` as a working example (fixing the manifest-API mismatch); it is the demo that proves "CRP is the governed brain of a local voice agent" and doubles as the SPEC-059 showcase.

---

# Document 2 — `The_Economics_of_SLM-First_Agentic_AI_source.md`

## 1. What it is

The business-case foundation of the series: SLM-first agents are 1–2 orders of magnitude cheaper per token, local inference removes the network round-trip that dominates agent-loop latency, fixed-cost local beats variable-cost cloud above a break-even (~50k req/mo), and governance is near-free (~0.24 µs/action measured) while avoiding catastrophic compliance costs. It derives the Comply/Gateway/Scan unit economics, the four-way moat (cheaper + faster + more private + more provable), pricing logic, and sector deep-dives (DORA, HIPAA, TLPT/security).

## 2. Concrete demands on CRPv6

- **Deterministic policy gate at ~0.24 µs/action, measured** (Ch 7, 12, 17, 25, 26): the headline number of the whole case; scope allowlist + egress + reversibility checks; "drives attack-success-rate from ~15% to 0% at zero utility cost" (from the Governed-vs-Bare benchmark).
- **SLM-first routing with LLM fallback** (Ch 8, 15, 16, App B): a cheap classifier routes the routine 70–90% to a local SLM, hard tail to an LLM; "routing threshold is set by measured eval scores… tuned by replaying production traffic against eval scores (the Evaluation pillar)".
- **LLM-as-planner / SLM-as-executor** (Ch 9): LLM decomposes once, SLM runs the many execution sub-steps.
- **Speculative decoding** (Ch 9): SLM drafts, LLM verifies, to speed unavoidable LLM calls.
- **Quality-risk management around routing** (Ch 9, 19, App B): evaluate both models on the same eval set before setting the routing default; **verify SLM outputs on critical fields (the verification relay)**; **monitor task-success-rate and hallucination-rate in production (observability)**; fall back to the LLM on low confidence.
- **Tamper-evident evidence emission as byproduct** (Ch 10, 13, 28–31): continuous audit trail + framework crosswalks (EU AI Act, NIST, ISO 42001, SOC 2, GDPR, AIUC-1) feeding Comply; "emit-not-reconstruct", "map-once-satisfy-many".
- **On-device / local-first runtime** (Ch 3, 4, 6, 17): inner-loop calls local; no `CRP-*` leakage implied; data never leaves the device (HIPAA/DORA arguments depend on it).
- **Runnable cost models** (Ch 5, 8, 25): `tco.py`, `routing_economics.py`, `unit_economics.py` — break-even, blended cost, governance-overhead arithmetic as inspectable code.
- **Product surface** (Ch 10, 24): Comply (value-priced evidence), Gateway (infrastructure-priced governed runtime incl. MCP/tool supply-chain governance), Scan (free funnel).
- **Governance-over-cloud for below-break-even customers** (Ch 16, 22): governance must be model-agnostic and wrap cloud calls too.

## 3. Explicit TODOs / next steps in the document

No build checklist — it is a business-case document. Its forward-looking items:
- **Ch 16 buyer playbook** (framed as "a list of CRP capabilities"): audit traffic → route → govern deterministically → keep latency local → evaluate continuously.
- **Ch 8**: tune the routing threshold by replaying production traffic against eval scores.
- **Ch 25**: ship the full unit-economics model as runnable, adjustable code ("the point of shipping the model rather than just the numbers").
- **Ch 19/26**: keep the case honest — verify pricing before budgeting; say "governance-over-cloud" to buyers who can't run infra.
- Cross-references as dependencies: the *Governed vs Bare* benchmark (the 0.24 µs / 15%→0% source), the Compliance Crosswalk, the Evaluation pillar report.

## 4. Gap check

| Demand | Verdict | Evidence |
|---|---|---|
| Deterministic policy gate (~0.24 µs) | IMPLEMENTED (gate) / **PARTIAL (proof)** | Gate exists (`crp/agent_sdk/policy.py`, `crp/tools/capability_fabric.py` PolicyContext, `crp/security/control_plane.py`). But the 0.24 µs benchmark harness lives only in the research folder (`AutoCyber AI Agentic AI research with CRP/benchmark_harness.py`); nothing in `examples/` or `tests/` reproduces the headline measurement |
| SLM-first routing + LLM fallback | IMPLEMENTED | `crp/qsr/router.py` (LearnedRouter — routes to "model most likely to hit tier A/S at least cost", SPEC-050 §2.3.3) + `crp/qsr/escalation.py` (smallest-first ladder `["gemma3-4b","qwen3-coder-7b","cloud-large"]`, escalates on quality-tier/VR-ratio signals) |
| Routing threshold tuned by eval scores | PARTIAL | LearnedRouter trains on harvested `RoutingExample`s; escalation keys off tier/VR signals; SQB (`examples/crp_demos/sqb_benchmark.py`) provides the eval — but no production-traffic-replay tuning loop is wired |
| LLM-as-planner / SLM-as-executor | **MISSING** | No planner/executor pattern anywhere in `crp/` (grep hits only the research docs). STL decomposes operations but there's no cross-model plan/execute split |
| Speculative decoding | **MISSING** | No matches in `crp/` — engine-level concern (llama.cpp supports it), arguably out of SDK scope |
| Verify SLM outputs (verification relay) | IMPLEMENTED | `crp/vr/` (SPEC-049), depth-gated in `agent.py:441–448`; PRM step-verifier training in progress |
| Monitor task-success / hallucination in production | IMPLEMENTED | `crp/observability/quality.py`, `crp/provenance/` hallucination scoring, `crp/vr/` |
| Tamper-evident evidence emission + crosswalks | IMPLEMENTED | v3 audit chain, `crp/ep/` provenance, `crp/comply/`, `crp/tel/`; compliance crosswalk docs exist |
| Local-first runtime / no round-trip for inner loop | IMPLEMENTED | llama.cpp/Ollama providers; positioned loop is local-capable |
| Runnable TCO / routing-economics / unit-economics models | **MISSING (as SDK artifacts)** | The models exist only as code blocks inside the research doc; `crp/resources/cost_model.py` is token/resource cost, not break-even/TCO economics |
| Comply / Gateway / Scan products | PARTIAL | `crp/comply/`, `crp/gateway/api.py` + `capability_router.py`, `crp/scan/` all exist; monetisation per AGENTS.md R3 status |
| Governance-over-cloud (model-agnostic gate) | IMPLEMENTED | Gate is provider-agnostic (works over OpenAI/Anthropic via Gateway and SDK) |

## 5. Priority picks

1. **In-repo reproducible governed-vs-bare policy-gate benchmark** — the ~0.24 µs/action and 15%→0% ASR numbers anchor the entire business case (cited in Ch 7, 12, 17, 25, 26, 27); they should be a runnable artifact under `examples/` or `tests/`, not only in the research folder.
2. **Planner/executor execution mode** — the one SLM-first architecture pattern from Ch 9 with zero repo counterpart; it maps the call multiplier onto the cost gradient and is a natural extension of the QSR router + STL decomposition already built.
3. **Ship the unit-economics/TCO model as an example script** — Ch 25 explicitly says "ship the model rather than just the numbers"; a `examples/unit_economics.py` fed by `CostProfile`/QSR-harvest data turns the "~84% cheaper" claim into something measurable on real CRP traffic and doubles as sales collateral.

---

## Cross-document notes

- Both docs lean hardest on the same three things: **positioning, the deterministic gate, and SLM-first routing** — all implemented (STL/tool_positioner, policy/TCF, QSR router+escalation).
- The sharpest *common* gap: **token-level streaming** — Doc 1 needs it for TTS; Doc 2's latency argument (TTFT, streaming) presumes it. Neither doc's flagship demo runs without it.
- Second common gap: **proof artifacts** — the voice demo (Doc 1 Ch 19/27) and the gate-overhead benchmark + unit-economics model (Doc 2 Ch 7/25) are the two pieces that convert these reports into verifiable, demoable CRPv6 claims.

<!-- ==================== The_Architecture_of_Agent_Security_source.md and The_Architecture_of_Evaluation_in_Agentic_AI_source.md ==================== -->
Both documents fully read (1,830 + 1,251 lines) and repo state verified. Here is the analysis.

---

# Document 1 — `The_Architecture_of_Agent_Security_source.md`

## 1. What it is
The seventh report in the AutoCyber agentic-architecture series (July 2026): a comprehensive threat-and-defense treatment for tool-using agents, anchored on the OWASP Agentic Top 10 (ASI01–ASI10) and real 2026 incidents (EchoLeak, GitHub MCP exploit, Replit DB meltdown, ClawHub poisoning). Its thesis: prompt injection is unsolved at the model layer, so security must be enforced *outside* the model by a deterministic policy mediating every action (CaMeL/FIDES/Progent/RTBAS/FORGE line) — "a prompt is a suggestion; a policy is an enforceable rule" — and Part IV argues CRP v6 *is* that convergent architecture, mapping every defense to a spec with copy-paste integration templates.

## 2. Concrete demands on CRPv6
From the Ch. 26 mapping table, Ch. 27–30 templates, and Appendix B (all claimed "ships"):

- **Deterministic policy gate / reference monitor** — complete mediation, fail-safe default-deny, context-aware, auditable; realized as **SPEC-006 (SPDL) + SPEC-033 (safety control plane)**, with a `control_plane.mediate(action, context)` returning allow/deny/require_approval (Ch. 16, 27).
- **Least agency via positioning** — minimal task-scoped tool/permission grants, just-in-time, revoked on completion; `Positioner.position(task, minimal_capabilities=True, pin_constraints=True)` (Ch. 15, 27).
- **Information-flow control** — provenance/sensitivity labels, Biba integrity (untrusted data can't decide consequential actions), taint blocking sensitive→unapproved-sink; **SPEC-027 + SPEC-006**, `ProvenanceTracker` (Ch. 18, 29).
- **Tamper-evident audit as security evidence** — every decision/provenance/tool call/approval recorded; HMAC hash-chain **plus** Ed25519-signed action receipts, external anchoring, replay for forensics; **SPEC-011/029** (Ch. 24, 28).
- **Sandboxing + execution rings + mandatory kill-switch** — ephemeral single-task sandboxes, network-egress control, config write-protection, resource limits, no untrusted `eval`, instant auditable termination; **SPEC-033/059** (Ch. 8, 19, 33).
- **Meaningful HITL** — impact-gated approval, context-rich requests (provenance, anomaly flag), fail-safe on timeout, quorum for irreversible, audited; **SPEC-033 + SPEC-026** (Ch. 11, 20).
- **Guardrails incl. behavioral invariant monitoring** — input/output filters (advisory) + deterministic "never do X" invariants that abort execution; **SPEC-006/049** (Ch. 21).
- **Agent identity & authorization** — unique verifiable agent identity, just-in-time task-scoped short-lived tokens, per-action authz, delegation chains with attenuation + provenance, instant revocation (Ch. 6, 22).
- **MCP/supply-chain security via Gateway** — vet + trust-score servers, require auth (never optional), pin tool descriptions (drift = poisoning), sign artifacts, block SSRF/egress to internal endpoints, single enforcement-and-audit point; **SPEC-016/033** (Ch. 7, 23, 30).
- **Multi-agent safety** — authenticated/integrity-protected inter-agent messaging, scope isolation (no authority inheritance), circuit breakers for cascades, fleet-wide behavioral trust scoring with decay, governed delegation with attenuated scope (**SPEC-012 + SPEC-058**) (Ch. 10, 25, 30).
- **Governed memory** — authority gate on writes (ingested content can never write constraint/authorization), constraint pinning against compaction eviction, conflict resolution by authority; **SPEC-045/006** (Ch. 9).
- **Runtime detection** — IoCs (leak strings, jailbreak markers, out-of-pattern tool calls), behavioral anomaly, trust decay → graduated constrain/gate/kill response; **SPEC-011/029/030** (Ch. 24, 33).
- **Red-team validation harness** — deterministic attack-success-rate (ASR) scoring per threat, driven to ~0, ongoing program with traceable-provenance data, failures → regression tests; tied to **SPEC-048** and EU AI Act Art. 55 (Ch. 32).
- **Compliance evidence emission** — controls → EU AI Act (Art. 9/12/14/15/55), NIST AI 600-1 (GOVERN/MAP/MEASURE/MANAGE), ISO 42001 crosswalk, evidence pack from audit chain; **SPEC-048** (Ch. 35).
- **Verification relay + quality tiers** — verify action preconditions/effects; tier autonomy by measured safety; **SPEC-049/026** (Ch. 26, Eval report).

## 3. Explicit TODOs / next steps stated in the document
- The **Agent security checklist** (Ch. 34): 15 checkbox items — least agency, policy gate, design pattern, IFC, sandboxing, HITL, guardrails, identity, supply chain, runtime detection, multi-agent, CRP integration, red-team, incident response, compliance. "Shortest secure path: CRP control plane + Gateway + HITL + red-team to ASR-zero."
- **Secure agent development lifecycle** (Ch. 41): threat-model → build with CRP control plane → red-team to ASR-zero in CI → deploy with monitoring + armed kill-switch → operate/evolve; maturity model Level 0→4 where Level 4 = "governed and provable (CRP)".
- **Appendix E project scaffold** — a `secure-agent/` tree (governance/, execution/, supply_chain/, identity/, detection/, multi_agent/, eval/, compliance/) presented as the build target.
- Appendix B asserts every defense "ships" in CRP specs — i.e., the document's working assumption is that all mapped specs are implemented; anything not actually shipping is an implicit TODO.
- Honest-limit flags: multi-agent defenses **[NASCENT]**, identity/delegation **[EVOLVING]**, MCP supply chain **[ACTIVELY EXPLOITED]** — ongoing-program items, not one-time builds.

## 4. Gap check (against repo state)

| Demand | Status | Evidence |
|---|---|---|
| SPDL policy engine (SPEC-006) | **IMPLEMENTED** | `crp/policy/` grammar/enforce/inheritance/profiles (`enforce_policy` → most-restrictive-wins decision) |
| Safety Control Plane (SPEC-033) + manifest + coverage | **IMPLEMENTED** | `crp/security/control_plane.py`, `safety_manifest.py`, `coverage.py` (registry, tune, register_rule) |
| Action-mediating gate (`mediate()` per action) | **PARTIAL** | No `mediate`/`check_action`/`ReferenceMonitor` in `crp/`; closest real path is `crp/agent_sdk/policy.py` → `PolicyContext` (allowlist/blocklist/`SafetyClass` gating in `crp/tools/capability_fabric.py:51-54`) + `halt_on_injection/pii` — tool-selection-time mediation, not a per-action scope/IFC reference monitor |
| Least agency / positioned tools | **PARTIAL** | `crp/stl/tool_positioner.py`, `crp/isa/position.py`, TCF allowlists exist; no `minimal_capabilities`/JIT grant-revoke lifecycle |
| IFC / provenance labels (Biba, taint) | **PARTIAL** | `crp/envelope/retrieval_integrity.py` (SPEC-027), `crp/ep/`, `crp/provenance/` exist; no label-propagation IFC policy ("untrusted can't decide consequential action") enforced at the gate |
| Audit chain as security evidence | **IMPLEMENTED (HMAC) / PARTIAL (receipts)** | `crp/security/audit_trail.py`, `crp/provenance/window_chain.py`, `crp/core/manifest_ledger.py`, `crp_shared/audit.py`; **no Ed25519** anywhere (`grep ed25519` → 0), no external anchoring |
| Sandboxing / execution rings | **MISSING (as a security layer)** | Only `crp/vr/exec_verifier.py` runs arithmetic claims in a locked-down subprocess (SPEC-049 verifier, 2s timeout) — not a general tool-execution sandbox |
| Kill-switch | **MISSING** | `grep kill_switch` → 0 hits in `crp/` |
| HITL checkpoints | **IMPLEMENTED** | `crp/security/checkpoint.py` — approve/reject/edit, timeout, reject actions, graceful fallback; `crp/comply/checkpoint_inbox.py` for async resolution. Quorum/multi-approver not evident |
| Injection detection (advisory) | **IMPLEMENTED** | `crp/security/injection.py` — 21 regex patterns + optional ML ensemble incl. trained `crp-safety-deberta-v1`; advisory-only by design, exactly the doc's "detection signal" role |
| Behavioral invariants | **PARTIAL** | SPDL policies + checkpoints approximate it; no dedicated invariant-monitor that aborts execution |
| Agent identity / JIT task-scoped tokens / delegation chains | **PARTIAL** | `crp/security/session_token.py` (HMAC session binding), `crp_shared/session_token.py`; no per-action authz, no attenuating delegation chain |
| MCP supply-chain gateway (vet/auth/pin/SSRF/trust-score) | **MISSING** | `crp/gateway/` (api, router, key_vault, capability_router, tool_adapter) has no vet/pin/ssrf/signature logic (`grep` → 0); `crp_mcp/` is CRP's own MCP server, not an MCP security gateway |
| Multi-agent safety (SPEC-012) | **PARTIAL** | `crp/agent/` (budget, chain, oversight, propagation) exists from v3; no scope isolation, no inter-agent message signing, no fleet trust |
| Governed delegation (SPEC-058) | **MISSING** | SPEC-058 appears only in docs/research MDs, zero code; not among implemented SPECs (049–057, 059) |
| Circuit breakers (cascade containment) | **PARTIAL** | `crp/core/circuit_breaker.py` is provider-call-level (CLOSED/OPEN/HALF-OPEN), not agent-cascade containment |
| Runtime detection + trust decay | **MISSING** | `grep trust_score/trust decay` → 0; observability events/metrics exist but no IoC monitor or graduated response |
| Governed memory (authority gate, constraint pinning) | **MISSING** | `grep authority gate/lattice, constraint pin` → 0; SPEC-045 is deferred frontier per AGENTS.md |
| Red-team / ASR harness | **MISSING** | `grep attack_success|red_team|AgentDojo` → 0 in `crp/`, `examples/`, `scripts/`; `tests/test_adversarial_provenance.py` is provenance-focused, not an ASR program |
| Compliance crosswalk (EU AI Act/ISO/NIST) | **IMPLEMENTED (framework) / PARTIAL (Art. 55)** | `crp/security/compliance.py` covers EU AI Act Art. 6/9–17 + ISO 42001; no adversarial-testing (Art. 55) evidence record because no red-team harness |
| Verification relay (SPEC-049) | **IMPLEMENTED** | `crp/vr/` — relay, z3_verifier, exec_verifier, extract, prm (PRM model training in progress per project state) |
| Quality tiers | **PARTIAL** | S/A/B/C/D tiers in `crp/core/dispatch_router.py` + QSR escalation (`crp/qsr/escalation.py`); not tied to measured ASR/reliability or autonomy gating |
| Intent compiler (SPEC-059) | **IMPLEMENTED** | `crp/agent_sdk/intent_compiler.py` |

## 5. Priority picks
1. **Kill-switch + runtime detection/trust-decay loop (Ch. 19/24/33)** — completely absent, yet it's the OWASP-mandated containment for rogue agents (ASI10) and code execution (ASI05); small module on top of existing audit/events, completes the "constrain → observe → recover" story the doc calls the 2026 runtime architecture.
2. **MCP supply-chain enforcement in the Gateway (Ch. 23/30)** — the doc calls MCP the #1 2026 attack surface and explicitly casts CRP Gateway as "the natural MCP security gateway"; vet/auth/description-pinning/SSRF-blocking is concrete, self-contained, and directly monetizable.
3. **Governed delegation (SPEC-058) (Ch. 6/22/25/30)** — the only v6 spec the document maps defenses to that has zero code; it closes confused-deputy-across-hops and is also the eval doc's multi-agent measurement target.

---

# Document 2 — `The_Architecture_of_Evaluation_in_Agentic_AI_source.md`

## 1. What it is
The fifth report in the series: the measurement discipline for "did the agent do the task correctly and safely?" It decomposes correctness into four axes (outcome, process, safety, reliability), establishes a grader hierarchy (deterministic state-check > programmatic rubric > calibrated LLM-judge), covers Goodhart/reward-hacking, red-teaming with deterministic ASR, statistical rigor (pass^k, bootstrap CIs, McNemar), CI/online evaluation — and in Part VI casts CRP's verification relay (SPEC-049) and quality tiers (SPEC-026) as the layer that turns measurement into runtime governance and auditable evidence.

## 2. Concrete demands on CRPv6
From Part VI (Ch. 16–17), Ch. 37, and Appendix F:

- **Verification relay (SPEC-049)** — an independent, deterministic verifier gates each agent result against a *checkable success criterion* before acceptance: outcome state-check, trajectory/process check, in-scope safety check, faithful-narration check, grounded/anti-fabrication check; unverified ⇒ flag/reject, recorded in audit (Ch. 16).
- **Quality tiers (SPEC-026)** — measured reliability → *enforced autonomy*: tier assigned from ASR (any success ⇒ human review), pass^k (<0.9 ⇒ supervised), outcome + verified rate (⇒ autonomous); autonomy capped at the measured tier (Ch. 16, 25).
- **Deterministic-grader principle everywhere** — push grading to the highest tier: state-check > rubric > calibrated LLM-judge; LLM-judge numbers only with human-calibration agreement (Ch. 4–5, 18).
- **Anti-gaming specs** — success criteria that name forbidden shortcuts (placeholder args, out-of-scope calls, fabricated findings, disabled checks); check spirit not letter (Ch. 8).
- **Safety red-teaming** — indirect (AgentDojo-style) + direct (AgentHarm-style) injection, scored *deterministically on the action*, ASR tracked to ~0 as an ongoing program with traceable-provenance data; doubles as EU AI Act Art. 55 record (Ch. 9, 28).
- **Statistical rigor** — pass^k (not pass@k), bootstrap CIs on every rate, McNemar paired tests for regressions, adequate sample sizes (Ch. 10–11).
- **Calibration & abstention** — ECE measurement, coverage vs accuracy-on-attempted, reward honest abstention over confident error; agent self-knowledge feeds the relay/tiers (Ch. 29).
- **CI gate + online eval** — merge gate with outcome floor / reliability floor / ASR ceiling / no-regression; cheap per-turn production labels feeding failures back into the eval set (Ch. 13–14).
- **Process/step verification (PRM)** — grade intermediate steps; hybrid outcome+process supervision (Ch. 6).
- **Faithful-narration check (SPEC-056 TEL)** — narration must match the actual trajectory (Ch. 16, App. F).
- **Compliance evidence pack** — version + test date + outcome CI + pass^k + ASR + tier + verification rate, recorded tamper-evident in the audit chain (SPEC-011/029); evidence supports, not certifies, compliance (Ch. 28).
- **Governed-vs-bare paired A/B** — the headline product claim: same agent, same tasks, governance as the only variable, McNemar on outcome, ASR bare-vs-governed, pass^k comparison, honest latency overhead (Ch. 37).
- **Capability evals** — tool-use (selection/args/order/error-handling), RAG triad (precision/recall/faithfulness), memory five-failure-modes incl. *poisoning* row only governed memory passes, multi-agent per-agent/hand-off/cascade blast-radius tests, efficiency frontier (correct-per-dollar) (Ch. 19–23).
- Positioning vs eval frameworks: CRP sits *above* LangSmith/Braintrust/etc. — runtime verification, tiered autonomy, audit evidence are the gap they leave (Ch. 17, 33).

## 3. Explicit TODOs / next steps stated in the document
- **Readiness checklist** (Ch. 18): four axes measured; graders pushed to highest tier; judge numbers ship with calibration; spec names forbidden shortcuts; red-team ASR → 0; pass^k + CIs + paired tests; contamination/drift guards; CI gate + online monitor; (CRP) runtime verification + tier-gated autonomy + audit.
- **"Shortest path" starter** (Ch. 18/36): 10 important tasks, deterministic grader each, 5 runs for pass^k + bootstrap CI, 5 red-team variants for ASR, wired into CI — "a day or two."
- **Eval-driven development** (Ch. 13): build the deterministic eval and CI gate *before* features.
- **Eval maturity model** (Ch. 38): Level 1 → Level 4 (continuous + governed), where Level 4 = SPEC-049 runtime verification + SPEC-026 tier-gating + audit — explicitly CRP's target.
- **Every capability claim needs a paired eval** (Ch. 37): "whenever the marketing says CRP improves X, there should be a paired eval that measures the improvement in X, with its CI and its honest cost."
- Appendix E `agent-eval/` scaffold (tasks/, graders/, stats/, safety/, online/, crp/, ci_gate.py) as the build target.

## 4. Gap check (against repo state)

| Demand | Status | Evidence |
|---|---|---|
| Verification relay (SPEC-049) | **IMPLEMENTED (claims-level) / PARTIAL (task-level)** | `crp/vr/relay.py` orchestrates symbolic verifiers (z3, sandboxed exec, extraction) + PRM with critique/repair; verifies *claims*, not yet the doc's full "task success criterion + world-state + in-scope + faithful" gate |
| PRM step verifier | **IMPLEMENTED (module) / in progress (model)** | `crp/vr/prm.py` (dirty in git, being wired); `crp-prm-deberta-v1` training on GPU per project state |
| Quality tiers S–D | **IMPLEMENTED** | `_classify_quality_tier` in `crp/core/dispatch_router.py`; QSR escalation ladder keyed on tier (`crp/qsr/escalation.py`) |
| Autonomy tiering by measured reliability (T0–T3) | **MISSING** | No ASR/pass^k-driven autonomy gate; tiers describe output quality, not earned autonomy |
| pass^k / bootstrap CI / McNemar | **MISSING** | `grep pass^k|pass_hat|mcnemar|bootstrap` → 0 in `crp/`, `examples/`, `scripts/` |
| Red-team ASR harness | **MISSING** | No AgentDojo-style suite, no ASR metric anywhere |
| Calibration (ECE) | **IMPLEMENTED** | `crp/ep/calibration.py` — per-(model, task-kind) reliability curves + ECE (SPEC-055 §7.3.2); also `crp/provenance/calibration.py` |
| Abstention / clarification | **PARTIAL** | `crp/clr/` (clarification loop) + `crp/security/clarify.py` + `should_clarify` in agent SDK; no coverage-vs-accuracy-on-attempted selective metrics |
| Deterministic-first grader hierarchy | **PARTIAL** | VR uses deterministic symbolic verifiers before PRM; SQB judge has rubric criteria (`sqb_benchmark.py` `judge_criteria`) but no position-debias/human-calibration reporting |
| Faithful narration (SPEC-056) | **IMPLEMENTED** | `crp/tel/faithful.py` (+ emitter/sse/report, AG-UI adapter) |
| SQB benchmark (SPEC-026 gate) | **IMPLEMENTED** | `examples/crp_demos/sqb_benchmark.py` (5 criteria incl. Factual F1 + LLM-judge usefulness), plus `sqb_positioned.py`, `sqb_kimi_judge.py` |
| Compliance evidence pack (Art. 55 adversarial record) | **PARTIAL** | `crp/security/compliance.py` (EU AI Act/ISO 42001) + audit chain exist; no red-team results to record, no eval-evidence pack |
| Governed-vs-bare paired A/B | **PARTIAL** | `examples/crp_demos/positioned_benchmark.py`, `comparison_backend.py`, `sqb_positioned.py` compare positioned vs baseline; not McNemar-paired, no ASR arm, no latency-overhead reporting |
| Online per-turn labeling → eval feedback | **PARTIAL** | `crp/qsr/harvest.py` harvests production routing examples; observability events exist; no failure-label → eval-set loop |
| Anti-gaming spec assertions | **PARTIAL** | VR grounding/fabrication checks + TEL faithfulness approximate "spirit checks"; no placeholder-arg/shortcut assertions in benchmarks |
| Memory five-failure-mode eval (incl. poisoning) | **MISSING** | No memory-eval harness (CKF/state infrastructure exists) |
| Multi-agent cascade/blast-radius test | **MISSING** | No multi-agent eval (and SPEC-058 delegation itself is missing) |
| Efficiency frontier (correct-per-dollar) | **PARTIAL** | `crp/resources/cost_model.py` tracks cost; benchmarks don't report frontier metrics |

## 5. Priority picks
1. **Stats toolkit: pass^k + bootstrap CI + McNemar (Ch. 10–11, 37)** — a small `crp/eval` (or `examples/crp_demos/stats.py`) module that instantly upgrades every existing benchmark into the "defensible number" format, and is the required machinery for the governed-vs-bare headline A/B that is the product's core sales claim.
2. **Red-team ASR harness wired to CI (Ch. 9, 13, 28)** — AgentDojo-style deterministic action-checks against the policy gate; produces the "ASR 0% gated vs 12% ungated" proof, the EU AI Act Art. 55 record, and regression tests — the single highest-leverage missing piece (it is also the security doc's Ch. 32 demand).
3. **Measured-reliability autonomy tiers (SPEC-026 as the doc defines it, Ch. 16)** — connect pass^k/ASR/verification-rate → tier → enforced autonomy in `crp.Agent`/QSR; this is what turns "evaluation as measurement" into "evaluation as governance," the doc's definition of CRP's unique gap.

---

## Cross-cutting note
The two documents converge on the same #1 gap: **a deterministic red-team/ASR program** (Security Ch. 32; Eval Ch. 9/28/37) — it validates every security control, generates Art. 55 compliance evidence, and produces the governed-vs-bare marketing headline. Second shared gap: **SPEC-058 governed delegation** (Security Ch. 6/25/30; Eval Ch. 22) — referenced by both, implemented by neither. Also note both documents' Appendix B/F claim every mapped spec "ships" — the gap table above is the correction: policy/audit/HITL/VR/TEL/STL claims hold, but kill-switch, sandboxing, egress control, trust-decay detection, MCP supply-chain checks, governed memory (SPEC-045, deferred), autonomy-by-measurement, and all pass^k/McNemar/ASR statistics do not.

<!-- ==================== The_Architecture_of_Grounding_and_World_Models_source.md and The_Architecture_of_Memory_in_Agentic_AI_source.md ==================== -->
Analysis complete — both documents fully read and repo state verified. Here is the structured report.

---

# Document 1: `The_Architecture_of_Grounding_and_World_Models_source.md`

## 1. What it is

The sixth and deliberately most speculative report in the agentic-architecture series (July 2026). It separates what genuinely ships in world models (Dreamer/JEPA latent RL, Genie/Cosmos generative simulation, driving rehearsal) from what is fragile research (LLM-as-world-model planning — fidelity collapses beyond ~2–3 steps, structural hallucination, silent failure) and what is contested (whether LLMs "have" world models at all). Its engineering thesis: prediction is safe only when **grounded** (retrieval + code schemas), **bounded** (short horizon + re-observe), and **verified** (against reality before costly actions) — and CRP's contribution is *governed prediction* (SPEC-051, predictive positioning), flagged throughout as **research-stage, roadmap, not shipped**.

## 2. Concrete demands on CRPv6

From Ch 9–11, 15, 27, 31 and Appendix F ("CRP v6 Spec → World-Model-Mechanism Mapping"):

- **SPEC-051 predictive positioning** — position the agent with predictions that are: grounded in governed memory + retrieved evidence; bounded to ~2 steps; tagged `prediction` (lowest authority); verified before costly action (Ch 10, App F). Doc status: *research-stage, build post-launch*.
- **Grounded state for prediction** — governed memory (SPEC-045) supplying `current_verified_state` (App F: "ships").
- **Predictions bounded to permitted actions** — SPDL policy (SPEC-006) + safety control plane (SPEC-033); never predict a forbidden action (Ch 10).
- **Verify prediction before costly/irreversible action** — the "anti-silent-failure gate" routed through the verification relay (SPEC-049) (Ch 9, 11, 27 step 6).
- **Predictions transparent as predictions** — narration must distinguish "I predict X" from "I know X" (SPEC-056, TEL) (Ch 11, 20).
- **Prediction accuracy measured → autonomy tier-gated** — rollout-drift measurement; tier autonomy by measured accuracy per domain (SPEC-026 quality tiers) (Ch 11, 27 step 7–8).
- **Everything audited** — every prediction, its grounding, verification, and the action written to the tamper-evident audit chain (SPEC-011/029) (Ch 11, 14, 27 step 8).
- **Explicit over implicit world models** — code-defined schemas / programmatic (WorldCoder-style) induced models, deterministic and inspectable (Ch 9, 18); small specialized domain models over giant general ones (SLM-first, Ch 38).
- **Uncertainty routing** — low-confidence predictions trigger real-evidence gathering, not action (Ch 28; ties to calibration/EP).
- **Narrow prototype** — "destructive-action foresight": 1-step, schema'd, grounded prediction of whether a probe is destructive, routed through the verification gate (Ch 31 — "the honest, shippable slice").
- **Cost engineering** — predict only at costly edges, pruned candidates, cached (Ch 29).

## 3. Explicit TODOs / next steps in the document

- Readiness checklist (Ch 15): reactive-by-default; grounded; schema-constrained; horizon bounded; predictions tagged low-authority; verify-before-costly; accuracy measured + tier-gated; transparent + audited.
- "What not to build yet" (Ch 15): no long-horizon rollouts; no acting on unverified predictions; no claiming "has a world model"; **do not prioritize predictive positioning over the shipping mechanisms — build after launch**.
- Build the narrow governed slice now (Ch 31 pentest prototype, App E scaffold: `world_model/`, `planning/lookahead.py`, `planning/drift_monitor.py`, `governance/`, `eval/prediction_accuracy.py`).
- Watch maturity signals (Ch 36) before expanding SPEC-051: reliable horizon extends to 5–10 steps, structural hallucination drops, calibration arrives, isolated world-model benchmarks mature, domain-specific WMs succeed.
- Mature uses to adopt cautiously: imagination-for-training anchored with ~40% real data (Ch 16), world-model off-policy evaluation as a *screen* (Ch 17), synthetic-data generation validated for plausibility (Ch 35).

## 4. Gap check (repo state on `crpv6-agent-sdk`)

| Demand | Status | Evidence |
|---|---|---|
| SPEC-051 predictive positioning | **IMPLEMENTED** (ahead of the doc) | `crp/pp/` exists: `world_model.py` (symbolic rule-based `WorldModel.predict` returning confidence/support/source), `induction.py` (`induce_rules` from action logs = programmatic/explicit model), `simulate.py` (`guarded_dispatch` — simulation-before-action gating for HIGH-risk ops, blocks + returns checkpoint), `causal_ckf.py` (causal edges). This is exactly the doc's recommended "programmatic, schema-constrained, bounded" form, not LLM free-imagination. |
| Anti-silent-failure gate (verify before costly) | **IMPLEMENTED** | `crp/pp/simulate.py:30` `guarded_dispatch` blocks predicted-policy-violating HIGH-risk actions and returns a checkpoint; `crp/vr/` (SPEC-049) has `ExecVerifier`, `extract_claims/verify_text`, PRM, Z3 verifier; `crp/security/checkpoint.py` for HITL. |
| Policy bounds on predicted actions (SPEC-006/033) | **IMPLEMENTED** | `crp/policy/` (SPDL v3), `crp/security/control_plane.py` + `safety_manifest.py`. |
| Predictions transparent as predictions (SPEC-056) | **PARTIAL** | `crp/tel/` ships AG-UI governance events (`crp.safety_scan`, `crp.provenance`…); no evidence of a dedicated "prediction" event type distinguishing hypothesis from fact. |
| Accuracy measured → autonomy tier-gated (SPEC-026) | **PARTIAL** | `crp/qsr/` (SPEC-050) is a quality-tier-supervised router with escalation ladders + `harvest`; `crp/ep/` (SPEC-055) has `CalibrationProfile` + `epistemic_adjust`. But no rollout-drift measurement of the world model itself and no per-domain prediction-accuracy→autonomy-tier wiring. |
| Grounded state via governed memory (SPEC-045) | **MISSING** | SPEC-045 remains frontier/deferred (AGENTS.md); no session/persistent-learning module. Predictions ground in CKF + induced rules from real action logs instead — a reasonable substitute, but the doc's named dependency isn't there. |
| Audit of predictions (SPEC-011/029) | **IMPLEMENTED (plumbing)** | `crp/security/audit_trail.py`, provenance window chain, `crp/btf/` Tier-E temporal log exist; whether `guarded_dispatch` outcomes are chain-recorded needs wiring verification. |
| Uncertainty → gather-real-evidence routing | **PARTIAL** | `crp/ep/calibration.py` + `semantic_entropy.py` provide calibration/uncertainty signals; no explicit low-confidence→probe-reality loop in `crp/pp`. |
| Rollout-drift measurement / prediction-accuracy eval | **MISSING** | No `drift_monitor` / `prediction_accuracy` equivalent; no isolated world-model benchmark in `tests/` or `scripts/`. |
| Narrow destructive-action foresight prototype (Ch 31) | **MISSING as demo** | The mechanism (`guarded_dispatch`) exists, but no pentest-domain `NetworkWorldModel`-style example/prototype in `examples/`. |

## 5. Priority picks from this document

1. **Prediction-accuracy evaluation + drift monitor for `crp/pp`** (`eval/prediction_accuracy.py` + tests) — the doc's Ch 11/15 make "measure accuracy, tier autonomy by it" a hard safety requirement, and it's the one governance piece with no code at all; it also feeds SPEC-026-style evidence.
2. **A narrow destructive-action foresight example** (`examples/` pentest prototype wired to `guarded_dispatch` + checkpoint + audit) — the doc's "honest, shippable slice"; turns existing `crp/pp` machinery into a demonstrable, auditable story with near-zero new core code.
3. **Prediction-labelled TEL event + audit wiring for `guarded_dispatch`** — closes the "transparent as predictions + audited" demand with small surface area.

---

# Document 2: `The_Architecture_of_Memory_in_Agentic_AI_source.md`

## 1. What it is

The fourth report in the series: the definitive memory pillar. It organizes agent memory into working memory (context engineering + the dangerous act of compaction), long-term memory (episodic/semantic/procedural; extraction, retrieval, and the under-designed invalidation problem), and continual learning (why naive fine-tuning is a catastrophic-forgetting trap; test-time learning and "sleep" consolidation instead). Its CRP thesis: **memory is where agentic AI most urgently needs governance** — provenance, write-authority, conflict resolution, retention/erasure, and a tamper-evident audit chain over whatever store (Mem0/Graphiti/owned) holds the bytes.

## 2. Concrete demands on CRPv6

From Ch 3, 13, 17 and Appendix F ("CRP v6 Spec → Memory-Mechanism Mapping"):

- **Constraint pinning** — policy-authored safety constraints re-asserted into context *every turn*, never compactable/evictable; defeats governance decay + Compaction-Eviction Attack (SPEC-006 SPDL, SPEC-033) (Ch 3).
- **Provenance on every memory** — source, authority, reason, timestamp on every fact/lesson (SPEC-027, SPEC-045) (Ch 13 mech 1).
- **Write-authority gate** — authority lattice `INGESTED < AGENT_INFERENCE < AGENT_VERIFIED < HUMAN < POLICY`; per-source, per-memory-type write permissions; ingested content can never write authorizations/constraints (SPEC-006/033); defeats memory poisoning / Zombie Agent (Ch 12–13 mech 2).
- **Conflict resolution by authority** — higher authority wins, recorded; not last-write-wins (SPEC-012, SPEC-044) (Ch 13 mech 3).
- **Retention + right-to-be-forgotten** — provable, *cascading* deletion of a memory and everything derived from it, as an auditable event (SPEC-045, SPEC-030, GDPR Art. 17) (Ch 13 mech 4, Ch 26).
- **Tamper-evident audit chain on every memory op** — write/update/invalidate/retrieve/consolidate all HMAC-chained (SPEC-011, SPEC-029) (Ch 13 mech 5).
- **Governed shared/multi-agent memory** — authority-scoped writes, provenance quarantine of low-trust agents' writes, shared governed store + per-agent scratchpads (SPEC-012, SPEC-058) (Ch 23).
- **Temporal/bi-temporal memory** — validity windows (valid-from/valid-to) plus transaction-time ("what did the agent believe when"); invalidation by construction; point-in-time queries (Ch 5.3, 20).
- **Four memory types distinguished** — working / episodic / semantic / procedural, each with the right store and lifecycle (Ch 4); **extraction with ADD/UPDATE/DELETE/NOOP** on a cheap batched model (Ch 5.1); **deliberate forgetting** (invalidate/decay/consolidate) (Ch 7); **skill library** as governed procedural memory (Ch 22).
- **Guarded test-time learning** — provenance + vetting of agent-authored lessons before they become durable; sleep-time consolidation pass (Ch 9–10; SPEC-045).
- **CSO as continuity object** — what persists across sessions (SPEC-030) (App F).
- **Memory observability** — recall tracing (what entered context and why), write tracing (incl. *denied* writes), memory diffing (Ch 27).
- **Memory evaluation** — four-failure-mode eval (retrieval, invalidation/stale-fact, temporal, long-range) **plus a poisoning row no public benchmark scores**, run in CI (Ch 19).
- **Compliance evidence emission** — memory history → CRP Comply artifacts (SPEC-011/029, SPEC-048) (Ch 26).

## 3. Explicit TODOs / next steps in the document

- Production readiness checklist (Ch 17): bounded context; pinned constraints; recall-first compaction + write-before-compact; four memory types; ADD/UPDATE/DELETE extraction; designed invalidation; owned raw event log; deliberate forgetting; guarded test-time learning; sleep consolidation; and the full governance block (provenance, write authority, authority-based conflicts, provable erasure, audit chain).
- "Shortest path to a demo" (Ch 17): `TemporalMemoryStore` + `GovernedMemory` + two tools (`recall`, `remember`) routed through the authority gate — then demo a poisoning attempt being **denied and recorded**.
- App E scaffold: `store/` (temporal store, bitemporal graph), `memory/` (working, extraction, retrieval, forgetting, skills), `governance/` (governed memory, authority lattice, compliance, observability), `learning/` (test-time, sleep), `eval/eval_memory.py`.
- Ch 19: build the four-failure-mode + poisoning eval and run it in CI.
- Open research it defers (Ch 28): parametric continual learning, hippocampal consolidation, self-evolving stability — explicitly *not* build targets.

## 4. Gap check (repo state)

| Demand | Status | Evidence |
|---|---|---|
| Constraint pinning / anti-eviction | **IMPLEMENTED** | `crp/state/critical_state.py:17` — Tier-0 `CriticalState` (goal/phase/blockers/constraints) "ALWAYS included in every envelope"; `crp/state/cso.py` `relay_cso()` enforces the preservation guarantee and re-injects dropped facts (line 276, 644). Compaction (`crp/state/compaction.py`) archives superseded facts rather than dropping constraints. |
| Provenance on every memory (SPEC-027/030) | **IMPLEMENTED** (in-session) | CSO `established_facts` carry `ProvenanceKind` (CKF/TOOL/CONVERSATION/DERIVED/USER); `crp/envelope/retrieval_integrity.py` (SPEC-027) with recency decay + contradiction detection. |
| Bi-temporal memory (valid + transaction time) | **IMPLEMENTED** | `crp/btf/temporal.py` (SPEC-057): `BiTemporalFact` with `valid_from/to` + `ingested_at/invalidated_at`, `true_in_world_at`, `believed_by_system_at` — exactly the doc's Ch 20 model. |
| Conflict resolution by authority | **PARTIAL** | `retrieval_integrity.resolve_fact_authority()` keeps "most recent + highest source trust" — a *retrieval-time heuristic*, not an authority lattice with recorded resolutions (SPEC-044 ADA is deferred). |
| Write-authority gate (INGESTED<AGENT<HUMAN<POLICY) | **MISSING/PARTIAL** | No `may_write` authority lattice anywhere in `crp/`. Nearest: `crp/security/quarantine.py` (1-window anti-poisoning, 0.7× confidence penalty on ingested facts) and injection scanning on ingest (`crp/core/extraction_facade.py:254-312`). Nothing stops an ingested "fact" from contradicting a human-authorized one at *write* time. |
| Retention + cascading right-to-be-forgotten | **IMPLEMENTED** | `crp/security/privacy.py`: `RetentionPolicy/RetentionManager` + `ErasureRequest/ErasureManager` (line 446+); GDPR erasure listed as v3 capability. Cascade-completeness via provenance tracing is plausible but unverified. |
| Audit chain on memory ops (SPEC-011/029) | **IMPLEMENTED** | `crp/security/audit_trail.py` (HMAC tamper-evident), `crp/provenance/window_chain.py`, compliance events on ingest/extraction. |
| Governed shared/multi-agent memory (SPEC-012/058) | **PARTIAL** | `crp/agent/` (budget, chain, oversight, propagation) + multi-agent safety spec exist from v3; SPEC-058 (governed delegation) is **not** among the implemented SPEC-049–057/059 set; no authority-scoped shared memory store. |
| Four memory types + ADD/UPDATE/DELETE/NOOP extraction | **PARTIAL** | `crp/state/horizons.py` (PERSISTENT/CONVERSATIONAL/EPHEMERAL tiers), warm/cold stores, `scratch_buffer.py` (SPEC-029 ephemeral tool context) — but these are *lifetime* tiers, not episodic/semantic/procedural cognitive types, and there is no LLM-driven 4-way memory-update op (the extraction pipeline extracts facts; supersession happens in compaction, not via explicit UPDATE/DELETE decisions). |
| Guarded test-time learning / skill library / sleep consolidation (SPEC-045) | **MISSING** | SPEC-045 is frontier/deferred; no scratchpad learner, no skill library, no sleep/vetting pass. |
| Memory observability (recall/write tracing, diffing) | **PARTIAL** | `crp/observability/` + audit trail + TEL events cover general tracing; no memory-specific recall-trace / denied-write-trace / memory-diff API. |
| Four-failure-mode + poisoning memory eval in CI | **MISSING** | No `eval_memory`-style harness in `tests/` or `scripts/`; poisoning-resistance tested only indirectly via quarantine/injection tests. |
| Memory-as-tool (`recall`/`remember` through authority gate) | **MISSING** | `crp/tools/` (SPEC-050 TCF) provides the descriptor/executor fabric to host such tools, but no governed recall/remember tools exist. |

## 5. Priority picks from this document

1. **Write-authority gate + authority lattice over memory writes** (`crp/security/` or `crp/state/`: `may_write(source, type, authority)` with deny-and-record) — the doc's single sharpest differentiator (Ch 13 mech 2, the Zombie-Agent defense); currently the biggest true gap, and it directly upgrades the existing quarantine heuristics into a governed control.
2. **The four-failure-mode + poisoning memory eval in CI** (`scripts/` or `tests/` harness: retrieval, invalidation, temporal, long-range, poisoning) — the doc's Ch 19 "prove it works" demand; cheap to build on `crp/btf` + CSO, and it's the evidence layer for every other memory claim.
3. **Governed `recall`/`remember` tools via TCF + denied-write observability** — the doc's "shortest path to a demo" (Ch 17); leverages the already-built `crp/tools` fabric and audit chain, and produces the poisoning-refusal demo that proves governed memory end-to-end.

---

## Cross-document note

The two documents reference overlapping spec infrastructure: SPEC-045 (governed/session-persistent memory) is a named dependency in *both* Appendix F mappings and is genuinely **missing** (deferred as frontier in AGENTS.md) — it is the highest-leverage shared gap. Conversely, the Grounding doc's headline claim ("SPEC-051 is research-stage, not shipped") is **outdated relative to the repo**: `crp/pp` already implements it in exactly the symbolic/bounded/governed form the doc recommends, so that document's Part IV should be read as a design rationale for code that now exists rather than as a future roadmap.

<!-- ==================== The_Architecture_of_Provenance_and_Audit_source.md and The_Compliance_Crosswalk_source.md ==================== -->
Analysis complete. Both documents were read in full (1,319 and 853 lines), and every demand was cross-checked against the repo with targeted greps.

---

# Document 1: `The_Architecture_of_Provenance_and_Audit_source.md`

## 1. What it is
The first "governance-evidence capstone" of the AutoCyber research series. It teaches how to build a tamper-evident, provenance-complete audit trail for agents: hash chaining, Merkle trees, external anchoring, WORM storage, Ed25519 signatures, content/events separation, crypto-shredding — assembled into a deployable `AuditTrail` class, then wired into CRP v6 as the implementation of SPEC-011 (audit chain), SPEC-029 (Tier-E action log), and SPEC-027 (provenance/retrieval integrity). The running example is a pentest agent whose every action must be provable to a client or court without trusting the operator.

## 2. Concrete demands on CRPv6
- **Provenance records on every data item/action/decision** with `source`, `authority` (INGESTED < AGENT < HUMAN < POLICY lattice), `reason`, `derived_from`, propagated via `combine()` (min-authority rule) (Ch 1–2; SPEC-027).
- **Action-and-decision granularity** — the audit unit is "agent did X on Y at T with result Z, decision D, provenance P", not conversation replay (§0.3, Ch 11; SPEC-029 Tier-E action log).
- **Hash-chained events log** — each entry embeds the previous entry's hash (Ch 3; SPEC-011).
- **Merkle tree over the chain** with O(log n) inclusion proofs and append-only consistency proofs (Ch 4).
- **External anchoring** of the Merkle root — RFC-3161 timestamping authority as default, CT-style log or blockchain as options (Ch 5).
- **WORM cold storage + hot/warm/cold tiering** for audit records (Ch 5).
- **Ed25519-signed entries** for non-repudiation; TEE attestation where configuration must be provable (Ch 6, 16).
- **Content/events separation** — tamper-evident events log holds hashes/metadata only; raw content in a separate AES-256-encrypted store, separately deletable (Ch 6).
- **Crypto-shredding** — per-subject keys in a KMS; GDPR erasure = key destruction, with the erasure itself an audited event (Ch 12).
- **Obligation-driven retention with audited expiry** (Ch 11).
- **One OpenTelemetry instrumentation feeding both observability backend and audit trail** (Ch 8).
- **Verification workflows**: integrity (re-walk chain), inclusion, consistency, attestation (Ch 13, App E).
- **Privacy-preserving audit**: selective disclosure / verifiable redacted excerpts (production-ready); ZK audit [EMERGING] (Ch 16).
- **Distributed multi-agent provenance**: per-agent chains, correlation IDs, cross-referenced hand-offs (Ch 17; SPEC-058).
- **Audit at scale**: batched Merkle-root anchoring, async non-blocking `record()`, BLAKE3 option, proof caching (Ch 18).
- **Chain-of-custody / forensic tooling**: evidence bundles, timeline reconstruction, root-cause via provenance, blast-radius, provable non-events (Ch 19, 22).
- **Continuous integrity monitoring** — periodic chain verification, anchor reconciliation, gap monitoring, signature sampling, alerting (Ch 23).
- **Key management**: signing keys in HSM/KMS, rotation preserving historical verifiability, separation of duties, protected anchor credentials (Ch 24).
- **SIEM export + self-contained auditor-handoff package** (events + inclusion proofs + public keys + verification instructions) (Ch 25).
- **Edge audit**: hardware-signed local chain, deferred opportunistic anchoring, sync cross-verification (Ch 26).
- **C2PA-style signed output manifests** (model + data lineage + policy + timestamp) (Ch 20).
- **`CRPAuditedControlPlane`** — every `SafetyControlPlane.mediate()` decision flows into the audit trail with provenance in one step (Ch 9).

## 3. Explicit TODOs stated in the document
- **Readiness checklist (Ch 14)** — 13 boxes: propagated provenance; action-granularity; hash chain; Merkle proofs; external anchoring; WORM+tiering; Ed25519/TEE; content/events separation; crypto-shredding; retention; OTel unification; CRP SPEC-011/029/027 integration; verification workflows.
- **Build-first sequence (Ch 27)** — 5 ordered steps: (1) provenance + append-only events, (2) hash chain + signatures, (3) Merkle + external anchoring, (4) WORM + crypto-shredding + retention, (5) CRP integration + OTel + monitoring + interoperability. "A security-and-compliance agent on client infrastructure needs Level 4."
- **Frontier to watch, not build yet (Ch 21)** — ZK audit, standardized agent-provenance formats, cross-org audit, legal admissibility.

## 4. Gap check vs repo state
| Demand | Status | Evidence |
|---|---|---|
| Hash-chained audit log (SPEC-011) | **IMPLEMENTED** | `crp/security/audit_trail.py` (HMAC-SHA256 chained entries, `verify_chain()`, `CHAIN_INTEGRITY_*` events); `crp/provenance/window_chain.py` |
| Action-granularity event types | **IMPLEMENTED** | `audit_trail.py` `ComplianceEventType` covers data/consent/oversight/LLM-decision/security events |
| Provenance with authority lattice + propagation (SPEC-027) | **PARTIAL** | `crp/envelope/retrieval_integrity.py` and the DPE (`crp/provenance/`) exist, but no unified `Provenance` record with INGESTED<AGENT<HUMAN<POLICY lattice and `combine()`/`trace_lineage()` propagation |
| Merkle tree + inclusion/consistency proofs | **MISSING** | zero `merkle` matches in `crp/` |
| External anchoring (RFC-3161/CT/blockchain) | **MISSING** | `anchor` matches are goal-compass/task anchors, unrelated |
| Ed25519 signatures / non-repudiation | **MISSING** | HMAC (symmetric) only; no asymmetric, third-party-verifiable signatures |
| Content/events separation | **PARTIAL** | AES-256-GCM at rest exists (`crp/security/encryption.py`); audit events hold metadata; but no explicit two-store pattern with `content_hash` refs and independent content deletion |
| Crypto-shredding | **MISSING** | `ErasureManager` (`privacy.py:459`) tracks erasure requests; no per-subject key destruction |
| Retention with audited expiry | **PARTIAL** | retention management + `RETENTION_EXPIRED/PURGED` events in `audit_trail.py`/`privacy.py`; obligation-window policy engine unclear |
| OpenTelemetry dual-consumer | **MISSING** | `crp/observability/metrics.py:10` explicitly states "no opentelemetry" |
| Verification workflows (inclusion/consistency/attestation) | **PARTIAL** | chain integrity verification exists; the other three missing |
| Multi-agent distributed audit (correlation IDs, cross-ref handoffs) | **PARTIAL** | delegation chains exist (`crp/agent/chain.py`); no cross-chain audit correlation |
| Audit at scale (batch/async anchoring, BLAKE3) | **MISSING** | recording is synchronous HMAC append |
| Forensics (timeline, blast-radius, provable non-events) | **MISSING** | no forensic/timeline/inclusion-proof matches |
| Continuous integrity monitoring | **MISSING** | no scheduler/anchor-reconciliation/alerting |
| KMS/HSM key management + rotation | **MISSING** | one stray "kms" mention in `manifest_ledger.py`; no key-manager |
| SIEM export + auditor handoff package | **MISSING** in SDK | no siem/syslog matches; `crp/comply/gateway_client.py:get_evidence_pack` is a plain aggregation without proofs |
| TEE attestation, ZK, edge audit, C2PA output manifests | **MISSING** | (doc itself marks ZK/edge as advanced) |
| `CRPAuditedControlPlane` wiring | **PARTIAL** | `crp/security/control_plane.py` exists and audit events cover oversight/RBAC, but no mediate-and-record-in-one-step wrapper with provenance |

## 5. Priority picks
1. **Merkle tree + inclusion/consistency proofs layered on the existing HMAC chain** — the single missing primitive that unlocks third-party verifiability, evidence-pack inclusion proofs, AIUC-1 E15, and the full EU Art 12 claim; small, stdlib-only, self-contained.
2. **Ed25519 entry signing + external anchoring hook** — converts "tamper-evident to ourselves" into "provable without trusting the operator" (non-repudiation, Ch 5–6), the core sales differentiator of Comply.
3. **Content/events separation hardening + crypto-shredding** — GDPR Art 17 over an immutable log is a required, concrete customer ask; `ErasureManager` is already half there.

---

# Document 2: `The_Compliance_Crosswalk_source.md`

## 1. What it is
The second capstone and "commercial heart of CRP Comply": a control-by-control mapping of what a CRP-governed agent emits to six frameworks — EU AI Act (Articles 8–17, 26, 27, 72, 73, Annex IV), NIST AI RMF, ISO/IEC 42001, SOC 2, GDPR, and the agent-native AIUC-1 (51 controls, Appendix E). Its central thesis: CRP *emits* compliance evidence continuously as a byproduct of runtime enforcement, so compliance becomes live infrastructure; it includes a `ComplianceEngine` design that maps emitted evidence to obligations and generates audit-ready evidence packs, with the honest scope note that CRP supports compliance but an assessor certifies.

## 2. Concrete demands on CRPv6
- **Runtime policy enforcement emitting allow/deny decision records** (SPEC-006/033) — EU Art 9/15, ISO A.8, SOC 2 CC7 (§0.2, Ch 5, 7).
- **Tamper-evident audit chain** (SPEC-011/029) — EU Art 12 "most directly satisfied"; GDPR Art 30; ISO A.7; SOC 2 CC7; AIUC-1 E15 (Ch 3, 5).
- **Provenance / data lineage on every input** (SPEC-027) — EU Art 10, GDPR 5/30, AIUC-1 A (Ch 5–7).
- **Recorded HITL approvals with context + kill-switch** — EU Art 14, GDPR Art 22, AIUC-1 E (Ch 3, 7; App B).
- **Red-team program producing attack-success-rate (ASR) records + governed-vs-bare benchmark** — EU Art 15/55, NIST MEASURE, AIUC-1 B1/C10–C12/D2/D4 (Ch 5, 19: "ASR 0% gated vs 12% ungated").
- **Verification relay (SPEC-049) + quality tiers (SPEC-026) + pass^k** — EU Art 15, AIUC-1 Reliability D1 (Ch 5, App B).
- **Post-market monitoring / runtime monitoring + online eval** (SPEC-030) — EU Art 72, AIUC-1 C8 (Ch 5).
- **Incident response + forensic reconstruction within Art 73 window** — EU Art 73, GDPR 33/34 (Ch 5).
- **Crypto-shred erasure + content/events separation + egress control** — GDPR Art 17, AIUC-1 D&P (Ch 5, App E).
- **Technical documentation generated from artifacts (Annex IV artifact→requirement map)** — EU Art 11 (Ch 4, 21).
- **Risk classification / threat model with continuous re-assessment** — EU Art 9, NIST MAP, ISO 6.1 (Ch 3, 12).
- **Unique agent identity + task-scoped authorization + delegation chains** — SOC 2 CC6, GDPR 32, AIUC-1 B7/E4 (Ch 5).
- **Multi-agent scope isolation (SPEC-012)** — EU Art 15, AIUC-1 A5/B (Ch 5).
- **Faithful narration / transparency emission (SPEC-056)** — EU Art 13, GDPR 13/14, AIUC-1 E16/E17 (App B/E).
- **MCP/supply-chain vetting via Gateway (SPEC-016)** — AIUC-1 E6/E9 (App E).
- **SPEC-048 no-code governance loop** turning runtime records into compliance deliverables (Ch 7).
- **`ComplianceEngine` class with `CROSSWALK` data (obligation → evidence query), `coverage(framework, scope)` (evidenced vs GAP), and `evidence_pack(framework, scope)` including `chain_intact` and per-record inclusion proofs** (Ch 8, App C template).
- **Gap-analysis tool** producing prioritized fix lists from coverage (Ch 21, `gap_analysis.py`).
- **Multi-framework coverage beyond EU/ISO** — NIST, SOC 2, GDPR, AIUC-1 collectors and packs (Ch 8's CROSSWALK dict).
- **Worked EU AI Act evidence pack artifact** (Ch 19) — quantified governance value, blocked-attack counts, independent verifiability.

## 3. Explicit TODOs stated in the document
- **90-day plan (Ch 9)** for the Aug 2, 2026 EU AI Act high-risk deadline: Days 1–30 inventory & classify + initial crosswalk coverage; Days 31–60 close high-severity gaps (wrap agents in the CRP control plane; enable audit chain, HITL, provenance, red-team); Days 61–90 generate evidence packs, produce Annex IV docs from artifacts, engage assessors, stand up continuous monitoring + incident-reporting workflow.
- **Per-obligation implementation checklist (Ch 21)** — Art 12 audit chain (highest priority), Art 9 threat model, Art 14 HITL, Art 15 red-team + policy gate, Art 10 provenance + crypto-shred, Art 11/Annex IV doc map, Art 72 monitoring, Art 73 forensics, plus "wrap in the CRP control plane" as the highest-leverage single step.
- **Compliance program loop (Ch 9)** — inventory → gap-analyze → close → generate → assess → monitor, run continuously; drift management via re-generate-on-change triggers (Ch 17).
- **Honest-scope requirement** — every pack carries "supports conformity; a qualified assessor certifies; not legal advice."

## 4. Gap check vs repo state
| Demand | Status | Evidence |
|---|---|---|
| Runtime policy gate (SPEC-006/033) with decision records | **IMPLEMENTED** | `crp/security/control_plane.py`, `crp/policy/`; audit events for denials/oversight |
| Tamper-evident audit chain (Art 12) | **PARTIAL** | HMAC chain exists (`crp/security/audit_trail.py`); lacks Merkle anchoring/inclusion proofs the packs require |
| HITL approvals recorded + oversight | **IMPLEMENTED** | `crp/security/checkpoint.py`, `crp/agent/oversight.py` (HTTP 451 + oversight tokens), `OVERSIGHT_*` events |
| Kill-switch | **PARTIAL** | HTTP 451 halt (`crp/headers/halt.py`) + oversight halt events; no explicit kill-switch/emergency-stop API (zero `kill_switch` matches) |
| Provenance (SPEC-027) | **PARTIAL** | `crp/envelope/retrieval_integrity.py` exists; full lineage records incomplete |
| Verification relay (SPEC-049) + quality tiers | **IMPLEMENTED** | `crp/vr/` (incl. `prm.py`), `QualityReport` tiers |
| Faithful narration / transparency (SPEC-056) | **IMPLEMENTED** | `crp/tel/` (Transparency Emission Layer, recent commit) |
| Post-market monitoring (SPEC-030) | **PARTIAL** | `crp/state/cso.py` + continuation quality monitor; no "online eval" record stream |
| Red-team ASR program + governed-vs-bare benchmark | **MISSING** | `tests/test_adversarial_provenance.py` exists but no ASR-emitting benchmark harness feeding the audit chain |
| Crypto-shred / content separation / egress | **PARTIAL** | erasure tracking + AES-256-GCM exist; crypto-shred and egress-control evidence missing |
| Annex IV / Art 11 docs from artifacts | **PARTIAL** | `crp/security/compliance.py` does risk classification (Art 6), transparency declarations (Art 13), technical documentation (Art 11), status reporting, impact assessment |
| Multi-framework `ComplianceEngine` + `CROSSWALK` + `coverage()` + `evidence_pack()` with inclusion proofs | **MISSING** | no crosswalk/ComplianceEngine matches; `crp/comply/gateway_client.py:get_evidence_pack` is an in-memory event aggregation (article counts only, no gap status, no proofs, EU-only) |
| Gap-analysis tool | **MISSING** | — |
| AIUC-1 control-level mapping | **DOCUMENTED, not coded** | `site-docs/aiuc-1.md` exists (site content); no AIUC-1 evidence collectors in code |
| NIST/SOC 2/GDPR/AIUC-1 evidence packs | **MISSING** | `compliance.py` covers EU AI Act + ISO 42001 only |
| SPEC-048 no-code governance | **IMPLEMENTED** | `crp/comply/no_code.py` |
| Agent identity + task-scoped authz + delegation | **IMPLEMENTED** | `crp/agent/` (budget, chain, oversight), `crp/security/binding.py`, `rbac.py` |
| Multi-agent isolation (SPEC-012) | **IMPLEMENTED** | `crp/agent/propagation.py`, multi-agent safety in security layer |
| MCP/supplier vetting via Gateway | **PARTIAL** | `crp/gateway/` + `capability_router.py` exist; vetting workflow not evident |

## 5. Priority picks
1. **`ComplianceEngine` (CROSSWALK-as-data + `coverage()` + `evidence_pack()`) in the SDK/Comply** — the actual productized crosswalk and the concrete deliverable Comply sells; upgrades the current stub `get_evidence_pack` into per-framework gap/evidence views (depends on pick 1 from Doc 1 for inclusion proofs).
2. **Red-team ASR benchmark harness (governed vs bare) that writes results into the audit chain** — the quantified "ASR 0% gated vs 12% ungated" evidence is the load-bearing claim for EU Art 15/55 and AIUC-1 B1/D4 and the centerpiece of the worked pack (Ch 19).
3. **Explicit kill-switch + incident-record API emitting Art 73-ready forensic records** — small surface, closes the EU Art 14/73 and AIUC-1 E1–E3 rows that currently have only the 451-halt partial.
