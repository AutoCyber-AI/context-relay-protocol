# CRP-SPEC-008: Dispatch Strategy Specification

**Document:** CRP-SPEC-008  
**Title:** Context Relay Protocol (CRP) — Dispatch Strategy Specification  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Date:** 2026-05-25  
**License:** CC BY 4.0 (specification text)  
**Prerequisites:** CRP-SPEC-001, CRP-SPEC-002, CRP-SPEC-003, CRP-SPEC-004, CRP-SPEC-005

---

## Abstract

This document specifies the nine dispatch strategies available in the CRP protocol. A dispatch strategy determines how the CRP gateway constructs, sends, verifies, and (optionally) iterates an LLM call. Strategies range from simple single-shot dispatch (`push`) to complex multi-pass verification (`reflexive`) and autonomous agent loops (`agentic`). Each strategy produces different header output, has different safety budget implications, and interacts differently with the DPE pipeline.

---

## 1. Strategy Overview

| Strategy | Passes | Use Case | Safety Budget Cost | Complexity |
|----------|--------|----------|-------------------|------------|
| `push` | 1 | Simple Q&A, fast response | Lowest | Minimal |
| `pull` | 1 | Retrieval-heavy, document extraction | Low | Low |
| `reflexive` | 2–3 | Verified response, self-critique | Medium | Medium |
| `agentic` | 2–8+ | Autonomous multi-step task completion | High | High |
| `hierarchical` | 2–4 | Multi-source aggregation and synthesis | Medium | Medium |
| `batch` | N | Parallel independent queries | Variable | Medium |
| `streaming` | 1 (streamed) | Real-time token delivery | Low | Low |
| `fan-out` | N parallel | Parallel sub-task delegation | Variable | High |
| `fan-in` | 1 (merge) | Result aggregation from parallel tasks | Variable | High |

Strategy selection is either explicit (via `CRP-Accept-Strategy` request header) or automatic (via TaskIntent analysis performed by the gateway).

---

## 2. TaskIntent Detection

### 2.1 Purpose

When the client does not specify `CRP-Accept-Strategy`, the gateway analyses the query to determine the optimal strategy automatically.

### 2.2 Classification Model

The gateway classifies the query into one of the following TaskIntent categories:

| TaskIntent | Indicators | Default Strategy |
|-----------|-----------|-----------------|
| `SIMPLE_QA` | Short query, single topic, no multi-part structure | `push` |
| `DOCUMENT_EXTRACTION` | References specific documents, extraction language ("find", "extract", "list") | `pull` |
| `VERIFIED_ANSWER` | High-stakes domain, medical/legal/financial context, explicit "verify" or "confirm" | `reflexive` |
| `MULTI_STEP_TASK` | Decomposable task, action verbs, sequential dependencies | `agentic` |
| `COMPARISON_SYNTHESIS` | Multiple sources/topics compared, "compare", "contrast", "synthesise" | `hierarchical` |
| `BULK_PROCESSING` | Multiple independent items to process | `batch` |
| `REAL_TIME` | Chat context, conversational, latency-sensitive | `streaming` |
| `PARALLEL_SUBTASKS` | Decomposable into independent subtasks | `fan-out` → `fan-in` |

### 2.3 Override Priority

```
1. CRP-Accept-Strategy header (highest priority — client explicit choice)
2. CRP-Safety-Policy upgrade-on-risk directive (overrides on risk trigger)
3. TaskIntent auto-detection (default)
```

---

## 3. Strategy: `push`

### 3.1 Description

Single-pass dispatch. The gateway constructs the Context Envelope, dispatches to the LLM, runs the DPE, and returns the response. No iteration, no verification pass.

### 3.2 Flow

```
[1] Envelope construction (CRP-SPEC-003)
[2] LLM dispatch (single call)
[3] DPE analysis (CRP-SPEC-005, all 13 stages)
[4] Header injection + response delivery
```

### 3.3 When to Use

- Simple factual queries with high CKF coverage
- Low-stakes interactions where speed matters more than verification
- Chat/conversational contexts where reflexive latency is unacceptable

### 3.4 Header Output

```
CRP-Context-Strategy: push
CRP-Agent-Revision-Round: 1/1
```

