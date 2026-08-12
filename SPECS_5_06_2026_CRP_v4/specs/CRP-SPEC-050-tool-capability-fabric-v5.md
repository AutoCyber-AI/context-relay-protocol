# CRP-SPEC-050: Tool Capability Fabric and Operation Orchestration

**Document:** CRP-SPEC-050  
**Title:** Context Relay Protocol (CRP) — Tool Capability Fabric and Operation Orchestration  
**Version:** 5.0.0  
**Status:** Stable — implemented in `crprotocol` 5.0.0 (Tool Capability Fabric)  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Proprietary (implementation)  
**Prerequisites:** CRP-SPEC-001 (Core), CRP-SPEC-002 (Headers), CRP-SPEC-003 (Envelope), CRP-SPEC-004 (Continuation), CRP-SPEC-006 (Safety Policy), CRP-SPEC-007 (Session Token), CRP-SPEC-012 (Multi-Agent Safety), CRP-SPEC-030 (Cognitive State Object), CRP-SPEC-031 (Semantic Task Layer), CRP-SPEC-049 (SLM Agent Execution Profile)

---

## Abstract

This specification defines the **Tool Capability Fabric (TCF)** and the **Operation State Machine** that let CRP select, sequence, and execute tools *outside* the language model. Instead of injecting every tool schema into the prompt and asking the model to choose, the protocol itself determines which capabilities are needed for the current Semantic Task Layer (STL) operation, composes a minimal **Tool Positioning Frame**, executes the resulting tool calls, and feeds the observations back into the Cognitive State Object (CSO) as typed facts. This keeps the model's context window focused on one cognitive operation at a time and lets small local models participate in agentic workflows that would otherwise exceed their reasoning capacity.

The TCF is language-, provider-, and runtime-neutral. A tool may be a local function, an MCP server capability, a sub-agent, a database query, or a web service. What matters to the protocol is the capability descriptor: what operation types the tool serves, what it consumes and produces, and how it is governed.

This specification also formalises **preventive safety** for tool use: a safety gate inspects the operation frame and tool parameters *before* the model generates output or the tool executes, and returns a contained halt response if the frame violates policy.

---

## 1. Introduction

### 1.1 The Tool-Injection Problem

Most agent frameworks expose tools to a model by listing every available tool schema in the system prompt. The model must then:

1. Infer the user's intent.
2. Decide which tool is relevant.
3. Generate valid arguments.
4. Reason about the result.
5. Decide what to do next.

All five jobs compete for the same context window. For a small local model, the combined load is beyond reliable operation: tool schemas alone can consume 10 K–50 K tokens, attention degrades over long tool descriptions, and argument errors multiply when the model must also track conversation history and task state.

CRP rejects this pattern. Under CRP, the protocol layer — not the model — drives information:

- The **STL** (CRP-SPEC-031) decides *what cognitive operation* is needed.
- The **TCF** decides *which capabilities* can advance that operation.
- The **Operation State Machine** tracks *where the agent is* in the plan.
- The **CSO** carries *what has been learned* between operations.
- The model is positioned on a focused frame that says: *"For this operation, use one of these 1–3 tools."*

### 1.2 Design Goals

1. **Tool selection is a protocol function**, not an LLM function.
2. **The model sees only the tools it needs for the current operation**, never the full catalogue.
3. **Tool results become typed facts in the CSO**, not raw text in the prompt.
4. **Execution order is explicit** — sequential, parallel, or conditional — and auditable.
5. **Safety is preventive**: the frame is inspected before generation and before execution.
6. **No hybrid auto-routing**: the assigned model does the work; the ecosystem amplifies it.

### 1.3 Non-Goals

- This spec does not define how tools are implemented internally (MCP, REST, function call, sub-agent).
- It does not train or fine-tune models for tool use.
- It does not replace STL (CRP-SPEC-031) or CSO (CRP-SPEC-030); it consumes and extends them.

---

## 2. Terminology

**Capability:** A callable unit exposed through the TCF. A capability may be a tool, an MCP tool, a sub-agent, a retrieval query, or any other executable primitive.

**Capability Descriptor:** A machine-readable declaration of a capability's inputs, outputs, operation types, dependencies, cost profile, and governance metadata.

