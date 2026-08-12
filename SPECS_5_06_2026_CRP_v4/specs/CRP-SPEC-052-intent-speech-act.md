# CRP-SPEC-052: Intent & Speech-Act Positioning

**Document:** CRP-SPEC-052  
**Title:** Context Relay Protocol (CRP) — Intent & Speech-Act Positioning —
Pragmatic Interpretation and Cross-Session Coreference Before Envelope Packing  
**Version:** 6.0.0  
**Status:** Implemented  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)  
**Prerequisites:** CRP-SPEC-001 (Core), CRP-SPEC-002 (Headers), CRP-SPEC-003 (Envelope),
CRP-SPEC-007 (Session Token), CRP-SPEC-009 (Contextual Knowledge Fabric),
CRP-SPEC-028 (Conversational Context — Multi-Horizon), CRP-SPEC-031 (Semantic Task Layer)

---

## Abstract

This specification defines the Intent & Speech-Act (ISA) layer for the Context
Relay Protocol. ISA runs a lightweight, local intent-and-speech-act classifier
and a cross-session coreference-resolution pass before the Context Envelope is
packed. The classifier tags each user turn with its speech act, directness,
implied constraints, and emotional valence; the coreference resolver rewrites
ambiguous references such as "it", "that approach", and "the second option"
against a session-scoped entity registry derived from the Contextual Knowledge
Fabric (CKF). The Semantic Task Layer (STL) then positions the model using the
interpreted intent rather than the raw text, improving routing, tool selection,
and output quality without increasing in-window token cost.

ISA is designed for small, local models. Both classifier and resolver complete
in a small number of milliseconds on CPU, preserving CRP's invariant of near-
zero per-call protocol overhead. All ISA metadata is carried as CRP HTTP
headers, session-token fields, and an `interpreted_intent` section in the
envelope, and is subject to Axiom 4: no `CRP-*` header ever reaches the LLM
provider.

---

## 1. Introduction

### 1.1 Motivation

CRP already classifies content *complexity* — for example, as `ENTITY_RICH`,
`REASONING_DENSE`, or `NARRATIVE` — but it does not classify communicative
*intent*. The following three turns have similar propositional content but
different speech acts:

- "Can you check the contract?" — request, indirect.
- "Check the contract." — request, imperative.
- "I wonder if the contract covers this." — question / expressive.

Routing each to the same STL operation is wasteful and sometimes wrong. A
softened request may need a clarifying acknowledgement before action; an
imperative may need no acknowledgement at all; a question may be satisfied by
retrieval rather than by a tool loop.

A second pragmatic gap is reference resolution. Similarity-based retrieval
(CRP-SPEC-028) surfaces relevant historical facts but does not bind pronouns
or deictic phrases to specific referents. A turn that says "Use the second
option" or "That approach failed" requires coreference resolution across
prior turns before the envelope is packed. SLMs struggle with this class of
ambiguity, and a protocol-level resolution pass materially improves
positioning quality.

ISA closes both gaps with small, fast, local models that run outside the LLM
context window.

### 1.2 Goals

1. Classify each user turn into a small set of speech acts before dispatch.
2. Quantify directness so the STL can decide whether to acknowledge, clarify,
   or act immediately.
3. Surface implied constraints such as scope restrictions, exclusions,
   temporal ordering, and hard constraints.
4. Resolve intra-turn and cross-turn coreference against a session entity
   registry before envelope packing.
5. Provide an `interpreted_intent` envelope section that the STL and envelope
   builder consume as authoritative input.
6. Keep total ISA latency low enough that it does not regress the positioned
   tool loop.
7. Prevent emotional valence or tone from influencing logical operation
   selection.

### 1.3 Non-Goals

- This specification does not train or fine-tune language models; it consumes
  already-trained classifiers.
- It does not replace the Semantic Task Layer; it supplies input to it.
- It does not perform open-domain natural-language understanding; the
  speech-act taxonomy and coreference targets are scoped to agentic task
  contexts.
- It does not modify safety policy decisions; valence is used for phrasing,
  not for action selection.
- It does not add in-window instructions; all ISA metadata is carried as
  protocol metadata or a structured envelope section.

---

## 2. Terminology

