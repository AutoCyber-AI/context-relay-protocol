# CRP-SPEC-023: The Amplification Boundary — Protocol Layering & Opt-In Capability Model

**Document:** CRP-SPEC-023  
**Title:** Context Relay Protocol (CRP) — The Amplification Boundary: Keeping the Core Fast, Model-Agnostic, and Unrestrictive  
**Version:** 3.0.0  
**Status:** Draft — Architectural Governing Specification  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-001, and governs CRP-SPEC-018, 019, 020, 021, 022

---

## Abstract

This document is the governing architectural specification that defines a hard boundary between **CRP Core** (the millisecond-fast, model-agnostic governance protocol) and **CRP Amplification** (the optional, opt-in, off-by-default capability layer that includes AIR, CQR, CLD, ROS, and PEF). It exists because the amplification capabilities, if applied indiscriminately, would destroy the protocol's core value: low-latency, universal, non-restrictive governance of any single AI call.

The governing principle: **CRP Core runs in milliseconds on any model and imposes nothing. CRP Amplification is a separate, explicitly-requested mode for the narrow case of a weak model performing an async, quality-critical task. The two MUST NOT be conflated, and the amplification layer MUST NEVER slow or restrict the core.**

---

## 1. Why This Boundary Must Exist

### 1.1 The Core Identity of CRP

CRP's verified, published value proposition is precise:

> A governance layer that adds **< 50 ms** to a single inference call, on **any model**, via a **single endpoint change**, emitting safety, provenance, and compliance signals with **zero in-window overhead**.

Every part of that sentence is load-bearing:
- **< 50 ms** — the DPE runs embeddings + NLI, not generation. It is fast.
- **any model** — CRP wraps OpenAI, Anthropic, Gemini, local, frontier, weak. No model is privileged or required.
- **single endpoint change** — `base_url` swap. No re-architecture.
- **zero in-window overhead** — CRP headers are stripped before the model (Axiom 4). The model's inference is untouched.

### 1.2 What Amplification Threatened

AIR, CQR, CLD, ROS, and PEF (SPEC-018 through 022) are powerful, but applied to the core they would:

| Amplification behaviour | Damage to core identity |
|------------------------|------------------------|
| Decompose 1 task into N micro-tasks | Destroys "< 50 ms" — now N inferences |
| Run consensus passes | Destroys "< 50 ms" — multiple generations |
| Impose decomposition architecture | Destroys "any model" — frontier models don't need it |
| Require multi-pass orchestration | Destroys "single endpoint change" — now a pipeline |
| Generate before governing | Destroys "zero in-window overhead" |

If amplification were the default, CRP would stop being a protocol and become an inference framework — slower, opinionated, and restrictive. That is the wrong product and it would sink the standardisation effort.

### 1.3 The Resolution

A hard architectural boundary. Two layers. One default-fast, universal, governance-only. One opt-in, narrow, powerful.

---

## 2. The Two Layers

### 2.1 CRP Core (Always On, Always Fast)

```
┌──────────────────────────────────────────────────────────────┐
│  CRP CORE — governance layer                                 │
│  Latency: < 50 ms overhead per call                          │
│  Models: ALL (frontier, mid, weak, local, hosted)            │
│  Imposes: NOTHING on how inference runs                      │
│  Passes: exactly 1 (the user's original inference)           │
│                                                               │
│  Includes:                                                    │
│   • Header emission (SPEC-002)                               │
│   • Context Envelope packing (SPEC-003)                      │
│   • DPE 13-stage analysis (SPEC-005) — post-hoc, fast        │
│   • Safety Policy enforcement (SPEC-006)                     │
│   • Session token (SPEC-007)                                 │
│   • HMAC audit chain (SPEC-011)                              │
│   • Compliance classification (SPEC-010)                     │
│   • Single-window continuation (SPEC-004) when requested     │
└──────────────────────────────────────────────────────────────┘
```

CRP Core is what runs by default. It wraps one inference call, analyses the output, emits headers, enforces policy, records provenance. One pass. Milliseconds of overhead. Any model. This is the protocol.

### 2.2 CRP Amplification (Opt-In, Off by Default)

