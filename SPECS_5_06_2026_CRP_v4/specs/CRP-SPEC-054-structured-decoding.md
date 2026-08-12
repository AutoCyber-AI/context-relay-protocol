# CRP-SPEC-054: Structured Decoding Enforcement

**Document:** CRP-SPEC-054  
**Title:** Context Relay Protocol (CRP) — Structured Decoding Enforcement — Token-Level Grammar Constraints for Guaranteed-Valid Tool Calls  
**Version:** 6.0.0  
**Status:** Implemented  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)  
**Prerequisites:** CRP-SPEC-008 (Dispatch & Provider Adaptation), CRP-SPEC-016 (Gateway Service), CRP-SPEC-031 (Semantic Task Layer)

---

## Abstract

This specification defines the Structured Decoding Enforcement (SDE) layer of the Context Relay Protocol. SDE guarantees that tool-call arguments emitted by a language model are structurally valid with respect to the selected tool's JSON schema *at generation time*, by applying grammar-constrained decoding in the CRP Gateway. Rather than generating text and then validating it post hoc, SDE compiles the tool schema into a grammar, computes a per-token validity bitmask, and masks invalid logits to negative infinity before sampling. This eliminates the generate-validate-retry loop for structural errors and is especially important for small language models (SLMs), where malformed arguments are a dominant failure mode.

SDE operates on the schema produced by the positioned tool loop (CRP-SPEC-031), is enforced by the Gateway (CRP-SPEC-016), and is dispatched through provider adapters (CRP-SPEC-008). It is a structural guarantee only: grounding, verification, and predictive simulation remain the responsibility of CRP-SPEC-005, CRP-SPEC-049, and CRP-SPEC-051 respectively.

---

## 1. Introduction

### 1.1 Motivation

SLM-powered agents frequently fail on tool calls not because they select the wrong tool, but because they emit malformed arguments: missing required fields, incorrect types, unescaped strings, hallucinated keys, or invalid JSON. These failures are structural, not semantic. Post-hoc validation followed by a retry consumes tokens, increases latency, and can still fail if the model repeatedly violates the same constraint.

Constrained decoding removes this entire class of error by construction. If the grammar forbids a token, the model cannot sample it. Modern structured-generation engines such as XGrammar reduce the per-token overhead to microsecond-scale by precomputing validity for the large majority of vocabulary tokens whose validity is context-independent. For many schemas, constrained generation is no slower than unconstrained generation and can be faster because the search space is reduced.

CRP-SPEC-031 isolates the schema of the selected tool before the model is called. SDE takes that isolated schema and enforces it at decode time. Together, schema adaptation (CRP-SPEC-050) and structured decoding enforcement close the SLM tool-call reliability gap.

### 1.2 Goals

1. Provide a provider-agnostic protocol mechanism for requesting grammar-constrained tool-call generation.
2. Make structural validity a primary guarantee of the Gateway generation path, not a post-hoc check.
3. Support both self-hosted inference engines (vLLM, SGLang, TensorRT-LLM, llama.cpp) and remote runtimes where the provider exposes structured-output parameters.
4. Cache compiled grammars per `(schema, tokenizer)` to amortise compilation cost.
5. Preserve Axiom 4: no `CRP-*` header or CRP-internal grammar metadata reaches the LLM provider.

### 1.3 Non-Goals

- SDE does not train, fine-tune, or modify model weights.
- It does not guarantee semantic correctness of argument *values*.
- It does not replace post-hoc validation; it makes validation a defence-in-depth layer rather than the primary guarantee.
- It does not define a new grammar language; it compiles JSON Schema to the grammar engine supported by the underlying runtime.

### 1.4 Relationship to prior work

SDE extends CRP-SPEC-016 (Gateway Service), adding grammar enforcement at generation time in the runtime proxy. It depends on CRP-SPEC-031 to supply the isolated tool schema and on CRP-SPEC-050 for schema adaptation. Where CRP-SPEC-049 (Verification Relay) consumes formal expressions, SDE SHOULD generate those expressions so that their structure is guaranteed before downstream verification.

