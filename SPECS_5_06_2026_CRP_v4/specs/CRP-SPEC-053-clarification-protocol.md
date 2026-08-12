# CRP-SPEC-053: The Clarification Protocol — Ambiguity as a First-Class Protocol Primitive

**Document:** CRP-SPEC-053  
**Title:** The Clarification Protocol — Ambiguity as a First-Class Protocol Primitive  
**Version:** 6.0.0  
**Status:** Implemented (basic protocol); deeper learned disambiguation is roadmap  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)  
**Prerequisites:** CRP-SPEC-001 (Core Protocol), CRP-SPEC-002 (HTTP Headers), CRP-SPEC-006 (Safety Policy), CRP-SPEC-011 (Audit Trail), CRP-SPEC-033 (Safety Control Plane / Inline HITL), CRP-SPEC-052 (Intent-Surface Alignment), CRP-SPEC-056 (Transparency Emission Layer)

---

## Abstract

The Clarification Protocol (CLR) makes interactive disambiguation a first-class CRP primitive. When a CRP agent cannot confidently determine user intent — because the intent classifier reports low confidence, because two or more parses are near-equiprobable, or because the cost of a mistaken reading is high — the protocol emits a structured **`CRP-Clarification-Required`** response instead of guessing. The response enumerates candidate interpretations, each annotated with the operations the agent would perform and a probability, and waits for the user to select or refine one. This turns "ask when uncertain" from an ad-hoc model behaviour into a governed, auditable, and interoperable protocol event.

CLR extends CRP-SPEC-001 by adding a new response type and relies on CRP-SPEC-052 for intent confidence and parse-divergence signals, CRP-SPEC-033 for inline human-in-the-loop handling, CRP-SPEC-056 for transparent interrupt rendering, and CRP-SPEC-011 for audit logging. The basic trigger, response schema, header, and lifecycle defined in this specification are implemented in `crprotocol` 6.0.0; deeper learned disambiguation models that improve candidate ranking from historical resolution data are roadmap.

---

## Terminology

**Ambiguity.** A property of a user turn for which more than one semantically distinct intent parse exists with comparable probability.

**Clarification candidate / interpretation.** One candidate reading of the user's intent, expressed as a plain-language paraphrase and the list of operations the agent would execute under that reading.

**Clarification threshold.** A policy-configurable scalar above which the agent MUST emit a clarification rather than proceed with the top-ranked parse.

**CRP-Clarification-Required.** The typed response kind returned by a CRP runtime when a turn is too ambiguous to resolve without user input.

**Default interpretation.** The candidate the runtime would select if forced to proceed without clarification. The protocol permits a default only when policy and risk tier allow it.

**Intent confidence.** The probability assigned by the intent classifier (CRP-SPEC-052) to the top-ranked parse.

**Parse divergence.** A measure of how close the second-ranked intent parse is to the top-ranked parse, e.g. `1 - (top_score - second_score)`.

**Resolved turn.** A clarification selection supplied by the user that is re-ingested as an unambiguous input, closing the clarification lifecycle.

---

## Specification

### 1. Clarification Trigger

A CRP runtime MUST evaluate whether to clarify before acting on an ambiguous user turn. The trigger fires when ambiguity is high and the cost of a wrong guess is non-trivial. Ambiguity is derived from CRP-SPEC-052 (`intent_confidence` and parse divergence); cost is derived from the active safety risk tier (CRP-SPEC-006 / CRP-SPEC-033).

The ambiguity score is computed as a weighted combination of the classifier's uncertainty and the divergence between the top two parses:

```python
# crp/clr/trigger.py — decide whether to clarify rather than guess
def should_clarify(
    intent_confidence: float,
    parse_divergence: float,
    risk: str,
    policy,
) -> bool:
    ambiguity = (1 - intent_confidence) * 0.5 + parse_divergence * 0.5
    # clarify when ambiguity is high, scaled DOWN the more reversible the action is
    risk_weight = {"LOW": 0.3, "MEDIUM": 0.7, "HIGH": 1.0}[risk]
    return ambiguity * risk_weight >= policy.clarification_threshold   # e.g. 0.4
```

**Inputs:**

