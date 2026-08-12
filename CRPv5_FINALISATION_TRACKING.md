# CRP v5 — Finalisation Tracking Report

> **Status:** ACTIVE — approved plan, gated on WASA AI critical gap audit
> **Owner:** Agent B (Safety Surface, SDK, Config, Products) + Core Protocol
> **Base version:** `crprotocol` 4.3.2 (PyPI live) → target **5.0.0**
> **Doctrine (non-negotiable):** *"The assigned model does the work. Make the local
> model capable — do not give up on it."* Positioning over injection. No hybrid
> auto-routing. No `CRP-*` header reaches the provider (Axiom 4).
> **Companion docs:** `WASA_AI_CRITICAL_GAP_AUDIT.md`, `CRP_SLM_PROTOCOL_PROPOSAL.md`,
> `SPECS_5_06_2026_CRP_v4/specs/CRP-SPEC-049-slm-agent-execution.md`,
> `SPECS_5_06_2026_CRP_v4/specs/CRP-SPEC-050-tool-capability-fabric.md`

---

## 0. The one-sentence goal

Make any **< 15 B model that runs on a laptop** behave as a capable agent by
**positioning** it on one isolated, specialised operation at a time — with full
awareness of where it is in the plan, the right 1–3 tools for that operation, and a
durable state object that carries findings forward — so that hundreds of tool calls
and frames compose into one coherent, complete response **without flooding context or
exceeding a bounded resource budget**.

---

## 1. Approved decisions (locked)

| # | Decision | Status |
|---|----------|--------|
| D1 | **Positioning is the only mode.** Zero tool-schema injection. The model never sees the catalogue. | ✅ Locked |
| D2 | **Canonical 10-operation taxonomy:** `RETRIEVE, ANALYSE, COMPARE, SYNTHESISE, GENERATE, VERIFY, TRANSFORM, PLAN, CLARIFY, REVISE` (single casing across enum + schema + headers). | ✅ Locked |
| D3 | **CLARIFY is first-class.** When the model lacks information/authority, it raises a CLARIFY operation that prompts the user for input or an action (wired to a checkpoint). | ✅ Locked |
| D4 | **No hybrid auto-routing.** Frontier models are explicit providers, never silent fallbacks. | ✅ Locked |
| D5 | **Findings are decoupled from context.** Observations → typed CSO facts + raw → Scratch Buffer pointers. The window never accumulates tool history. | ✅ Locked |
| D6 | **Bounded working set guarantee.** Per-operation context is bounded by the capability profile, independent of session length (O(N), not O(N²)). | ✅ Locked |

---

## 2. Build sequence & status

Legend: ☐ not started · ◐ in progress · ☑ done