---

## 2. Terminology

**Structured decoding enforcement (SDE):** The protocol layer that compiles a tool schema to a grammar and applies it during token sampling.

**Grammar-constrained decoding:** A decoding strategy that restricts the model's output to strings belonging to a formal grammar, typically by masking invalid logits at each step.

**Tool-call schema:** The JSON Schema describing the arguments accepted by a single tool. In CRP this is the schema isolated by the Semantic Task Layer for the active operation.

**Compiled grammar:** A runtime-specific representation of the tool-call schema, ready to be used by a grammar matcher.

**Grammar matcher:** A state machine that tracks which tokens are valid at the current decode position and advances its state as tokens are accepted.

**Token bitmask:** A binary mask over the model vocabulary where each bit indicates whether the corresponding token is permitted by the grammar at the current position.

**Schema adaptation:** The process of simplifying or reshaping a tool schema for a small model, performed by the Tool Capability Fabric (CRP-SPEC-050).

**CFG-capable engine:** A structured-generation backend that supports context-free grammars and therefore recursive or deeply nested schemas (e.g., XGrammar).

**FSM-based engine:** A structured-generation backend that compiles constraints to finite-state machines; faster for flat schemas but unable to handle unbounded recursion (e.g., Outlines).

---

## 3. Specification

### 3.1 Scope and applicability

SDE applies whenever the CRP Gateway routes a tool-call generation request and the selected operation has isolated a single tool schema. It is RECOMMENDED for all `small-local` and `capable-local` capability profiles (CRP-SPEC-049) and OPTIONAL for `frontier` profiles, where models are less prone to structural errors but still benefit from the guarantee.

SDE operates on the *adapted* schema if schema adaptation has been applied (CRP-SPEC-050). The enforcement target is the schema the model actually sees.

### 3.2 Grammar compilation

The Gateway SHALL compile the selected tool's argument schema to a grammar before generation begins. Compilation is performed once per `(schema, tokenizer)` pair and the result SHALL be cached.

The compiled grammar MUST accept exactly the JSON objects permitted by the adapted schema, including:

- Required and optional fields.
- Type constraints (`string`, `integer`, `number`, `boolean`, `array`, `object`).
- Nested objects and arrays up to the recursion depth supported by the engine.
- Enumerated values, where present.

The compilation step MAY be skipped if the underlying runtime accepts a JSON Schema directly and compiles it internally. In that case the Gateway SHALL pass the schema to the runtime using the provider-specific parameter defined in §3.6.

The following example illustrates the compilation interface. It is informative and MAY be adapted to the runtime in use.

```python
import json
from functools import lru_cache

@lru_cache(maxsize=512)
def compile_tool_grammar(tool_schema_json: str, tokenizer_info_key: str):
    """Compile a tool schema to a grammar, caching per (schema, tokenizer)."""
    schema = json.loads(tool_schema_json)
    tokenizer_info = _TOKENIZER_INFO[tokenizer_info_key]
    compiler = _GrammarCompiler(tokenizer_info)
    return compiler.compile_json_schema(schema)
```

### 3.3 Token-level enforcement

During generation the Gateway SHALL apply the compiled grammar so that every sampled token preserves the possibility of producing a valid tool-call argument.

For runtimes where the Gateway controls the sampling loop, the enforcement procedure is:

1. Build or retrieve a `GrammarMatcher` for the compiled grammar.
2. At each decode step, fill a bitmask with the vocabulary tokens that are valid at the current matcher state.
3. Apply the bitmask to the model logits, setting the logit of every invalid token to negative infinity.
4. Sample from the masked logits.
5. Accept the sampled token into the matcher, advancing its state.
6. Repeat until the matcher reports completion.

