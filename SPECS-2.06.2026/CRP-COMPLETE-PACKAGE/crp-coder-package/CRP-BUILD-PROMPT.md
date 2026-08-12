# CRP v4 — Complete Build Prompt for Engineering

**For:** Lead Developer / Engineering Team
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Date:** 2026-06-01
**Scope:** Build CRP from the verified v3 foundation to the full v4 architecture

---

## PART 0 — WHAT YOU ARE BUILDING (READ FIRST)

CRP is **not** a RAG wrapper, a prompt manager, or an agent framework.
It is a **governance-and-positioning protocol that sits between any
application and any LLM**, doing two things no other layer does together:

1. **GOVERNANCE** — every model interaction is verified, attributed,
   risk-scored, audited (tamper-evident), and compliance-classified —
   in < 50ms, on any model, emitted as HTTP headers any proxy can read.

2. **POSITIONING** — instead of injecting a pile of context and making
   the model figure out what to do, CRP decides what the task is, how
   deep it must go, and positions the model on one focused cognitive
   operation at a time. The protocol drives information; the model
   drives response.

The verified v3 implementation already proves governance works
(HTTP 451 halts, HMAC chains, DPE, CKF recall — all tested against a
real local LLM). v4 adds the context-quality layer (CDR), the
graph/multi-horizon/state architecture, and the positioning layer (STL).

**The guiding principle through every build decision:**
> CRP Core runs in milliseconds, on any model, imposing nothing.
> Everything expensive is opt-in, off by default, and async.

---

## PART 1 — BUILD ORDER (TIERED)

### TIER 1 — CORE PROTOCOL (the millisecond governance + quality layer)
**This is the product. Build, test, benchmark this before anything else.**

| Order | Spec | Build |
|-------|------|-------|
| 1 | SPEC-009 | CKF: HNSW index, fact schema, ingestion, **graph edges** (needed for 025), Coverage Set + Turn Log + Scratch Buffer on the session object |
| 2 | SPEC-003 | Envelope packing: Phase 1 retrieval, Phase 2 ranking, Phase 3 primacy-recency sandwich |
| 3 | SPEC-024 | **CDR** — novelty-weighted retrieval. THE core quality fix. Implement the full formula (relevance × novelty × recency × ngram-guard) exactly as in §7 |
| 4 | SPEC-027 | Retrieval integrity: recency term (folds into CDR), contradiction resolution, parallel coverage isolation for fan-out |
| 5 | SPEC-025 | **CDGR** — graph retrieval. Seed with CDR, walk CKF graph, bridge-value scoring for connector facts |
| 6 | SPEC-005 | DPE: 13-stage pipeline. Stages 1–5, 7–8 critical path. Extend Stage 2 attribution with TOOL_GROUNDED / CONVERSATION_GROUNDED (from 029) |
| 7 | SPEC-030 | **CSO** — Cognitive State Object. The relay primitive. Replaces text-summary continuation. Decisions-with-rationale, dependency graph, preservation verification |
| 8 | SPEC-004 | Continuation/DAG: now relays the CSO (not text). Loop exit rules (§ from 024). Revision protocol (from 030) |
| 9 | SPEC-006 | Safety Policy parser + enforcer. halt-on CRITICAL → HTTP 451 |
| 10 | SPEC-007 | Session token: HKDF, signed, carries CSO ref + Coverage Set + embedding-model id |
| 11 | SPEC-002 | Header emission: all headers, emitted from DPE report + CSO + STL state |
| 12 | SPEC-011 | Audit trail: HMAC chain, 30+ events, CSO revision events, NDJSON export |
| 13 | SPEC-017 | Zero-CKF mode + progressive activation + onboarding hints |

### TIER 2 — THE POSITIONING LAYER (what makes CRP revolutionary)
**Build after Tier 1 is benchmarked and proven.**

