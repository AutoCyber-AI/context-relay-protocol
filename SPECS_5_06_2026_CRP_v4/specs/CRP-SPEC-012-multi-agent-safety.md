# CRP-SPEC-012: Multi-Agent Safety Protocol

**Document:** CRP-SPEC-012  
**Title:** Context Relay Protocol (CRP) — Multi-Agent Safety Protocol  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Date:** 2026-05-25  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-001, CRP-SPEC-002, CRP-SPEC-004, CRP-SPEC-005, CRP-SPEC-006, CRP-SPEC-008

---

## Abstract

This document specifies the safety protocol for multi-agent CRP deployments — scenarios where orchestrator agents delegate to specialist agents, which may further delegate to sub-agents, forming hierarchical chains of AI calls. It defines the Safety Budget depletion model, header propagation rules across agent hops, policy inheritance and tightening, circuit breaker semantics, oversight escalation triggers, and the provenance chain across multi-agent boundaries. The Safety Budget mechanism specified here is novel — no existing agent framework provides an equivalent session-scoped, header-observable risk accumulation signal.

---

## 1. The Multi-Agent Safety Problem

### 1.1 Risk Accumulation

In a single AI call, risk is bounded — the DPE classifies it and the Safety Policy gates it. In a multi-agent chain, risk accumulates invisibly:

- Agent A makes 3 calls, each LOW risk → cumulative risk appears negligible
- Agent B makes 2 calls, each MEDIUM risk → cumulative risk is moderate
- Agent C makes 1 call that produces HIGH risk → but the chain's total exposure is already significant

Without a mechanism to track cumulative risk across the chain, each agent evaluates risk in isolation. The orchestrator has no signal that the aggregate session risk is approaching dangerous levels.

### 1.2 The Circuit Breaker Analogy

Distributed systems solved this with circuit breakers (Netflix Hystrix, 2012): when failure rate exceeds a threshold, the circuit opens and requests are rejected to prevent cascade failure.

CRP's Safety Budget is the AI equivalent: when cumulative risk consumption exceeds a threshold, the budget depletes, oversight is escalated, and eventually the session halts — preventing cascading risk accumulation across agent chains.

---

## 2. Safety Budget Specification

### 2.1 Initialisation

Every CRP session starts with a safety budget of 1.0:

```
initial_safety_budget = 1.0
```

The budget is stored in the session token (`sb` field, CRP-SPEC-007 §2.2) and emitted as `CRP-Agent-Safety-Budget` on every response.

### 2.2 Depletion Rules

After each DPE analysis, the budget is decremented based on the risk classification:

| Risk Level | Default Decrement | Configurable Range |
|-----------|-------------------|-------------------|
| `LOW` | 0.00 | 0.00 – 0.05 |
| `MEDIUM` | 0.05 | 0.02 – 0.10 |
| `HIGH` | 0.15 | 0.10 – 0.25 |
| `CRITICAL` | 0.35 | 0.25 – 0.50 |

Decrement values are configurable per gateway deployment but MUST fall within the specified ranges to maintain interoperability across gateways.

### 2.3 Budget Thresholds and Actions

| Budget Level | Threshold | Automatic Action |
|-------------|-----------|-----------------|
| Healthy | > 0.50 | No action — normal operation |
| Caution | 0.25 – 0.50 | Gateway emits `CRP-Safety-Budget-Warning: caution` header |
| Low | 0.10 – 0.24 | Gateway upgrades `CRP-Safety-Oversight-Mode` to `human-review` regardless of Safety Policy. Gateway emits `CRP-Safety-Budget-Warning: low` |
| Depleted | ≤ 0.10 | Gateway halts session with HTTP 451. Safety budget depletion is a hard stop — no override except explicit human oversight token |
| Exhausted | ≤ 0.00 | Session terminated. No further calls accepted. Audit trail closed |

### 2.4 Budget Recovery

Safety budget does NOT recover within a session. Once consumed, it is permanently reduced. This is intentional — cumulative risk within a session should compound, not reset.

A new session starts with a fresh budget of 1.0.

### 2.5 Re-Dispatch Budget Accounting

When the DPE triggers a re-dispatch (CRP-SPEC-005 §19), the re-dispatch does NOT decrement the budget — only the final, delivered response's risk level decrements the budget. This prevents the remediation mechanism from itself depleting the budget.