**Speech act:** The communicative function of an utterance — for example,
`request`, `question`, `assertion`, or `expressive`.

**Directness:** A scalar from 0 (strongly indirect) to 1 (explicit imperative)
indicating how forcefully the turn asks for action.

**Implied constraint:** A domain-agnostic constraint category surfaced from
surface cues, such as `restrict-scope`, `exclusion`, `temporal-order`, or
`hard-constraint`.

**Valence:** A scalar from -1 to +1 representing the emotional polarity of the
turn. Valence informs output tone only and MUST NOT influence logical
operation selection.

**Session entity registry:** A set of typed entities and discourse mentions
maintained for a session, extending the Contextual Knowledge Fabric
(CRP-SPEC-009).

**Coreference cluster:** A group of mentions, produced by a neural coreference
model, that refer to the same entity.

**Canonical mention:** The longest non-pronominal span in a coreference
cluster, used to rewrite pronominal references.

**Interpreted intent:** The envelope section that contains the resolved turn,
speech act, directness, constraints, tone hint, and intent confidence.

**Intent confidence:** A score indicating classifier certainty; consumed by
CRP-SPEC-053 (Clarification Protocol) to trigger clarification when confidence
is low.

---

## 3. Specification

### 3.1 Intent and speech-act classification

Every user turn submitted to a CRP Gateway or SDK client SHOULD pass through
the `IntentClassifier` before envelope packing. The classifier emits an
`IntentTag` describing the pragmatic properties of the turn.

```python
# CRP reference shape: crp/isa/intent.py
from dataclasses import dataclass

@dataclass
class IntentTag:
    speech_act: str          # request | question | assertion | expressive
    directness: float        # 0 (hinted) .. 1 (explicit imperative)
    implied_constraints: list[str]
    valence: float           # -1 (frustrated) .. +1 (positive); tone only
```

The reference implementation uses a distilled SetFit classifier with the model
identifier `autocyber/crp-intent-setfit`. This model is trained for four-way
speech-act classification and is small enough to run on CPU in sub-10 ms for
typical user turns. The speech-act taxonomy is fixed by this specification:

| Speech act | Description |
|------------|-------------|
| `request` | Turn asks the agent to perform an action. |
| `question` | Turn asks for information without requesting action. |
| `assertion` | Turn states a fact or claim for the agent to consider. |
| `expressive` | Turn communicates an attitude, opinion, or feeling. |

A conformant implementation MAY extend the taxonomy, but the four values above
MUST be supported so that downstream components can rely on them.

Directness, implied constraints, and valence MAY be derived by lightweight
heuristics in the reference implementation. Example heuristics include:

- Directness is lowered when the turn ends in a question mark or starts with
  softening phrases such as "can you", "could you", "would you", or
  "i wonder".
- Directness is raised for bare imperatives or explicit pleases.
- Constraints are inferred from cue words such as "only", "without",
  "before", and "must".
- Valence is negative when the turn contains friction words such as
  "still", "again", "broken", "wrong", or "not working".

Implementations are free to replace the heuristics with learned models, but
the contract — an `IntentTag` with the four fields above — MUST remain stable.

### 3.2 Cross-session coreference resolution

Before envelope packing, pronouns and deictic references in the current turn
MUST be resolved against the session entity registry. The registry is an
extension of the CKF (CRP-SPEC-009) that records discourse mentions, not only
extracted facts.

```python
# CRP reference shape: crp/isa/coref.py
class CoreferenceResolver:
    def resolve(self, turn: str, session_entities: dict[str, str]) -> str:
        """Rewrite pronouns/deixis in `turn` using clusters and the registry."""
        ...
```

The resolver operates in two stages:

1. **Neural coreference.** A local neural coreference model (for example,
   `fastcoref`) is run over a short window containing the current turn and the
   most recent entities from the registry. Each cluster identifies mentions
   that refer to the same entity. The canonical mention for the cluster is the
   longest non-pronominal span. Pronouns in the current turn are replaced with
   the canonical mention.

2. **Ordinal deixis resolution.** Phrases such as "the second option",
   "that approach", or "the last one" are resolved against the ordered
   session entity registry. The registry MUST preserve insertion order or an
   explicit ranking so that ordinal references are deterministic.