| Symbol | Source | Meaning |
|--------|--------|---------|
| `intent_confidence` | CRP-SPEC-052 | Probability of the top-ranked intent parse |
| `parse_divergence` | CRP-SPEC-052 | `1 - (top_score - second_score)`; higher when the top two parses are close |
| `risk` | CRP-SPEC-006 / policy | `LOW`, `MEDIUM`, or `HIGH` for the operation class under consideration |
| `policy.clarification_threshold` | CRP-SPEC-006 | Policy-configurable scalar, default 0.4 |

**Guidance:**

- A runtime MAY use a policy-specified threshold that differs by operation class.
- A runtime SHOULD apply a lower threshold (i.e. be more likely to clarify) for irreversible, costly, or safety-relevant operations.
- A runtime MAY apply an unconditional clarification requirement for specified operation classes regardless of the computed score.

### 2. Structured Clarification Response

When `should_clarify` returns true, the runtime MUST NOT return a normal completion. Instead it returns a **`CRP-Clarification-Required`** structured response.

#### 2.1 Response types

```python
# crp/clr/response.py — the CRP-Clarification-Required structured response
from dataclasses import dataclass, field


@dataclass
class Interpretation:
    reading: str            # a plain-language paraphrase of one candidate intent
    operations: list[str]   # what the agent would do under this reading
    probability: float


@dataclass
class ClarificationRequired:
    kind: str = "CRP-Clarification-Required"
    reason: str = ""
    interpretations: list[Interpretation] = field(default_factory=list)
    default: int | None = None      # index the agent would pick if forced (with consent)
```

#### 2.2 Response construction

A conformant runtime constructs the response as follows:

```python
def build_clarification(
    candidates: list[Interpretation],
    reason: str,
) -> dict:
    candidates.sort(key=lambda c: -c.probability)
    return {
        "kind": "CRP-Clarification-Required",
        "reason": reason,
        "interpretations": [c.__dict__ for c in candidates],
        "default": 0 if candidates[0].probability - candidates[1].probability > 0.25 else None,
    }
```

**Requirements on the response body:**

1. `kind` MUST be exactly `CRP-Clarification-Required`.
2. `reason` MUST be a short, machine-readable token or human-readable phrase describing why clarification is required (e.g. `ambiguous-target`, `low-confidence`, `near-equiprobable-parses`).
3. `interpretations` MUST contain at least two distinct candidate interpretations.
4. Each interpretation MUST include:
   - `reading`: a plain-language paraphrase of the candidate intent;
   - `operations`: the list of operations the agent would perform if that interpretation were selected;
   - `probability`: a score in `[0.0, 1.0]` reflecting the runtime's belief in that interpretation.
5. Interpretations MUST be sorted by descending probability.
6. `default` MAY name the index the runtime would select if forced. It MUST be omitted (or `null`) when the top two candidates are within 0.25 probability of each other, and it MUST be omitted for `HIGH`-risk actions unless policy explicitly permits auto-defaulting.

### 3. Header Field

A CRP runtime emitting a clarification MUST include the following response header so that intermediaries and clients can detect the condition without parsing the response body:

```abnf
X-CRP-Clarification = "required" ";" OWS "candidates=" 1*DIGIT
                      [ ";" OWS "reason=" quoted-string ]
                      [ ";" OWS "default=" ( 1*DIGIT / "none" ) ]
```

**Example:**

```http
X-CRP-Clarification: required; candidates=2; reason="ambiguous-target"; default=none
```

**Field semantics:**

| Parameter | Meaning |
|-----------|---------|
| `required` | Fixed token indicating a clarification response |
| `candidates` | Number of interpretations supplied in the body |
| `reason` | Short reason token matching `reason` in the body |
| `default` | Index of the default interpretation, or `none` |

This header is subject to the same governance and stripping rules as other CRP headers. It is intended for CRP-aware clients and intermediaries; it MUST NOT be forwarded to an upstream LLM provider (Axiom 4 of CRP-SPEC-002).

### 4. Clarification Lifecycle

The lifecycle of a clarification is:

1. **Detect.** The runtime evaluates `should_clarify` after CRP-SPEC-052 intent classification.
2. **Emit.** If the trigger fires, the runtime returns `CRP-Clarification-Required` with the `X-CRP-Clarification` header.
3. **Render.** The client presents the interpretations to the user. Rendering SHOULD use the Transparency Emission Layer (CRP-SPEC-056) as an `INTERRUPT` so the user understands the agent is asking rather than acting.
4. **Select.** The user selects an interpretation, supplies a free-text refinement, or cancels the turn.
5. **Resolve.** The selection is re-ingested as a resolved turn. The ISA envelope (CRP-SPEC-052) is updated with the resolved intent and confidence set to a sentinel value (e.g. `1.0`) indicating human-resolved disambiguation.
6. **Proceed.** The agent continues from the resolved turn.
7. **Audit.** Both the clarification request and the user's resolution are appended to the audit trail (CRP-SPEC-011).

```text
User turn
    │
    ▼
Intent classifier (SPEC-052)
    │
    ▼
should_clarify()? ──Yes──► CRP-Clarification-Required
    │                              │
    No                             ▼
    │                       Client renders interpretations
    ▼                              │
Proceed normally                 ▼
                          User selects / refines
                                 │
                                 ▼
                          Resolved turn (SPEC-052)
                                 │
                                 ▼
                          Proceed + audit (SPEC-011)
```

### 5. Policy Control

CRP-SPEC-006 (Safety Policy) MAY govern clarification behaviour through the following policy knobs:

- `clarification_threshold`: the scalar threshold used by `should_clarify`.
- `require_clarification_for`: a list of operation classes for which clarification is mandatory regardless of computed ambiguity.
- `allow_default_for_risk`: a risk tier below which a default interpretation may be offered (default: `LOW` only).
- `max_interpretations`: the maximum number of candidates the runtime may present (default: 5).

Policy inheritance follows CRP-SPEC-006 layering (global → organisation → session → runtime override).

### 6. Client Handling

A CRP-aware client that receives a `CRP-Clarification-Required` response MUST:

1. **Recognise the response kind.** Inspect the response body `kind` field or the `X-CRP-Clarification` header and enter clarification mode rather than displaying a normal completion.
2. **Present all interpretations.** Render every candidate `reading` together with its `operations` so the user understands the consequences of each choice.
3. **Surface the default honestly.** If a `default` index is present, the client MAY pre-select it but MUST make the pre-selection obvious and allow the user to change it.
4. **Support refinement.** The client SHOULD allow the user to reject all candidates and supply a free-text clarification instead of selecting one.
5. **Support cancellation.** The client MUST allow the user to cancel the turn; the runtime MUST treat cancellation as a resolved event with no further action.
6. **Return a resolved turn.** When the user selects an interpretation or supplies a refinement, the client MUST package that input as a new turn and include the original clarification `request_id` or audit reference so the runtime can correlate the resolution.
7. **Render via TEL.** The client SHOULD emit the clarification as a Transparency Emission Layer `INTERRUPT` event (CRP-SPEC-056) so that observers see the agent asking rather than guessing.

A non-CRP-aware client that receives `CRP-Clarification-Required` SHOULD fall back to displaying the structured response as plain text and SHOULD advise the user to rephrase their request.

---

## Integration Points

### With CRP-SPEC-001 (Core Protocol)

CLR extends the Core Protocol by adding `CRP-Clarification-Required` as a valid response type alongside normal completions, continuations, and halt responses. A core runtime that supports CRP-SPEC-053 MUST recognise this response type and route it to the appropriate client handler rather than treating it as a model output.

### With CRP-SPEC-002 (HTTP Headers)

The `X-CRP-Clarification` header is a CRP header and is subject to Axiom 4: it MUST be stripped before any request is forwarded to an LLM provider, and it MUST be preserved between CRP-aware parties.

### With CRP-SPEC-006 (Safety Policy)

The clarification threshold and mandatory-clarification operation classes are policy-controlled. The risk tier used in `should_clarify` comes from the safety policy evaluation.

### With CRP-SPEC-011 (Audit Trail)

Every clarification event MUST be auditable. The audit record MUST contain:

- the original ambiguous turn;
- the computed ambiguity score and risk tier;
- the full set of interpretations returned;
- the user's resolution or cancellation; and
- timestamps for emit, render, and resolve events.