**Tool Capability Fabric (TCF):** The protocol-level registry and retrieval system that stores capability descriptors and returns the minimal relevant set for a given operation frame.

**Operation Frame:** The focused assignment the STL produces for one cognitive operation (CRP-SPEC-031 §5).

**Tool Positioning Frame:** A small extension of the Operation Frame that adds the 1–3 capabilities the model may call for this operation, plus their schemas and output contracts.

**Operation State Machine:** The explicit lifecycle of an agentic task: `INTENT_CLASSIFIED → OPERATION_POSITIONED → TOOL_SELECTED → TOOL_EXECUTED → OPERATION_VERIFIED → INTEGRATED → COMPLETE`, with loops and halts.

**Tool Observation:** A typed fact produced by executing a capability and stored in the CSO.

**Preventive Halt:** A safety decision that stops an operation before the model generates output or a tool executes, returning the problematic frame for inspection.

---

## 3. Tool Capability Fabric

### 3.1 Capability Descriptor

Every capability registered in the TCF MUST provide a descriptor. The canonical representation is JSON; the schema is defined in `schemas/capability-descriptor.json`.

```json
{
  "capability_id": "query_regulation",
  "kind": "tool",
  "version": "1.2.0",
  "operation_types": ["RETRIEVE", "ANALYSE"],
  "serves_intents": ["compliance_lookup", "evidence_gathering"],
  "input_schema": {
    "type": "object",
    "properties": {
      "regulation": {"type": "string"},
      "topic": {"type": "string"}
    },
    "required": ["topic"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "articles": {"type": "array", "items": {"type": "string"}},
      "summary": {"type": "string"}
    }
  },
  "produces_facts": true,
  "consumes_facts": ["regulation_corpus"],
  "dependencies": [],
  "mutually_exclusive_with": ["web_search"],
  "cost_profile": {
    "tokens": 120,
    "latency_ms": 400,
    "safety_class": "read-only"
  },
  "data_residency": "EU",
  "allowed_policy_domains": ["comply", "legal"],
  "embedding_vector": [0.01, -0.04, ...],
  "embedding_model": "all-MiniLM-L6-v2",
  "metadata": {
    "provider": "crp-comply",
    "description": "Query the embedded regulation corpus for relevant articles."
  }
}
```

### 3.2 Required Descriptor Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `capability_id` | string | YES | Stable identifier. |
| `kind` | string | YES | `tool`, `mcp-tool`, `agent`, `query`, `service`. |
| `version` | string | YES | SemVer of the descriptor. |
| `operation_types` | string[] | YES | STL operation types this capability serves (CRP-SPEC-031 §3). |
| `serves_intents` | string[] | NO | Intent tokens for coarse filtering. |
| `input_schema` | JSON Schema | YES | Valid arguments. |
| `output_schema` | JSON Schema | YES | Returned structure. |
| `produces_facts` | boolean | YES | Whether output should be stored in the CSO. |
| `consumes_facts` | string[] | NO | Fact categories the capability may read. |
| `dependencies` | string[] | NO | Capability IDs that must run first. |
| `mutually_exclusive_with` | string[] | NO | Capability IDs that MUST NOT be offered together. |
| `cost_profile` | object | YES | `tokens`, `latency_ms`, `safety_class`. |
| `data_residency` | string | NO | Jurisdiction constraint for policy enforcement. |
| `allowed_policy_domains` | string[] | NO | Policy domains under which the capability is permitted. |
| `embedding_vector` | number[] | REC | Dense vector for semantic retrieval. |
| `embedding_model` | string | REC | Model ID used for the vector. |
| `metadata` | object | NO | Human-readable description, provider, tags. |

### 3.3 TCF Indexing

The TCF MUST support retrieval by:

1. **Operation type:** exact match on `operation_types`.
2. **Intent token:** exact or prefix match on `serves_intents`.
3. **Semantic similarity:** cosine similarity over `embedding_vector`.
4. **Schema compatibility:** whether the capability's `input_schema` can be satisfied by facts already in the CSO.

Implementations MAY use approximate nearest-neighbour search, sparse keyword indexes, or exact filtering as appropriate for scale.

### 3.4 Policy Pre-Filter

Before any capability is offered to the model or executed, the gateway MUST apply the active `CRP-Safety-Policy`:

- Capabilities whose `safety_class` is blocked by policy are removed.
- Capabilities whose `data_residency` conflicts with `CRP-Compliance-Data-Residency` are removed.
- Capabilities whose `allowed_policy_domains` do not intersect the session's policy domains are removed.
- Capabilities in the session's explicit blocklist (`CRP-Tool-Blocklist`) are removed.
- Capabilities not in the session's explicit allowlist (`CRP-Tool-Allowlist`), when an allowlist is present, are removed.

---

## 4. Protocol-Level Tool Selection

### 4.1 Selection Algorithm

For each positioned operation, the gateway MUST execute the following algorithm to produce the Tool Positioning Frame:

```
1. Start with the Operation Frame from the STL (operation_type, assignment, frame_content, goal_compass).
2. Retrieve from TCF all capabilities whose operation_types include the current operation_type.
3. Apply the policy pre-filter (§3.4).
4. Score remaining capabilities by:
   a. Semantic similarity to the operation assignment and frame_content.
   b. Schema compatibility with facts already in the CSO.
   c. Intent overlap with the user's request.
   d. Inverse cost (prefer lower latency/token cost).
5. Apply dependency resolution: if a high-scoring capability requires another, include the dependency first.
6. Apply mutual-exclusion rules: drop conflicting pairs, keeping the higher-scored item.
7. Select the top-K capabilities, where K is determined by the model's capability profile (§4.2).
8. Compose the Tool Positioning Frame (§4.3).
```

### 4.2 Frame Size by Model Capability Profile

The `CRP-Agent-Capability-Profile` header tells the protocol how many capabilities the model can reliably reason about in one operation:

| Profile | Max capabilities per frame | Typical use |
|---------|---------------------------|-------------|
| `frontier` | 5–7 | Large models with native tool reasoning. |
| `capable-local` | 3–4 | 8B–14B tool-tuned models with grammar. |
| `small-local` | 1–2 | ≤8B models; one preferred tool plus fallback. |

The default is `frontier`. The gateway MAY reduce the frame further based on observed error rates.

### 4.3 Tool Positioning Frame

The Tool Positioning Frame is a JSON object attached to the Operation Frame:

```json
{
  "tool_positioning_frame": {
    "operation_type": "RETRIEVE",
    "selection_reason": "operation_requires_factual_lookup",
    "capabilities": [
      {
        "capability_id": "query_regulation",
        "assignment": "Use this tool when you need a regulation article relevant to the topic.",
        "input_schema": {...},
        "example_call": {"topic": "high-risk AI system registration"},
        "output_contract": "Return only the JSON object the tool produces."
      }
    ],
    "constraints": {
      "max_calls": 1,
      "allowed_depth": "D2",
      "structured_output_mode": "json-schema"
    }
  }
}
```

The frame is rendered into the prompt as a compact instruction. The model is told *which* capabilities are available for this operation, *what each does*, and *what form the output must take*. It is not told about other capabilities in the registry.

### 4.4 Model Output Contract

For tool-selection operations, the model MUST emit a structured output matching the contract in the frame. The contract is translated to provider-specific constrained decoding:

- OpenAI / Anthropic: `response_format` or `tools[].function.parameters`
- Ollama: `format`
- vLLM / SGLang: `guided_json` / `guided_grammar`
- llama.cpp: GBNF grammar

The contract MUST be deterministic given the frame so the gateway can validate the model's output without a second LLM call.

---

## 5. Operation State Machine

### 5.1 States

| State | Description |
|-------|-------------|
| `INTENT_CLASSIFIED` | STL has mapped the user request to an operation plan. |
| `OPERATION_POSITIONED` | Operation Frame and Tool Positioning Frame built; model about to be called. |
| `TOOL_SELECTED` | Model emitted a valid tool-selection output; parameters parsed and validated. |
| `TOOL_EXECUTED` | Capability executed; observation stored in CSO. |
| `OPERATION_VERIFIED` | DPE / safety verifier checked the operation output. |
| `INTEGRATED` | Result merged into CSO; next operation prepared. |
| `COMPLETE` | Final response assembled and returned. |
| `HALTED` | Preventive safety or failure halt; no further tool/model calls. |

### 5.2 Transitions

