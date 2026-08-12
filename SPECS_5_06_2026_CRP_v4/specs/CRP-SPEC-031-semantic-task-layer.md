# CRP-SPEC-031: The Semantic Task Layer (STL) — Positioning, Not Injection

**Document:** CRP-SPEC-031  
**Title:** Context Relay Protocol (CRP) — The Semantic Task Layer: Role Separation and Cognitive Positioning for Agentic AI  
**Version:** 1.0.0  
**Status:** Foundational — Repositions the Architecture  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Governs:** the relationship between the user, the protocol, and the model across all prior specs  
**Prerequisites:** CRP-SPEC-003, CRP-SPEC-005, CRP-SPEC-024, CRP-SPEC-030

---

## Abstract

Every context mechanism in CRP so far — CDR, CDGR, the multi-horizon tiers, the Cognitive State Object — ultimately does the same thing: assemble context and place it in the model's prompt. This is *injection*. However sophisticated the assembly, the model still receives a body of context and must itself decide what matters, infer what the task is, and generate a response — three cognitive jobs at once. This specification rejects injection as the terminal paradigm and defines its replacement: **positioning**.

In the positioning paradigm, a Semantic Task Layer (STL) sits outside the model and performs the cognition *about* the cognition — it classifies what kind of task the user needs, determines how deep that task must go, decomposes it into focused cognitive operations, and *positions* the model on exactly one operation at a time with only the minimal semantic frame that operation requires. The model stops being the **driver of information** (sifting context to decide relevance) and becomes the **driver of response** (a focused generation engine pointed at a precise target). The protocol drives information; the model drives response. This is role separation.

Per the design decisions governing this specification: positioning is **anchored** (each focused operation carries a minimal goal-compass so its output coheres with the whole), and depth is **negotiated** (the STL proposes a depth and plan, executes, and revises mid-flight if the work reveals more is needed). The result is the goal that motivated CRP from the beginning: context management lifted entirely out of the LLM, into a semantic layer that makes the model focus on the right thing at the right depth at the right time — so that builders of agentic AI never have to manage context themselves.

This document includes a task taxonomy and depth model an implementer can build directly, and — as required — an honest assessment separating what is genuinely novel here from what is reframing of existing ideas.

---

## 1. Injection vs Positioning

### 1.1 The Injection Paradigm (What CRP Has Been)

```
User request
   → assemble context (CDR/CDGR/CSO/tiers)
   → inject assembled context into prompt
   → MODEL: read context, decide what matters, infer task, generate
                    └──────────── three jobs at once ───────────┘
```

The model is overloaded. It performs relevance-selection, task-inference, and generation simultaneously. Even with perfect retrieval, the model still has to figure out, from a body of injected context, what it is supposed to *do* and which parts of the context serve that. Sophistication in assembly does not remove this burden — it just changes what gets injected.

### 1.2 The Positioning Paradigm (What CRP Becomes)

```
User request
   → STL: classify task kind, determine depth, decompose into operations
   → for each focused operation, in sequence:
        → position the model: "your single job is X; depth Y;
           here is the minimal frame X needs; here is the goal-compass"
        → MODEL: generate X (one job)
        → integrate result into CSO, advance the plan
   → assemble final response from positioned operations
```

The model never decides what matters or what the task is. The STL has already done that. The model receives one focused cognitive operation, a minimal frame, and a goal-compass, and produces one focused output. The cognition *about* the work happens outside the model. The cognition *of* the work happens inside it.

### 1.3 Why This Is Not Just "Smaller Prompts"

Positioning is not merely trimming the injected context. The distinction is *who does the relevance reasoning*. Under injection, the model reasons about relevance (badly, while also generating). Under positioning, the STL reasons about relevance (systematically, as a dedicated function) and the model never sees the irrelevant material at all — not because it was trimmed, but because the STL determined it was not part of *this operation's* frame. The model is not given less of the same pile. It is given a different thing: a precise cognitive assignment.

---

## 2. Role Separation