| Order | Spec | Build |
|-------|------|-------|
| 14 | SPEC-028 | Multi-Horizon Context Model: three tiers (Persistent/Conversational/Ephemeral), Turn Log, intent classification, reference resolution, per-turn tier blend |
| 15 | SPEC-029 | Ephemeral/Tool context: Scratch Buffer, structure-aware summarisation, freshness gating, bimodal persistence, tool-output provenance (TOOL_GROUNDED) |
| 16 | SPEC-031 | **STL** — Semantic Task Layer. The conductor. Task taxonomy (8 operations), depth model (D1–D5, negotiated), Operation Frames, goal-compass (anchored positioning). This drives all of Tier 1 |

### TIER 3 — PRODUCTS (revenue)
| Order | Spec | Build |
|-------|------|-------|
| 17 | SPEC-016 | Gateway service: OpenAI-compatible endpoints, provider routing, key vault, tier quotas |
| 18 | SPEC-013 | CRP Scan GitHub Action: detection patterns, SARIF, Comply funnel |
| 19 | SPEC-014 + SPEC-026 | Conformance suite + **Semantic Quality Benchmark** (Factual F1, multi-hop recall, LLM-as-judge). The binding quality criterion |

### TIER 4 — OPT-IN AMPLIFICATION (build only when a customer needs it)
**Governed by SPEC-023. OFF by default. Async only. For weak local models.**

| Spec | Build |
|------|-------|
| SPEC-023 | The boundary governor. Read FIRST — it defines what must never be default |
| SPEC-018 | AIR — multi-window feedback (error quarantine useful; n-gram superseded by CDR) |
| SPEC-019 | CQR — failure detection (C1–C6) stays in DPE/Core; remediation is opt-in |
| SPEC-020 | CLD — cognitive load distribution; working memory = the CSO (SPEC-030 §7) |
| SPEC-021 | ROS — reliability orchestration (consensus); async only |
| SPEC-022 | PEF — parallel execution fabric; batching makes 020/021 viable |

---

## PART 2 — THE NON-NEGOTIABLE INVARIANTS

Enforce these as hard constraints. Violating any one breaks CRP's identity.

1. **CORE LATENCY:** Core path (govern one inference) adds < 50ms.
   CDR < 1ms. CDGR < 2ms. CSO ops < tens of ms. NEVER add an inference
   pass to the Core path. Tier 4 amplification is the ONLY place extra
   passes are allowed, and only with explicit CRP-Amplification-Mode.

2. **MODEL-AGNOSTIC:** Identical governance contract on GPT-5, Claude,
   a 70B, or a 1B local model. No model required or privileged.

3. **AXIOM 4 — STRIP BEFORE FORWARDING:** No CRP-* header ever reaches
   the LLM provider. Strip all CRP headers from the outbound request.

4. **POSITIONING NOT INJECTION (Tier 2+):** When STL is active, the
   model receives an Operation Frame (one task + minimal frame +
   goal-compass), never the assembled context pile. Frame is built UP
   from operation requirements, not trimmed DOWN from everything.

5. **EMBEDDING CONSISTENCY:** Coverage Set, Turn Log, and CKF facts MUST
   use the same embedding model. Record the model id in the session
   token. Reject mismatched updates. (SPEC-027 §2.5)

6. **STATE RELAY VERIFIED:** The CSO preservation guarantee — every
   still-valid prior fact survives the relay or is repaired. No silent
   state loss. (SPEC-030 §5)

7. **HMAC CHAIN UNBROKEN:** Every window/operation extends the chain.
   Tampering surfaces as CRP-Provenance-Chain-Integrity: BROKEN.

8. **AMPLIFICATION IS OPT-IN:** Tier 4 is OFF by default, async-only,
   declares cost up front, warns/defaults-to-Core on strong models.

---

## PART 3 — THE CORE ALGORITHMS (implement exactly)

