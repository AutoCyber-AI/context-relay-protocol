# CRP-SPEC-058: Governed Delegation

**Document:** CRP-SPEC-058  
**Title:** Context Relay Protocol (CRP) — Governed Delegation: Carrying the Policy Envelope,
Audit Chain, and Verification Guarantees Across an Agent-to-Agent Boundary  
**Version:** 6.0.0  
**Status:** Roadmap (preview spec)  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)  
**Prerequisites:** CRP-SPEC-002 (HTTP Headers), CRP-SPEC-006 (Safety Policy), CRP-SPEC-011 (Audit Trail), CRP-SPEC-033 (Safety Control Plane), CRP-SPEC-049 (Verification Relay), CRP-SPEC-056 (Transparency Emission Layer)

---

## Abstract

This specification defines **Governed Delegation**, the CRP protocol mechanism by which an orchestrator agent may delegate a sub-task to another agent while carrying CRP governance — Safety Policy, audit-chain continuity, and verification requirements — across the agent boundary. Existing agent-to-agent transports such as A2A move the message payload but leave policy, provenance, and verification guarantees behind: the delegated agent runs under its own policy (or none), its reasoning is opaque to the delegator, and the audit chain forks. Governed Delegation closes that gap with three primitives: a **delegation envelope** that propagates constraints as signed headers, a **cross-agent audit link** that binds the sub-agent's HMAC sub-chain into the delegator's chain, and a **verification handshake** that lets the delegator require a Verification Relay verdict and a faithful-narration attestation on the returned result.

This document is a **preview / roadmap specification**. It specifies the wire format, header fields, semantic invariants, and conformance criteria expected for CRP v6 implementations, but it does not claim a shipping reference implementation.

---

## 1. Terminology

**Delegator.** The agent that originates a delegation. It holds the parent CRP session and is ultimately responsible for the sub-task.

**Delegate.** The agent that receives and executes the delegated sub-task. It runs a distinct CRP session (its own session token and audit chain) and is bound by the delegator's delegation envelope.

**Delegation envelope.** A signed data structure carried on the delegation request that contains the inherited policy, identity, scope, remaining safety budget, and required return attestations.

**Cross-agent audit link.** A cryptographic binding, via the HMAC chain, between the delegator's session and the delegate's session, so that an auditor can traverse from the parent session to the child session and back.

**Verification handshake.** The contract by which the delegator declares which attestations the delegate MUST return (e.g., a Verification Relay verdict or a Transparency Emission Layer faithful-narration receipt), and by which the delegator rejects results that fail to satisfy them.

**Scope intersection.** The delegated sub-task's scope MUST be the set-theoretic intersection of the delegator's scope and the sub-task's scope, never a superset.

**CRP-* headers.** All CRP protocol headers. They MUST be stripped before any request is forwarded to a non-CRP-aware LLM provider (Axiom 4, CRP-SPEC-001).

---

## 2. Introduction

### 2.1 Motivation

CRP's single-agent guarantees — Safety Policy enforcement, HMAC audit chains, Verification Relay verdicts, and Transparency Emission Layer faithful narration — are well defined for one session. Multi-agent systems, however, commonly split work: an orchestrator delegates a sub-task to a specialist agent. Protocols such as Google's A2A carry the task message, parameters, and result between agents, but they do not carry the *governance context* in which the sub-task was authorised. The result is:

- **Policy discontinuity.** The delegate applies its own safety configuration, which may be weaker than the delegator's.
- **Provenance fork.** The delegate's audit chain is separate from the delegator's; an auditor must manually correlate the two sessions.
- **Verification gap.** The delegator has no protocol-level way to demand that the delegate's reasoning or output be verified to the same standard it holds itself to.

Governed Delegation makes CRP the governance layer that travels with the task. It does not replace A2A or any other agent-to-agent transport; it layers over it, exactly as CRP layers governance over raw LLM calls.

### 2.2 Scope

This specification defines:

1. The delegation envelope format and signing rules.
2. Header fields used to carry the envelope and the delegation response.
3. Session-token fields that record delegation ancestry.
4. Cross-agent audit-chain linking rules.
5. Verification-handshake semantics.
6. Policy inheritance and scope-reduction rules.
7. Conformance and security requirements for CRP v6 implementations.

### 2.3 Out of Scope

- This spec does not define the agent-to-agent message body. It is transport-agnostic and interoperates with A2A, MCP, ACP, or bespoke transports.
- It does not specify how a delegator discovers or selects a delegate.
- It does not introduce new LLM provider semantics; all `CRP-*` headers are stripped before provider forwarding.

### 2.4 Non-Goals

- This spec is **not** a replacement for A2A. It governs the CRP envelope that travels alongside the A2A message.
- It does **not** authorise the delegate to relax any constraint from the delegator.
- It does **not** permit a delegate to re-delegate beyond the scope granted by the original delegator without a fresh, tightened delegation envelope.

---

## 3. Specification

### 3.1 Delegation Envelope

The delegation envelope is a JSON object that the delegator signs with the parent session's HMAC key (CRP-SPEC-011 §2). It MUST be present on every governed delegation.

```json
{
  "policy": { "halt-on": "CRITICAL", "require-grounding": 0.80 },
  "identity": {
    "delegator_session_id": "crp_sess_a1b2c3",
    "delegator_agent_id": "agent-A",
    "ultimate_principal": "user-123"
  },
  "scope": ["domain:compliance", "action:read", "regulation:GDPR"],
  "budget": 0.45,
  "require": {
    "vr_verdict": true,
    "faithful_narration": true,
    "min_quality_tier": "A"
  },
  "audit_parent": "sha256:abcd1234...",
  "exp": "2026-08-08T11:00:00Z"
}
```

Envelope fields:

| Field | Required | Description |
|-------|----------|-------------|
| `policy` | MUST | The inherited Safety Policy (CRP-SPEC-006). The delegate MUST enforce it or a tighter version. |
| `identity` | MUST | Who delegated, the parent session id, and the ultimate human principal. |
| `scope` | MUST | The granted capability scope for this sub-task. MUST be an intersection with the delegator's own scope. |
| `budget` | MUST | Remaining safety budget (CRP-SPEC-012) that the delegate is permitted to consume. |
| `require` | MUST | Attestations the delegate MUST return. |
| `audit_parent` | MUST | The delegator's current chain-tip hash at the moment of delegation. |
| `exp` | SHOULD | Expiration time for the envelope, after which the delegate MUST reject it. |

The delegator computes the envelope as:

```python
envelope = {
    "policy": parent_ctx.policy_envelope,
    "identity": parent_ctx.identity,
    "scope": intersect(parent_ctx.scope, sub_task.scope),
    "budget": parent_ctx.remaining_budget(),
    "require": {"vr_verdict": True, "faithful_narration": True},
    "audit_parent": parent_ctx.audit.current_hash,
    "exp": now_plus_ttl(),
}
signed = hmac_sign(envelope, parent_ctx.session_hmac_key)
```

The delegate MUST verify the HMAC before accepting the envelope. Verification failure MUST result in an HTTP 401 response with `CRP-Delegation-Integrity: BROKEN`.

### 3.2 Scope and Least Privilege

The delegate's effective scope MUST be the intersection of the delegator's scope and the sub-task scope. A delegate MUST NOT acquire permissions it did not have through the delegator.

```
Parent scope:     {read, write, admin}
Sub-task scope:   {read}
Delegate scope:   {read}                ← VALID

Parent scope:     {read}
Sub-task scope:   {read, write}
Delegate scope:   {read}                ← VALID (intersection)

Parent scope:     {read}
Sub-task scope:   {write}
Delegate scope:   {}                    ← VALID but empty; task should be rejected
```

If the intersection is empty, the delegator SHOULD NOT send the request, and the delegate MUST reject it with HTTP 403 and `CRP-Delegation-Scope: empty-intersection`.

### 3.3 Safety Budget Inheritance

