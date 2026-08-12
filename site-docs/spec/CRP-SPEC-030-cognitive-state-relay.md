# CRP-SPEC-030: The Cognitive State Object & State Relay Protocol

**Document:** CRP-SPEC-030  
**Title:** Context Relay Protocol (CRP) - The Cognitive State Object: What CRP Actually Relays  
**Version:** 1.0.0  
**Status:** Foundational - Redefines the Relay Primitive  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Amends:** CRP-SPEC-004 (Continuation), CRP-SPEC-020 (CLD working memory), CRP-SPEC-029 (tool-reasoning link)  
**Prerequisites:** CRP-SPEC-004, CRP-SPEC-005, CRP-SPEC-011

---

## Abstract

This document addresses the most fundamental integrity question in CRP: *what does a context relay window actually relay?* The honest answer, until now, is **text** - each window summarises its output as prose and feeds that summary to the next window. This is functionally identical to conversation-summary memory, a technique that predates CRP by years. It makes the "relay" in Context Relay Protocol a misnomer: the protocol does not relay cognitive state, it relays a lossy text digest. The summary is unverified, the reasoning behind decisions is discarded, prior windows cannot be revised, and there is no structured contract for what a window is meant to accomplish.

This specification defines the **Cognitive State Object (CSO)** - a structured, verifiable, revisable representation of the reasoning state that is relayed between windows in place of (or alongside) the text summary. The CSO carries not just *what was produced* but *why*: the decisions made and their justifications, the facts established and their provenance, the open questions, the constraints, and the reasoning dependencies between them. With the CSO as the relay primitive, CRP windows stop being chunked-generation steps and become genuine state-transfer operations - which is what a protocol named "Context Relay" must do to earn the name. The CSO is also the precise object SPEC-020 (CLD) referred to as "externalised working memory" but never specified, and the missing link in SPEC-029 between a tool result and the decision it informed.

---

## 1. The Problem: Text Relay Is Not State Relay

### 1.1 What a Window Relays Today

```
Window N produces output → summarise(output) → text_summary → Window N+1 prompt
```

The text summary is the entire inheritance Window N+1 receives about Window N's work. This has four fatal properties:

1. **Lossy and unverified.** Summarisation drops detail. Nothing checks that the summary preserved the facts that mattered. A dropped constraint is silently lost forever.
2. **Reasoning-blind.** The summary records conclusions, not the reasoning that produced them. Window N+1 knows *what* was decided, never *why*. It cannot evaluate whether a prior decision still holds under new information.
3. **Irreversible.** The summary is append-only narrative. If Window N+1 discovers Window N erred, there is no structured way to revise the earlier decision - only to contradict it, producing incoherence.
4. **Contractless.** There is no explicit statement of what each window was *for*. The window's purpose is implicit in the prompt, not a verifiable part of the relayed state.

### 1.2 Why This Makes "Relay" a Misnomer

A relay, in engineering, transfers a signal with fidelity. CRP's text-summary relay transfers a degraded, interpreted, lossy digest. It is closer to a game of telephone than a relay. To be a genuine context relay protocol, CRP must transfer *state* with verifiable fidelity - and state is more than text.

---

## 2. The Cognitive State Object

### 2.1 Definition