### CDR ranking (SPEC-024 §7.1) — the quality core
```python
CDR_MIN_RELEVANCE = 0.55
MIN_NOVELTY_FLOOR = 0.20
COVERAGE_PENALTY_CAP = 0.80

def cdr_rank(facts, query_emb, session):
    out = []
    for f in facts:
        rel = cosine(f.embedding, query_emb)
        if rel < CDR_MIN_RELEVANCE: continue
        if session.coverage_set:
            wsum = sum(e.depth_weight * cosine(f.embedding, e.embedding)
                       for e in session.coverage_set)
            tot  = sum(e.depth_weight for e in session.coverage_set)
            cov  = wsum / tot
        else: cov = 0.0
        residual = (max(cosine(f.embedding, r.embedding) for r in session.residual_set)
                    if session.residual_set else 0.0)
        eff_rel  = max(rel, residual)
        novelty  = max(1.0 - min(cov, COVERAGE_PENALTY_CAP), MIN_NOVELTY_FLOOR)
        recency  = recency_factor(f)          # SPEC-027 §3
        ngram    = 1.0 - min(0.80, ngram_overlap(f, session.ngram_blacklist) * 0.15)
        out.append((f, f.importance_weight * eff_rel * novelty * recency * ngram))
    out.sort(key=lambda x: x[1], reverse=True)
    return out
```

### STL execution cycle (SPEC-031 §7) — the positioning core
```python
def stl_execute(user_request, session):
    operations = classify_operations(user_request)        # §3, the 8-op taxonomy
    depth      = propose_depth(user_request, operations)  # §4, D1–D5
    plan       = decompose_into_plan(operations, depth)
    for op in plan:
        frame = build_operation_frame(                    # §5 — MINIMAL, built up
            op,
            frame_content = retrieve_for_operation(op, session),  # CDR/CDGR, this op only
            goal_compass  = make_goal_compass(user_request, op),  # §6, ~80 tokens
        )
        result = position_model(frame)                    # ONE focused call
        verify_against_success_test(result, op, dpe)      # SPEC-005
        integrate_into_cso(result, session.cso)           # SPEC-030
        depth = maybe_renegotiate_depth(depth, result)    # §4.4, bounded
    return assemble_final_response(session.cso)
```

### CSO relay (SPEC-030) — verified state transfer
```python
def relay_cso(prior_cso, window_output, dpe):
    new_cso = extract_cso(window_output)          # facts + decisions(WITH rationale)
    new_cso = integrate(prior_cso, new_cso)       # merge, build dependency graph
    preservation = verify_preservation(prior_cso, new_cso, dpe)  # §5
    if preservation < 1.0:
        new_cso = repair(new_cso, prior_cso)      # re-inject dropped valid facts
    new_cso.hmac = hmac_chain(prior_cso.hmac, new_cso)   # SPEC-011
    return new_cso
```

---

## PART 4 — VALIDATION (the binding criterion)

Build SPEC-026 (Semantic Quality Benchmark) and use it as the gate.
A feature ships ONLY if it improves BOTH:
- **Factual F1** (recall × precision of facts vs ground truth)
- **LLM-as-judge usefulness score**

Reducing repetition / increasing word count is NOT sufficient.

### The decisive benchmarks:
1. **CDR test:** Window 5 repetition < 1.0% AND Factual F1 ≥ Window 1.
   Proves quality holds at quantity.
2. **CDGR test:** multi_hop_recall jumps vs CDR-only. Proves graph
   retrieval surfaces connector facts flat retrieval misses.
3. **STL test:** positioned execution beats injected execution on
   Factual F1 + coherence, AND CRP-STL-Frame-Vs-Inject < 0.30
   (positioning uses <30% of the tokens injection would).
4. **Amplification test (Tier 4, when built):** 7B + full CRP on a
   4090 vs 70B naive on A100 — quality parity at lower compute/cost.

---

## PART 5 — WHAT TO IGNORE / DEPRIORITISE

- **SPEC-018 n-gram blacklist as primary mechanism** — superseded by CDR.
  Keep only as the thin secondary guard in SPEC-024 §5.
- **SPEC-022 PEF** — don't build until SPEC-020/021 are needed by a real
  customer. It only exists to make those fast.