---

## 3. Header Propagation Across Agent Hops

### 3.1 Headers That Propagate Downstream (Orchestrator → Sub-Agent)

| Header | Propagation Rule | Purpose |
|--------|-----------------|---------|
| `CRP-Agent-Safety-Budget` | MUST propagate — sub-agent inherits budget ceiling | Risk budget inheritance |
| `CRP-Safety-Policy` | MUST propagate — sub-agent MUST NOT relax | Policy inheritance |
| `CRP-Agent-Session-Parent` | MUST propagate — set to orchestrator's session ID | DAG ancestry tracking |
| `CRP-Agent-Loop-Depth` | MUST propagate — incremented by 1 | Recursion depth control |
| `CRP-Safety-Mode` | SHOULD propagate — sub-agent inherits safety mode | Consistency |
| `CRP-Compliance-Data-Residency` | MUST propagate — data residency cannot be relaxed | GDPR jurisdiction |

### 3.2 Headers That Propagate Upstream (Sub-Agent → Orchestrator)

| Header | Propagation Rule | Purpose |
|--------|-----------------|---------|
| `CRP-Agent-Safety-Budget` | MUST propagate — orchestrator reads remaining budget | Budget visibility |
| `CRP-Safety-Hallucination-Risk` | MUST propagate — orchestrator sees per-agent risk | Risk aggregation |
| `CRP-Provenance-HMAC` | MUST propagate — chain extends across agent boundary | Provenance continuity |
| `CRP-Provenance-Chain-Integrity` | MUST propagate — orchestrator needs chain status | Integrity signal |
| `CRP-Compliance-Audit-Trail-URI` | MUST propagate — evidence chain spans all agents | Compliance continuity |
| `CRP-Quality-Score` | SHOULD propagate — orchestrator assesses sub-agent quality | Quality visibility |

### 3.3 Headers That Do NOT Propagate

| Header | Reason |
|--------|--------|
| `CRP-Session-Token` | Session tokens are per-session; sub-agents have their own sessions |
| `CRP-Context-ETag` | Each agent has its own CKF state |
| `CRP-Context-Quality-Tier` | Quality tier is per-envelope, not per-chain |
| `CRP-Set-Session` | Sub-agent issues its own session tokens |

---

## 4. Policy Inheritance and Tightening

### 4.1 The Tightening Rule

A sub-agent's Safety Policy MUST be equal to or more restrictive than its parent's on every directive:

```
Parent: halt-on CRITICAL; require-grounding 0.75; warn-on HIGH
Child:  halt-on HIGH; require-grounding 0.80; warn-on MEDIUM     ← VALID (tighter)
Child:  warn-on CRITICAL; require-grounding 0.60                  ← INVALID (relaxed)
```

### 4.2 Directive-Level Comparison

| Directive | More Restrictive Means |
|-----------|----------------------|
| `halt-on` | Lower risk level (MEDIUM > HIGH > CRITICAL) |
| `warn-on` | Lower risk level |
| `require-grounding` | Higher threshold |
| `require-entailment` | Higher threshold |
| `require-quality` | Fewer accepted tiers |
| `require-flow` | Higher threshold |
| `require-completeness` | Higher threshold |
| `max-repetition` | Lower level (NONE > MINOR > SIGNIFICANT) |
| `block-*` | Present is more restrictive than absent |
| `oversight` | halt > human-review > auto > log-only |

### 4.3 Enforcement

When a sub-agent request arrives at a CRP gateway:

1. Gateway extracts `CRP-Agent-Session-Parent`
2. Gateway retrieves the parent session's Safety Policy (from the parent session token or the session store)
3. Gateway compares each directive in the child's `CRP-Safety-Policy` against the parent's
4. Any relaxation → HTTP 403 with:
   ```json
   {
     "error": "safety_policy_inheritance_violation",
     "directive": "halt-on",
     "parent_value": "CRITICAL",
     "child_value": "warn-on CRITICAL",
     "message": "Child policy cannot relax parent's halt-on CRITICAL to warn-on CRITICAL"
   }
   ```

### 4.4 Policy Elevation