### With CRP-SPEC-033 (Safety Control Plane / Inline HITL)

Clarification is a non-blocking, interactive grounding primitive, distinct from the risk-based HITL checkpoint defined in CRP-SPEC-033. A single turn may pass through clarification first and then a safety checkpoint later if the resolved action is high-risk.

### With CRP-SPEC-052 (Intent-Surface Alignment)

CLR consumes `intent_confidence` and parse-divergence signals produced by the ISA classifier. The resolved turn produced by CLR feeds back into ISA so that subsequent classification benefits from the disambiguated context.

### With CRP-SPEC-056 (Transparency Emission Layer)

The client SHOULD render a clarification as a TEL `INTERRUPT` event so the user can observe that the agent has stopped to ask rather than act. The interpretations SHOULD be emitted as structured narration.

---

## Conformance Requirements

A CRP implementation claiming conformance with CRP-SPEC-053 MUST satisfy the following requirements:

1. **Trigger correctness.** The runtime MUST evaluate `should_clarify` using ambiguity and risk inputs and a policy-configurable threshold.
2. **No guessing.** When `should_clarify` fires, the runtime MUST emit `CRP-Clarification-Required` rather than proceed with the top-ranked parse.
3. **Minimum candidates.** A clarification response MUST include at least two distinct interpretations.
4. **Interpretation content.** Each interpretation MUST include a `reading`, a list of `operations`, and a `probability`.
5. **Default restriction.** A default interpretation MUST NOT be offered for `HIGH`-risk actions unless policy explicitly permits it, and MUST NOT be offered when the top two candidates are within 0.25 probability.
6. **Header presence.** A clarification response MUST include the `X-CRP-Clarification` header with `candidates` and `reason` parameters.
7. **Header stripping.** The runtime MUST strip `X-CRP-Clarification` and all other `CRP-*` headers before forwarding requests to an LLM provider (Axiom 4).
8. **Audit record.** The runtime MUST record the clarification request and the user's resolution to the audit trail.
9. **Policy integration.** The runtime MUST honour `clarification_threshold`, `require_clarification_for`, `allow_default_for_risk`, and `max_interpretations` from CRP-SPEC-006 policy.
10. **Lifecycle closure.** The runtime MUST accept a resolved turn and continue execution from the selected interpretation.

A conformant implementation MAY additionally:

- rank interpretations using learned models trained on historical resolution data;
- generate natural-language paraphrases of interpretations using a local model; and
- collapse near-duplicate interpretations before presenting them.

---

## Security Considerations

1. **Information disclosure.** Interpretations reveal the agent's internal candidate intents. In multi-tenant or shared-session contexts, the runtime MUST ensure that interpretations do not leak facts, tools, or operation names from other tenants or sessions.
2. **Denial of service via ambiguity loops.** A malicious or malformed input could cause repeated clarification rounds. Runtimes SHOULD cap the number of consecutive clarifications per session and SHOULD escalate to human handoff or session termination after the cap.
3. **Social engineering.** An attacker may craft inputs that force a clarification containing a desirable default. Runtimes MUST ignore client-provided default indices and MUST recompute the default from policy on every clarification.
4. **Prompt injection in interpretations.** If interpretations are rendered by a model, they MUST be treated as untrusted user content and passed through the same input-validation pipeline as the original user turn (CRP-SPEC-015).
5. **Audit integrity.** Clarification records are part of the tamper-evident audit chain. Their hashes MUST extend the session HMAC chain per CRP-SPEC-011 so that "the agent asked rather than guessed" is provable.
6. **Privacy.** Clarifications can expose uncertainty about sensitive topics. Audit logs SHOULD support differential retention and erasure in accordance with the session's privacy policy.

---

## References

- CRP-SPEC-001: Core Protocol
- CRP-SPEC-002: HTTP Headers
- CRP-SPEC-006: Safety Policy
- CRP-SPEC-011: Audit Trail
- CRP-SPEC-015: Security & Privacy
- CRP-SPEC-033: Safety Control Plane / Inline HITL
- CRP-SPEC-052: Intent-Surface Alignment
- CRP-SPEC-056: Transparency Emission Layer