The delegate receives a sub-budget derived from the delegator's remaining safety budget (CRP-SPEC-012). The delegate's gateway decrements this budget according to the same rules as a single-agent session. The delegate MUST return the remaining budget to the delegator in its response headers.

A delegate MUST NOT start a fresh, unbounded safety budget for a delegated sub-task. Any child session created for delegation MUST record `CRP-Agent-Session-Parent` pointing to the delegator session and MUST initialise its budget from the envelope's `budget` field.

### 3.4 Policy Inheritance and Tightening

The delegate's effective Safety Policy MUST be equal to or more restrictive than the policy in the delegation envelope, using the tightening semantics of CRP-SPEC-012 §4. A gateway receiving a delegation request MUST reject any policy relaxation with HTTP 403.

If the delegate does not explicitly set a policy, it inherits the envelope policy verbatim.

### 3.5 Cross-Agent Audit Link

The delegate's audit chain MUST begin with a `DELEGATION_ACCEPTED` event that records:

- `delegator_session_id`
- `delegator_chain_tip` (the `audit_parent` value)
- `delegate_session_id`
- `envelope_hash`
- `scope_after_intersection`
- `budget_granted`

The delegate's chain then proceeds normally. When the delegate completes the sub-task, its final window HMAC becomes the **delegate chain tip**. The delegator records this tip in a `SUB_AGENT_RESULT` audit event and incorporates it into its own next window HMAC, exactly as described in CRP-SPEC-012 §8:

```
orchestrator_window_hmac = HMAC-SHA256(
    session_id || window_number || window_timestamp
    || response_content_hash || dpe_report_hash
    || previous_window_hmac || delegate_chain_tip,
    orchestrator_session_hmac_key
)
```

This creates a cryptographic link without merging the two chains. An auditor verifies:

1. The delegator's chain from its root to the `SUB_AGENT_RESULT` event.
2. The delegate's chain from its `DELEGATION_ACCEPTED` event to its tip.
3. That the delegate tip recorded by the delegator matches the delegate chain tip.
4. That the `DELEGATION_ACCEPTED` event records the correct delegator chain tip.

If any link fails, `CRP-Provenance-Chain-Integrity: BROKEN` MUST be emitted.

### 3.6 Verification Handshake

The `require` object in the delegation envelope declares what the delegate MUST produce. The following requirement tokens are defined in this specification:

| Token | Meaning |
|-------|---------|
| `vr_verdict` | The result MUST include a CRP-SPEC-049 Verification Relay verdict (`VALID`, `INVALID`, or `UNKNOWN`). |
| `faithful_narration` | The result MUST include a CRP-SPEC-056 Transparency Emission Layer attestation that the produced narration is faithful to the underlying reasoning trace. |
| `min_quality_tier` | The result MUST meet at least the specified CRP quality tier (S, A, B, C, D). |
| `audit_sub_chain` | The result MUST include a URI or embedded copy of the delegate's audit sub-chain. |

The delegate MUST satisfy all `require` entries. If the delegate cannot produce a required attestation, it MUST return an error rather than a result. The delegator MUST reject any result whose attestations do not meet the `require` contract.

### 3.7 Header Fields

All header fields use the `CRP-` prefix and are subject to Axiom 4 stripping before forwarding to LLM providers.

#### 3.7.1 CRP-Delegation-Envelope

**Direction:** REQ (delegator → delegate)  
**Required:** REQUIRED for governed delegation

**Definition:** A Base64-url-encoded, HMAC-signed delegation envelope (§3.1).

**Syntax:**
```abnf
CRP-Delegation-Envelope = base64url-envelope "." base64url-signature
```

**Example:**
```
CRP-Delegation-Envelope: eyJw...9.fyS5...
```

#### 3.7.2 CRP-Delegation-Scope

**Direction:** BOTH  
**Required:** REQUIRED when scope is non-empty

**Definition:** The effective scope after intersection, expressed as a comma-separated list of capability tokens.

**Syntax:**
```abnf
CRP-Delegation-Scope = scope-token *( "," OWS scope-token )
scope-token = 1*( ALPHA / DIGIT / "-" / ":" / "_" )
```