### 3.5 Safety Budget Impact

Standard DPE risk-based decrement only. No additional budget consumption from strategy overhead.

---

## 4. Strategy: `pull`

### 4.1 Description

Retrieval-optimised dispatch. The gateway prioritises the envelope packing phase — maximising fact coverage from the CKF with aggressive retrieval (higher K, broader community expansion). The LLM is instructed to extract and organise rather than generate.

### 4.2 Flow

```
[1] Extended envelope construction (K=100 per sub-query, vs default K=50)
[2] Grounding mode forced to context-strict
[3] LLM dispatch with extraction-oriented system prompt
[4] DPE analysis (all 13 stages)
[5] Header injection + response delivery
```

### 4.3 System Prompt Augmentation

```
"You are performing a document extraction task. Answer using ONLY the 
provided context. Structure your response to faithfully reproduce the 
relevant information from the source material. Do not add interpretation 
or external knowledge."
```

### 4.4 Header Output

```
CRP-Context-Strategy: pull
CRP-LLM-Grounding-Mode: context-strict
```

---

## 5. Strategy: `reflexive`

### 5.1 Description

Two-to-three-pass verified dispatch. The gateway dispatches the initial response, then dispatches a verification/critique pass, then optionally dispatches a refinement pass. This is the primary strategy for high-stakes, accuracy-critical responses.

### 5.2 Flow

```
[Pass 1: Generate]
  [1] Envelope construction
  [2] LLM dispatch (generation)
  [3] DPE analysis → risk_level_1

[Pass 2: Verify]
  [4] Construct verification prompt:
      "Review the following response for accuracy against the provided context.
       Identify any errors, unsupported claims, or omissions.
       Response to verify: [Pass 1 response]"
  [5] LLM dispatch (verification) with temperature=0.2
  [6] Parse verification output for identified issues

[Pass 3: Refine (conditional)]
  If verification identified issues:
    [7] Construct refinement prompt:
        "Revise the following response to address these issues:
         [verification findings]
         Original response: [Pass 1 response]"
    [8] LLM dispatch (refinement) with temperature=0.3
    [9] DPE analysis on refined response → risk_level_final

  If verification found no issues:
    [7] DPE analysis on Pass 1 response → risk_level_final
```

### 5.3 Token Cost

Reflexive dispatch costs 2–3× the tokens of a single push dispatch. This is billed at Gateway usage rates and logged in the audit trail.

### 5.4 Safety Budget Impact

Only the FINAL risk level (after verification/refinement) decrements the safety budget. Intermediate passes do not decrement.

### 5.5 Header Output

```
CRP-Context-Strategy: reflexive
CRP-Agent-Revision-Round: 2/3     (if refinement occurred)
CRP-Agent-Revision-Round: 1/2     (if verification found no issues)
```

### 5.6 When Triggered Automatically

Reflexive is auto-triggered when:
- `CRP-Safety-Policy` contains `upgrade-on-risk reflexive` AND initial push produces HIGH risk
- `CRP-Safety-Mode: strict` is set
- DPE Stage 7 detects SEVERE repetition (re-dispatch as reflexive)
- DPE Stage 9 detects low flow score (re-dispatch with flow augmentation)

---

## 6. Strategy: `agentic`

### 6.1 Description

Autonomous multi-step task completion. The gateway enters an iterative cognitive loop where it analyses the task, plans steps, executes them (potentially with tool calls), evaluates results, and iterates until the task is complete or the safety budget is exhausted.

### 6.2 Cognitive Loop Phases

```
[Phase 1: ANALYZE]    Decompose the task into sub-goals
[Phase 2: PLAN]       Determine execution order and required tools
[Phase 3: GENERATE]   Execute the current step (LLM call or tool call)
[Phase 4: EVALUATE]   Assess whether the step achieved its sub-goal
[Phase 5: CRITIQUE]   Identify gaps or errors in the current state
[Phase 6: REFINE]     Adjust the plan based on critique
[Phase 7: INTEGRATE]  Merge step results into the cumulative output
[Phase 8: COMPLETE]   Final output assembly and DPE analysis
```