```
┌──────────────────────────────────────────────────────────────┐
│  CRP AMPLIFICATION — capability layer (OPT-IN)               │
│  Latency: seconds to minutes (multiple inferences)           │
│  Models: best suited to small/weak models                    │
│  Imposes: a decomposition + orchestration pipeline           │
│  Passes: many (parallel/batched)                             │
│  DEFAULT STATE: OFF                                          │
│                                                               │
│  Includes (all opt-in):                                       │
│   • AIR (SPEC-018) — multi-window feedback                   │
│   • CQR (SPEC-019) — cognitive failure interruption          │
│   • CLD (SPEC-020) — cognitive load distribution             │
│   • ROS (SPEC-021) — reliability orchestration               │
│   • PEF (SPEC-022) — parallel execution fabric               │
└──────────────────────────────────────────────────────────────┘
```

Amplification is invoked ONLY when the operator explicitly requests it, for a task they have determined warrants it. It is never automatic, never imposed, and never on the critical path of a normal governed call.

---

## 3. The Activation Rules (Normative)

### 3.1 Amplification Is OFF by Default

A conformant CRP implementation MUST default to Core behaviour. Amplification capabilities MUST NOT activate unless explicitly requested via:

```
CRP-Amplification-Mode: <capability>
```

Absent this header, CRP runs Core only. One pass. Fast.

### 3.2 Amplification Requires Explicit Opt-In Per Capability

```abnf
CRP-Amplification-Mode = amp-capability *( OWS "," OWS amp-capability )
amp-capability = "air"        ; multi-window feedback
               / "cqr"        ; cognitive failure interruption
               / "cld"        ; cognitive load distribution (multi-pass)
               / "ros"        ; reliability orchestration (multi-pass)
               / "full"       ; all of the above
```

Example — operator explicitly wants full amplification for an async task:
```
CRP-Amplification-Mode: full
CRP-Amplification-Async: true
```

### 3.3 Amplification MUST Declare Its Cost Up Front

When amplification is requested, the gateway MUST return an estimate BEFORE executing, allowing the caller to confirm or decline:

```
CRP-Amplification-Estimate: passes=18; est-wall-clock-ms=22000; est-cost-tier=high
```

For synchronous requests where the estimate exceeds a latency budget, the gateway MUST either (a) decline and return Core-only with a notice, or (b) require `CRP-Amplification-Async: true` confirming the caller accepts the latency.

### 3.4 Amplification MUST NOT Be Applied to Models That Do Not Benefit

The gateway SHOULD detect the model tier (via SPEC-001 inference-layer detection) and:
- For **frontier/large models** (capable of the task in one pass): amplification SHOULD warn that it provides marginal benefit and significant latency cost, and SHOULD default to Core even if requested, unless `CRP-Amplification-Force: true` is set
- For **small/weak local models**: amplification is appropriate when the task is async and quality-critical

This prevents the anti-pattern of imposing decomposition overhead on a model that does not need it.

### 3.5 The Core Path MUST Never Be Slowed by Amplification

The DPE, header emission, Safety Policy, and HMAC chain — the Core governance functions — MUST execute at Core latency (< 50 ms overhead) regardless of whether amplification is available in the deployment. Amplification code paths MUST NOT add latency to Core-only requests. This is a hard performance isolation requirement.

---

## 4. Model-Agnosticism Is Preserved

### 4.1 The Universal Contract

CRP Core works identically across all models:

| Model | CRP Core behaviour |
|-------|-------------------|
| GPT-5 / Claude / frontier | Wrap, govern, emit headers, < 50 ms. Amplification: not recommended (model is already capable). |
| Mid-tier (mixtral, 70B) | Wrap, govern, emit headers, < 50 ms. Amplification: optional for hard tasks. |
| Small local (7B, 8B) | Wrap, govern, emit headers, < 50 ms. Amplification: beneficial for async quality tasks. |
| Tiny (1–3B) | Wrap, govern, emit headers, < 50 ms. Amplification: most beneficial, if async. |

The governance contract is identical for every model. Only the *optional* amplification layer is model-sensitive — and even then, only as guidance, never as restriction.

### 4.2 No Model Is Required or Privileged

CRP imposes no model requirement. It does not require a specific provider, size, or capability. A user with any OpenAI-compatible endpoint gets full Core governance. This is non-negotiable and this document exists to protect it.

---

## 5. The Decision Tree (How the Gateway Chooses)