**Example:**
```
CRP-Delegation-Scope: domain:compliance,action:read,regulation:GDPR
```

#### 3.7.3 CRP-Delegation-Integrity

**Direction:** RES  
**Required:** REQUIRED on every delegation response

**Definition:** Whether the delegation envelope signature and chain linkage verified successfully.

**Syntax:**
```abnf
CRP-Delegation-Integrity = "VALID" / "BROKEN" / "UNVERIFIED" / "EXPIRED"
```

**Values:**

| Value | Meaning |
|-------|---------|
| `VALID` | Envelope signature, scope, budget, and policy inheritance all verify. |
| `BROKEN` | Signature mismatch, chain-tip mismatch, or policy relaxation detected. |
| `UNVERIFIED` | The receiving agent is not CRP-governance-aware and did not process the envelope. |
| `EXPIRED` | The envelope `exp` time has passed. |

#### 3.7.4 CRP-Delegation-VR-Verdict

**Direction:** RES (delegate → delegator)  
**Required:** REQUIRED when `require.vr_verdict` is true

**Definition:** The Verification Relay verdict for the delegate's result.

**Syntax:**
```abnf
CRP-Delegation-VR-Verdict = "VALID" / "INVALID" / "UNKNOWN" / "MISSING"
```

If the verdict is `INVALID`, the delegator SHOULD reject the result and either halt or re-delegate with tightened requirements.

#### 3.7.5 CRP-Delegation-Faithful-Narration

**Direction:** RES  
**Required:** REQUIRED when `require.faithful_narration` is true

**Definition:** A claim that the Transparency Emission Layer has attested the narration to be faithful.

**Syntax:**
```abnf
CRP-Delegation-Faithful-Narration = "attested" / "unattested" / "partial"
```

#### 3.7.6 CRP-Agent-Session-Parent

**Direction:** BOTH  
**Required:** REQUIRED for delegated sessions

**Definition:** The parent session id. Carried on every request/response that crosses the delegation boundary so that gateways can verify policy inheritance.

**Syntax:**
```abnf
CRP-Agent-Session-Parent = "crp_sess_" 1*( ALPHA / DIGIT / "-" / "_" )
```

#### 3.7.7 CRP-Agent-Loop-Depth

**Direction:** BOTH  
**Required:** REQUIRED

**Definition:** Incremented by one on each delegation hop. Used to prevent unbounded delegation chains.

**Syntax:**
```abnf
CRP-Agent-Loop-Depth = 1*DIGIT
```

A gateway MUST reject delegation requests whose depth exceeds `max_loop_depth` (default 5) with HTTP 403 and `CRP-Safety-Halt-Reason: delegation-depth-exceeded`.

### 3.8 Session Token Fields

CRP-SPEC-007 session tokens for delegated sessions SHOULD include the following optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `delegation_parent_session` | string | Parent session id (`CRP-Agent-Session-Parent`). |
| `delegation_envelope_hash` | string | `sha256:` hash of the accepted delegation envelope. |
| `delegation_scope` | string[] | Effective scope after intersection. |
| `delegation_budget_ceiling` | float | Budget ceiling inherited from the delegator. |
| `delegation_requirements` | object | Copy of the `require` object. |
| `delegation_depth` | integer | Current `CRP-Agent-Loop-Depth`. |
| `delegate_chain_tip` | string | Final delegate chain tip, recorded after sub-task completion. |

### 3.9 A2A Interoperability

When Governed Delegation is layered over A2A:

1. The A2A `task` message carries the task payload as usual.
2. The `CRP-Delegation-Envelope` header is attached to the A2A request metadata.
3. The A2A response metadata carries `CRP-Delegation-Integrity`, `CRP-Delegation-VR-Verdict`, and `CRP-Delegation-Faithful-Narration`.
4. The A2A body MUST NOT contain the raw delegation envelope; the envelope travels only in the CRP header.

A non-CRP-aware A2A peer ignores the headers and behaves as today. A CRP-aware peer MUST verify and reject unmet requirements.

### 3.10 Delegate Result Rejection

