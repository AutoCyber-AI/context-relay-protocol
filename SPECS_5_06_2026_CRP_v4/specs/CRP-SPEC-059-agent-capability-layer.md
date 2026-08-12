# CRP-SPEC-059: The Agent Capability Layer — Typed Tool Manifest, Intent-Compiler, and Tool-Result Envelope

**Document:** CRP-SPEC-059  
**Title:** The Agent Capability Layer — Typed Tool Manifest, Intent-Compiler, and Tool-Result Envelope  
**Version:** 6.0.0  
**Status:** Implemented  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)  
**Prerequisites:** CRP-SPEC-008 (Dispatch & Provider Adaptation), CRP-SPEC-009 (Contextual Knowledge Fabric), CRP-SPEC-011 (Audit Trail), CRP-SPEC-031 (Semantic Task Layer), CRP-SPEC-054 (Structured Decoding)

---

## Abstract

This specification closes the Tool-Use roadmap gaps T1 (typed tool manifest), T2 (intent-compiler convention), and T4 (tool-result envelope) for CRP v6. It defines the **Agent Capability Layer**: a small set of protocol objects and contracts that let developers declare an agent's tools once, compile model-generated intents into safe invocations, and capture tool results as structured, auditable envelopes.

The layer is implemented as an **Agent SDK** that composes existing CRP primitives — the Semantic Task Layer, Contextual Knowledge Fabric, structured decoding, safety policy, audit chain, and decision-provenance engine — into a single builder surface. Creating a governed agent becomes a declaration of `tools + policy + model`; the protocol supplies the loop, not the developer. The model never emits raw `argv`; dangerous or malformed calls are prevented by typed intents, grammar-constrained parameterisation, and safety-class gating.

This specification does not introduce new execution semantics for the model itself. It is a reuse and safety layer around the existing CRP positioning and governance stack.

---

## 1. Introduction

### 1.1 Motivation

CRP v6 already specifies how to position an agent (`CRP-SPEC-031`), how to select a minimal tool set (`CRP-SPEC-050`), how to constrain LLM output (`CRP-SPEC-054`), and how to prove safety and grounding (`CRP-SPEC-005`, `CRP-SPEC-006`, `CRP-SPEC-011`). What was missing was the **builder surface** that turns those primitives into a reusable agent runtime.

Without such a surface, every new agent re-implements the same wiring: declaring tool schemas, translating model output into executable calls, enforcing safety gates, capturing results, hashing them into the audit chain, and narrating the run. The Agent Capability Layer factors that wiring into the protocol. It is the bridge between "CRP is a set of specs" and "CRP is a kit for building governed agents."

### 1.2 Goals

1. Provide a **typed tool manifest** that carries everything selection, parameterisation, gating, and audit need.
2. Define an **intent-compiler** contract: the model fills a typed intent, and a deterministic `compile()` step transforms it into the real invocation.
3. Define a **tool-result envelope** that keeps structured results in-window, raw output out-of-window by reference, and links every result into the HMAC audit chain.
4. Expose the existing protocol through an **Agent SDK** (`crp.Agent`) whose loop is composed from shipped CRP primitives.
5. Make agent construction declarative — tools plus policy plus model — without re-implementing positioning, safety, memory, or provenance.

### 1.3 Non-Goals

- This specification does not train or fine-tune models.
- It does not replace MCP, A2A, ACP, LangChain, LlamaIndex, or Haystack; it complements them with CRP governance objects.
- It does not define a new HTTP transport; objects are carried inside existing CRP envelopes, session tokens, and the CKF.
- It does not mandate a particular programming language for the reference implementation.

---

## 2. Terminology

**Tool manifest:** A governable description of a single tool, including its name, purpose, effect class, safety class, privilege requirement, and argument schema.

**Intent:** A typed, validated object that the model emits when it wants to use a tool. It contains only the logical parameters; it does not contain raw shell `argv` or executable code.