```
INTENT_CLASSIFIED → OPERATION_POSITIONED
OPERATION_POSITIONED → TOOL_SELECTED (model emits tool call)
OPERATION_POSITIONED → OPERATION_VERIFIED (no tool needed, direct generation)
TOOL_SELECTED → HALTED (preventive safety violation)
TOOL_SELECTED → TOOL_EXECUTED (validation passed)
TOOL_EXECUTED → OPERATION_VERIFIED
OPERATION_VERIFIED → INTEGRATED
INTEGRATED → OPERATION_POSITIONED (next operation)
INTEGRATED → COMPLETE (plan finished)
```

### 5.3 Concurrency

Independent operations MAY execute in parallel when the plan declares them branchable. Tool observations from parallel branches are merged into the CSO only after both branches reach `OPERATION_VERIFIED`.

---

## 6. Tool Execution Semantics

### 6.1 Execution Order

The gateway executes capabilities in the order determined by the dependency resolver. A capability MUST NOT execute before its dependencies have produced observations.

### 6.2 Validation

Before executing a capability, the gateway MUST:

1. Validate arguments against the capability's `input_schema`.
2. Apply parameter-level safety policy (e.g., no PII, no cross-border data).
3. Check rate limits and safety-budget balance (CRP-SPEC-012).
4. Confirm the capability is in the current Tool Positioning Frame.

If validation fails, the operation moves to `HALTED` with a preventive halt response.

### 6.3 Observation Storage

A successful execution produces a **Tool Observation**. Observations are stored in the CSO as typed facts with provenance:

```json
{
  "fact_id": "f_obs_0192837465",
  "fact_type": "TOOL_OBSERVATION",
  "capability_id": "query_regulation",
  "operation_type": "RETRIEVE",
  "window_id": "win_...",
  "provenance": {
    "source_type": "TOOL",
    "source_id": "query_regulation",
    "invocation_id": "inv_...",
    "timestamp": "2026-06-26T10:27:53Z"
  },
  "payload": {...},
  "grounding_class": "CONTEXT_GROUNDED"
}
```

### 6.4 Feedback Loop

After integration, the STL uses the new observations to:

- Decide whether the current operation is complete.
- Propose the next operation.
- Retrieve a new Tool Positioning Frame for that operation.

The model never sees the raw observation unless the next frame explicitly includes it as `frame_content`.

---

## 7. Header Fields

All header fields use the `CRP-` prefix and are subject to Axiom 4 stripping before forwarding to LLM providers.

### 7.1 CRP-Agent-Capability-Profile

**Direction:** BOTH  
**Required:** RECOMMENDED

**Definition:** Advertises the execution profile of the attached model/ecosystem.

**Syntax:**
```abnf
CRP-Agent-Capability-Profile = "frontier" / "capable-local" / "small-local"
```

### 7.2 CRP-Agent-Operation-State

**Direction:** RES  
**Required:** RECOMMENDED

**Definition:** The current state of the Operation State Machine.

**Syntax:**
```abnf
CRP-Agent-Operation-State = "INTENT_CLASSIFIED" / "OPERATION_POSITIONED" /
                            "TOOL_SELECTED" / "TOOL_EXECUTED" /
                            "OPERATION_VERIFIED" / "INTEGRATED" /
                            "COMPLETE" / "HALTED"
```

### 7.3 CRP-Agent-Operation-Type

**Direction:** BOTH  
**Required:** RECOMMENDED

**Definition:** The active STL operation type (CRP-SPEC-031 §3).

**Syntax:**
```abnf
CRP-Agent-Operation-Type = "RETRIEVE" / "SYNTHESISE" / "ANALYSE" /
                           "COMPARE" / "GENERATE" / "TRANSFORM" /
                           "EVALUATE" / "PLAN"
```

### 7.4 CRP-Agent-Operation-Plan

**Direction:** RES  
**Required:** OPTIONAL

**Definition:** A hash or compact representation of the planned operation sequence.

**Syntax:**
```abnf
CRP-Agent-Operation-Plan = plan-hash
plan-hash = "sha256:" 64HEXDIG / operation-sequence
operation-sequence = operation *( "," OWS operation )
```

### 7.5 CRP-Tool-Positioning-Frame

**Direction:** BOTH  
**Required:** OPTIONAL when tool use is expected