### 6.3 Loop Control

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_iterations` | 8 | Maximum loop iterations before forced completion |
| `max_tool_calls` | 10 | Maximum tool invocations per session |
| `completion_threshold` | 0.85 | Completeness score (Stage 8) to trigger COMPLETE |
| `budget_floor` | 0.10 | Safety budget below which loop is halted |

### 6.4 Safety Budget Consumption

Each iteration through the loop that produces a HIGH or CRITICAL DPE result decrements the safety budget. Budget depletion below `budget_floor` forces the loop to exit at the COMPLETE phase regardless of task completion.

### 6.5 Header Output

```
CRP-Context-Strategy: agentic
CRP-Agent-Phase: EVALUATE
CRP-Agent-Loop-Depth: 1
CRP-Agent-Tool-Calls: 3
CRP-Agent-Safety-Budget: 0.62
```

### 6.6 Tool Integration

The agentic strategy supports tool calls via the gateway's tool registry. Tool calls are:
- Logged in the audit trail as `TOOL_CALL` events
- Subject to HMAC chain extension (tool call + result included in chain)
- Not subject to DPE analysis (tools return structured data, not natural language)
- Counted toward `CRP-Agent-Tool-Calls`

---

## 7. Strategy: `hierarchical`

### 7.1 Description

Multi-source aggregation. The gateway dispatches separate queries for each information source or topic, then synthesises the results in a final aggregation pass. Designed for comparison and synthesis tasks.

### 7.2 Flow

```
[1] Query decomposition → N sub-queries (one per source/topic)
[2] For each sub-query:
    [2a] Envelope construction (topic-specific CKF facts)
    [2b] LLM dispatch (topic-specific response)
    [2c] DPE analysis per sub-response
[3] Aggregation envelope construction:
    - Includes summaries of all sub-responses as facts
    - Includes cross-cutting CKF facts
[4] LLM dispatch (synthesis/comparison)
[5] Full DPE analysis on synthesis response
[6] Cross-window coherence check against sub-responses
```

### 7.3 DAG Structure

Hierarchical dispatch produces a fan-out → fan-in DAG pattern (CRP-SPEC-004 §6, §7):

```
Query: "Compare EU AI Act and GDPR on automated decisions"
     │
     ├──→ Sub-response A: EU AI Act analysis
     ├──→ Sub-response B: GDPR analysis
     │
     └──→ Synthesis: Comparison and contrast
```

### 7.4 Header Output

```
CRP-Context-Strategy: hierarchical
CRP-Context-Window: 3/5       (synthesis is Window 3 after 2 sub-responses)
```

---

## 8. Strategy: `batch`

### 8.1 Description

Parallel processing of multiple independent queries. Each query gets its own envelope, dispatch, and DPE analysis. Results are returned as a batch. There is no cross-query context sharing.

### 8.2 Flow

```
[1] Receive batch of N queries
[2] For each query (parallel):
    [2a] Envelope construction
    [2b] LLM dispatch
    [2c] DPE analysis
