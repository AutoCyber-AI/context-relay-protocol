# CRP-SPEC-049: SLM Agent Execution Profile

**Document:** CRP-SPEC-049  
**Title:** Context Relay Protocol (CRP) — Small Language Model (SLM) Agent Execution Profile  
**Version:** 5.0.0  
**Status:** Stable — implemented in `crprotocol` 5.0.0 (positioned-tool-loop)  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Proprietary (implementation)  
**Prerequisites:** CRP-SPEC-001 (Core), CRP-SPEC-002 (Headers), CRP-SPEC-003 (Envelope), CRP-SPEC-004 (Continuation), CRP-SPEC-007 (Session Token), CRP-SPEC-016 (Gateway Service), CRP-SPEC-031 (Semantic Task Layer), CRP-SPEC-050 (Tool Capability Fabric)

---

## Abstract

This specification defines CRP protocol primitives that enable small language models (SLMs, ≤ 15 B parameters) to participate reliably in agentic workflows such as CRP Comply. It introduces capability advertisement, dynamic tool-subset negotiation, structured-decoding directives, prompt-cache lifecycle hints, and execution-mode contracts. These primitives are carried as CRP HTTP headers and session-token fields and are translated by the CRP Gateway into provider-specific request semantics, while obeying Axiom 4: no `CRP-*` header reaches the LLM provider.

CRP does **not** treat SLMs as limited models that must be protected by capability tiers or escalated to frontier models. Instead, it amplifies the SLM through the surrounding protocol: the Semantic Task Layer (CRP-SPEC-031) positions the model on one operation at a time, and the Tool Capability Fabric (CRP-SPEC-050) selects the minimal tool set for that operation. This specification is the execution-level companion to those two positioning and orchestration specs.

---

## 1. Introduction

### 1.1 Motivation

Frontier models can ingest long system prompts, dozens of tool schemas, and multi-turn ReAct instructions in a single call. Small local models cannot. Recent work (TinyAgent, XGrammar-2, Less-is-More, Gorilla) shows that SLMs become reliable agents when the execution path is shaped to their strengths: smaller tool sets, constrained decoding, stable prompt prefixes for KV-cache reuse, and explicit operation sequencing performed by the protocol rather than the model.

CRP already provides context relay, safety governance, continuation, audit, the Semantic Task Layer, and the Tool Capability Fabric. This specification adds the **execution contract** that lets gateways and inference servers expose the decoding and loop features the SLM can use, and lets the protocol choose the right execution mode for that model.

### 1.2 Goals

1. Make SLM-powered agents a first-class CRP use case without breaking existing CRP invariants.
2. Let a model, worker, or gateway advertise concrete decoding and loop capabilities.
3. Enable dynamic negotiation of the tool subset exposed to the model on each turn, as determined by CRP-SPEC-050.
4. Carry structured-decoding directives in a provider-agnostic form.
5. Keep prompt prefixes byte-stable so inference servers can reuse KV state.
6. Support explicit, configurable execution modes (single-shot, planner-actor, verifier, etc.).

### 1.3 Non-Goals

- This spec does not train or fine-tune models.
- It does not replace MCP, A2A, or ACP; it complements them with CRP governance metadata.
- It does not mandate a particular inference server.
- It does **not** define hybrid edge-to-frontier routing as a protocol mechanism; see §4.9.

---

## 2. Terminology

**Capability profile:** A coarse runtime class (`frontier`, `capable-local`, `small-local`) used by the gateway to decide framing parameters such as the number of tools per operation frame.

**Tool subset:** The list of tool identifiers enabled for a single window, as produced by the Tool Capability Fabric (CRP-SPEC-050).

**Structured-decoding directive:** A CRP-level request to constrain LLM output to a JSON schema, grammar, or regex.

**Prompt-cache hint:** A directive indicating how many leading tokens of a rendered prompt must remain byte-stable across turns.

**Execution mode:** The loop contract the agent runtime uses for a given operation or task.

---

## 3. Capability Advertisement

### 3.1 CRP-Agent-Capability-Profile

**Direction:** BOTH  
**Required:** RECOMMENDED

**Definition:** The execution profile of the model/ecosystem serving this request. Unlike a capability *tier*, this profile does not limit what the model may do; it informs the gateway how much scaffolding to provide.

**Syntax:**
```abnf
CRP-Agent-Capability-Profile = "frontier" / "capable-local" / "small-local"
```

**Values:**

| Value | Typical models | Protocol scaffolding |
|-------|----------------|----------------------|
| `frontier` | Claude 3.5/4, GPT-4o/o3, DeepSeek-V3 | Full multi-tool frame; model may plan and reflect |
| `capable-local` | Qwen2.5-14B, xLAM-2-8B, ToolACE-8B, Llama-3.1-8B with grammar | 3–4 tools per frame; STL drives plan; verifier on ANALYSE/EVALUATE |
| `small-local` | Qwen2.5-3B/7B, Llama-3.2-3B, Phi-4-mini, xLAM-1B/3B | 1–2 tools per frame; constrained decoding; explicit operation state machine; CSO carries all progress |

