# CRP-SPEC-004: Window Continuation & DAG Specification

**Document:** CRP-SPEC-004  
**Title:** Context Relay Protocol (CRP) — Window Continuation, Context Enlargement & Directed Acyclic Graph  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Repository:** https://github.com/crprotocol/spec  
**Date:** 2026-05-24  
**License:** CC BY 4.0 (specification text)  
**Prerequisites:** CRP-SPEC-001 (Core), CRP-SPEC-002 (Headers), CRP-SPEC-003 (Envelope)

---

## Abstract

This document specifies the Window Continuation mechanism — CRP's approach to extending effective AI context beyond a single model's token limit by chaining multiple dispatch calls into a directed acyclic graph (DAG). It defines the Window DAG structure, continuation pointer semantics, fan-out/fan-in patterns for parallel agent dispatch, cross-window provenance stitching via HMAC chain extension, and the session token state relay that enables stateless context continuity across language boundaries and gateway instances.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Terminology](#2-terminology)
3. [Window DAG Structure](#3-window-dag-structure)
4. [Continuation Lifecycle](#4-continuation-lifecycle)
5. [Linear Continuation](#5-linear-continuation)
6. [Fan-Out Pattern](#6-fan-out-pattern)
7. [Fan-In Pattern](#7-fan-in-pattern)
8. [Cross-Window Context Transfer](#8-cross-window-context-transfer)
9. [HMAC Chain Extension](#9-hmac-chain-extension)
10. [Session Token State Relay](#10-session-token-state-relay)
11. [Window Limits & Depth Control](#11-window-limits--depth-control)
12. [Context Summarisation](#12-context-summarisation)
13. [Quality Evolution Tracking](#13-quality-evolution-tracking)
14. [Header Semantics for Continuation](#14-header-semantics-for-continuation)
15. [Agentic Continuation](#15-agentic-continuation)
16. [Error Handling & Recovery](#16-error-handling--recovery)
17. [Security Considerations](#17-security-considerations)
18. [References](#18-references)

---

## 1. Introduction

### 1.1 The Context Enlargement Problem

A single LLM call is bounded by its context window — typically 128K–200K tokens for frontier models in 2026. Many real-world tasks require more context than a single window can hold: multi-document analysis, extended agentic sessions, iterative research workflows, and cross-domain synthesis.

CRP solves this through **continuation windows** — a chain of LLM calls where each call builds on the context and outputs of prior calls, maintaining provenance integrity, quality tracking, and safety budget across the entire chain.

### 1.2 Why a DAG, Not a Linear Chain

A linear chain (Window 1 → Window 2 → Window 3) is the simplest continuation model but insufficient for complex workflows:

- **Fan-out:** An orchestrator agent dispatches three specialist agents simultaneously, each with its own continuation chain. This is a tree, not a line.
- **Fan-in:** The results of the three specialists are merged back into a single synthesis window. This creates a convergence point — a DAG node with multiple parents.
- **Branching:** A reflexive dispatch (verify → refine) creates a branch where Window 2a (verification) and Window 2b (refinement) are siblings, not sequential.

The DAG structure accommodates all these patterns while maintaining a single provenance chain root.

---

## 2. Terminology

**Window:** A single AI call within a CRP session. Each window has a unique identifier, a Context Envelope, an LLM response, a DPE analysis, and an HMAC hash.

**Window DAG:** The directed acyclic graph connecting all windows in a session. Edges represent context flow — a child window received context derived from its parent(s).

**Continuation Pointer:** An opaque token (`CRP-Context-Continuation-Id`) that references a specific window in the DAG, enabling a subsequent call to resume from that point.

**Fan-Out:** A pattern where one parent window spawns multiple child windows that execute in parallel.

**Fan-In:** A pattern where multiple parent windows merge their results into a single child window.

**Linear Continuation:** The simplest pattern: Window 1 → Window 2 → Window 3, each building sequentially on the previous.

**Session Root:** The first window in the DAG. Its HMAC is the anchor for the entire chain.

---

## 3. Window DAG Structure

### 3.1 Node Definition

Each node (window) in the DAG contains:

```
WindowNode {
  window_id:           string         // "crp_win_" + 16-char identifier
  session_id:          string         // Parent session ID
  window_number:       integer        // Sequential position (1-indexed)
  parent_ids:          string[]       // IDs of parent windows (empty for root)
  child_ids:           string[]       // IDs of child windows (empty for leaf)
  continuation_id:     string         // Outbound continuation pointer
  pattern:             enum           // LINEAR | FAN_OUT | FAN_IN | BRANCH
  strategy:            string         // Dispatch strategy used
  envelope_etag:       string         // Context Envelope ETag
  quality_tier:        enum           // S | A | B | C | D
  risk_level:          enum           // CRITICAL | HIGH | MEDIUM | LOW
  safety_budget:       float          // Safety budget after this window
  hmac:                string         // This window's HMAC hash
  hmac_chain_tip:      string         // The chain tip after this window
  timestamp:           ISO 8601       // Window creation time
  token_count:         integer        // Envelope tokens consumed
  response_hash:       string         // SHA-256 of LLM response content
}
```

### 3.2 Edge Definition

An edge from Window A to Window B means: "Window B's Context Envelope includes context derived from Window A." Edges carry metadata:

```
WindowEdge {
  source_id:           string         // Parent window ID
  target_id:           string         // Child window ID
  transfer_type:       enum           // FULL_CONTEXT | SUMMARY | FACTS_ONLY | RESULT_ONLY
  transferred_tokens:  integer        // Tokens from parent included in child's envelope
  summary_hash:        string         // Hash of summarised content (if SUMMARY type)
}
```

### 3.3 DAG Invariants

The Window DAG MUST satisfy these invariants at all times:

1. **Acyclic:** No window can be its own ancestor. Gateway MUST detect cycles and reject the call.
2. **Single root:** Every session has exactly one root window (window_number = 1, parent_ids = []).
3. **Connected:** Every window is reachable from the root via parent edges.
4. **HMAC chained:** Every window's HMAC incorporates its parent's HMAC (or parents' HMACs for fan-in). Removing or modifying any ancestor invalidates all descendants.
5. **Monotonic window numbering:** `window_number` increments monotonically within a session. Fan-out children share the same window_number but are distinguished by `window_id`.

---

## 4. Continuation Lifecycle

### 4.1 Session Initialisation

```
1. Client sends first request to gateway (no CRP-Context-Continuation-Id)
2. Gateway creates session:
   - Generates session_id
   - Generates session HMAC key via HKDF (see CRP-SPEC-015 §3.1)
   - Creates root WindowNode (window_number=1)
   - Runs 3-phase packing → Envelope → LLM dispatch → DPE
   - Computes Window 1 HMAC (no previous HMAC — chain starts here)
3. Gateway responds with:
   - CRP-Context-Session-Id: crp_sess_...
   - CRP-Context-Window: 1/5
   - CRP-Context-Continuation-Id: crp_cont_...   (points to Window 1)
   - CRP-Set-Session: token=...; Window=1; QualityHistory=A
   - CRP-Provenance-HMAC: sha256:... (root HMAC)
   - CRP-Provenance-Chain-Integrity: UNVERIFIED  (first window)
```

### 4.2 Continuation Request

```
1. Client sends next request with:
   - CRP-Context-Continuation-Id: crp_cont_...  (from Window 1 response)
   - CRP-Session-Token: (from CRP-Set-Session)
   - (Optional) CRP-Context-Cache: reuse-ckf
2. Gateway validates session token (signature, expiry, scope)
3. Gateway resolves continuation pointer → finds Window 1 in DAG
4. Gateway creates Window 2 as child of Window 1
5. Gateway runs 3-phase packing with:
   - Deferred facts from Window 1 (facts that didn't fit)
   - Summary of Window 1's response
   - New facts from CKF (if query has expanded)
6. Gateway dispatches, runs DPE, extends HMAC chain
7. Gateway responds with:
   - CRP-Context-Window: 2/5
   - CRP-Context-Continuation-Id: crp_cont_...  (new pointer to Window 2)
   - CRP-Set-Session: updated token with Window=2, QualityHistory=A,A
   - CRP-Provenance-HMAC: sha256:... (chained from Window 1)
   - CRP-Provenance-Chain-Integrity: VALID
   - CRP-Provenance-Window-Lineage: crp_win_a7f3 -> crp_win_b9c2
```

### 4.3 Session Completion

A session ends when:
- The client stops sending continuation requests
- The maximum window depth is reached (default: 5)
- The safety budget is depleted (≤ 0.00)
- The client sends a request without `CRP-Context-Continuation-Id`, starting a new session

---

## 5. Linear Continuation

### 5.1 Pattern

The simplest continuation pattern. Each window has exactly one parent and produces at most one child.

```
Window 1 ──→ Window 2 ──→ Window 3 ──→ Window 4
  │              │              │              │
  root         child          child          leaf
```

### 5.2 Context Transfer

In linear continuation, Window N+1 receives:

1. **Summary of Window N's response** — a compressed representation (see §12)
2. **Deferred facts** — high-relevance facts that didn't fit in Window N's budget
3. **New query-specific facts** — if the user's next query requires additional CKF facts
4. **Cross-window metadata** — quality history, safety budget, HMAC chain tip

### 5.3 Fact Deduplication Across Windows

The gateway maintains a `facts_seen` registry per session:

```
facts_seen = set()

for each window:
    candidate_facts = Phase1_Select(query, ckf)
    new_facts = [f for f in candidate_facts if f.fact_id not in facts_seen]
    envelope = Phase2_Rank(new_facts) → Phase3_Pack(new_facts)
    facts_seen.update([f.fact_id for f in envelope.facts])
```

This ensures facts are not re-packed across windows, maximising the information density of each window.

---

## 6. Fan-Out Pattern

### 6.1 When Fan-Out Occurs

Fan-out is triggered when:
- `CRP-Context-Strategy: fan-out` or `CRP-Agent-Dispatch-Strategy: fan-out` is set
- The gateway determines that the task decomposes into N independent sub-tasks
- An orchestrator agent delegates to N specialist agents

### 6.2 Structure

```
                 Window 1 (Orchestrator)
                 /         |          \
          Window 2a    Window 2b    Window 2c
          (Agent A)    (Agent B)    (Agent C)
```

### 6.3 Child Window Properties

Each fan-out child:
- Has `parent_ids = [Window 1 ID]`
- Has the same `window_number` as its siblings (window_number = 2 for all three)
- Has a unique `window_id`
- Receives its own Context Envelope (different query, different facts)
- Inherits the parent's safety budget (NOT the full budget — the parent's remaining budget at dispatch time)
- Has `pattern = FAN_OUT`

### 6.4 Safety Budget Partitioning

When fan-out creates N children from a parent with safety budget B:

```
child_budget = B  // Each child inherits the SAME budget, not B/N
```

The budget is not divided because each child operates independently. However, when fan-in occurs (§7), the merged child's budget is the MINIMUM of all parent budgets:

```
fan_in_budget = min(parent_a.safety_budget, parent_b.safety_budget, parent_c.safety_budget)
```

This ensures the most-depleted agent's risk level is respected in the aggregated output.

### 6.5 Header Semantics

The orchestrator's fan-out request:
```
CRP-Context-Strategy: fan-out
CRP-Agent-Session-Parent: crp_sess_orchestrator_...
CRP-Agent-Loop-Depth: 0
CRP-Agent-Safety-Budget: 0.85
```

Each child's request carries:
```
CRP-Agent-Session-Parent: crp_sess_orchestrator_...
CRP-Agent-Loop-Depth: 1
CRP-Agent-Safety-Budget: 0.85  (inherited, not divided)
```

---

## 7. Fan-In Pattern

### 7.1 When Fan-In Occurs

Fan-in merges results from multiple parallel windows into a single synthesis window. It is the natural successor to fan-out and is triggered when:
- All fan-out children have completed
- The orchestrator issues a synthesis request referencing multiple continuation pointers

### 7.2 Structure

```
    Window 2a    Window 2b    Window 2c
          \         |          /
           Window 3 (Synthesis)
```

### 7.3 Merge Protocol

**Step 7.3.1:** Client sends a synthesis request with multiple continuation IDs:

```
CRP-Context-Continuation-Id: crp_cont_2a, crp_cont_2b, crp_cont_2c
CRP-Context-Strategy: fan-in
```

**Step 7.3.2:** Gateway validates all continuation pointers belong to the same session and share a common ancestor.

**Step 7.3.3:** Gateway constructs the synthesis envelope:
1. Summarises each child's response (see §12)
2. Includes summaries as facts in the synthesis envelope
3. Includes any additional CKF facts needed for cross-cutting synthesis

**Step 7.3.4:** Gateway computes the merged safety budget:
```
merged_budget = min(child_a.safety_budget, child_b.safety_budget, child_c.safety_budget)
```

**Step 7.3.5:** Gateway computes the fan-in HMAC:
```
fan_in_hmac = HMAC-SHA256(
  window_3.content_hash
  || SORT([child_a.hmac, child_b.hmac, child_c.hmac]).join("|")
  || window_3.timestamp,
  session_hmac_key
)
```

The HMACs of all children are sorted lexicographically and concatenated, ensuring the fan-in HMAC is deterministic regardless of child completion order.

### 7.4 Window Node Properties

The fan-in window has:
- `parent_ids = [Window 2a ID, Window 2b ID, Window 2c ID]`
- `pattern = FAN_IN`
- `safety_budget = min(all parent budgets)`
- `hmac` computed from all parent HMACs (see §7.3.5)

---

## 8. Cross-Window Context Transfer

### 8.1 Transfer Types

Four transfer types are defined, controlling what information flows from parent to child:

| Type | What is Transferred | When Used |
|------|-------------------|-----------|
| `FULL_CONTEXT` | Complete parent response + envelope | Linear continuation with sufficient budget |
| `SUMMARY` | Compressed summary of parent response | Default for continuation windows |
| `FACTS_ONLY` | Only the deferred facts (no response content) | When parent response is not relevant to child query |
| `RESULT_ONLY` | Only the final result/answer (no supporting detail) | Fan-in synthesis (each child's conclusion only) |

### 8.2 Transfer Type Selection

The gateway selects the transfer type based on token budget pressure:

```
available_budget = token_budget - query_tokens - system_prompt_tokens

if parent_response_tokens + deferred_facts_tokens <= available_budget * 0.60:
    transfer_type = FULL_CONTEXT
elif summary_tokens + deferred_facts_tokens <= available_budget * 0.60:
    transfer_type = SUMMARY
elif deferred_facts_tokens <= available_budget * 0.60:
    transfer_type = FACTS_ONLY
else:
    transfer_type = RESULT_ONLY
```

The 0.60 threshold reserves 40% of the budget for new facts specific to the child's query.

### 8.3 Transfer Recording

Each transfer is recorded as a DAG edge with metadata (see §3.2). This enables auditors to trace exactly what context flowed between windows and in what form.

---

## 9. HMAC Chain Extension

### 9.1 Linear Chain Extension

For linear continuation (single parent):

```
window_hmac = HMAC-SHA256(
  session_id
  || window_number
  || timestamp_iso8601
  || content_hash         // SHA-256 of LLM response
  || dpe_report_hash      // SHA-256 of DPE output
  || parent_hmac,          // Previous window's HMAC (chain link)
  session_hmac_key
)
```

### 9.2 Fan-Out Chain Extension

Each fan-out child chains from the common parent:

```
child_a_hmac = HMAC-SHA256(
  ... || parent_hmac,       // Same parent HMAC for all siblings
  session_hmac_key
)
child_b_hmac = HMAC-SHA256(
  ... || parent_hmac,       // Same parent HMAC
  session_hmac_key
)
```

### 9.3 Fan-In Chain Extension

Fan-in merges multiple parent HMACs (see §7.3.5):

```
sorted_parent_hmacs = SORT([child_a.hmac, child_b.hmac, child_c.hmac])
merged_parent_input = sorted_parent_hmacs.join("|")

fan_in_hmac = HMAC-SHA256(
  session_id
  || window_number
  || timestamp_iso8601
  || content_hash
  || dpe_report_hash
  || merged_parent_input,    // All parent HMACs, sorted and joined
  session_hmac_key
)
```

### 9.4 Chain Verification

To verify the chain from root to any leaf:

1. Start at the root window. Verify its HMAC against its content using the session key.
2. Follow the DAG edges to the next window(s).
3. For each window, verify: `HMAC(content || parent_hmac(s), key) == stored_hmac`
4. If any verification fails: `CRP-Provenance-Chain-Integrity: BROKEN`

Full-chain verification is performed on every response. The result is emitted as `CRP-Provenance-Chain-Integrity`.

---

## 10. Session Token State Relay

### 10.1 What the Session Token Carries

The `CRP-Set-Session` token is updated after every window and carries:

```json
{
  "session_id": "crp_sess_7f3a...",
  "window_number": 3,
  "quality_history": ["A", "A", "B"],
  "safety_budget_remaining": 0.63,
  "hmac_chain_tip": "sha256:9bce472f...",
  "dag_structure": "LINEAR",
  "continuation_id": "crp_cont_c1d4...",
  "issued_at": "2026-05-24T09:02:00Z",
  "expires_at": "2026-05-24T10:02:00Z"
}
```

### 10.2 Stateless Relay

The session token enables stateless continuation across:

- **Gateway instances:** Any CRP gateway instance that receives a valid token can reconstruct the session context without shared storage. The HMAC chain tip verifies the token's position in the chain.
- **Language boundaries:** A Go service can relay the token to a Python CRP sidecar — no shared database needed.
- **Process restarts:** If the gateway restarts, the token carries sufficient state to resume.

### 10.3 Token Expiry and Continuation

Session tokens expire (default: 1 hour). If a client presents an expired token:
- Gateway returns HTTP 401
- Client MUST re-authenticate and start a new session
- The previous session's HMAC chain is preserved in the audit trail but cannot be continued

---

## 11. Window Limits & Depth Control

### 11.1 Maximum Window Depth

```
default_max_windows = 5
```

Configurable per gateway deployment. Maximum depth is reported in `CRP-Context-Window: N/M` where M is the max.

### 11.2 Maximum Fan-Out Width

```
default_max_fan_out = 10
```

A single parent window MUST NOT fan out to more than `max_fan_out` children. Gateway MUST reject fan-out requests exceeding this limit.

### 11.3 Maximum DAG Nodes

```
default_max_dag_nodes = 50
```

Total windows in a single session MUST NOT exceed `max_dag_nodes`. This prevents runaway agentic sessions from consuming unbounded resources.

### 11.4 Depth Control via Headers

Clients can observe and control depth via:

```
CRP-Context-Window: 4/5         // 4th of 5 max windows
CRP-Agent-Loop-Depth: 3         // 3 levels deep in agent hierarchy
CRP-Agent-Safety-Budget: 0.12   // Budget nearly depleted
```

When `window_number = max_windows`, the gateway MUST NOT issue a new `CRP-Context-Continuation-Id`. The response indicates the session is complete.

---

## 12. Context Summarisation

### 12.1 Purpose

When transferring context from parent to child windows, the full parent response may be too large to include. The gateway generates a compressed summary to carry the essential information forward.

### 12.2 Summarisation Algorithm

The gateway uses the LLM itself to generate the summary:

1. Construct a summarisation prompt: "Summarise the following response in N tokens, preserving all factual claims, numbers, dates, and conclusions."
2. Set `N = min(parent_response_tokens * 0.25, available_budget * 0.30)`
3. Dispatch the summarisation call with `CRP-LLM-Temperature: 0.1` (low variance)
4. The summary becomes a fact in the child window's envelope with `importance_weight: 0.95`

### 12.3 Summary Verification

The DPE runs a lightweight fidelity check on the summary against the parent response:
- If the summary distorts the parent response (fidelity_score < 0.80), the gateway falls back to `RESULT_ONLY` transfer type
- Summary hash is recorded in the DAG edge for audit trail verification

### 12.4 Summarisation Cost

Summarisation requires an additional LLM call. This call:
- Is counted toward the session's token usage
- Does NOT decrement the safety budget (it's a protocol operation, not a user-facing generation)
- Is logged in the audit trail as a `SUMMARISATION` event
- Is NOT billed to the user at Gateway usage rates (it's overhead)

---

## 13. Quality Evolution Tracking

### 13.1 Quality History

The session token carries `QualityHistory` — the quality tier of every window in the session:

```
QualityHistory=A,A,B,B,C
```

### 13.2 Degradation Detection

If quality is monotonically degrading (each window worse than or equal to the previous):

| Pattern | Detection | Gateway Action |
|---------|-----------|----------------|
| A → A → B | First drop | Log warning, continue |
| A → B → C | Sustained degradation | Recommend strategy upgrade in response |
| B → C → D | Critical degradation | Emit `CRP-Context-Quality-Tier: D` with warning; recommend session restart |
| Any → D → D | Persistent deficiency | Gateway MAY refuse continuation; return HTTP 503 |

### 13.3 Header Output

```
CRP-Set-Session: ...; QualityHistory=A,A,B
CRP-Context-Quality-Tier: B
```

---

## 14. Header Semantics for Continuation

### 14.1 Request Headers for Continuation

| Header | Purpose in Continuation |
|--------|------------------------|
| `CRP-Context-Continuation-Id` | Resume from this window in the DAG |
| `CRP-Session-Token` | Carry signed session state |
| `CRP-Context-Cache` | Control CKF behaviour for this window |
| `CRP-Context-If-Match` | Skip envelope rebuild if CKF unchanged |
| `CRP-Accept-Quality` | Minimum quality tier for this window |
| `CRP-Agent-Safety-Budget` | Budget ceiling (for sub-agents) |

### 14.2 Response Headers for Continuation

| Header | Purpose in Continuation |
|--------|------------------------|
| `CRP-Context-Window` | Current position / max depth |
| `CRP-Context-Continuation-Id` | Pointer for next window (absent = session complete) |
| `CRP-Set-Session` | Updated token with new window state |
| `CRP-Provenance-HMAC` | Chain extended from parent |
| `CRP-Provenance-Chain-Integrity` | Full chain verification result |
| `CRP-Provenance-Window-Lineage` | DAG path from root to current |
| `CRP-Context-Quality-Tier` | This window's quality |
| `CRP-Agent-Safety-Budget` | Budget after this window |

### 14.3 Fan-Out Multi-Continuation Request

For fan-out, the client issues N parallel requests, each with:
```
CRP-Context-Continuation-Id: crp_cont_parent_...
CRP-Context-Strategy: fan-out
CRP-Agent-Session-Parent: crp_sess_parent_...
```

The gateway detects that the same continuation ID is being used for multiple requests and creates sibling nodes.

### 14.4 Fan-In Multi-Parent Request

```
CRP-Context-Continuation-Id: crp_cont_2a, crp_cont_2b, crp_cont_2c
CRP-Context-Strategy: fan-in
```

Multiple continuation IDs separated by commas indicate a fan-in request.

---

## 15. Agentic Continuation

### 15.1 Agent Chains as DAG Subgraphs

When an orchestrator agent delegates to sub-agents, each sub-agent's session is a subgraph of the orchestrator's DAG:

```
Orchestrator Window 1
├── Agent A: Window 2a → Window 3a (linear chain)
├── Agent B: Window 2b → Window 3b → Window 4b (deeper chain)
└── Agent C: Window 2c (single window)
│
Orchestrator Window 5 (fan-in synthesis)
```

### 15.2 Cross-Agent Safety Budget

The orchestrator's safety budget flows down to each sub-agent:
1. Orchestrator dispatches with budget 0.85
2. Agent A returns with budget 0.62 (consumed 0.23 via HIGH-risk calls)
3. Agent B returns with budget 0.31 (consumed 0.54 via CRITICAL-risk calls)
4. Agent C returns with budget 0.80 (consumed 0.05 via LOW-risk calls)
5. Fan-in synthesis budget = min(0.62, 0.31, 0.80) = 0.31

The orchestrator sees `CRP-Agent-Safety-Budget: 0.31` on the synthesis response and can decide whether to proceed.

### 15.3 Loop Depth Tracking

```
CRP-Agent-Loop-Depth: 0   (orchestrator)
CRP-Agent-Loop-Depth: 1   (sub-agents)
CRP-Agent-Loop-Depth: 2   (sub-sub-agents, if any)
```

Gateway MUST reject calls where loop depth exceeds `max_loop_depth` (default: 5) to prevent infinite recursion.

---

## 16. Error Handling & Recovery

### 16.1 Broken Continuation

If a client presents a `CRP-Context-Continuation-Id` that the gateway cannot resolve:
- Return HTTP 404 with body: `{"error": "continuation_not_found", "continuation_id": "..."}`
- The client MUST start a new session

### 16.2 Expired Session

If the session token has expired:
- Return HTTP 401
- Include `CRP-Safety-Retry-After: 0` (retry immediately with new session)

### 16.3 Fan-Out Child Failure

If one fan-out child fails (LLM error, timeout, CRITICAL risk halt):
- Other children are NOT cancelled (they may already be complete)
- The failed child's window node is marked `status: FAILED` in the DAG
- Fan-in synthesis can proceed with partial results if configured: `CRP-Agent-Fan-In-Policy: partial` (default: `require-all`)

### 16.4 HMAC Chain Break During Continuation

If chain verification fails during a continuation request:
- Return HTTP 409 Conflict
- Set `CRP-Provenance-Chain-Integrity: BROKEN`
- Log a CRITICAL audit incident
- The session CANNOT be continued — client MUST start a new session

---

## 17. Security Considerations

### 17.1 Continuation ID Unguessability

Continuation IDs MUST be generated using a CSPRNG (cryptographically secure pseudo-random number generator) and MUST contain sufficient entropy (at least 128 bits) to prevent prediction. An attacker who guesses a continuation ID could inject themselves into a session.

### 17.2 Session Token Signature Verification

On every continuation request, the gateway MUST verify the session token signature before processing. A replayed or modified token MUST be rejected with HTTP 401.

### 17.3 Cross-Session Isolation

Continuation IDs from Session A MUST NOT be usable in Session B. The gateway MUST validate that the presented continuation ID belongs to the session identified by the session token.

### 17.4 Fan-Out Resource Limits

Fan-out can amplify resource consumption. The `max_fan_out` and `max_dag_nodes` limits (§11) MUST be enforced to prevent denial-of-service via unbounded fan-out.

### 17.5 Summary Injection

Context summaries (§12) are generated by an LLM and injected into subsequent envelopes. A compromised or adversarial LLM could generate a summary that poisons future context. Mitigation: the DPE fidelity check on summaries (§12.3) detects distorted summaries. Gateway SHOULD fall back to `RESULT_ONLY` transfer if summary fidelity is low.

---

## 18. References

### Normative References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-002 — Header Field Specification
- CRP-SPEC-003 — Context Envelope & Packing
- CRP-SPEC-007 — Session Token & State Relay
- CRP-SPEC-011 — Audit Trail & HMAC Chain
- CRP-SPEC-015 — Security & Privacy

### Informative References

- CRP-SPEC-005 — Decision Provenance Engine
- CRP-SPEC-008 — Dispatch Strategy Specification
- CRP-SPEC-012 — Multi-Agent Safety Protocol

---

## Appendix A: DAG Visualisation Example

A complete 5-window session with fan-out and fan-in:

```
Session: crp_sess_7f3a9bc2

Window 1 [root, LINEAR, Quality=A, Risk=LOW, Budget=1.00]
│
├──► Window 2a [FAN_OUT, Quality=A, Risk=LOW, Budget=0.95]
│         │
│         └──► Window 3a [LINEAR, Quality=B, Risk=HIGH, Budget=0.80]
│
├──► Window 2b [FAN_OUT, Quality=A, Risk=MEDIUM, Budget=0.90]
│
└──► Window 2c [FAN_OUT, Quality=B, Risk=LOW, Budget=0.95]

         Window 3a ──┐
         Window 2b ──┼──► Window 4 [FAN_IN, Quality=B, Risk=MEDIUM, Budget=0.80]
         Window 2c ──┘

HMAC Chain:
  Root: sha256:a1b2c3...
  W2a:  HMAC(W2a_content || Root_HMAC, key) = sha256:d4e5f6...
  W2b:  HMAC(W2b_content || Root_HMAC, key) = sha256:g7h8i9...
  W2c:  HMAC(W2c_content || Root_HMAC, key) = sha256:j0k1l2...
  W3a:  HMAC(W3a_content || W2a_HMAC, key)  = sha256:m3n4o5...
  W4:   HMAC(W4_content || SORT[W3a,W2b,W2c]_HMACs, key) = sha256:p6q7r8...

QualityHistory: A, [A,A,B], [B], B   (brackets denote parallel windows)
Safety Budget:  1.00 → [0.95, 0.90, 0.95] → [0.80] → 0.80 (fan-in = min)

Window Lineage (for W4):
  CRP-Provenance-Window-Lineage: crp_win_1 -> [crp_win_2a -> crp_win_3a, crp_win_2b, crp_win_2c] -> crp_win_4
```

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0 (specification text). CRP™ is a trademark of AutoCyber AI Pty Ltd.*