The CSO is the structured state that is relayed between windows. It is produced at the end of each window (derived from the window's output and reasoning) and consumed at the start of the next window (injected as structured context, not prose).

```
CognitiveStateObject {
  cso_id:            string           // unique, chained to prior CSO
  window_number:     integer
  prior_cso_hash:    string           // HMAC link to predecessor (SPEC-011)

  // ── WHAT WAS ESTABLISHED ──
  established_facts: [
    {
      fact_id:        string
      statement:      string          // the established fact
      provenance:     enum            // CKF | TOOL | CONVERSATION | DERIVED | USER
      provenance_ref: string          // specific source (scratch_id, fact_id, turn_id)
      confidence:     float           // DPE attribution confidence
      window_origin:  integer         // which window established this
    }
  ]

  // ── WHAT WAS DECIDED AND WHY ──
  decisions: [
    {
      decision_id:    string
      choice:         string          // what was decided
      rationale:      string          // WHY - the reasoning (this is what text relay loses)
      alternatives:   string[]        // what was considered and rejected
      depends_on:     string[]        // fact_ids / decision_ids this rests on
      revisable:      boolean         // can later windows revise this?
      window_origin:  integer
    }
  ]

  // ── WHAT REMAINS ──
  open_questions:    string[]         // unresolved items
  constraints:       string[]         // hard constraints that must hold
  goal_state:        GoalState        // the window contract (§4)

  // ── REASONING DEPENDENCIES ──
  dependency_graph:  Edge[]           // which decisions/facts depend on which (§3)

  // ── INTEGRITY ──
  cso_hmac:          string           // tamper-evident (SPEC-011)
  verified:          boolean          // did DPE verify this CSO preserves prior state? (§5)
}
```

### 2.2 The Crucial Addition: Decisions Carry Rationale

The single most important field is `decisions[].rationale`. Text summarisation records "chose PostgreSQL." The CSO records "chose PostgreSQL *because* the workload requires ACID transactions and the team has operational expertise, *rejecting* MongoDB (no multi-document ACID at the time of decision) and DynamoDB (vendor lock-in concern)." 

When a later window encounters new information ("the team is migrating to a Mongo-native stack"), it can evaluate whether the *rationale* still holds - and if not, revise the decision (§6). Text relay makes this impossible because the rationale was never relayed. State relay makes it routine.

### 2.3 The CSO Replaces and Supersedes Specific Prior Mechanisms

| Prior mechanism | Subsumed into CSO |
|----------------|-------------------|
| SPEC-004 text continuation summary | `established_facts` + `decisions` (structured, not prose) |
| SPEC-024 Residual Task Anchor | `goal_state.remaining` (§4) |
| SPEC-020 "externalised working memory" (undefined) | the entire CSO (§7) |
| SPEC-028 Active Thread Summary | `goal_state` + `open_questions` for Tier C |
| SPEC-029 tool-result → decision link (missing) | `decisions[].provenance_ref` to scratch_id (§8) |

The CSO is the unifying primitive these specs each gestured at partially.

---

## 3. The Reasoning Dependency Graph

### 3.1 Why Dependencies Matter

Decisions and facts are not independent. Decision B may rest on Fact A and Decision X. If Fact A is later invalidated (a tool result refreshes, a contradiction is resolved per SPEC-027), every decision depending on A must be flagged for re-evaluation. The dependency graph makes this propagation possible.

```
Fact A: "etcd v3.5 is deployed"  
   ↑ depends on
Decision B: "use the v3.5 TLS configuration syntax"
   ↑ depends on
Decision C: "generate certs with the new SAN format"
```

If a later window establishes "actually the deployment is v3.4," Fact A is invalidated, and the dependency graph immediately identifies B and C as requiring revision. Without the graph, B and C silently remain in the relayed state as if still valid - corrupting every subsequent window.

### 3.2 Invalidation Propagation

```python
def invalidate(cso, invalidated_fact_id):
    affected = set()
    queue = [invalidated_fact_id]
    while queue:
        node = queue.pop()
        for edge in cso.dependency_graph:
            if edge.depends_on == node:
                affected.add(edge.dependent)
                queue.append(edge.dependent)
    # affected = all decisions/facts that must be re-evaluated
    for item_id in affected:
        mark_for_revision(cso, item_id)
    return affected
```

This is the mechanism that makes CRP's relayed state *self-correcting* rather than *accumulating-error*. It directly addresses the error-compounding failure (CRP-SPEC-019 Class via SPEC-018) at the structural level rather than the prompt level.

---

## 4. The Goal State: A Universal Window Contract

### 4.1 What Every Window Is For

The `goal_state` is the explicit contract for what a window must accomplish, and it generalises across all CRP modes (document, conversation, tool, agentic) - replacing the mode-specific anchors (ResidualSet, Active Thread Summary) with one structure:

```
GoalState {
  mode:          enum         // DOCUMENT | CONVERSATION | TOOL | AGENTIC
  objective:     string       // what this window must achieve
  remaining:     string[]     // what is left to do (document: sections;
                              //   conversation: open thread questions;
                              //   agentic: uncompleted sub-tasks)
  success_test:  string       // how to know this window succeeded
  completion:    float        // 0.0–1.0 progress toward overall goal
}
```

### 4.2 Mode-Specific Population

| Mode | objective | remaining | success_test |
|------|-----------|-----------|--------------|
| DOCUMENT | "write section N" | unwritten sections | section covers required sub-topics |
| CONVERSATION | "answer the user's turn" | open thread questions | user's intent addressed |
| TOOL | "use tool result to advance task" | unprocessed tool outputs | result correctly incorporated |
| AGENTIC | "complete sub-task N" | uncompleted sub-tasks | sub-task verification passes |

One structure, four modes. This is the general window contract the integrity check found missing.

---

## 5. CSO Verification: The Summary Is No Longer a Blind Spot

### 5.1 Verified State Transfer

The fatal flaw of text relay is that the summary is unverified - a dropped fact is silently lost. The CSO is verified by the DPE before it is relayed:

```
1. Window N produces output + draft CSO
2. DPE checks: does the CSO's established_facts set preserve every
   fact from Window N-1's CSO that is still valid?
3. DPE checks: does every decision still have its dependencies intact?
4. DPE checks: are there facts in the output that the CSO failed to capture?
5. If preservation fails → the CSO is repaired (missing facts re-added)
   before relay, OR the window is flagged for re-generation
6. Only a verified CSO is relayed forward
```

### 5.2 The Preservation Guarantee

```
preservation_score = |valid prior facts present in new CSO| / |valid prior facts|
```

A `preservation_score < 1.0` means the relay dropped state. The DPE MUST repair the CSO (re-inject dropped facts) until preservation is complete, or halt. This converts the summary from a silent single-point-of-failure into a verified, guaranteed-complete state transfer. This is the integrity fix for the lossy-summary gap.

### 5.3 Header

```
CRP-Relay-Preservation: 1.00
CRP-Relay-Preservation: 0.94; repaired=3
```

---

## 6. Backtracking: Revisable State

### 6.1 The Append-Only Limitation

SPEC-004's DAG is append-only - windows accumulate, never revise. When a later window reveals an earlier error, the only recourse is contradiction, producing incoherence. The CSO enables structured revision.

### 6.2 Revision Protocol

```
1. Window N establishes new information that invalidates a prior
   decision/fact (detected via dependency graph, §3)
2. The invalidated item and its dependents are marked for revision
3. A REVISION WINDOW is dispatched:
   - Its goal_state.objective = "revise decision X given new fact Y"
   - It receives the original decision's rationale, the new fact,
     and the dependent items
   - It produces a revised decision with updated rationale
4. The dependency graph is updated; dependents are re-evaluated
5. The revision is recorded in the audit trail (SPEC-011) as a
   REVISION event - the original decision is not erased, it is
   superseded with a tamper-evident link
```

### 6.3 Why Revision Is Bounded

Revision cannot loop infinitely: each revision is recorded, and a decision that has been revised `MAX_REVISIONS` times (default 3) is escalated to human oversight rather than revised again. This prevents thrashing while enabling correction.

### 6.4 Header

```
CRP-Relay-Revisions: 1
CRP-Relay-Revision-Target: decision_db_choice
```

---

## 7. SPEC-020 (CLD) Rebuilt on the CSO

### 7.1 The Gap in SPEC-020

SPEC-020 specified Cognitive Load Distribution - decompose a task, externalise working memory, let the model do atomic execution. But it never defined *what the working memory state actually is*. It said "the protocol remembers" without specifying the structure of what is remembered. The CSO is that structure.

### 7.2 The Working Memory State IS the CSO

In CLD, each atomic micro-task receives a *slice* of the CSO - exactly the established facts, decisions, and constraints it depends on (via the dependency graph), and nothing else. The micro-task produces output plus its contribution to the CSO (new facts, new decisions with rationale). The protocol merges that contribution into the session CSO, verifies preservation, and passes the relevant slice to the next micro-task.

```
CLD micro-task execution, redefined:
  input  = CSO.slice(relevant_to=micro_task.dependencies)
  output = micro_task_result + CSO_contribution
  merge  = CSO.integrate(CSO_contribution, verify=True)
```

This is what SPEC-020 meant by "externalised working memory." The CSO makes it concrete: the working memory is a verified, structured, dependency-tracked state object, not an undefined blob. CLD's capability-amplification claim now rests on a real primitive.

### 7.3 Why This Strengthens the CLD Thesis

A weak model doing one atomic micro-task with exactly the right CSO slice - the specific facts and decisions it needs, their rationale, their provenance - is far more reliable than a weak model holding everything in its context. The CSO slice is the mechanism that lets the protocol, not the model, hold the working memory. SPEC-020's thesis was sound; it lacked this primitive to be implementable. Now it has it.

---

## 8. SPEC-029 (Tool Context) Linked Through the CSO

### 8.1 The Gap in SPEC-029

SPEC-029 stored tool results in the Scratch Buffer and made them a grounding source. But it left a gap: the *link between a tool result and the decision it informed* was lost. A tool result sat in the buffer; the decision it justified sat in a window summary; nothing connected them. An auditor asking "why did the system decide X?" could not trace it to "because tool Y returned Z."

### 8.2 The CSO Closes the Loop

A decision in the CSO carries `provenance_ref` pointing to the scratch entry that informed it:

```
Decision {
  choice:        "scale the cluster to 5 nodes"
  rationale:     "current CPU utilisation is 87%, above the 80% threshold"
  provenance:    TOOL
  provenance_ref: "scratch_metrics_004"     ← the tool result that informed this
  depends_on:    ["fact_threshold_80pct"]
}
```

Now the chain is complete and auditable: tool `scratch_metrics_004` returned 87% CPU → Decision "scale to 5 nodes" was made because of it → the decision's rationale cites the exact reading → the provenance hash of the tool result is in the audit chain (SPEC-029 §6.3) → the whole thing is HMAC-linked (SPEC-011).

### 8.3 Tool-Result Invalidation Propagates to Decisions

Because tool results are in the dependency graph, when a tool result goes stale (SPEC-029 §4) or is refreshed with a different value, the decisions that depended on it are automatically flagged for revision (§6). If the CPU reading refreshes to 45%, the "scale to 5 nodes" decision is flagged - its rationale no longer holds. This is the tool-reasoning link SPEC-029 was missing, delivered through the CSO dependency graph.

---

## 9. What the CSO Makes CRP

### 9.1 The Honest Repositioning

With the CSO, the claim "Context Relay Protocol" becomes accurate. CRP relays a verified cognitive state - facts with provenance, decisions with rationale, dependencies, goals, and constraints - between windows, with tamper-evidence and preservation guarantees. This is categorically different from chunked generation with a summary:

| | Chunked generation (before) | State relay (with CSO) |
|--|----------------------------|------------------------|
| What's relayed | text summary | verified cognitive state |
| Reasoning preserved | no | yes (decision rationale) |
| Revisable | no (append-only) | yes (dependency-driven revision) |
| Verified | no (lossy summary) | yes (preservation guarantee) |
| Tool→decision link | lost | explicit (provenance_ref) |
| Working memory | undefined | the CSO itself |
| Self-correcting | no (errors compound) | yes (invalidation propagation) |

### 9.2 What Remains Genuinely Borrowed (Honest)

The *idea* of carrying state between generation steps is not itself novel - agent frameworks carry scratchpads, and blackboard architectures carried structured state in the 1980s. What is novel in CRP is the *combination*: a verified, provenance-carrying, dependency-tracked, tamper-evident, revisable state object that is the formal relay primitive of an HTTP-header-governed protocol, with preservation guarantees enforced by an independent analysis engine (DPE) and recorded in a cryptographic chain. No agent framework verifies state preservation. None makes the state tamper-evident. None propagates invalidation through a dependency graph as a protocol guarantee. That combination is the contribution, and it should be claimed precisely - not as "we invented carrying state" but as "we made state transfer verified, attributable, and tamper-evident at the protocol level."

---

## 10. Headers Summary

| Header | Meaning |
|--------|---------|
| `CRP-Relay-Preservation` | Fraction of prior valid state preserved in the relay (1.00 = complete) |
| `CRP-Relay-Revisions` | Number of prior decisions revised this window |
| `CRP-Relay-Revision-Target` | Which decision was revised |
| `CRP-Relay-CSO-Facts` | Count of established facts in the current CSO |
| `CRP-Relay-CSO-Decisions` | Count of decisions (with rationale) in the current CSO |
| `CRP-Relay-Dependency-Depth` | Maximum depth of the reasoning dependency graph |

---

## 11. What This Does Not Solve

The CSO's quality depends on the extraction of decisions and rationale from window output. If the model's output does not make its reasoning explicit, the rationale extracted will be thin. CRP can prompt the model to externalise reasoning (and the CLD reasoning scaffolds, SPEC-019, help), but it cannot recover reasoning the model never expressed. The CSO captures and verifies the reasoning that is present; it cannot manufacture reasoning that is absent.

The CSO adds overhead beyond pure text relay - structured extraction, dependency tracking, preservation verification. This is more than the <1ms of CDR but still bounded (extraction and graph operations, not inference) - low tens of milliseconds. It remains within the Core latency budget for a single window relay and does not require extra model passes.

---

## 12. References

- CRP-SPEC-004 - Window Continuation & DAG (relay mechanism, now state-based)
- CRP-SPEC-005 - Decision Provenance Engine (CSO verification)
- CRP-SPEC-011 - Audit Trail (CSO HMAC chaining, revision events)
- CRP-SPEC-020 - Cognitive Load Distribution (working memory = CSO)
- CRP-SPEC-027 - Retrieval Integrity (fact invalidation feeds dependency graph)
- CRP-SPEC-029 - Ephemeral & Tool Context (tool→decision provenance link)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