```
Incoming request
     │
     ▼
Is CRP-Amplification-Mode set?
     │
     ├── NO (default) ──────────────► CRP CORE
     │                                 1 pass, < 50ms overhead, any model
     │                                 [THIS IS THE COMMON CASE]
     │
     └── YES ──► Is the task async (CRP-Amplification-Async: true)?
                  │
                  ├── NO ──► Does estimate fit latency budget?
                  │           ├── YES ► run requested amplification
                  │           └── NO  ► decline, return Core + notice
                  │
                  └── YES ─► Is the model one that benefits?
                             ├── frontier ► warn, default to Core
                             │              unless Force=true
                             └── small/weak ► run amplification via PEF
                                              (parallel + batched, SPEC-022)
```

The overwhelmingly common path is the top branch: **no amplification header, Core only, milliseconds, any model.** Amplification is the rare, deliberate exception.

---

## 6. What This Means for Each Amplification Spec

This document amends the status of SPEC-018 through 022:

| Spec | Revised Status |
|------|---------------|
| SPEC-018 (AIR) | Opt-in. Activates only with `CRP-Amplification-Mode: air` or `full`. Multi-window tasks only. |
| SPEC-019 (CQR) | Two parts: **detection** (the failure taxonomy, C1–C6 flags) is Core and fast — it is part of the DPE. **Remediation** (scaffolds, re-dispatch) is opt-in amplification. |
| SPEC-020 (CLD) | Opt-in only. Never default. For weak models + async tasks. |
| SPEC-021 (ROS) | Opt-in only. Never default. Multi-pass — async only. |
| SPEC-022 (PEF) | The execution engine for amplification when it IS invoked. Not active for Core. |

Note the important nuance on CQR: **detecting** cognitive failures (C1–C6) is cheap and stays in Core — the DPE already does this analysis. Only the **remediation** (extra passes, scaffolds) is amplification. So even a fast Core call tells you *what* failure modes are present; fixing them automatically is the opt-in part.

---

## 7. The Honest Product Positioning

### 7.1 Two Sentences That Must Both Be True

**CRP Core:** "Governance for any AI call — safety signals, provenance, and compliance evidence — in milliseconds, on any model, with one line of code."

**CRP Amplification:** "Optionally, for async quality-critical workloads on small local models, CRP can orchestrate decomposition, parallel multi-pass execution, and consensus to make a weak model produce output that rivals a large one."

The first sentence is the protocol. The second is an advanced capability. Conflating them breaks the first. Keeping them separate lets both be true.

### 7.2 Why This Makes the Research Story STRONGER, Not Weaker

A protocol that says "I govern any model in milliseconds, AND I have an optional mode that makes small models punch above their weight when you want it" is more credible than one that claims "I make every model do 34 passes." The first respects the engineer's judgment about when to spend latency. The second imposes a cost they didn't ask for.

Researchers respect optionality and honest cost accounting. The amplification thesis (small models + orchestration challenge scaling) lands harder when it's presented as a deliberate, measured choice for the right workload — not as a mandatory tax on every call.

---

## 8. Standards Impact

This boundary protects the IETF/IANA standardisation effort. The Internet-Drafts describe CRP Core: HTTP headers, governance semantics, safety policy, provenance. These are fast, universal, and clearly protocol-shaped — exactly what standards bodies recognise.

Amplification is explicitly OUT OF SCOPE for the header registration and the core I-Ds. It is documented separately as an optional capability. This keeps the standards submission clean: a header vocabulary and governance contract, not an inference orchestration framework. The IANA expert reviewing CRP headers sees a Cache-Control analogue, not a distributed computing system.

---

## 9. Summary

| Property | CRP Core | CRP Amplification |
|----------|----------|-------------------|
| Default state | ON | OFF |
| Latency overhead | < 50 ms | seconds–minutes |
| Inference passes | 1 | many (parallel/batched) |
| Model requirement | none — any model | best for small/weak |
| Imposes architecture | no | yes (when opted in) |
| Real-time safe | yes | no (async only) |
| In standards scope | yes | no (separate) |
| Use case | every governed AI call | weak model + async + quality-critical |

**CRP runs in milliseconds, on any model, imposing nothing. That is the protocol, and it is protected. Amplification is a powerful optional tool you reach for deliberately — never a tax you pay by default.**

---

## 10. References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-005 — Decision Provenance Engine
- CRP-SPEC-018 through 022 — the amplification capability layer (governed by this document)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