Only references that can be resolved with high confidence SHOULD be rewritten.
When resolution is ambiguous, the raw form MUST be retained and a low
`intent_confidence` value MUST be emitted so that CRP-SPEC-053 can request
clarification.

The resolver is not required to retain a full document-level coreference model;
it only needs enough recent history to resolve the references that matter for
the next operation. The recommended lookback is the most recent six entities in
the registry plus the current turn.

### 3.3 Positioning with interpreted intent

The output of ISA is an `interpreted_intent` object that becomes a first-class
section of the Context Envelope (CRP-SPEC-003). The STL and Envelope Builder
consume this section instead of, or in addition to, the raw user turn.

```python
# CRP reference shape: crp/isa/position.py
def build_intent_section(raw_turn, intent_tag, resolved_turn) -> dict:
    return {
        "raw": raw_turn,
        "resolved": resolved_turn,                     # references rewritten
        "speech_act": intent_tag.speech_act,
        "directness": intent_tag.directness,
        "constraints": intent_tag.implied_constraints,
        "tone_hint": "acknowledge_friction" if intent_tag.valence < 0 else "neutral",
        "intent_confidence": _confidence(intent_tag),  # feeds SPEC-053 gate
    }
```

The fields are:

| Field | Type | Meaning |
|-------|------|---------|
| `raw` | string | The original user turn, preserved for audit and fallback. |
| `resolved` | string | The turn after coreference resolution. |
| `speech_act` | string | One of the supported speech-act values. |
| `directness` | float | 0.0 to 1.0 inclusive. |
| `constraints` | list[string] | Implied constraint categories. |
| `tone_hint` | string | Advisory tone guidance for the response renderer. |
| `intent_confidence` | float | 0.0 to 1.0; high values indicate reliable classification and resolution. |

The `resolved` turn MUST be used as the primary task text for STL
classification and operation selection. The `raw` turn MUST remain available in
the audit trail and in any clarification prompt so that the user can verify the
rewrite.

The `tone_hint` is purely advisory. A gateway or client MAY ignore it, but a
conformant implementation MUST NOT let `tone_hint` override safety decisions or
logical routing.

### 3.4 Header fields

ISA data is carried as CRP HTTP headers on both request and response. All
headers are subject to Axiom 4 stripping before forwarding to an LLM provider.

#### 3.4.1 CRP-Intent-Speech-Act

**Direction:** BOTH  
**Required:** RECOMMENDED

**Definition:** The classified speech act of the user turn.

**Syntax:**
```abnf
CRP-Intent-Speech-Act = "request" / "question" / "assertion" / "expressive"
```

**Example:**
```
CRP-Intent-Speech-Act: request
```

#### 3.4.2 CRP-Intent-Directness

**Direction:** BOTH  
**Required:** OPTIONAL

**Definition:** A decimal scalar indicating the directness of the turn.

**Syntax:**
```abnf
CRP-Intent-Directness = "0" / "1" / "0" 1*DIGIT "." 1*DIGIT / "1.0"
```

**Example:**
```
CRP-Intent-Directness: 0.9
```

#### 3.4.3 CRP-Intent-Constraints

**Direction:** BOTH  
**Required:** OPTIONAL

**Definition:** A comma-separated list of implied constraint categories.

**Syntax:**
```abnf
CRP-Intent-Constraints = constraint *( "," OWS constraint )
constraint = "restrict-scope" / "exclusion" / "temporal-order" /
             "hard-constraint" / token
```

**Example:**
```
CRP-Intent-Constraints: restrict-scope,hard-constraint
```

#### 3.4.4 CRP-Intent-Confidence

**Direction:** BOTH  
**Required:** RECOMMENDED

**Definition:** The confidence of the combined classification and coreference
resolution. Low values trigger the Clarification Protocol (CRP-SPEC-053).

**Syntax:**
```abnf
CRP-Intent-Confidence = "0" / "1" / "0" 1*DIGIT "." 1*DIGIT / "1.0"
```

**Example:**
```
CRP-Intent-Confidence: 0.94
```

#### 3.4.5 CRP-Intent-Resolved-Turn

**Direction:** BOTH  
**Required:** OPTIONAL