- **Backward-looking continuation summaries** — replaced entirely by the
  CSO (SPEC-030) and forward-looking goal_state.

---

## PART 6 — REPO STRUCTURE

```
context-relay-protocol/
├── crp/
│   ├── core/
│   │   ├── ckf/              # SPEC-009 (graph-enabled)
│   │   ├── envelope/         # SPEC-003
│   │   ├── retrieval/        # SPEC-024 (CDR), 025 (CDGR), 027 (integrity)
│   │   ├── dpe/              # SPEC-005
│   │   ├── state/            # SPEC-030 (CSO), 007 (session token)
│   │   ├── continuation/     # SPEC-004 (CSO-based)
│   │   ├── policy/           # SPEC-006
│   │   ├── audit/            # SPEC-011
│   │   └── headers/          # SPEC-002
│   ├── context/
│   │   ├── multihorizon/     # SPEC-028 (tiers, intent, references)
│   │   └── ephemeral/        # SPEC-029 (scratch buffer, tools)
│   ├── stl/                  # SPEC-031 (positioning, taxonomy, depth) ← Tier 2
│   ├── amplify/              # SPEC-018-022 ← Tier 4, opt-in, isolated
│   │   └── (governed by SPEC-023 boundary checks)
│   ├── gateway/              # SPEC-016
│   └── conformance/          # SPEC-014 + SPEC-026 (SQB)
└── tests/
    ├── conformance/          # 25+ vectors
    └── sqb/                  # semantic quality benchmark
```

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*

---
---

# BUILD PROMPT UPDATE v2 — Specs 033–037

**Appended:** 2026-06-01. Five new specs add the safety control surface,
the storage engine, the Scan remediation engine, and the unified config.
This section tells the coder what changed and what to build.

## NEW SPECS AND WHERE THEY SLOT

| Spec | What it is | Tier | Slots into |
|------|-----------|------|-----------|
| SPEC-033 | Safety Control Plane + inline HITL **Checkpoint** primitive | Tier 1 (safety) + Tier 3 (Comply UI) | core safety + CRP Comply |
| SPEC-034 | Safety coverage map + **checkpoint resolution lifecycle** + addable rules | Tier 1 | completes 033 |
| SPEC-035 | **Context Lifecycle & Access Tiering** — the multi-primitive storage engine | Tier 1 (core perf) | replaces "implementation detail" storage in 009/028/029 |
| SPEC-036 | **CRP Scan Remediation Engine** — detection → fix | Tier 3 (products) | completes SPEC-013 |
| SPEC-037 | **Unified Config** — one `crp.config.yaml` governs everything | cross-cutting | wraps all config surfaces |

## TIER 1 ADDITIONS (build with the core)

### Storage engine (SPEC-035) — build this INTO the State Layer
The State Layer (Gateway blueprint §3) is now FIVE primitives, not one store:
1. **CKF graph** (SPEC-009/025) — semantic + multi-hop. Already planned.
2. **Rolling Context Log** (NEW) — append-only ring buffer, ephemeral
   disk-file + pointer index. Serves "last N turns / recent" in microseconds.
   This is the Turn Log (SPEC-028) backing store. Memory-mapped file or
   in-memory ring; spill to disk for durability.
3. **Hot Cache** (NEW) — in-memory LRU keyed by (query bucket + CKF ETag).
   Serves repeat queries in microseconds. Invalidate on CKF state change.
4. **Inverted Index** (NEW) — term/key → fact. Serves exact-match and named
   lookups in microseconds. Built incrementally with the CKF.
5. **Pointer-Based Ephemeral Store** (NEW) — Scratch Buffer (SPEC-029)
   backed by disk blobs addressed by scratch_id; summary in memory, blob
   on demand.

**Build the Access Router (SPEC-035 §3):** a fast dispatcher that picks
the primitive per access by KNOWN intent (from STL operation type / SPEC-028
intent) — NOT by guessing. Check hot cache first, then route by access type.
Compose multiple primitives in parallel for blended access.