When a sub-agent does not specify `CRP-Safety-Policy`, it inherits the parent's policy verbatim. This is the default and recommended behaviour — explicit policy is only needed when the sub-agent wants to TIGHTEN.

---

## 5. Circuit Breaker Pattern

### 5.1 Definition

The CRP circuit breaker is a session-scoped safety mechanism that transitions through three states based on the safety budget:

```
CLOSED ──(budget > 0.50)──→ Normal operation
   │
   └── Risk events decrement budget
   │
HALF-OPEN ──(0.10 < budget ≤ 0.50)──→ Cautious operation
   │         Oversight mode: human-review
   │         Strategy: forced to reflexive
   │         New agent delegations: blocked unless explicitly approved
   │
   └── Further risk events decrement budget
   │
OPEN ──(budget ≤ 0.10)──→ Session halted
         HTTP 451 returned
         No further calls accepted
         Requires new session with fresh budget
```

### 5.2 State Transitions

| From | To | Trigger | Headers Emitted |
|------|----|---------|----------------|
| CLOSED | HALF-OPEN | Budget drops below 0.50 | `CRP-Safety-Budget-Warning: caution` |
| HALF-OPEN | HALF-OPEN | Budget between 0.10 and 0.50 | `CRP-Safety-Oversight-Mode: human-review` (forced) |
| HALF-OPEN | OPEN | Budget drops to ≤ 0.10 | HTTP 451, `CRP-Safety-Retry-After: new-session-required` |
| OPEN | (session ends) | — | `SESSION_TERMINATED` audit event |

### 5.3 Circuit Breaker in Multi-Agent Context

When an orchestrator queries a sub-agent and receives a response with `CRP-Agent-Safety-Budget: 0.08`:
1. The orchestrator's gateway reads this value
2. The orchestrator's own budget is updated to `min(orchestrator_budget, sub_agent_returned_budget)`
3. If the orchestrator's budget transitions to HALF-OPEN or OPEN, the corresponding actions trigger

This means a single sub-agent's budget depletion can cascade upward to halt the entire agent chain. This is the correct behaviour — it prevents orchestrators from ignoring downstream risk.

---

## 6. Oversight Escalation in Hierarchical Agents

### 6.1 Escalation Path

```
Sub-agent CRITICAL risk detected
     │
     ▼
Sub-agent gateway halts (HTTP 451)
     │
     ▼
Orchestrator receives 451 from sub-agent
     │
     ▼
Orchestrator logs CRITICAL event in its own audit trail
Orchestrator's safety budget decremented by 0.35
     │
     ▼
If orchestrator budget < 0.50:
  Orchestrator forced to HALF-OPEN (human-review mode)
     │
     ▼
Orchestrator surfaces to client:
  CRP-Safety-Hallucination-Risk: HIGH  (from sub-agent)
  CRP-Agent-Safety-Budget: 0.28       (depleted)
  CRP-Safety-Oversight-Mode: human-review
```

### 6.2 Oversight Token Flow

When a human reviewer approves an oversighted response:

```
Human Reviewer → CRP Comply/Visualise UI → Approves response

Oversight Token generated:
  CRP-Oversight-Token: approved:sha256:<reviewer_sig>
  reviewer_id: reviewer@company.com
  approval_scope: session_id + window_id
  approval_timestamp: ISO 8601

Client retries with:
  CRP-Oversight-Token: approved:sha256:<reviewer_sig>

Gateway validates token → releases halted response
Safety budget is NOT replenished — the risk event is logged but the human has accepted it
```

---

## 7. Agent Identity and Trust

### 7.1 Agent Registration

In multi-agent deployments, each agent type SHOULD be registered in the CRP gateway configuration:

```yaml
agents:
  orchestrator:
    api_key: crp_gw_prod_orch_...
    max_loop_depth: 3
    max_delegations: 5
    allowed_strategies: [push, reflexive, fan-out, fan-in]
    safety_policy: "halt-on CRITICAL; require-grounding 0.80"
  
  specialist_legal:
    api_key: crp_gw_prod_legal_...
    max_loop_depth: 1
    max_delegations: 0        # cannot delegate further
    allowed_strategies: [push, reflexive]
    safety_policy: "halt-on HIGH; require-grounding 0.90; block-fabrication"
```

### 7.2 Delegation Control