**Definition:** The user turn after coreference resolution. The raw turn is
carried in the request body or envelope `raw` field.

**Syntax:**
```abnf
CRP-Intent-Resolved-Turn = *VCHAR
```

The header value MUST be UTF-8 encoded and percent-escaped if it contains
characters not allowed in HTTP header values.

### 3.5 Session-token fields

CRP-SPEC-007 session tokens MAY include the following optional ISA fields:

| Field | Type | Description |
|-------|------|-------------|
| `speech_act` | string | Active `CRP-Intent-Speech-Act`. |
| `directness` | float | Active `CRP-Intent-Directness`. |
| `constraints` | list[string] | Active `CRP-Intent-Constraints`. |
| `intent_confidence` | float | Active `CRP-Intent-Confidence`. |
| `resolved_turn` | string | Active resolved turn, if available. |
| `coref_registry_hash` | string | `sha256:` of the session entity registry snapshot used for resolution. |

### 3.6 Context Envelope section

The Context Envelope (CRP-SPEC-003) MAY contain an `interpreted_intent`
object as defined in §3.3. The Envelope Builder uses this section to:

1. Select the STL operation type (CRP-SPEC-031).
2. Decide whether to add an acknowledgement or clarification turn.
3. Apply constraint categories to operation framing.
4. Pass the resolved turn to the Tool Capability Fabric (CRP-SPEC-050) for
tool selection.

The `interpreted_intent` section MUST NOT be added to the LLM prompt verbatim;
it is consumed by protocol machinery. The resolved turn MAY be used as the task
text, optionally accompanied by a short, machine-generated framing sentence
describing constraints.

---

## 4. Integration Points

### 4.1 Semantic Task Layer

ISA is the immediate upstream consumer of the user turn and the immediate
upstream supplier to the Semantic Task Layer (CRP-SPEC-031). The STL receives
the resolved turn and the `IntentTag` fields, and uses them to classify the
operation and negotiate depth. For example:

- A `question` with low directness may map to `CLARIFY` or `RETRIEVE`.
- A `request` with high directness and a single constraint may map to a
  constrained `ANALYSE` or `GENERATE`.
- An `expressive` with negative valence may trigger a `CLARIFY` operation to
  confirm the user's goal before acting.

### 4.2 Context Envelope

The Envelope Builder (CRP-SPEC-003) embeds `interpreted_intent` as a metadata
section. It also uses the section to tune packing depth and continuation
triggers: highly indirect turns are more likely to need a follow-up
clarification, while imperative requests may need no continuation beyond the
operation result.

### 4.3 Contextual Knowledge Fabric

The coreference resolver extends CKF typed nodes (CRP-SPEC-009) with discourse
mentions. Each mention records the turn in which it appeared, its canonical
form, and any ordinal position. The CKF graph-walk and pattern-query machinery
remains responsible for retrieving related facts; ISA is responsible for binding
ambiguous references to retrieved facts.

### 4.4 Multi-Horizon Context

The session entity registry is stored in the `CONVERSATIONAL` or `EPHEMERAL`
horizon (CRP-SPEC-028), depending on whether the user has marked the session
as persistent. Resolved turns flow into the turn log for downstream retrieval,
while the registry itself is updated on every turn that introduces or refers to
entities.

### 4.5 Clarification Protocol

`intent_confidence` is the primary input to the Clarification Protocol
(CRP-SPEC-053). A gateway or client SHOULD route to clarification when any of
the following hold:

- `intent_confidence` is below the deployment threshold (default 0.6).
- The speech act is `expressive` and the STL cannot derive a concrete
  operation.
- Coreference resolution produced multiple candidate canonical mentions with
  similar scores.

### 4.6 Tool Capability Fabric

The resolved turn and constraint list are passed to the Tool Capability Fabric
(CRP-SPEC-050) for tool selection. Constraints such as `exclusion` or
`restrict-scope` narrow the candidate tool set before ranking.

---

## 5. Conformance Requirements

A CRP-ISA conformant implementation MUST satisfy all of the following:

1. **Speech-act coverage.** Support at least the speech acts `request`,
   `question`, `assertion`, and `expressive`.