The profile is advisory. A gateway MAY override a client-provided profile based on health-frame data or observed quality history, but it MUST NOT use the profile to refuse a request or auto-escalate to a different model class.

### 3.2 CRP-Agent-Model-Capabilities

**Direction:** BOTH  
**Required:** OPTIONAL

**Definition:** A machine-readable list of concrete capabilities supported by the attached model/server.

**Syntax:**
```abnf
CRP-Agent-Model-Capabilities = capability *( "," OWS capability )
capability = "tool-call" / "structured-output" / "prefix-cache" /
             "streaming" / "grammar" / "function-call-json" /
             "constrained-json" / "logprobs"
```

**Example:**
```
CRP-Agent-Model-Capabilities: tool-call,grammar,prefix-cache,streaming
```

---

## 4. Header Fields

All header fields use the `CRP-` prefix and are subject to Axiom 4 stripping before forwarding to LLM providers.

### 4.1 CRP-Agent-Tool-Subset

**Direction:** BOTH  
**Required:** RECOMMENDED when `CRP-Agent-Capability-Profile` is `capable-local` or `small-local`

**Definition:** The tool identifiers enabled for this window. Tools outside this subset MUST NOT be injected into the prompt. The subset SHOULD be produced by the Tool Capability Fabric (CRP-SPEC-050).

**Syntax:**
```abnf
CRP-Agent-Tool-Subset = tool-id *( "," OWS tool-id )
tool-id = 1*( ALPHA / DIGIT / "-" / "_" / "." )
```

**Example:**
```
CRP-Agent-Tool-Subset: query_regulation,lookup_gdpr,request_clarification
```

### 4.2 CRP-Agent-Execution-Mode

**Direction:** BOTH  
**Required:** OPTIONAL

**Definition:** The loop contract the agent runtime must use.

**Syntax:**
```abnf
CRP-Agent-Execution-Mode = "single-shot" / "planner-actor" / "react" /
                          "verifier" / "retrieval-then-answer" /
                          "positioned-tool-loop"
```

**Values:**

| Value | Meaning |
|-------|---------|
| `single-shot` | One LLM call; no tool loop |
| `planner-actor` | Plan once, execute tools, synthesise |
| `react` | Full multi-turn ReAct with reflection |
| `verifier` | Review/verify a previous window's output |
| `retrieval-then-answer` | Retrieve evidence, then answer in one call |
| `positioned-tool-loop` | Default CRP mode: STL positions each operation, TCF selects tools, model emits calls |

### 4.3 CRP-Agent-Loop-Guard

**Direction:** REQ  
**Required:** OPTIONAL

**Definition:** Hard limits on the agent loop for this window. These are safety bounds, not capability limits.

**Syntax:**
```abnf
CRP-Agent-Loop-Guard = max-iters "/" timeout-ms [ "/" max-duplicates ]
max-iters = 1*DIGIT
timeout-ms = 1*DIGIT
max-duplicates = 1*DIGIT
```

**Example:**
```
CRP-Agent-Loop-Guard: 3/120000/2
```

### 4.4 CRP-LLM-Structured-Output-Mode

**Direction:** REQ  
**Required:** OPTIONAL

**Definition:** Requests provider-agnostic constrained decoding.

**Syntax:**
```abnf
CRP-LLM-Structured-Output-Mode = "json-schema" / "grammar" / "regex" / "off"
```

**Default:** `off`

### 4.5 CRP-LLM-Structured-Output-Schema

**Direction:** REQ  
**Required:** OPTIONAL; REQUIRED when `CRP-LLM-Structured-Output-Mode` is `json-schema` or `grammar`

**Definition:** The schema or grammar used to constrain output. MAY be an inline JSON value or a SHA-256 hash of a schema registered out-of-band.

**Syntax:**
```abnf
CRP-LLM-Structured-Output-Schema = "sha256:" 64HEXDIG / inline-json-schema
```

### 4.6 CRP-LLM-Prompt-Cache-Hint

**Direction:** REQ  
**Required:** OPTIONAL

**Definition:** Indicates that the first N tokens of the rendered prompt must remain byte-stable across turns to enable KV-cache reuse.

**Syntax:**
```abnf
CRP-LLM-Prompt-Cache-Hint = "pin:" pin-tokens [ "/" stable-hash ]
pin-tokens = 1*DIGIT
stable-hash = "sha256:" 64HEXDIG
```

**Example:**
```
CRP-LLM-Prompt-Cache-Hint: pin:2048/sha256:abc123...
```

### 4.7 CRP-Agent-Operation-State

**Direction:** RES  
**Required:** RECOMMENDED

**Definition:** The current state of the Operation State Machine (CRP-SPEC-050 §5).