Agents SHOULD have configured delegation limits:
- `max_delegations`: Maximum number of sub-agents this agent can create
- `max_loop_depth`: Maximum nesting depth below this agent
- `allowed_strategies`: Strategies this agent is permitted to use

Exceeding these limits → HTTP 403.

---

## 8. Provenance Chain Across Agent Boundaries

### 8.1 Cross-Agent HMAC Linking

When a sub-agent session completes and its result is consumed by the orchestrator:

1. The sub-agent's final window HMAC is recorded as a `SUB_AGENT_RESULT` event in the orchestrator's audit trail
2. The orchestrator's next window HMAC incorporates the sub-agent's chain tip:

```
orchestrator_window_hmac = HMAC-SHA256(
  ... || sub_agent_chain_tip || ...,
  orchestrator_session_hmac_key
)
```

This creates a cryptographic link between the two sessions' provenance chains without merging them into a single chain.

### 8.2 Auditor Traversal

An auditor verifying a multi-agent session:
1. Starts at the orchestrator's root
2. Encounters `SUB_AGENT_RESULT` events containing `sub_agent_session_id` and `sub_agent_chain_tip`
3. Requests the sub-agent's audit trail from CRP Comply
4. Verifies the sub-agent's chain independently
5. Confirms the sub-agent's chain tip matches the value recorded in the orchestrator's event

If any link fails → the multi-agent provenance is broken.

---

## 9. Multi-Agent Quality Assurance

### 9.1 Cross-Agent Coherence

When an orchestrator synthesises results from multiple sub-agents (fan-in), DPE Stage 6 (Cross-Window Coherence, CRP-SPEC-005 §8) runs across the sub-agent responses:

- Sub-Agent A says "revenue grew 15%"
- Sub-Agent B says "revenue declined 3%"
- Cross-agent contradiction detected → flagged in the synthesis window's DPE report

### 9.2 Cross-Agent Completeness

DPE Stage 8 (Completeness, CRP-SPEC-005 §10) verifies that the aggregate response from all sub-agents covers all sub-queries the orchestrator decomposed:

- Orchestrator decomposed into: [legal analysis, financial analysis, technical analysis]
- Sub-Agent A returned: legal analysis (complete)
- Sub-Agent B returned: financial analysis (partial)
- Sub-Agent C returned: technical analysis (complete)
- Completeness score: 83% → `CRP-Quality-Completeness: 0.83; uncovered=financial-detail`

### 9.3 Cross-Agent Flow

Flow analysis (DPE Stage 9) is applied when the orchestrator stitches sub-agent results into a single response for the end user. The flow score measures whether the stitched output reads as a coherent document or as separate reports pasted together.

---

## 10. Security Considerations

### 10.1 Budget Inflation Attack

A malicious sub-agent could attempt to report a higher safety budget than its actual budget (i.e., lying about its budget to avoid triggering the circuit breaker). Mitigation:
- The gateway computes the budget decrement server-side — the sub-agent cannot set its own budget
- The budget in the session token is HMAC-signed — tampering breaks the signature
- Budget is decremented by the gateway, not by the agent application code

### 10.2 Policy Bypass via New Session

A sub-agent could attempt to start a new session (fresh budget, fresh policy) instead of continuing under the parent's policy. Mitigation:
- The orchestrator sets `CRP-Agent-Session-Parent` — the sub-agent's gateway checks if a parent session exists
- If a parent session is referenced, the gateway enforces policy inheritance
- If the sub-agent starts a completely independent session (no parent reference), it is not part of the orchestrator's provenance chain — the orchestrator cannot use its results without provenance linkage

### 10.3 Infinite Delegation

Agent A delegates to Agent B delegates to Agent C... → unbounded chain. Mitigation:
- `CRP-Agent-Loop-Depth` is incremented on every hop
- Gateway enforces `max_loop_depth` (default: 5) — exceeding returns HTTP 403
- `max_delegations` per agent type limits fan-out width
- `max_dag_nodes` per session (default: 50) limits total complexity

---

## 11. References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-004 — Window Continuation & DAG
- CRP-SPEC-005 — Decision Provenance Engine
- CRP-SPEC-006 — Safety Policy Directive Language
- CRP-SPEC-008 — Dispatch Strategy Specification
- CRP-SPEC-015 — Security & Privacy

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