### 2.1 The Two Roles

| Role | Performed by | Responsibilities |
|------|-------------|-----------------|
| **Information Driver** | STL (outside the model) | Classify task kind. Determine depth. Decompose into operations. Decide relevance. Sequence operations. Position the model. Integrate results. Decide when done. |
| **Response Driver** | LLM (inside) | Generate the specific output for the one operation it is positioned on. Nothing else. |

### 2.2 What the Model No Longer Does

Under STL, the model no longer:
- Decides what context is relevant (the STL framed the operation)
- Infers what the task is (the STL classified and assigned it)
- Plans the sequence (the STL sequenced)
- Tracks overall progress (the CSO + STL track it)
- Decides when the work is complete (the STL's depth model decides)

The model does exactly one thing: produce the response for the cognitive operation it is currently positioned on. This is the focused-generation role a language model is actually good at, stripped of the information-management roles it performs poorly.

---

## 3. The Task Taxonomy

To position the model, the STL must first know what *kind* of cognitive work the user needs. Every user request reduces to one or a sequence of these fundamental cognitive operation types. This taxonomy is implementable directly.

### 3.1 The Eight Fundamental Cognitive Operations

| Operation | Definition | Characteristic depth | Frame the model needs |
|-----------|-----------|---------------------|----------------------|
| `RETRIEVE` | Surface a specific known fact | Shallow | The query + candidate facts |
| `SYNTHESISE` | Combine multiple facts into a new statement | Medium | The facts to combine + the combination goal |
| `ANALYSE` | Examine something for structure, cause, implication | Deep | The subject + the analytical lens + relevant evidence |
| `COMPARE` | Identify similarities/differences across items | Medium | The items + the comparison dimensions |
| `GENERATE` | Produce new content to a specification | Variable | The spec + style anchors + constraints |
| `TRANSFORM` | Convert content from one form to another | Shallow–Medium | The source + the target form |
| `EVALUATE` | Judge something against criteria | Medium | The subject + the criteria + evidence |
| `PLAN` | Produce an ordered sequence of steps toward a goal | Deep | The goal + constraints + available actions |

### 3.2 Why Eight and Not More

These eight are *cognitively distinct* — each requires a different semantic preparation and a different success test. They are not domains (medicine, law) or formats (essay, table); those are surface features. They are the underlying cognitive operations beneath any request. A request to "write a legal memo comparing two cases" decomposes into RETRIEVE (case facts) → COMPARE (the cases) → ANALYSE (implications) → GENERATE (the memo). The taxonomy is the alphabet; real tasks are words spelled from it.

### 3.3 Operation Classification

The STL classifies each operation by a fast semantic check (no model call for classification — pattern + embedding heuristics, sub-millisecond):

```python
def classify_operation(request_fragment):
    # Verb-anchored + embedding similarity to operation prototypes
    if matches(request_fragment, RETRIEVE_MARKERS):   # "what is", "find", "look up"
        return RETRIEVE
    if matches(request_fragment, COMPARE_MARKERS):     # "compare", "versus", "difference"
        return COMPARE
    if matches(request_fragment, ANALYSE_MARKERS):     # "why", "how does", "implications"
        return ANALYSE
    # ... embedding fallback to nearest operation prototype
    return embedding_nearest_operation(request_fragment)
```

---

## 4. The Depth Model

### 4.1 Depth Is Negotiated, Not Fixed

Per the governing design decision, depth is **negotiated**: the STL proposes a depth, executes at that depth, and revises mid-execution if the work reveals the proposed depth was insufficient (or excessive).

### 4.2 The Five Depth Levels

| Depth | Name | Operations | Cognitive budget |
|-------|------|-----------|-----------------|
| D1 | Lookup | single RETRIEVE | 1 operation, minimal frame |
| D2 | Composition | RETRIEVE + SYNTHESISE | 2–3 operations |
| D3 | Examination | + ANALYSE / COMPARE / EVALUATE | 3–6 operations |
| D4 | Investigation | multi-pass ANALYSE, cross-checking | 6–12 operations |
| D5 | Deep synthesis | full decomposition, PLAN-driven, revision loops | 12+ operations |

### 4.3 Depth Proposal

The STL proposes initial depth from the request's signals:

```python
def propose_depth(request, task_operations):
    signals = {
        "explicit_depth": detect_depth_request(request),  # "briefly" → D1, "thorough" → D4+
        "operation_complexity": max(op.characteristic_depth for op in task_operations),
        "scope_breadth": count_distinct_subjects(request),
        "stakes": detect_stakes(request),                  # "for a regulator" → deeper
    }
    return weighted_depth(signals)
```

### 4.4 Depth Renegotiation (Mid-Execution)

The STL revises depth when execution reveals the proposal was wrong:

**Deepen** when:
- An operation surfaces unresolved complexity (DPE completeness low despite the operation completing)
- A contradiction is found that requires investigation (SPEC-027)
- The goal-compass check shows the output is not converging on the goal

**Shallow** when:
- Operations are returning high-confidence, low-complexity results faster than the proposed depth assumed
- The user's actual need was simpler than the request's phrasing suggested

```
CRP-STL-Depth-Proposed: D3
CRP-STL-Depth-Final: D4; renegotiated=deepen; reason=unresolved-complexity
```

### 4.5 Renegotiation Is Bounded

Depth can be renegotiated at most `MAX_DEPTH_RENEGOTIATIONS` times (default 2) to prevent oscillation. Beyond that, the STL commits to the current depth and completes, flagging the remaining uncertainty rather than deepening indefinitely.

---

## 5. Positioning: The Operation Frame

### 5.1 What the Model Receives

For each cognitive operation, the STL constructs an **Operation Frame** — the minimal, focused assignment that positions the model:

```
OperationFrame {
  operation_type:   enum            // RETRIEVE | SYNTHESISE | ... (§3)
  assignment:       string          // the ONE thing to do, imperatively stated
  frame_content:    string          // ONLY the context THIS operation needs
  goal_compass:     GoalCompass     // anchored positioning (§6)
  success_test:     string          // how the STL will judge the output
  output_contract:  string          // expected form of the output
  depth:            enum            // D1–D5, how far to take this operation
}
```

### 5.2 The Frame Is Minimal by Construction

`frame_content` contains only what the specific operation requires — determined by the operation type's frame requirement (§3.1) and the CSO slice (SPEC-030 §7.2) relevant to this operation. A RETRIEVE operation gets the query and candidate facts. It does not get the conversation history, the document outline, or the other sub-tasks' state. This is where token efficiency comes from: the model is never handed the union of everything; it is handed the intersection of what *this* operation needs.

### 5.3 Token Efficiency Is a Consequence, Not a Goal

Under injection, you reduce tokens by trimming. Under positioning, minimal token use is structural: the frame is built up from what the operation requires, not trimmed down from everything available. A D1 lookup frame might be 300 tokens. A D4 analysis operation's frame might be 2,000. Neither is "the whole context minus trimming" — each is "exactly this operation's requirement." Across a full task, total tokens are far lower than injecting the assembled context into every window, because no operation ever carries another operation's frame.

---

## 6. Anchored Positioning: The Goal-Compass

### 6.1 Why Not Fully Blind

Per the governing design decision, positioning is **anchored**, not blind. A fully blind operation (the model sees only its micro-task with zero awareness of the larger goal) maximises focus and token efficiency but risks incoherence — the operation's output may be locally correct but not fit the whole. The goal-compass is the minimal anchor that prevents this.

### 6.2 The Goal-Compass Structure

```
GoalCompass {
  ultimate_goal:    string     // one sentence: what the user ultimately wants
  this_operation_serves: string // one sentence: how THIS operation contributes
  fit_constraint:   string     // one sentence: what makes this output fit the whole
}
```

Three sentences. Roughly 60–100 tokens. The model doing a SYNTHESISE operation knows: the user ultimately wants a migration plan (ultimate_goal), this operation produces the risk-assessment section (this_operation_serves), and it must use the same severity scale as the prior sections (fit_constraint). The model produces a locally-focused output that globally coheres — without carrying the entire global context.

### 6.3 The Coherence-Efficiency Balance

The goal-compass is the deliberate, bounded cost paid for coherence. It is far smaller than injecting the full goal context (which would reintroduce the injection problem) but non-zero (unlike blind positioning). This is the anchored middle path: ~80 tokens of compass to keep N focused operations globally coherent, versus thousands of tokens to give each operation full global context. The compass is the efficient coherence primitive.

---

## 7. The STL Execution Cycle

### 7.1 End-to-End

```
1. RECEIVE user request
2. CLASSIFY → sequence of cognitive operations (§3)
3. PROPOSE depth (§4)
4. DECOMPOSE into an operation plan (ordered, with dependencies)
5. FOR each operation in plan:
     a. BUILD Operation Frame (minimal frame + goal-compass) (§5, §6)
     b. POSITION the model on the operation (single focused call)
     c. VERIFY output against success_test (DPE, SPEC-005)
     d. INTEGRATE result into CSO (SPEC-030)
     e. RENEGOTIATE depth if needed (§4.4)
6. ASSEMBLE final response from operation outputs
7. RETURN — user receives the result; never saw the machinery
```

### 7.2 The User Never Manages Context

The entire cycle is invisible to the user and the application developer. They issue a request. They receive a result. They never assemble context, never tune retrieval, never manage windows, never think about tokens. The STL is the all-in-one context management layer for agentic AI: the promise that **you never have to worry about context management** because the protocol does the information-driving and the model does the response-driving, automatically.

### 7.3 Relationship to Everything Below

The STL is the conductor. It does not replace the lower specs — it *drives* them:

| Lower spec | STL uses it for |
|-----------|----------------|
| CDR/CDGR (024/025) | building an operation's `frame_content` (the minimal retrieval for THIS operation) |
| Multi-horizon (028/029) | sourcing frame content from the right tier per operation |
| CSO (030) | integrating operation results; slicing state per operation |
| DPE (005) | the `success_test` verification of each operation's output |
| Safety/provenance (006/011) | governing and recording every positioned operation |
| CLD/ROS (020/021) | the execution substrate when an operation needs amplification (opt-in) |

The STL is the missing top layer that makes all the lower machinery serve a single coherent purpose: positioning the model, not injecting at it.

---

## 8. Headers

| Header | Meaning |
|--------|---------|
| `CRP-STL-Operations` | The operation sequence, e.g. `RETRIEVE,COMPARE,ANALYSE,GENERATE` |
| `CRP-STL-Operation-Current` | The operation currently positioned, e.g. `ANALYSE 3/4` |
| `CRP-STL-Depth-Proposed` | Initial proposed depth (D1–D5) |
| `CRP-STL-Depth-Final` | Final depth after any renegotiation |
| `CRP-STL-Frame-Tokens` | Tokens in the current operation frame (efficiency measure) |
| `CRP-STL-Frame-Vs-Inject` | Ratio of positioning tokens to what full injection would have cost |
| `CRP-STL-Goal-Compass-Tokens` | Tokens spent on the anchoring compass (coherence cost) |

`CRP-STL-Frame-Vs-Inject` is the headline efficiency metric: if positioning uses 4,000 tokens across all operations where injection would have used 28,000, this reads `0.14` — an 86% reduction, structural not trimmed.

---

## 9. HONEST NOVELTY ASSESSMENT

As required, a ruthless separation of what is genuinely novel here from what is reframing.

### 9.1 What Is Genuinely Novel

**The role-separation framing as a protocol contract.** The explicit, header-observable separation of "information driver" (protocol) from "response driver" (model), enforced as a wire-level contract with the model receiving only Operation Frames, is not something existing systems formalise. Agent frameworks blur these roles; the model in a ReAct loop still decides relevance and next action. STL makes the separation a hard protocol boundary. This is novel as a *formalisation*.

**Positioning as structurally-minimal framing (vs trimming).** The distinction that the frame is *built up from operation requirements* rather than *trimmed down from available context* is a genuine conceptual contribution. Most "context optimisation" is trimming. Building the frame from the operation's cognitive type is a different construction principle.

**The `Frame-Vs-Inject` efficiency made a measurable protocol signal.** Exposing the positioning-vs-injection token ratio as a header turns an abstract efficiency claim into a measured, auditable quantity.

### 9.2 What Is Reframing (Honest)

**The task taxonomy.** The eight cognitive operations are a clean synthesis but not a discovery. Cognitive task taxonomies exist in instructional design (Bloom's taxonomy), in NLP (the various task-type ontologies), and in agent literature. CRP's eight are a pragmatic, implementable set, but claiming them as novel would be false. They are a *useful organisation*, not a new finding.

**Decomposition into sub-operations.** Task decomposition is the core of every agent framework (LangChain, AutoGPT, CrewAI all decompose). STL decomposes too. What differs is *why* — decomposition here serves positioning (minimal framing) rather than tool-use orchestration. The decomposition itself is not novel; its purpose is.

**Depth levels.** Adaptive computation / variable-effort inference is an active research area (test-time compute scaling). STL's five depth levels are a practical operationalisation, not a new concept. The *negotiation* (mid-execution revision) is a modest contribution; the *idea* of variable depth is not.

**"Outside the LLM" context management.** RAG already moves knowledge outside the model. Memory systems already externalise state. STL extends this to *task cognition*, which is a further step, but it is on a continuum others are already walking, not a clean break.

### 9.3 The Honest Bottom Line

STL's genuine contribution is **the formalisation of role separation as a governed protocol boundary, with positioning (minimal operation framing) as the mechanism and an auditable efficiency signal as the proof.** That is real and, as far as can be determined, not formally done elsewhere as a protocol.

What STL is *not* is a fundamental discovery about cognition or a wholly new computational paradigm. It assembles known ideas — task decomposition, variable depth, externalised context, role specialisation — into a coherent, governed, measurable protocol layer. The novelty is in the *integration and formalisation as a standard*, the same way CRP's overall novelty is integration-and-governance rather than any single new algorithm.

Claiming more than this would not survive scrutiny from the researchers you want to convince. Claiming exactly this is defensible and still significant: **CRP would be the first protocol to make "the model drives response, not information" an enforceable, auditable contract.** That sentence is true, and it is enough.

---

## 10. What STL Does Not Solve

STL positions the model well; it cannot make the model capable of an operation it fundamentally cannot perform. A D5 analysis positioned perfectly still fails if the model cannot reason at that level — positioning is necessary, not sufficient (CLD/ROS, opt-in, address capability; STL addresses focus).

STL's classification and depth proposal are heuristic. Misclassification (treating an ANALYSE as a RETRIEVE) produces an under-framed operation. The renegotiation loop catches some of this (low completeness triggers deepening), but a confidently-wrong classification can still mis-position. This is a real failure mode requiring the SQB validation (SPEC-026) extended to STL: measure whether positioned execution beats injected execution on Factual F1 and coherence, per operation type.

The goal-compass mitigates but does not eliminate incoherence across operations. Three sentences of anchor cannot carry every subtlety of global context. For tasks where deep global coherence is paramount, the compass may be insufficient and a heavier integration pass (SPEC-030 composition) is needed.

---

## 11. References

- CRP-SPEC-003 — Context Envelope (frame content assembly)
- CRP-SPEC-005 — Decision Provenance Engine (operation success tests)
- CRP-SPEC-024/025 — CDR/CDGR (per-operation retrieval)
- CRP-SPEC-026 — Semantic Quality Benchmark (STL validation)
- CRP-SPEC-028/029 — Multi-Horizon Context (per-operation tier sourcing)
- CRP-SPEC-030 — Cognitive State Object (operation result integration)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