**Why:** millisecond retrieval requires the right primitive per access.
Do NOT force everything through the vector index. The router + five
primitives are the performance architecture. Emit `CRP-Context-Retrieval-Ms`.

**Lifecycle (SPEC-035 §4):** implement the promotion rule — ephemeral data
(rolling log, scratch) that proves durable (pinned / referenced ≥2× / named)
is promoted into the CKF. Most ephemeral data is never promoted; it rolls
off or evicts. Each primitive has defined cleanup.

### Checkpoint primitive (SPEC-033 + SPEC-034) — build the full lifecycle
`crp.checkpoint()` is the inline human-in-the-loop primitive. Build:
- Three declaration forms: call, decorator, `checkpoint_when(condition)`.
- The **resolution state machine** (SPEC-034 §2): CREATED→PENDING→
  {APPROVED|REJECTED|EDITED|TIMEOUT}→RESOLVED.
- **APPROVE** → resume with the value. **EDIT** → re-verify the edited value
  through the DPE, then resume. **REJECT** → run the chosen `on_reject`
  behaviour (raise|fallback|retry|abort|escalate); on `retry`, feed the
  rejection reason into AIR (SPEC-018) as a constraint. **TIMEOUT** → apply
  `on_timeout` policy (default reject/fail-safe).
- End-user messaging (`user_message_pending`, fallback messages) — the end
  user NEVER sees a raw error.
- **Async checkpoints** — park the operation's CSO/session state (SPEC-030)
  so it resumes correctly hours later on any instance.
- Every resolution is a `CHECKPOINT_RESOLVED` audit event (who/when/what/why)
  — this is EU AI Act Art. 14 human-oversight evidence.

### Safety Control Plane (SPEC-033) — build the unified safety surface
- `client.safety` object: `show()`, `set()`, `profile()`, `explain()`,
  `rule()`, `checkpoint_when()`, `coverage()`, `manifest()`, `audit()`.
- The **Safety Registry**: one catalogue of every safety setting with
  default, range, effect, and the regulation it maps to.
- **Custom rules** (`@client.safety.rule`): developer checks that run as
  first-class DPE stages. Sandbox them and time-bound them (a custom rule
  must not hang the pipeline). A rule may RETURN a checkpoint.
- The **Safety Manifest** (SPEC-033 §5): one declarative object that IS the
  `safety:` section of the unified config (SPEC-037).

### Addable safety rules (SPEC-034 §11) — ship as built-in toggles
Add these as built-in DPE checks, each toggleable in the config:
jailbreak detection, toxicity/harmful-content, secret/credential leakage
(block by default), copyright/verbatim reproduction, excessive-agency/tool
gating, goal-drift (compare agent actions to CSO goal_state). These cover
the remaining DETECTABLE safety gaps. Do NOT claim to cover the
model-internal concerns (alignment, bias, sycophancy — SPEC-034 §12);
checkpoints are the answer for those.

## TIER 3 ADDITIONS (products)

### CRP Scan Remediation Engine (SPEC-036) — completes SPEC-013
The Scan funnel now has a payoff. Build:
- **Three remediation classes:** code fix (PR), config fix (Comply), guided
  fix (human decision → resolves to code/config).
- **Remediation template library** keyed by detection rule (CRP001–005):
  deterministic AST-level diffs for common patterns (OpenAI/Anthropic/
  LangChain base_url swaps, wrapper insertions). Reviewable, reproducible.
- **Delivery:** free tier shows remediation PREVIEWS in PR annotations;
  paid tier opens auto-generated **remediation PRs** (never direct commits;
  always reviewable). Config fixes post to the **CRP Comply** Safety Control
  Plane as pre-filled, one-click-apply remediations.
- **Scan→Comply handoff API:** findings + recommended settings flow from
  Scan into Comply's control plane. This is HOW Comply is "utilised."
- **Post-merge verification:** next scan confirms findings cleared,
  conformance score rises.
- Non-standard integrations → optional CRP-powered code-fix generator
  (CRP governing its own remediation), always marked needs-review.