**Definition:** The minimal set of capabilities selected for the current operation. In requests, a client MAY propose a frame; in responses, the gateway reports the frame it used.

**Syntax:**
```abnf
CRP-Tool-Positioning-Frame = base64url-encoded-json-object
```

### 7.6 CRP-Tool-Observation-Count

**Direction:** RES  
**Required:** OPTIONAL

**Definition:** Number of tool observations stored in the CSO for this session.

**Syntax:**
```abnf
CRP-Tool-Observation-Count = 1*DIGIT
```

### 7.7 CRP-Safety-Preventive-Halt

**Direction:** RES  
**Required:** OPTIONAL

**Definition:** Indicates that a preventive safety gate halted the operation. The value is a URI or inline reference to the halted frame.

**Syntax:**
```abnf
CRP-Safety-Preventive-Halt = "frame:" frame-id / "uri:" URI
```

### 7.8 CRP-Tool-Allowlist

**Direction:** REQ  
**Required:** OPTIONAL

**Definition:** A comma-separated list of capability IDs permitted for this session or window.

**Syntax:**
```abnf
CRP-Tool-Allowlist = capability-id *( "," OWS capability-id )
capability-id = 1*( ALPHA / DIGIT / "-" / "_" / "." )
```

### 7.9 CRP-Tool-Blocklist

**Direction:** REQ  
**Required:** OPTIONAL

**Definition:** A comma-separated list of capability IDs prohibited for this session or window.

**Syntax:**
```abnf
CRP-Tool-Blocklist = capability-id *( "," OWS capability-id )
```

### 7.10 CRP-Structured-Output-Contract

**Direction:** BOTH  
**Required:** OPTIONAL

**Definition:** Declares the constrained-output contract for this operation.

**Syntax:**
```abnf
CRP-Structured-Output-Contract = contract-type "/" contract-ref
contract-type = "json-schema" / "grammar" / "regex" / "tool-call"
contract-ref = "sha256:" 64HEXDIG / inline-value
```

---

## 8. Session Token and CSO Extensions

CRP-SPEC-007 session tokens and CRP-SPEC-030 Cognitive State Objects SHOULD include:

| Field | Type | Description |
|-------|------|-------------|
| `capability_profile` | string | Active `CRP-Agent-Capability-Profile`. |
| `operation_state` | string | Current state-machine state. |
| `operation_type` | string | Current STL operation. |
| `operation_plan_hash` | string | Hash of planned operation sequence. |
| `tcf_selection` | object[] | Selected capability IDs with selection reason. |
| `tool_observations` | object[] | Typed facts from executed capabilities. |
| `preventive_halt_history` | object[] | Record of halted frames. |
| `structured_output_contract` | object | Active contract for current operation. |

---

## 9. Context Envelope Profile

The Context Envelope (CRP-SPEC-003) MAY contain a `tool_orchestration` object:

```json
{
  "tool_orchestration": {
    "capability_profile": "small-local",
    "operation_state": "OPERATION_POSITIONED",
    "operation_type": "RETRIEVE",
    "operation_plan_hash": "sha256:...",
    "positioning_frame": {...},
    "structured_output_contract": {
      "type": "tool-call",
      "schema_hash": "sha256:..."
    },
    "preventive_halt": null
  }
}
```

The Envelope Builder uses this profile to decide how much context to pack and whether the current window is a tool-selection window or a synthesis window.

---

## 10. Preventive Safety

### 10.1 Policy Grammar Extensions

CRP-SPEC-006 safety policies are extended with the following directives:

```
allow-tools capability-id [, capability-id]*
block-tools capability-id [, capability-id]*
require-oversight-for operation-type [when condition]
max-tool-calls-per-operation integer
block-parameter capability-id parameter-name [when condition]
```

### 10.2 Inspection Points

A preventive safety gate MUST inspect:

1. The Operation Frame and Tool Positioning Frame before the model call.
2. The model's tool-selection output before execution.
3. The resolved tool arguments before execution.
4. The operation state transition before advancing.

### 10.3 Preventive Halt Response

If any inspection point fails, the gateway MUST return HTTP 451 with a body containing the actual problematic frame:

```json
{
  "crp_halt_reason": "PREVENTIVE_SAFETY_VIOLATION",
  "halt_point": "TOOL_SELECTED",
  "problematic_frame": {
    "operation_type": "RETRIEVE",
    "capability_id": "web_search",
    "violation": "data_residency_policy_EU_only",
    "blocked_parameter": "region=us-east-1",
    "policy_rule": "block-tools web_search when data_residency=EU"
  },
  "session_id": "crp_sess_...",
  "audit_trail_uri": "https://comply.crprotocol.io/t/...",
  "headers": {
    "CRP-Safety-Preventive-Halt": "frame:<YOUR_HF_VALUE>"
  }
}
```

The LLM never receives the problematic frame. Downstream consumers MUST treat a 451 with `crp_halt_reason` as a hard stop.

---

## 11. Gateway Behaviour

A CRP agentic-execution conformant gateway MUST:

1. Parse the headers in §7 and the session-token fields in §8.
2. Maintain the Operation State Machine for each session.
3. Query the TCF for capabilities matching the current STL operation.
4. Apply the policy pre-filter (§3.4) before any capability is offered or executed.
5. Compose the Tool Positioning Frame respecting the model's capability profile (§4.2).
6. Translate `CRP-Structured-Output-Contract` into provider-specific constrained decoding.
7. Validate tool-selection output against the frame before execution.
8. Execute capabilities, store observations in the CSO, and advance the state machine.
9. Strip ALL `CRP-*` headers before forwarding to the LLM provider (Axiom 4).
10. NEVER auto-escalate to a frontier model. Routing is explicit configuration, not a runtime decision.

---

## 12. SLM Amplification Profile

The protocol MUST follow the **SLM Amplification Rule**: the smaller the model, the more the ecosystem does.

| Model class | Capability profile | Typical orchestration |
|-------------|-------------------|----------------------|
| Frontier (70B+) | `frontier` | Full multi-tool frame; model may plan and reflect. |
| Capable local (8B–14B) | `capable-local` | 3–4 tools per frame; STL drives plan; verifier on ANALYSE/EVALUATE. |
| Small local (≤8B) | `small-local` | 1–2 tools per frame; constrained decoding; operation state machine explicit; CSO carries all progress. |

This is amplification, not limitation. The protocol adds structure so the model can focus on the one cognitive job it is positioned to do.

---

## 13. Conformance

A conforming implementation MUST:

1. Register every capability it exposes in a TCF descriptor.
2. Select capabilities using the algorithm in §4.1.
3. Track operation state using the states in §5.1.
4. Store successful tool results as CSO observations (§6.3).
5. Enforce preventive safety before generation and execution (§10).
6. Strip `CRP-*` headers from provider requests (Axiom 4).
7. Not perform automatic hybrid routing.

---

## 14. References

- CRP-SPEC-002: HTTP Headers
- CRP-SPEC-003: Context Envelope
- CRP-SPEC-006: Safety Policy
- CRP-SPEC-007: Session Token
- CRP-SPEC-012: Multi-Agent Safety
- CRP-SPEC-030: Cognitive State Object
- CRP-SPEC-031: Semantic Task Layer
- CRP-SPEC-049: SLM Agent Execution Profile

---

## 15. Appendix: Example Flow

**User request:** *"Is my AI system high-risk under the EU AI Act?"*

1. **INTENT_CLASSIFIED** — STL classifies: `ANALYSE` → `RETRIEVE` → `EVALUATE`.
2. **OPERATION_POSITIONED** — First operation is `RETRIEVE`.
   - TCF retrieves: `query_regulation`, `lookup_gdpr`.
   - Policy filter removes `web_search` due to EU data-residency rule.
   - Frame size `small-local` → select 1 capability: `query_regulation`.
   - `CRP-Tool-Positioning-Frame` emitted.
3. **TOOL_SELECTED** — SLM emits call: `query_regulation({"topic": "high-risk AI system"})`.
4. **TOOL_EXECUTED** — Capability runs; observation stored in CSO.
5. **OPERATION_VERIFIED** — DPE checks grounding.
6. **INTEGRATED** — CSO updated; next operation `EVALUATE`.
7. **OPERATION_POSITIONED** — TCF retrieves `classify_ai_act_risk`; frame composed.
8. ... continues until `COMPLETE`.