**Intent compiler:** The deterministic, versioned transform from a filled intent to the real invocation (e.g., a function call, HTTP request, or subprocess `argv`).

**Tool-result envelope:** A structured record of a tool execution, separating parsed in-window data from raw out-of-window data and carrying a provenance hash.

**Effect class:** A classification of a tool's side-effect behaviour: `read_only`, `idempotent`, or `irreversible`.

**Safety class:** A classification of the oversight required before a tool may run: `auto`, `gated` (policy check), or `hitl` (human-in-the-loop approval).

**Agent SDK:** The developer-facing builder (`crp.Agent`) that composes the tool manifest, intent compiler, result envelope, STL, TCF, structured decoding, safety policy, and audit primitives into a single agent runtime.

**Operation frame:** The context window produced by the Semantic Task Layer for one operation, containing the goal, the selected tool subset, and any prior facts required for that operation.

---

## 3. Specification

### 3.1 Typed Tool Manifest (T1)

Every tool available to a CRP agent MUST be declared through a **tool manifest**. The manifest is a first-class, governable artifact indexed by the CKF so that selection-as-retrieval (T5) and operation framing can discover it without executing the tool.

A conformant manifest MUST contain the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | REQUIRED | Stable identifier for the tool. Used in tool-subset selection and audit logs. |
| `description` | string | REQUIRED | Human-readable summary of what the tool does. |
| `when_to_use` | string | REQUIRED | Conditions under which the tool should be selected. |
| `when_not_to_use` | string | OPTIONAL | Conditions under which the tool must NOT be selected. |
| `effect` | enum | REQUIRED | `read_only`, `idempotent`, or `irreversible`. |
| `safety_class` | enum | REQUIRED | `auto`, `gated`, or `hitl`. |
| `requires_privilege` | string | OPTIONAL | A privilege or scope label (e.g., `pentest`) that the session must hold. |
| `arg_schema` | JSON Schema | REQUIRED | Schema describing the typed parameters the model may emit. Feeds structured decoding. |

The `arg_schema` MUST be supplied to the structured-decoding layer (`CRP-SPEC-054`) so that the model can only emit syntactically valid intents for the selected tool.

A manifest SHOULD be immutable once published. A new version with a breaking change SHOULD use a new stable `name` or an explicit version field so that audit logs unambiguously identify which compiler was used.

Example manifest fields for a port-scanning tool (informative):

```json
{
  "name": "port_scan",
  "description": "Fingerprint open services on a single host.",
  "when_to_use": "when a target host is in authorised scope and needs service discovery",
  "when_not_to_use": "any host outside the authorised CIDR list",
  "effect": "read_only",
  "safety_class": "gated",
  "requires_privilege": "pentest",
  "arg_schema": {
    "type": "object",
    "properties": {
      "target": { "type": "string" },
      "stealth": { "type": "boolean", "default": true }
    },
    "required": ["target"]
  }
}
```

### 3.2 Intent Compiler (T2)

The **intent compiler** is the only place where a model-facing intent becomes a real-world invocation. This boundary is the central safety mechanism of the layer.

A conformant implementation MUST satisfy the following contract:

1. The model fills a **typed intent** whose fields are exactly those declared in `arg_schema`.
2. The intent is validated against `arg_schema` before compilation.
3. `compile(intent)` is deterministic and versioned. Given the same intent, it MUST produce the same invocation.
4. `compile()` MAY return an `argv` list, a structured request dict, or any other provider-specific invocation object.
5. The model MUST NOT be given an interface that allows it to emit raw `argv`, shell fragments, or unvalidated paths.
6. The compiled invocation MUST retain provenance metadata linking it back to the intent and to the active operation frame.

For example, a `PortScan` intent with `target` and `stealth` fields might compile to:

```json
{
  "argv": ["nmap", "-sS", "-oX", "-", "10.0.0.5"],
  "sandbox": "read_only",
  "provenance": {
    "intent": { "target": "10.0.0.5", "stealth": true },
    "manifest": "port_scan"
  }
}
```