2. **Intent tag contract.** Emit an `IntentTag` or equivalent structure with
   `speech_act`, `directness`, `implied_constraints`, and `valence` fields.

3. **Directness range.** Represent directness as a scalar in the inclusive
   range [0.0, 1.0].

4. **Valence semantics.** Use valence only for tone or phrasing guidance.
   Valence MUST NOT influence logical operation selection, safety decisions, or
   grounding requirements.

5. **Coreference before packing.** Run coreference resolution before the
   Context Envelope is packed whenever the current turn contains unresolved
   pronouns or deictic references. If resolution fails or is ambiguous,
   retain the raw turn and emit a low `intent_confidence`.

6. **Session entity registry.** Maintain a session-scoped registry that links
   discourse mentions to CKF typed nodes. The registry MUST preserve enough
   history and ordering to resolve ordinal deixis deterministically.

7. **`interpreted_intent` section.** Include `raw`, `resolved`, `speech_act`,
   `directness`, `constraints`, `tone_hint`, and `intent_confidence` in the
   envelope section when ISA is enabled.

8. **Latency budget.** Complete intent classification and coreference
   resolution within a total latency budget that does not regress the
   positioned tool loop. The reference target is sub-10 ms per turn on CPU for
   typical user turns.

9. **Header stripping.** Strip all `CRP-*` headers before forwarding the
   request to an LLM provider (Axiom 4).

10. **Confidence-driven clarification.** Forward `intent_confidence` to the
    Clarification Protocol (CRP-SPEC-053) so that low-confidence turns can be
    clarified with the user rather than guessed.

11. **Audit preservation.** Preserve the raw user turn in the audit trail even
    when the resolved turn is used for operation selection.

---

## 6. Security Considerations

### 6.1 Model supply chain

ISA classifiers and coreference models are local. Implementations MUST load
models from trusted sources and verify their provenance. The reference model
`autocyber/crp-intent-setfit` is distributed through the AutoCyberAI Hugging
Face organisation and is referenced from `crp/ml/manifest.json`.

### 6.2 Adversarial turns

A user may craft turns designed to confuse the classifier, for example by
phrasing a harmful request as an innocent question or by using pronouns to
obscure the target of an action. ISA is an advisory layer, not a security
gate. All safety policy enforcement remains the responsibility of
CRP-SPEC-006, CRP-SPEC-033, and CRP-SPEC-034. The `interpreted_intent`
section MUST NOT bypass safety checks.

### 6.3 Coreference errors

Incorrect coreference resolution can cause the agent to act on the wrong
entity, which is a correctness and safety concern. Implementations SHOULD:

- Only rewrite references when the resolver is confident.
- Fall back to the raw turn and trigger clarification when confidence is low.
- Record both raw and resolved forms in the audit trail so that errors can be
  diagnosed.

### 6.4 Privacy

The session entity registry may contain personal or sensitive entities. It
MUST be subject to the same retention, encryption, and erasure policies as the
rest of CRP session state (CRP-SPEC-007, CRP-SPEC-015).

### 6.5 Determinism

Coreference and classifier outputs SHOULD be deterministic enough for audit
reproducibility. Random seeds, model caching, and registry ordering MUST be
logged or controlled so that a later auditor can reconstruct why a particular
resolved turn was produced.

---

## 7. References

- CRP-SPEC-001: Core Protocol
- CRP-SPEC-002: HTTP Headers
- CRP-SPEC-003: Context Envelope
- CRP-SPEC-004: Continuation and State Relay
- CRP-SPEC-006: Safety Policy
- CRP-SPEC-007: Session Token
- CRP-SPEC-009: Contextual Knowledge Fabric
- CRP-SPEC-015: Security & Privacy
- CRP-SPEC-028: Conversational Context — Multi-Horizon
- CRP-SPEC-031: Semantic Task Layer
- CRP-SPEC-033: Safety Control Plane
- CRP-SPEC-034: Safety Coverage
- CRP-SPEC-050: Tool Capability Fabric and Operation Orchestration
- CRP-SPEC-053: Clarification Protocol

---

*Copyright © 2026 AutoCyber AI Pty Ltd. This specification is licensed under
Creative Commons Attribution 4.0 International. Reference implementations are
licensed under the Elastic License 2.0.*