| Step | Deliverable | Files | Status |
|------|-------------|-------|--------|
| **0** | **Taxonomy reconciliation** — unify enum ↔ schema ↔ headers on the canonical 10 ops | `crp/stl/classifier.py`, `schemas/capability-descriptor.json`, `crp/headers/names.py`, SPEC-049/050 | ☑ **done** — canonical 10 ops; `operation_from_token` normaliser (EVALUATE→VERIFY); spec ABNF aligned at step 8 |
| **1** | **Tool Capability Fabric** — descriptor + registry/retrieval + executor + `ToolResultExtractor` | `crp/tools/{descriptor,capability_fabric,executor,__init__}.py` | ☑ **done** — 29 TCF + 20 STL + 6 smoke tests green; ruff clean |
| **2** | **Operation State Machine** + CSO extensions (`tool_observations`, `preventive_halt_history`) | `crp/stl/operation_state.py`, `crp/state/cso.py` | ☑ **done** — 10 state-machine tests; CSO observations stored as typed facts |
| **3** | **Tool Positioner** — Operation Frame → Tool Positioning Frame (1–3 tools by profile) | `crp/stl/tool_positioner.py` | ☑ **done** — frame composer + robust tool-call parser (15 tests) |
| **4** | **Make STL live** — real positioned loop (`run_positioned`); preventive-safety gate; INTEGRATE→CSO; structured-decoding contract at the `model_call` boundary | `crp/stl/positioned.py` | ☑ **done** — live loop + 8B validation; full 13-stage DPE verify is a follow-up |
| **5** | **Observation Store + Resource Governor + Visibility event stream** | `crp/state/`, `crp/observability/`, `crp/resources/` | ☑ **done** — `ResourceGovernor` (slow-and-steady, device-tier capping); observations→CSO; OSM event stream |
| **6** | **CLARIFY + Checkpoint consolidation** — make checkpoints faultless, test them, wire CLARIFY | `crp/security/clarify.py`, `crp/security/checkpoint.py` | ☑ **done** — sync `clarify` bridge (Invariant 10 fallback); CLARIFY op + oversight approval wired; async `Checkpoint` retained for webhooks |
| **7** | **Expose** — `client.dispatch_positioned()` / execution-mode `positioned-tool-loop`; preventive safety gate; SDK + Gateway wiring | `crp/sdk/client.py`, `crp/core/orchestrator.py`, `crp-gateway/` | ☑ **done** — `dispatch_positioned()` wired; `CRP-Agent-*` headers; validated live on 8B (191-token bounded window). Gateway-product wiring tracked separately in the `crp-gateway` repo |
| **8** | **Version bump 5.0.0**, promote SPEC-049/050 from draft, conformance, CHANGELOG | `crp/_version.py`, specs, `CHANGELOG.md` | ☑ **done** — 5.0.0 shipped to PyPI; SPEC-049/050 → Stable; CHANGELOG written; tagged `v5.0.0` |

---

## 3. New v5 components (beyond the original TCF plan)

### 3.1 Observation Store (formalises the wasa-ai archetype)
- Each tool result → typed `EstablishedFact(provenance=TOOL)` in the CSO + raw output → `ScratchBuffer` pointer (pinned until the report operation runs).
- **Fixes wasa-ai's M1 bug by design:** the report operation reads the full typed observation set from the CSO; raw evidence is never destroyed before reporting.

### 3.2 Resource Governor (CRP's protocol-layer slice of resource management)
- Detects device tier → adapts **capability profile** (frame size: small-local 1–2, capable-local 3–4, frontier 5–7), **tool concurrency**, **continuation / loop-guard limits**, **depth**, and **prompt-cache pinning**.
- **Proactive** (acts at ~70–80% of budget), not OOM-reactive.
- **Prime directive — "slow and steady over fast and failing."** On a constrained device the Governor *throttles and serialises* (smaller frames, single-flight tool execution, lower concurrency, capped continuation) to keep utilisation under the target — deliberately accepting slower runs rather than risking OOM/overheat. Speed is the trade; stability is the guarantee.
- Explicitly **does NOT** do quantization / KV compression / offloading — that is the inference engine's job (llama.cpp / vLLM / llama-swap). Component **offload is application-specific**: for WASA AI the candidates are **WASA's own heavy services** (its RAG service, knowledge/embedding components) hosted on Railway — **not** the CRP Gateway — while the positioned **LLM stays local** (see §5 and the WASA audit).

### 3.3 Visibility event stream ("not a blind machine")
- Every Operation-State-Machine transition emits a streamable, HMAC-chained event: `intent_classified → operation_positioned(type, tools) → tool_selected → tool_executed → observation_stored(fact) → operation_verified → integrated(completion%, remaining) → … → complete`.
- One mechanism delivers both **live UI** (user sees plan, current op, each tool call, each finding, % complete) and **audit**.

### 3.4 Operation-as-role (the six SLM roles)
- The report's six roles (router, guardrail, tool-caller, edge-executor, doc-processor, workflow-step) are realised as **operation/role frames** — one local model wearing different hats per operation — with the *option* to register distinct fine-tuned local SLMs as TCF capability providers. Always local; never silent frontier escalation.

### 3.5 CLARIFY + Checkpoint consolidation
- **Known issue:** checkpoints exist (`crp/security/checkpoint.py`) but are **fragmented and untested**. v5 consolidates them into one tested mechanism and wires the CLARIFY operation to raise a checkpoint that prompts the user for information or an action (and gates `destructive`/`mutating` tools — essential for a pen-test agent).