The compiler MAY wrap the underlying binary or service with additional scope checks, network namespaces, read-only filesystems, or audit logging, provided those checks are deterministic and auditable.

### 3.3 Tool-Result Envelope (T4)

Every tool execution MUST be captured as a **Tool-Result Envelope**. The envelope separates structured result data (which may be carried in-window) from raw output (which is stored out-of-window by reference), attaches a parse confidence, and includes a provenance hash that links the result into the HMAC audit chain.

A conformant Tool-Result Envelope MUST contain the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `invocation` | object | REQUIRED | The compiled invocation, including provenance metadata. |
| `outcome` | enum | REQUIRED | `ok`, `error`, or `timeout`. |
| `parsed` | object | REQUIRED | Structured result kept in-window for the next operation. |
| `parse_confidence` | float | REQUIRED | Confidence score for the parsing step (0.0–1.0). |
| `raw_ref` | string | REQUIRED | Pointer to the raw tool output stored out-of-window (e.g., a store key or URI). |
| `provenance_hash` | string | REQUIRED | Hash linking this envelope into the CRP audit chain (`CRP-SPEC-011`). |

The capture process MUST:

1. Run the tool in the sandbox implied by its `effect` class.
2. Parse the raw output into a structured `parsed` object using a tool-specific parser.
3. Store the raw output outside the context window and record its reference in `raw_ref`.
4. Compute a `provenance_hash` over the invocation and the raw reference, and append it to the session's HMAC chain.
5. Return the envelope so the agent runtime can add it to the Cognitive State Object (`CRP-SPEC-030`) and continue the loop.

If parsing fails, the envelope MUST still be created with `outcome: error` and `parsed` containing the diagnostic information required for the agent to decide whether to retry, escalate, or halt.

### 3.4 Agent SDK Composition

The **Agent SDK** is a thin composition layer over the existing CRP primitives. Its purpose is to make the protocol reusable: a developer declares tools and a policy, and the protocol supplies the loop.

A conformant Agent SDK implementation MUST implement the following loop or an equivalent decomposition:

1. **Position:** Use the Semantic Task Layer (`CRP-SPEC-031`) to pick the next operation and the minimal tool subset for that operation.
2. **Parameterise:** For each selected tool, build a structured-decoding grammar from the manifest's `arg_schema` and ask the model to fill the typed intent. The output is guaranteed syntactically valid.
3. **Gate:** Apply the tool's `safety_class` before any side effect: `auto` may proceed; `gated` requires a policy check; `hitl` requires explicit human approval (`CRP-SPEC-033`). If approval is not granted, the step is skipped and the loop continues fail-closed.
4. **Execute:** Run the compiled invocation in a sandbox appropriate to its `effect` class.
5. **Capture:** Create a Tool-Result Envelope, store raw output by reference, and append the provenance hash to the audit chain.
6. **Safety and Quality:** Run the Decision Provenance Engine on the latest window, recording risk stage, risk level, quality tier, and confidence.
7. **Memory:** Add the envelope and any generated output to the CKF/CSO so subsequent operations can retrieve them.
8. **Narrate:** When the task is complete, produce a faithful, entailment-checked narrative of the run.

The SDK SHOULD expose this loop through a builder such as `crp.Agent(model, tools, policy, memory, stream, depth)`.

The SDK SHOULD NOT re-implement provider routing, token counting, continuation, or safety primitives when they are already supplied by `CRP-SPEC-008`, `CRP-SPEC-004`, `CRP-SPEC-006`, or `CRP-SPEC-033`.

### 3.5 Tool Manifest Indexing

Tool manifests SHOULD be indexed in the CKF (`CRP-SPEC-009`) as selection-as-retrieval documents. Indexing allows the Tool Capability Fabric (`CRP-SPEC-050`) and the Semantic Task Layer (`CRP-SPEC-031`) to discover tools by semantic similarity to the current operation rather than by static enumeration.