### CRP Comply = the AI Safety Control Centre (decision, SPEC-034 §14)
The Safety Control Plane is NOT a separate product. It is the management +
evidence surface of **CRP Comply**. Build into Comply:
- The safety registry UI (see/tune every setting).
- The **checkpoint human inbox** (reviewers see decision + reasoning +
  evidence + risk, then approve/reject/edit).
- Custom-rule management.
- The Scan→Comply remediation inbox (SPEC-036 §4).
- The regulation coverage view (SPEC-033 §6.2).

## CROSS-CUTTING (SPEC-037) — the unified config

Build `crp.config.yaml` / `CRPConfig` as the single source of truth:
- Sections: model, safety, context, knowledge, amplification, compliance,
  deployment. EVERY field optional with a sane default — the whole file is
  optional and CRP runs safely with no config.
- **Layered override** (SPEC-037 §4): per-call > session > config file >
  profile > system defaults.
- **One source of truth across SDK, Gateway, Comply** (SPEC-037 §5): code
  edits reflect in the dashboard; dashboard edits write back to the config
  store. Emit `CRP-Config-Hash` for config provenance (auditable: which
  config governed which call).
- The `safety:` section IS the Safety Manifest (SPEC-033). The `context.
  storage:` section tunes the SPEC-035 primitives. The `amplification:`
  section honours the SPEC-023 boundary (off by default).
- **Validate** the config (ranges, embedding-model consistency, dangerous
  combinations like fail-open timeouts on financial checkpoints).

## UPDATED INVARIANTS (add to PART 2)

9. **Storage: right primitive per access.** Never force all retrieval
   through the vector index. The Access Router (SPEC-035) selects per
   access by known intent. Recency = rolling log (pointer read); exact =
   inverted index; repeat = hot cache; volume = pointer store; semantic =
   CKF graph. Target single-digit-ms retrieval; emit CRP-Context-Retrieval-Ms.

10. **Checkpoints never leave the end user with a raw error.** Every
    rejection/timeout path resolves to a handled outcome (fallback message,
    retry, graceful abort). Edited values are re-verified through the DPE.

11. **Remediations are always proposals.** Scan opens PRs and pre-filled
    Comply remediations — NEVER direct commits to protected branches, NEVER
    auto-applied safety settings. The human reviews and applies.

12. **Config is optional and provenanced.** CRP runs safely with no config
    file. When present, every call carries CRP-Config-Hash tying it to the
    exact configuration in force.

## UPDATED BUILD ORDER

Tier 1 now also includes: the five-primitive storage engine + Access Router
(SPEC-035), the Checkpoint primitive + resolution lifecycle (SPEC-033/034),
the Safety Control Plane object + custom rules (SPEC-033), and the addable
safety rules (SPEC-034 §11).

Tier 3 now also includes: the Scan Remediation Engine (SPEC-036) and the
Comply Safety Control Centre surfaces.

Cross-cutting, build early so everything reads from it: the Unified Config
(SPEC-037).

Recommended sequence within Tier 1: build the storage engine + router FIRST
(everything retrieves through it), then the safety control plane + checkpoints
(governance surface), then wire the unified config so both read from one place.

## VALIDATION ADDITIONS (add to PART 4)

5. **Storage test:** each access type hits its correct primitive and returns
   in target time — recency < 1ms (log), exact < 1ms (index), repeat < 1ms
   (cache), semantic < 5ms (CKF). Blended access bounded by slowest primitive.
6. **Checkpoint test:** each resolution path (approve/reject/edit/timeout)
   progresses correctly; edited values re-verified; rejection retry feeds
   AIR; async checkpoint resumes after restart; every resolution audited.
7. **Remediation test:** a detected ungoverned call produces a correct,
   mergeable PR diff; a config gap produces a correct Comply remediation;
   post-merge scan confirms the finding cleared.
8. **Config test:** omitting the config runs safely on defaults; layered
   overrides resolve in the correct precedence; invalid values rejected;
   CRP-Config-Hash present and stable.

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*