The delegator MUST reject a delegate result when any of the following hold:

1. `CRP-Delegation-Integrity` is not `VALID`.
2. A required attestation (`vr_verdict`, `faithful_narration`, etc.) is missing or fails.
3. The returned quality tier is below `require.min_quality_tier`.
4. The delegate exceeded the granted scope.
5. The delegate's remaining safety budget is negative or inconsistent with the reported risk events.

On rejection, the delegator SHOULD emit `CRP-Delegation-Result: rejected` and record a `DELEGATION_REJECTED` audit event containing the reason. The delegator MAY then re-delegate with a tightened scope, escalate to human oversight, or halt the session.

---

## 4. Integration Points

This specification extends and depends on the following existing CRP specifications:

- **CRP-SPEC-002 (HTTP Headers).** Defines the `CRP-*` header namespace and Axiom 4 stripping. Governed Delegation adds the delegation header family.
- **CRP-SPEC-006 (Safety Policy).** Provides the policy grammar and tightening semantics that the delegation envelope inherits.
- **CRP-SPEC-011 (Audit Trail).** Provides the HMAC chain algorithm and the cross-agent linking pattern used to bind the delegate chain to the delegator chain.
- **CRP-SPEC-033 (Safety Control Plane).** Supplies the control-plane registry and kill-switch surface that SHOULD be consulted before a delegate accepts a high-risk delegation.
- **CRP-SPEC-049 (Verification Relay).** Supplies the `vr_verdict` attestation that may be required in the verification handshake.
- **CRP-SPEC-056 (Transparency Emission Layer).** Supplies the `faithful_narration` attestation that may be required in the verification handshake.
- **CRP-SPEC-012 (Multi-Agent Safety).** Defines safety budget propagation and policy tightening across agent hops, which this specification reuses verbatim for delegation.

---

## 5. Conformance Requirements

### 5.1 Conformance Levels

Because this is a preview/roadmap specification, implementations MAY claim **preview support** rather than full conformance. A full conformant implementation MUST satisfy all normative requirements in §5.2.

### 5.2 Mandatory Behaviour

A CRP v6 implementation that claims Governed Delegation support MUST:

1. Parse and verify a `CRP-Delegation-Envelope` header on incoming delegation requests.
2. Reject delegation envelopes whose HMAC signature does not verify with HTTP 401 and `CRP-Delegation-Integrity: BROKEN`.
3. Reject delegations whose effective scope is not a subset of the delegator's scope with HTTP 403 and `CRP-Delegation-Scope: empty-intersection` or equivalent.
4. Reject delegations whose Safety Policy relaxes the inherited policy with HTTP 403 and a clear error body.
5. Initialise a delegated session's safety budget from the envelope's `budget` field, not from default values.
6. Emit a `DELEGATION_ACCEPTED` audit event containing the delegator session id, delegator chain tip, delegate session id, envelope hash, scope, and budget.
7. Emit a `SUB_AGENT_RESULT` event in the delegator's audit trail that records the delegate's final chain tip.
8. Include the delegate chain tip in the delegator's next window HMAC.
9. Produce the headers required by the verification handshake (`CRP-Delegation-VR-Verdict`, `CRP-Delegation-Faithful-Narration`) when requested.
10. Strip all `CRP-*` headers before forwarding any request to a non-CRP-aware LLM provider (Axiom 4).
11. Increment `CRP-Agent-Loop-Depth` on each delegation hop and enforce `max_loop_depth`.
12. Reject delegate results whose required attestations are missing or fail.

### 5.3 Optional Behaviour

A conformant implementation MAY:

1. Cache verified delegation envelopes to avoid re-verifying on every message of a long-running delegated session.
2. Embed the delegate audit sub-chain in the `SUB_AGENT_RESULT` event rather than only recording the tip.
3. Support non-A2A transports (MCP, ACP, bespoke HTTP) using the same header semantics.
4. Provide a visual/administrative interface showing the delegation DAG.

### 5.4 Test Vectors