A conformant implementation SHOULD store, for each manifest:
- its `name` as a stable key;
- its `description`, `when_to_use`, and `when_not_to_use` as searchable text;
- its `effect` and `safety_class` as filterable tags;
- its `arg_schema` hash as a versioned reference.

### 3.6 Safety Class Behaviour

The `safety_class` field in a manifest determines the gate applied before the compiled invocation is executed.

| Safety class | Required gate |
|--------------|---------------|
| `auto` | No pre-execution gate beyond normal input validation and audit logging. Suitable for read-only, low-risk tools. |
| `gated` | A policy check against the active Safety Policy (`CRP-SPEC-006`) and session scope. Execution proceeds only if the check passes. |
| `hitl` | Human-in-the-loop approval (`CRP-SPEC-033`). If approval is not obtained within the configured timeout, the invocation MUST NOT run. |

The gate MUST run on the **compiled invocation**, not on the raw model output, so that the actual side effect is what is inspected.

### 3.7 Effect Class and Sandbox

The `effect` class informs the execution sandbox and the retry semantics of a tool.

| Effect class | Meaning |
|--------------|---------|
| `read_only` | Tool does not change state. It may be retried or cached freely. |
| `idempotent` | Tool may change state, but repeating it safely yields the same outcome. |
| `irreversible` | Tool causes a non-repeatable side effect (e.g., redacting a document). Such tools SHOULD carry `safety_class: hitl`. |

A conformant runtime MUST refuse to execute an `irreversible` tool unless its `safety_class` is `hitl` or an equivalent out-of-band governance approval is recorded.

---

## 4. Integration Points

The Agent Capability Layer is intentionally composed from existing CRP specifications. Implementations MUST respect the contracts of the prerequisites.

| Spec | Role in this layer |
|------|--------------------|
| CRP-SPEC-008 (Dispatch) | Routes LLM calls to the configured provider; the SDK does not duplicate routing. |
| CRP-SPEC-009 (CKF) | Indexes tool manifests and carries prior tool-result facts across operations. |
| CRP-SPEC-011 (Audit) | Receives provenance hashes from every tool invocation and intent compilation. |
| CRP-SPEC-031 (STL) | Positions each operation and selects the tool subset exposed to the model. |
| CRP-SPEC-054 (Structured Decoding) | Constrains intent generation to the manifest's `arg_schema`. |
| CRP-SPEC-050 (TCF) | Performs selection-as-retrieval over indexed manifests and supplies the tool subset. |
| CRP-SPEC-005 (DPE) | Scans each window for fabrication, hallucination, contradiction, and quality tier. |
| CRP-SPEC-006 (Safety Policy) | Supplies the policy rules for `gated` tools. |
| CRP-SPEC-033 (Safety Control Plane) | Supplies the checkpoint / human-in-the-loop mechanism for `hitl` tools. |
| CRP-SPEC-030 (CSO) | Carries the structured results and operation state across windows. |

### 4.1 Interaction with the Gateway

When the Agent SDK runs through a CRP Gateway, the gateway MUST continue to enforce Axiom 4: no `CRP-*` header reaches the LLM provider. Structured-decoding directives derived from `arg_schema` MUST be translated into provider-specific request fields as required by `CRP-SPEC-054`.

### 4.2 Interaction with the Audit Chain

Every `compile()` call and every Tool-Result Envelope MUST extend the session's HMAC audit chain. The `provenance_hash` MUST be computed over the invocation plus the raw-output reference so that tampering with either is detectable.

### 4.3 Interaction with the Cognitive State Object

Structured `parsed` results SHOULD be added to the CSO (`CRP-SPEC-030`) as facts. The CSO, not the raw tool output, is what subsequent operations retrieve through CDR/CDGR.

---

## 5. Conformance Requirements