[3] Aggregate results
[4] Return batch response with per-query headers
```

### 8.3 Safety Budget

Each query in the batch decrements the session safety budget independently. If the budget is depleted mid-batch, remaining queries are halted.

### 8.4 Header Output

Batch responses include per-item headers in a structured JSON response. The top-level headers reflect the worst-case across all items:

```
CRP-Context-Strategy: batch
CRP-Safety-Hallucination-Risk: HIGH    (worst across batch items)
CRP-Agent-Safety-Budget: 0.45         (after all items)
```

---

## 9. Strategy: `streaming`

### 9.1 Description

Real-time token-by-token delivery via Server-Sent Events (SSE). The DPE runs in two modes depending on `CRP-Stream-Safety-Mode`:

| Mode | Behaviour |
|------|-----------|
| `buffer` | Full response buffered, DPE runs, then response streamed to client |
| `pass-through` | Tokens streamed immediately; DPE runs concurrently and emits risk annotations inline; final headers sent as SSE trailer event |

### 9.2 Pass-Through DPE

In `pass-through` mode, the DPE runs a lightweight real-time analysis:
- Fabrication patterns detected mid-stream can trigger `CRP-Safety-Stop-Inject` (CRP-SPEC-005) — the gateway injects a stop sequence to terminate the completion
- Full DPE analysis runs on the complete response after streaming finishes
- Final risk headers are emitted as an SSE event: `event: crp-headers\ndata: {"CRP-Safety-Hallucination-Risk": "LOW", ...}`

### 9.3 Header Output

```
CRP-Context-Strategy: streaming
CRP-Stream-Safety-Mode: pass-through
```

### 9.4 Safety Considerations

Pass-through mode means the client receives tokens BEFORE DPE analysis completes. If the final DPE analysis reveals CRITICAL risk:
- The trailing SSE event carries `CRP-Safety-Hallucination-Risk: CRITICAL`
- A violation report is fired to `report-uri`
- The audit trail records the violation
- But the client has already received the tokens — the halt cannot be retroactive

For this reason, `CRP-Safety-Mode: strict` MUST use `buffer` mode, not `pass-through`.

---

## 10. Strategy: `fan-out`

### 10.1 Description

Parallel delegation of sub-tasks to independent processing paths. See CRP-SPEC-004 §6 for the complete DAG specification.

### 10.2 Dispatch Semantics

The gateway creates N child windows from a single parent:
1. Decomposes the task into N independent sub-tasks
2. Creates N child WindowNodes in the DAG
3. Dispatches each child independently (may use different strategies per child)
4. Each child receives the parent's safety budget (not divided — see CRP-SPEC-004 §6.4)

### 10.3 Header Output

```
CRP-Context-Strategy: fan-out
CRP-Agent-Dispatch-Strategy: fan-out
CRP-Agent-Session-Parent: crp_sess_parent_...
```

---

## 11. Strategy: `fan-in`

### 11.1 Description

Merge results from multiple parallel windows into a single synthesis. See CRP-SPEC-004 §7 for the complete merge protocol.

### 11.2 Dispatch Semantics

1. Client presents multiple continuation IDs (comma-separated)
2. Gateway validates all IDs belong to the same session
3. Gateway summarises each child's response
4. Gateway constructs synthesis envelope with all summaries as facts
5. LLM dispatches synthesis
6. DPE runs cross-window coherence (Stage 6) across all merged children
7. Safety budget = min(all child budgets)

### 11.3 Header Output

```
CRP-Context-Strategy: fan-in
CRP-Agent-Safety-Budget: 0.31    (minimum across merged children)
```

---

## 12. Strategy Selection Matrix

### 12.1 Decision Tree

```
Is CRP-Accept-Strategy set?
├── YES → Use specified strategy
└── NO → TaskIntent analysis:
    ├── SIMPLE_QA → push
    ├── DOCUMENT_EXTRACTION → pull
    ├── VERIFIED_ANSWER → reflexive
    ├── MULTI_STEP_TASK → agentic
    ├── COMPARISON_SYNTHESIS → hierarchical
    ├── BULK_PROCESSING → batch
    ├── REAL_TIME → streaming
    └── PARALLEL_SUBTASKS → fan-out → fan-in

Post-dispatch override:
├── DPE risk HIGH + upgrade-on-risk set → upgrade to specified strategy
├── DPE repetition SEVERE → re-dispatch as reflexive
└── DPE flow < 0.30 → re-dispatch with flow augmentation
```

### 12.2 Strategy Compatibility with Safety Modes

| Strategy | strict | warn | permissive |
|----------|--------|------|-----------|
| push | ✓ (buffer mode) | ✓ | ✓ |
| pull | ✓ | ✓ | ✓ |
| reflexive | ✓ (recommended) | ✓ | ✓ |
| agentic | ✓ (with budget floor) | ✓ | ✓ |
| hierarchical | ✓ | ✓ | ✓ |
| batch | ✓ | ✓ | ✓ |
| streaming | buffer mode only | ✓ | ✓ |
| fan-out | ✓ | ✓ | ✓ |
| fan-in | ✓ | ✓ | ✓ |

---

## 13. References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-003 — Context Envelope & Packing
- CRP-SPEC-004 — Window Continuation & DAG
- CRP-SPEC-005 — Decision Provenance Engine

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