Implementations SHOULD pass at least the following test vectors:

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| TV-058-01 | Valid envelope with matching HMAC and subset scope. | Delegate accepts; `CRP-Delegation-Integrity: VALID`. |
| TV-058-02 | Envelope with tampered policy. | Delegate rejects; `CRP-Delegation-Integrity: BROKEN`. |
| TV-058-03 | Sub-task scope wider than parent scope. | Delegate rejects; scope is empty intersection. |
| TV-058-04 | Delegate relaxes inherited policy. | Gateway rejects with HTTP 403. |
| TV-058-05 | Delegation depth exceeds `max_loop_depth`. | Gateway rejects with HTTP 403. |
| TV-058-06 | Delegate returns result without required `vr_verdict`. | Delegator rejects result. |
| TV-058-07 | Delegate chain tip does not match recorded value. | `CRP-Provenance-Chain-Integrity: BROKEN`. |
| TV-058-08 | `CRP-*` headers are absent from the request forwarded to an LLM provider. | Axiom 4 holds. |

---

## 6. Security Considerations

### 6.1 Envelope Tampering

A malicious intermediary could modify the delegation envelope to expand the delegate's scope, raise the budget, or weaken the policy. The HMAC signature over the envelope prevents undetected tampering. Implementations MUST use the parent session's HMAC key (derived per CRP-SPEC-015 §3.1) and MUST verify before acting.

### 6.2 Policy Bypass via Independent Session

A delegate could ignore the delegation envelope and start a fresh CRP session with default or weaker policy. This is mitigated because:

- The delegator records the delegate session id in the `DELEGATION_ACCEPTED` event and expects results only from that session.
- A result returned outside the delegated session has no provenance link into the delegator's chain and MUST be rejected.
- Gateways SHOULD reject delegation requests that carry `CRP-Agent-Session-Parent` but no `CRP-Delegation-Envelope`.

### 6.3 Budget Inflation

A delegate could falsely claim a low risk level to avoid depleting the inherited budget. Budget decrements MUST be computed by the delegate's gateway, not by the delegate application code, and the session token budget field MUST be HMAC-signed per CRP-SPEC-012 §2.

### 6.4 Infinite Delegation

Unbounded `A → B → C → ...` chains are prevented by `CRP-Agent-Loop-Depth` and `max_loop_depth`. Delegators SHOULD also enforce `max_dag_nodes` per session (default 50) to limit fan-out complexity.

### 6.5 Cross-Agent Identity Confusion

The `identity` field in the envelope preserves the ultimate principal across hops so that the delegate knows who it is ultimately serving and so that audit logs name the same principal at every layer. A delegate MUST NOT treat the immediate delegator as the final user when making authorisation decisions about data access.

### 6.6 Verification Handshake Spoofing

A delegate could return a fabricated `CRP-Delegation-VR-Verdict: VALID` without actually running the Verification Relay. The delegator SHOULD verify the verdict against the delegate's audit sub-chain (which records the actual `DPE_COMPLETED` / verification events) rather than trusting the header alone.

### 6.7 Axiom 4 Preservation

Delegation headers are `CRP-*` headers and MUST be stripped before any request reaches a non-CRP-aware LLM provider. Implementations MUST NOT leak `CRP-Delegation-Envelope` contents to providers.

---

## 7. References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-002 — HTTP Headers
- CRP-SPEC-004 — Continuation and State Relay
- CRP-SPEC-005 — Decision Provenance Engine
- CRP-SPEC-006 — Safety Policy Directive Language
- CRP-SPEC-007 — Session Token
- CRP-SPEC-008 — Dispatch Strategy Specification
- CRP-SPEC-011 — Audit Trail & HMAC Chain
- CRP-SPEC-012 — Multi-Agent Safety Protocol
- CRP-SPEC-015 — Security & Privacy
- CRP-SPEC-033 — Safety Control Plane
- CRP-SPEC-049 — Verification Relay
- CRP-SPEC-056 — Transparency Emission Layer

*Companion volume:* Vidiniotis, C. (2026). *The Architecture of Transparency in Agentic AI Systems*. AutoCyber AI.

---

*End of specification.*