A CRP-SPEC-059 conformant implementation MUST satisfy all of the following:

1. **Manifest conformance:** Every tool exposed to the model MUST be representable by the manifest structure in §3.1.
2. **Intent isolation:** The model MUST NOT be able to emit raw invocations, shell fragments, or unvalidated paths. It MUST emit only typed intents described by `arg_schema`.
3. **Compiler determinism:** `compile()` MUST be deterministic and versioned for a given manifest version.
4. **Structured parameterisation:** Intent generation MUST be constrained by `CRP-SPEC-054` using the manifest's `arg_schema`.
5. **Gate-before-side-effect:** `safety_class` gates MUST run on the compiled invocation before execution; `hitl` tools MUST NOT run without approval.
6. **Envelope completeness:** Every tool execution MUST produce a Tool-Result Envelope containing the fields in §3.3, including a valid `provenance_hash`.
7. **Raw-out-of-window:** Raw tool output MUST be stored outside the context window and referenced, not inlined, unless the output is small enough to be treated as a parsed fact.
8. **Audit linkage:** Every compile and capture step MUST extend the HMAC audit chain (`CRP-SPEC-011`).
9. **Axiom 4 preservation:** If the runtime forwards requests to an LLM provider, it MUST strip all `CRP-*` headers before forwarding.
10. **Fail-closed HITL:** A `hitl` step that times out or is rejected MUST result in the invocation being skipped, and the user MUST receive a graceful fallback, not a raw error.
11. **Declarative reuse:** The SDK MUST allow a new agent to be created by declaring tools and policy without requiring the developer to re-implement the positioning, safety, memory, or provenance loop.

---

## 6. Security Considerations

**Model cannot touch raw invocation surfaces.** By separating the typed intent from the compiled invocation, the specification removes the largest class of tool-use injection attacks: the model is never given an interface that maps directly to shell `argv`, file paths, or network requests.

**Deterministic compilation is auditable.** Because `compile()` is deterministic and versioned, an auditor can replay an intent and verify that the invocation produced was the one intended by the manifest.

**Safety classes are fail-closed.** `gated` and `hitl` tools require explicit approval. The default behaviour on timeout or rejection is to skip the invocation and continue, not to fall back to execution.

**Raw output by reference prevents context-window exfiltration and bloat.** Large or sensitive tool output is stored out-of-window; only a structured summary and reference pointer enter the context envelope.

**Provenance hashing detects tampering.** Any change to the invocation or the raw output invalidates the `provenance_hash`, surfacing as a broken audit chain (`CRP-Provenance-Chain-Integrity: BROKEN`).

**Privilege labels limit scope.** `requires_privilege` lets deployments reject tools at runtime when the session does not hold the required scope (e.g., a penetration-testing privilege).

**Axiom 4 remains absolute.** Even when the Agent SDK runs behind a gateway, no `CRP-*` header reaches the LLM provider.

---

## 7. References

- CRP-SPEC-001: Core Protocol
- CRP-SPEC-002: HTTP Headers
- CRP-SPEC-003: Context Envelope
- CRP-SPEC-004: Continuation and State Relay
- CRP-SPEC-005: Decision Provenance Engine
- CRP-SPEC-006: Safety Policy
- CRP-SPEC-007: Session Token
- CRP-SPEC-008: Dispatch & Provider Adaptation
- CRP-SPEC-009: Contextual Knowledge Fabric
- CRP-SPEC-011: Audit Trail
- CRP-SPEC-030: Cognitive State Object
- CRP-SPEC-031: Semantic Task Layer
- CRP-SPEC-033: Safety Control Plane
- CRP-SPEC-049: SLM Agent Execution Profile
- CRP-SPEC-050: Tool Capability Fabric and Operation Orchestration
- CRP-SPEC-054: Structured Decoding
- CRP-SPEC-056: Transparency and AG-UI Mapping

---

*End of CRP-SPEC-059.*