---

## 4. The bounded-resource guarantee (the "40%" question)

CRP makes **two distinct guarantees**, and it is important not to conflate them:

1. **Deterministic CRP guarantee (always holds):** the per-operation working set
   (prompt + KV cache) is **bounded by the capability profile's frame budget** and is
   **independent of how many tool calls have already happened**. A session of 3 calls
   and a session of 300 calls use the **same-size window**. This is the O(N) (not O(N²))
   property — and it is exactly what prevents the context/memory growth that caused
   WASA's OOM and overheating during long runs.

2. **System baseline guarantee (conditional):** total local CPU/RAM staying under a
   target (e.g. 40%) also depends on **co-resident components** CRP does not control —
   model weights, embedding models, and the Kali QEMU VM. To hold the baseline on
   constrained hardware the **Resource Governor** keeps the positioned LLM **local** but
   runs it **slow and steady** (throttled, serialised) to stay under budget, and the
   application offloads its **own** heavy services — for WASA AI, its RAG service and
   knowledge/embedding components — to Railway (**not** the CRP Gateway).

> **Net:** CRP v5 guarantees the **growth** is bounded (no OOM from long runs, steady
> CPU from small prompts), with an accepted modest speed trade-off — **slow and steady
> over fast and failing**. The **baseline** under 40% on a laptop is held by the Governor
> throttling the local model plus offloading the application's own heavy services (e.g.
> WASA's RAG/knowledge) to Railway. See `WASA_AI_CRITICAL_GAP_AUDIT.md` §4 for the math.

---

## 5. Cross-repo impact & sequencing

| Repo | Role in v5 | Action |
|------|-----------|--------|
| **context-relay-protocol** | The protocol + library (this repo) | Build steps 0–8 here first; validate on local 8B |
| **crp-gateway** (`C:\Users\User\Desktop\crp-gateway`) | CRP's own managed runtime (an independent product, **not** a WASA dependency) | Wire Operation State Machine + TCF into the hosted Gateway |
| **crp-comply** | First CRP-native consumer (revenue) | Retire bespoke ReAct loop → `dispatch_positioned()` |
| **crp-scan** | Static scanner / GitHub Action | Later; consumes capability descriptors |
| **wasa_ai-master** | Proof case + design pressure-test | Becomes CRP-native; offloads **its own** RAG/knowledge services to Railway |

---

## 6. Gates (must pass, in order)

1. **G0 — WASA critical gap audit** (this turn) → defines what CRP must solve vs. infra/consolidation. → see companion doc.
2. **G1 — Taxonomy reconciliation** lands cleanly; existing tests stay green.
3. **G2 — TCF + Operation State Machine** unit-tested; descriptor validates against `schemas/capability-descriptor.json`.
4. **G3 — Live positioned loop** runs end-to-end on **meta-llama-3.1-8b-instruct** (LM Studio `192.168.0.6:1234`) for a multi-operation task, bounded window confirmed.
5. **G4 — SQB re-run** (kimi-k2.6 judge): positioned ≥ baseline on factual F1 and usefulness.
6. **G5 — Scale test:** ≥ 100 tool calls in one session with **flat** working-set size (resource telemetry recorded).
7. **G6 — Demo:** a visual demo that conveys the positioned tool loop, the operation state machine, CSO growth, and flat resource usage.

---

## 7. Testing & demo plan (kimi + local SLM + visuals)

**Test bench (confirmed reachable):** LM Studio `http://192.168.0.6:1234/v1`
- `meta-llama-3.1-8b-instruct` — capable-local target
- `qwen2.5-7b-instruct`, `qwen3-4b`, `mergebench-gemma-2-2b-it` — profile spread
- `gemma-3-270m-it-qat` — small-local extreme
- `text-embedding-nomic-embed-text-v1.5` — TCF semantic retrieval
- **Judge:** kimi-k2.6 (`api.moonshot.ai/v1`, `temperature=0.6`, `thinking:{type:disabled}`) — key read from local file, **never printed**.