The following example shows a manual enforcement path. Implementations SHOULD delegate to the runtime when the runtime supports guided decoding natively.

```python
def mask_logits(self, logits: torch.Tensor) -> torch.Tensor:
    """Apply the grammar bitmask to logits before sampling."""
    self._matcher.fill_next_token_bitmask(self._mask)
    apply_token_bitmask_inplace(logits, self._mask.to(logits.device))
    return logits

def accept(self, token_id: int) -> bool:
    """Advance the grammar state with the sampled token."""
    return self._matcher.accept_token(token_id)
```

The Gateway SHALL NOT forward the bitmask, matcher state, or any other SDE internal data to the LLM provider.

#### 3.3.1 Deterministic sampling recommendation

When SDE is active, the Gateway SHOULD set the sampling temperature to a low value (0.0–0.2) for tool-call generation. Grammar enforcement already constrains the token distribution; high temperatures increase variance without improving validity and can mask quality drift in small models. Implementations MAY expose a `CRP-Agent-Sampling-Mode` header, but this is outside the scope of SDE.

### 3.4 Engine selection

Different structured-generation engines are optimal for different schema shapes. The Gateway SHALL select an engine according to the following rules:

1. If the schema is recursive, contains self-references, or has a maximum nesting depth greater than three, the engine MUST be CFG-capable (e.g., XGrammar).
2. If the schema changes per request and time-to-first-token is critical, a dynamic per-request engine (e.g., llguidance) MAY be used.
3. Otherwise, the default engine is XGrammar or the runtime's default structured-generation backend.

The engine selection is an implementation detail of the Gateway and is not exposed in CRP headers.

### 3.5 Hosted runtime path

When the Gateway forwards to a hosted runtime that supports guided decoding (vLLM, SGLang, TensorRT-LLM, llama.cpp, OpenAI, Anthropic, Ollama), the Gateway SHALL translate the CRP-level structured-decoding directive into the provider-specific request field.

The following table lists the provider-specific parameters that MUST be used where available:

| Runtime / provider | Request parameter for JSON schema | Request parameter for grammar |
|---|---|---|
| vLLM | `guided_json` | `guided_grammar` |
| SGLang | `guided_json` or `json_schema` | `guided_grammar` |
| TensorRT-LLM | `response_format` with schema | runtime-specific grammar field |
| llama.cpp | `grammar` (GBNF) | `grammar` |
| OpenAI | `response_format` with `json_schema` | not supported |
| Anthropic | `tools[].function.parameters` / `response_format` | not supported |
| Ollama | `format` with schema or `"json"` | not supported |

The Gateway MUST strip all `CRP-*` headers before forwarding the request (Axiom 4, CRP-SPEC-002).

### 3.6 Grammar caching

Compilation cost SHALL be amortised through a cache keyed by:

- A normalised representation of the adapted JSON Schema.
- The tokenizer identifier or vocabulary fingerprint.
- The selected grammar engine and version.

The cache MUST be bounded to prevent unbounded memory growth. Implementations SHOULD support cache eviction and invalidation when the grammar engine version changes.

### 3.7 Composition with schema adaptation

CRP-SPEC-050 MAY adapt a tool schema to improve SLM reliability: reducing nesting depth, collapsing optional objects, or adding default values. SDE MUST enforce the *adapted* schema, not the original schema. This ensures that the model is constrained to exactly the shape it was positioned to emit.

If no adapted schema is available, SDE enforces the original tool schema.

### 3.8 Header fields

SDE introduces no new CRP HTTP headers. It is triggered by the presence of a tool-call schema on a Gateway request whose operation context indicates tool-call generation. The Gateway MAY emit the existing diagnostics headers `CRP-Structured-Output-Applied` and `CRP-Grammar-Engine` on the response for observability, but these are OPTIONAL and MUST be stripped on any upstream forward.

### 3.9 Error handling

If a schema cannot be compiled to a grammar (for example, because it uses an unsupported JSON Schema construct), the Gateway MUST:

1. Record the compilation failure in the quality report and audit log.
2. Fall back to post-hoc JSON Schema validation of the generated output.
3. Continue processing the request rather than failing the entire task, unless safety policy explicitly requires halting.

If the matcher reaches a state where no token is valid (a dead end), the Gateway MUST:

1. Abort the current generation.
2. Return a structured error indicating that the grammar could not be satisfied.
3. Allow the surrounding agent loop to decide whether to retry, revise the schema, or escalate to human oversight.

### 3.10 Example: end-to-end flow

The following example illustrates a complete SDE flow for a small-local model generating a tool call.

1. The STL (CRP-SPEC-031) classifies the operation as `RETRIEVE` and selects the tool `lookup_regulation`.
2. The TCF (CRP-SPEC-050) adapts the tool schema to a flat JSON object with three required string fields: `jurisdiction`, `topic`, and `year`.
3. The Gateway retrieves the adapted schema, looks up the cache for `(schema_hash, tokenizer_id)`, and compiles the grammar if missing.
4. The Gateway sets `guided_json` on a vLLM request or applies a local grammar matcher.
5. The model emits a token sequence that the grammar matcher accepts.
6. The generated arguments are parsed, validated, and recorded with `structure_valid: true` in the provenance record.
7. Post-hoc validation runs as defence in depth and confirms the result.

---

## 4. Integration Points

### 4.1 Semantic Task Layer (CRP-SPEC-031)

The STL isolates one operation and one tool schema per window. SDE consumes that isolated schema. If the STL produces an adapted schema, SDE enforces the adapted version.

### 4.2 Tool Capability Fabric (CRP-SPEC-050)

The TCF selects the minimal tool subset and may reshape the selected tool's schema. SDE receives the final schema from the TCF and treats it as the enforcement target.

### 4.3 Gateway Service (CRP-SPEC-016)

The Gateway is the enforcement site. It compiles the schema, applies or delegates the grammar, caches compiled grammars, and translates CRP-level constraints into provider-specific request parameters.

### 4.4 Dispatch & Provider Adaptation (CRP-SPEC-008)

Provider adapters translate the CRP structured-decoding intent into the format required by each LLM runtime. Adapters MAY fall back to post-hoc validation only when the runtime provides no guided-decoding mechanism; in that case the fallback MUST be logged and the quality report MUST reflect the reduced guarantee.

### 4.5 Verification Relay (CRP-SPEC-049)

Formal expressions and verification artefacts consumed by the Verification Relay SHOULD be generated under SDE. This closes an injection vector in which a malformed or adversarially-shaped expression is accepted by a downstream verifier.

### 4.6 Decision Provenance Engine (CRP-SPEC-005)

SDE contributes a structural-validity assertion to the provenance record for each tool-call generation. The DPE uses this assertion together with grounding and entailment checks to compute the final provenance score.

---

## 5. Conformance Requirements

A CRP-SDE conformant implementation MUST satisfy the following requirements:

1. **Enforcement as primary guarantee.** For every tool-call generation routed through the Gateway, the selected tool's argument schema MUST be enforced at decode time. Post-hoc validation MUST remain only as defence in depth.

2. **CFG capability for recursive schemas.** Recursive or deeply nested schemas MUST be handled by a CFG-capable engine.

3. **Caching.** Compiled grammars MUST be cached per `(schema, tokenizer)` to avoid repeated compilation cost.

4. **Axiom 4 compliance.** No `CRP-*` header and no SDE-internal metadata (bitmask, matcher state, grammar identifier) MAY reach the LLM provider.

5. **Provider translation.** The Gateway MUST translate CRP structured-decoding intent into the parameters supported by the target runtime.

6. **Graceful fallback.** If the selected runtime does not support guided decoding, the Gateway MAY fall back to post-hoc validation, but it MUST record the fallback in the quality report and MUST NOT claim SDE enforcement for that generation.