**Syntax:**
```abnf
CRP-Agent-Operation-State = "INTENT_CLASSIFIED" / "OPERATION_POSITIONED" /
                            "TOOL_SELECTED" / "TOOL_EXECUTED" /
                            "OPERATION_VERIFIED" / "INTEGRATED" /
                            "COMPLETE" / "HALTED"
```

### 4.8 CRP-Agent-Operation-Type

**Direction:** BOTH  
**Required:** RECOMMENDED

**Definition:** The active STL operation type (CRP-SPEC-031 §3).

**Syntax:**
```abnf
CRP-Agent-Operation-Type = "RETRIEVE" / "SYNTHESISE" / "ANALYSE" /
                           "COMPARE" / "GENERATE" / "TRANSFORM" /
                           "EVALUATE" / "PLAN"
```

### 4.9 Removed Headers

The following headers from earlier drafts are **removed** from this specification:

- `CRP-Agent-Model-Tier` — replaced by `CRP-Agent-Capability-Profile`.
- `CRP-Routing-Target` — CRP does not support hybrid edge-to-frontier routing as a protocol mechanism. If a deployment wishes to use a frontier model, it MUST configure that model as the explicit provider.
- `CRP-Routing-Decision` — removed with routing target.

Rationale: automatic escalation to a frontier model violates the SLM-first design principle and is not acceptable for air-gapped, privacy-first, or cost-constrained deployments.

---

## 5. Session Token Fields

CRP-SPEC-007 session tokens MAY include the following optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `capability_profile` | string | Active `CRP-Agent-Capability-Profile` |
| `tool_subset_hash` | string | `sha256:` of the enabled tool list |
| `execution_mode` | string | Active `CRP-Agent-Execution-Mode` |
| `cache_pin_hash` | string | `sha256:` of the stable prefix |
| `model_capabilities` | string[] | Capability tokens from `CRP-Agent-Model-Capabilities` |
| `loop_guard` | object | `{max_iters, timeout_ms, max_duplicates}` |
| `operation_state` | string | Current Operation State Machine state (CRP-SPEC-050) |
| `operation_type` | string | Current STL operation (CRP-SPEC-031) |

---

## 6. Context Envelope Profile

The Context Envelope (CRP-SPEC-003) MAY contain a `model_profile` object:

```json
{
  "model_profile": {
    "capability_profile": "small-local",
    "capabilities": ["tool-call", "grammar", "streaming"],
    "tool_subset": ["query_regulation", "lookup_gdpr"],
    "execution_mode": "positioned-tool-loop",
    "structured_output": {
      "mode": "json-schema",
      "schema_hash": "sha256:..."
    },
    "cache_hint": {
      "pin_tokens": 2048,
      "stable_hash": "sha256:..."
    }
  }
}
```

The Envelope Builder uses this profile to control packing depth, continuation triggers, and whether to invoke the Semantic Task Layer for chunking. Tool selection itself is performed by the Tool Capability Fabric (CRP-SPEC-050).

---

## 7. Gateway Behaviour

A CRP-SLM conformant gateway MUST:

1. Parse the headers in §4 and the session-token fields in §5.
2. Keep the pinned prefix byte-stable per `CRP-LLM-Prompt-Cache-Hint`.
3. Accept the tool subset provided by the Tool Capability Fabric (CRP-SPEC-050) and expose it through `CRP-Agent-Tool-Subset`.
4. Translate `CRP-LLM-Structured-Output-*` into provider-specific request fields:
   - OpenAI / Anthropic: `response_format`, `tools[].function.parameters`
   - Ollama: `format`
   - vLLM / SGLang: `guided_json`, `guided_grammar`, structural tags
   - llama.cpp: `grammar` (GBNF)
5. Strip ALL `CRP-*` headers before forwarding to the LLM provider (Axiom 4).
6. Refuse to implement automatic escalation to a frontier model. Routing is explicit configuration.
7. Update `CRP-Agent-Operation-State` and `CRP-Agent-Operation-Type` on every response.

---

## 8. SLM Amplification, Not Limitation

The capability profile is **not** a limit on what the model may attempt. It is a dial that controls how much scaffolding the protocol provides:

| Profile | What the protocol does |
|---------|------------------------|
| `frontier` | Lets the model see more tools and plan more freely; still uses STL/TCF for efficiency |
| `capable-local` | Selects 3–4 tools per frame, runs verifier operations, keeps state in CSO |
| `small-local` | Selects 1–2 tools per frame, uses strict structured output, advances the operation state machine explicitly |

The smaller the model, the more the protocol reasons *around* it. This is the **SLM Amplification Rule**: halve the model capability, double the ecosystem scaffolding.

---

## 9. References

- CRP-SPEC-002: HTTP Headers
- CRP-SPEC-003: Context Envelope
- CRP-SPEC-004: Continuation and State Relay
- CRP-SPEC-006: Safety Policy
- CRP-SPEC-007: Session Token
- CRP-SPEC-016: Gateway Service
- CRP-SPEC-031: Semantic Task Layer
- CRP-SPEC-050: Tool Capability Fabric and Operation Orchestration