**Tests to build:**
- `tests/test_tcf.py` — descriptor validation, retrieval, policy pre-filter, top-K by profile.
- `tests/test_operation_state.py` — state machine transitions + CSO observation storage.
- `tests/test_positioned_loop.py` — end-to-end positioned loop (mock provider).
- `examples/crp_demos/` live runs against the local 8B; SQB via `sqb_benchmark.py`.
- **Scale harness:** synthetic 100-tool session asserting flat working-set + bounded RSS.

**Demos to finalise/build (some exist but are broken):**
- `examples/crp_demos/v4/server.py` (+ `static/`) — assess & repair.
- **Flagship:** a "positioned tool loop" visual demo — live operation state machine, the 1–3-tool frames, CSO findings accumulating, and a resource graph staying flat across 100s of calls.

---

## 8. Risks & open items

- **R1** — Checkpoints fragmented/untested (D3 dependency). Must be consolidated before CLARIFY ships.
- **R2** — Two operation taxonomies in the tree today; step 0 must not break the live classifier/frame_builder.
- **R3** — `stl_execute` currently simulates the model call; making it live touches the provider manager + DPE + CSO — highest-integration-risk step.
- **R4** — Resource Governor must never block a call; it adapts, it does not refuse.
- **R5** — Railway offload introduces a network dependency; the Governor must degrade gracefully to local-only (accepting the speed downside) when offline/air-gapped.

---

## 9. Realised state audit (2026-07-01) — the honest answer

> **What is really the state of CRPv5?** The positioned agentic loop is **real and
> working for single- and multi-turn requests**, proven end-to-end on Kimi (frontier)
> and the local 8B. It is **not yet** wired to the v4 deep-context/continuation
> subsystems. Below is the audited truth.

### Working (verified end-to-end, local 8B + Kimi + logic)
| Use case | Status | Evidence |
|----------|--------|----------|
| Tool-call agentic execution | ✅ working | `run_positioned` + TCF + executor; e2e local 3/3, Kimi 3/3 |
| Context positioning (in-turn) | ✅ working | CSO `to_prompt_context` carries facts across operations; e2e PASS |
| **Multi-turn state relay** | ✅ **NEW, working** | `prior_cso` param seeds established_facts/observations/decisions; window advances; e2e Kimi PASS + regression test `test_multi_turn_state_relay` |
| CLARIFY / human-in-the-loop | ✅ working | `resolve_clarification`; e2e PASS |
| Preventive oversight halt | ✅ working | `_preventive_check` + oversight set; e2e PASS |
| Resource-governed profile | ✅ working | `ResourceGovernor.plan`; e2e PASS |
| Bounded working set | ✅ working | 68 tok across 5 relayed turns; ≤206 tok on real tasks |

### Honest gaps (NOT yet wired into the positioned loop)
| Gap | Impact | Where it lives |
|-----|--------|----------------|
| Output continuation (one operation exceeding the token wall) | Long single-operation generations truncate; mitigated because work is split into operations and turns | `crp/continuation/` exists, not called from `positioned.py` |
| CDR/CDGR auto-retrieval | `context_facts` is passed in manually, not retrieved by novelty/graph walk | `crp/envelope/cdr.py`, `crp/ckf/cdgr.py` exist, not imported |
| Multi-horizon context / scratch buffer | Frame builder uses a flat fact list, no PERSISTENT/CONVERSATIONAL/EPHEMERAL blend | `crp/state/horizons.py`, `scratch_buffer.py` exist, not imported |
| DPE verification in the loop | No credibility/entailment gate on each operation's output | `crp/provenance/` exists, not imported |

### Verdict
The loop is a **real agentic executor with proven multi-turn continuity and bounded
windows**. The remaining gaps are *depth* enhancements (auto-retrieval, output
continuation, DPE gating) — valuable next, but the core "positioning + multi-turn +
context carry-forward" is done and tested. Test harnesses: `examples/crp_demos/e2e_v5_test.py`
(every use case, local+Kimi+logic) and `examples/crp_demos/positioned_benchmark.py`.

---

*Tracking report generated 2026-06-30; realised-state audit added 2026-07-01.*