7. **Structural-only claim.** SDE conformance guarantees only structural validity. Implementations MUST NOT claim semantic or security validity on the basis of SDE alone.

8. **Schema provenance.** The enforced schema MUST be traceable to the output of the positioned tool loop (CRP-SPEC-031) and, if applicable, the schema adaptation step (CRP-SPEC-050).

### 5.1 Conformance classes

- **SDE-native:** The Gateway applies or delegates grammar-constrained decoding on every supported tool-call generation. This is the preferred class.
- **SDE-fallback:** The Gateway does not have access to a guided-decoding runtime for a particular provider and relies on post-hoc validation, while still satisfying the schema-provenance, Axiom 4, and reporting requirements above.
- **SDE-disabled:** The deployment explicitly disables SDE. Implementations MUST record this choice in the audit log and MUST NOT advertise SDE conformance for generations handled in this mode.

---

## 6. Security Considerations

### 6.1 Injection containment

By constraining the model output to a known grammar, SDE prevents a broad class of prompt-injection attacks that attempt to elicit malformed, oversized, or syntactically surprising tool-call arguments. An attacker cannot cause the model to emit unescaped JSON control characters, extra fields, or nested payloads outside the schema shape.

### 6.2 Structural vs. semantic validity

SDE does not constrain the *semantic* content of arguments. A grammatically valid call can still contain malicious values, incorrect identifiers, or hallucinated references. Therefore SDE MUST be composed with:

- The trusted policy gate (tool-use volume) from CRP-SPEC-050.
- Predictive simulation and safety checks from CRP-SPEC-051.
- Grounding and verification from CRP-SPEC-005 and CRP-SPEC-049.

### 6.3 Cache poisoning

Compiled-grammar caches keyed by schema must use a normalised schema representation. Implementations MUST verify that the cache key faithfully represents the schema; otherwise a substituted or mutated schema could be matched against an incompatible compiled grammar, breaking the validity guarantee.

### 6.4 Denial of service

Pathological schemas with very large enumerations, extreme nesting, or recursive self-references can increase compilation time or per-step overhead. Implementations SHOULD impose bounds on:

- Maximum schema nesting depth accepted for enforcement.
- Maximum compiled grammar size.
- Maximum cache entries and total cache memory.

If a schema exceeds these bounds, the Gateway MUST fall back to post-hoc validation and MUST record the event.

### 6.5 Provider leakage

When delegating structured decoding to a hosted runtime, the Gateway transmits the tool schema to that runtime. The schema is assumed to be non-sensitive. If a deployment treats tool schemas as sensitive, it SHOULD use a self-hosted runtime or encrypt the transport channel.

---

## 7. References

- CRP-SPEC-002: HTTP Headers
- CRP-SPEC-003: Context Envelope
- CRP-SPEC-005: Decision Provenance Engine
- CRP-SPEC-007: Session Token
- CRP-SPEC-008: Dispatch & Provider Adaptation
- CRP-SPEC-016: Gateway Service
- CRP-SPEC-031: Semantic Task Layer
- CRP-SPEC-049: Verification Relay
- CRP-SPEC-050: Tool Capability Fabric and Operation Orchestration
- CRP-SPEC-051: Predictive Simulation & Policy Gate

### 7.1 Informative references

- XGrammar documentation, `xgrammar.mlc.ai`, 2026.
- Willard, B., & Louf, R. (2023). *Outlines: Guided text generation*. arXiv:2305.18246.
- Beurer-Kellner, L., et al. (2024). *Guiding LLMs The Right Way: Fast, Non-Invasive Constrained Text Generation*. arXiv:2403.06988.
- Sharma, A., et al. (2024). *The Shift from Models to Compound AI Systems*. Berkeley AI Research.
- Wu, Q., et al. (2023). *AutoGen: Enabling next-gen LLM applications via multi-agent conversation*. arXiv:2308.08155.
