# CRP-SPEC-057: Bi-Temporal Contextual Knowledge Fabric

**Document:** CRP-SPEC-057  
**Title:** Context Relay Protocol (CRP) — Bi-Temporal Contextual Knowledge Fabric:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Event-Time vs Ingestion-Time Fact Validity  
**Version:** 6.0.0  
**Status:** Implemented  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)  
**Prerequisites:** CRP-SPEC-009 (Contextual Knowledge Fabric), CRP-SPEC-027 (Retrieval Integrity)

---

## Abstract

This specification extends the Contextual Knowledge Fabric (CRP-SPEC-009) with **bi-temporal fact validity**. Every time-sensitive fact carries two independent validity intervals: **event time** (when the fact was true in the world) and **ingestion time** (when the CRP system learned, believed, or stopped believing it). This separation lets the fabric answer "what was actually true at time *T*?" and "what did we believe at time *T*?" as distinct queries. It also enables honest audit ("we acted correctly on what we knew *then*, even though the fact later changed") and prevents retrieval from grounding generation on facts that have been superseded by later events.

Bi-temporality is applied selectively to time-sensitive facts. It is implemented as an additive layer on top of the existing CKF fact model; non-temporal facts and edges continue to behave as defined in CRP-SPEC-009. Retrieval (CRP-SPEC-028) gains an `as_of` temporal filter, and retrieval integrity (CRP-SPEC-027) is extended to verify temporal consistency.

---

## 1. Introduction

### 1.1 Motivation

CKF facts in CRP v5 are point-in-time assertions. In production systems, facts expire and are superseded. For example, the assertion "the production database is on host .40" may be true until a migration replaces it with host .55. A similarity-based retrieval that returns the old assertion after the migration is grounded in a stale fact and can produce a confidently wrong answer. Worse, the system has no way to distinguish between:

- a fact that is currently true but was unknown at the time of a past decision, and
- a fact that was once believed but later invalidated.

Existing retrieval based on semantic similarity (CRP-SPEC-028) has no temporal validity dimension, so it cannot select facts according to the query's temporal context. Bi-temporality fixes this at the substrate by recording, for each time-sensitive fact:

- `valid_from` / `valid_to` — the event-time interval during which the fact was true in the world, and
- `ingested_at` / `invalidated_at` — the ingestion-time interval during which the CRP system believed the fact.

This design is inspired by temporal knowledge-graph systems, but it is scoped to the governance needs of CRP: correctness of grounded generation, honest audit, and provenance replay.

### 1.2 Goals

1. Add event-time and ingestion-time validity to CKF facts without breaking the existing CKF model.
2. Enable "as-of" retrieval: return the fact that was true in the world at a specified time.
3. Enable "believed-at" inspection: report what the system believed at a specified time.
4. Preserve history by superseding facts rather than overwriting them.
5. Keep current-query retrieval simple by defaulting to currently-valid facts unless a historical context is supplied.
6. Maintain compatibility with retrieval integrity (CRP-SPEC-027), multi-horizon context (CRP-SPEC-028), and the audit chain (CRP-SPEC-011).

### 1.3 Non-Goals

- This specification does not turn the CKF into a full temporal knowledge graph or a temporal database.
- It does not mandate a particular timestamp granularity; implementations MAY use second-level or finer resolution as appropriate.
- It does not define causal or probabilistic temporal reasoning; it records and filters by explicit validity intervals only.
- It does not require bi-temporal annotations on every fact; only time-sensitive facts MUST carry them.

---

## 2. Terminology

**Event time:** The time interval during which a fact is true in the world. Represented by `valid_from` (inclusive) and `valid_to` (exclusive, or `None` if still valid).

**Ingestion time:** The time interval during which the CRP system believes a fact. Represented by `ingested_at` (inclusive) the moment the fact was recorded) and `invalidated_at` (exclusive, or `None` if still believed).

**Bi-temporal fact:** A CKF fact annotated with both event-time and ingestion-time intervals.

**Supersession:** The act of closing an old fact's validity interval and inserting a successor fact, rather than mutating the old fact in place.

**As-of retrieval:** A query that asks for the fact that was true in the world at a specific event time.

**Believed-at retrieval:** A query that asks what the system believed at a specific ingestion time.

**Currently valid:** A fact whose `valid_to` is `None`, i.e., it is still believed to be true in the world.

**Temporal consistency:** The property that, for any subject-predicate pair, the event-time intervals of successive facts form a non-overlapping, ordered sequence when supersession is used correctly.

---

## 3. Specification

### 3.1 Bi-Temporal Fact Model

A bi-temporal fact is a CKF fact extended with four timestamps. The core subject-predicate-object triple remains unchanged, so existing CKF consumers that do not interpret temporality can still treat the fact as an ordinary assertion.

The reference implementation defines the model as follows:

```python
@dataclass
class BiTemporalFact:
    subject: str
    predicate: str
    object: str
    valid_from: datetime              # event time: when true in the world
    valid_to: datetime | None = None  # None = still valid
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    invalidated_at: datetime | None = None   # when CRP stopped believing it
```

**Field semantics:**

| Field | Type | Meaning |
|-------|------|---------|
| `subject` | string | Entity the fact is about |
| `predicate` | string | Relationship or property name |
| `object` | string | Value of the relationship or property |
| `valid_from` | datetime | Event time at which the fact became true (inclusive) |
| `valid_to` | datetime \| None | Event time at which the fact ceased to be true (exclusive); `None` means currently true |
| `ingested_at` | datetime | Ingestion time at which CRP learned the fact |
| `invalidated_at` | datetime \| None | Ingestion time at which CRP stopped believing the fact; `None` means still believed |

### 3.2 Temporal Predicates

Two predicates determine whether a fact matches a temporal query.

**`true_in_world_at(t)`** returns `True` if and only if:

```
valid_from <= t  AND  (valid_to is None OR t < valid_to)
```

**`believed_by_system_at(t)`** returns `True` if and only if:

```
ingested_at <= t  AND  (invalidated_at is None OR t < invalidated_at)
```

These predicates are independent. A fact can be true in the world but not yet known to the system (future ingestion), or can be falsely believed by the system (incorrect ingestion later invalidated). Both states are representable and auditable.

### 3.3 Fact Insertion and Supersession

When a new time-sensitive fact arrives for a subject-predicate pair that already has a currently-valid fact, the implementation MUST supersede the old fact rather than overwrite it. Supersession closes the old fact's intervals and inserts a new fact with fresh intervals.

The reference supersession procedure is:

```python
def supersede(ckf, fact: BiTemporalFact, new_object: str, at: datetime) -> BiTemporalFact:
    """Close the old fact and insert its successor."""
    fact.valid_to = at
    fact.invalidated_at = datetime.now(timezone.utc)
    new_fact = BiTemporalFact(
        subject=fact.subject,
        predicate=fact.predicate,
        object=new_object,
        valid_from=at,
        ingested_at=datetime.now(timezone.utc),
    )
    ckf.insert(new_fact)
    return new_fact
```

**Invariants of supersession:**

1. The old fact's `valid_to` MUST equal the new fact's `valid_from` when both express the same transition moment.
2. The old fact's `invalidated_at` MUST be set to the ingestion time at which the supersession was recorded.
3. The old fact MUST NOT be deleted or mutated in place; only its interval endpoints may be closed.
4. A successor fact SHOULD inherit the subject and predicate of the fact it supersedes.

### 3.4 Retrieval Operations

A conformant bi-temporal CKF MUST support at least the following retrieval operations.

#### 3.4.1 As-Of Retrieval

`retrieve_as_of(subject, predicate, world_time)` returns the unique fact that was true in the world at `world_time`, or `None` if no such fact exists.

```python
def retrieve_as_of(ckf, subject: str, predicate: str, world_time: datetime) -> BiTemporalFact | None:
    candidates = ckf.facts(subject=subject, predicate=predicate)
    return next((f for f in candidates if f.true_in_world_at(world_time)), None)
```

If multiple facts overlap in event time for the same subject-predicate pair, the result is implementation-defined and SHOULD be flagged by retrieval integrity checks (§3.6).

#### 3.4.2 Current Retrieval

`current(subject, predicate)` returns the fact whose `valid_to` is `None` for the given subject-predicate pair, or `None` if none exists.

```python
def current(ckf, subject: str, predicate: str) -> BiTemporalFact | None:
    candidates = ckf.facts(subject=subject, predicate=predicate)
    return next((f for f in candidates if f.valid_to is None), None)
```

Current retrieval is the default for ordinary queries that do not specify a historical context.

#### 3.4.3 Believed-At Retrieval

`believed_at(subject, predicate, system_time)` returns the fact that the system believed at ingestion time `system_time`. This is primarily an audit and debug operation.

```python
def believed_at(ckf, subject: str, predicate: str, system_time: datetime) -> BiTemporalFact | None:
    candidates = ckf.facts(subject=subject, predicate=predicate)
    return next((f for f in candidates if f.believed_by_system_at(system_time)), None)
```

### 3.5 Default Temporal Behaviour for Current Queries

Unless a query explicitly supplies a historical `as_of` or `believed_at` parameter, retrieval MUST default to currently-valid facts (`valid_to is None`). This preserves the existing CKF behaviour for consumers that do not supply temporal context and prevents stale facts from silently entering the context envelope.

### 3.6 Temporal Consistency and Retrieval Integrity

Retrieval integrity (CRP-SPEC-027) is extended with the following temporal checks:

1. **Event-time overlap:** For a given subject-predicate pair, no two non-superseded facts SHOULD have overlapping `valid_from`/`valid_to` intervals. Overlaps indicate a data-quality error or missing supersession.
2. **Ingestion-time inversion:** A fact's `invalidated_at` MUST NOT be earlier than its `ingested_at`.
3. **Event-time inversion:** A fact's `valid_to` MUST NOT be earlier than its `valid_from`.
4. **Future event time:** A fact whose `valid_from` is in the future relative to the query wall-clock SHOULD be excluded from current retrieval and flagged as suspicious.

When an inconsistency is detected, the implementation MUST surface it through the existing retrieval-integrity signals (e.g., confidence downgrade, audit record, or explicit warning) and MUST NOT silently return a possibly incorrect fact.

### 3.7 Serialisation

Bi-temporal facts MUST be serialisable in a form that preserves all four timestamps. The reference implementation provides a `to_dict()` representation using ISO 8601 strings:

```python
{
    "subject": "db",
    "predicate": "host",
    "object": "prod.internal",
    "valid_from": "2024-06-01T00:00:00+00:00",
    "valid_to": None,
    "ingested_at": "2025-01-15T09:23:17.123456+00:00",
    "invalidated_at": None,
}
```

All timestamps SHOULD be stored with timezone information. UTC (`+00:00`) is RECOMMENDED.

### 3.8 Storage Backend Requirements

A bi-temporal CKF store MUST persist the four timestamps alongside the subject-predicate-object triple. The storage backend MAY index facts by:

- subject and predicate (existing CKF requirement),
- `valid_from` and `valid_to` for efficient as-of retrieval,
- `ingested_at` and `invalidated_at` for audit and believed-at retrieval.

The in-memory reference store (`TemporalCKF`) is a minimal implementation. Production backends (e.g., SQLite, PostgreSQL, or a graph store) SHOULD add the relevant temporal indexes.

---

## 4. Integration Points

### 4.1 Contextual Knowledge Fabric (CRP-SPEC-009)

Bi-temporal facts are first-class CKF facts. The CKF graph walk, semantic fallback, and community detection defined in CRP-SPEC-009 operate on the subject-predicate-object triple as before. Temporal filters are applied before or during retrieval; they do not alter the graph structure.

### 4.2 Retrieval Integrity (CRP-SPEC-027)

Temporal consistency checks (§3.6) are added to the retrieval-integrity pipeline. A fact that fails a temporal check MUST be treated similarly to a contradictory or stale fact under CRP-SPEC-027: its relevance score is downgraded, and an integrity event is emitted.

### 4.3 Multi-Horizon Context (CRP-SPEC-028)

The `as_of` parameter for as-of retrieval MAY be supplied by the conversational context layer when a user query includes an explicit temporal reference ("what did we believe last quarter?", "was .40 exposed on 3 June?"). When no temporal reference is present, the conversational layer MUST default to current retrieval.

### 4.4 Context Envelope (CRP-SPEC-003)

Facts inserted into the context envelope SHOULD retain their temporal metadata. The envelope builder MAY filter to currently-valid facts by default and MAY include a small number of recently-superseded facts only when the query explicitly asks for history.

### 4.5 Audit Chain (CRP-SPEC-011)

Every supersession operation MUST extend the HMAC audit chain. The audit record SHOULD contain at minimum:

- the subject and predicate,
- the previous `object` value,
- the new `object` value,
- the `valid_from` of the new fact,
- the `ingested_at` of the new fact,
- the `invalidated_at` assigned to the old fact.

This makes the system's belief evolution verifiable after the fact.

### 4.6 Session Token (CRP-SPEC-007)

The session token MAY carry a `bi_temporal_enabled` boolean and a `default_as_of` timestamp for the current turn. These fields are advisory and are used only to propagate temporal context across turns.

### 4.7 Gateway Service (CRP-SPEC-016)

A CRP Gateway that exposes bi-temporal facts via HTTP SHOULD accept an optional `CRP-As-Of` header (see §5) and translate it into the retrieval layer's `as_of` parameter. The gateway MUST strip the header before forwarding to LLM providers (Axiom 4).

---

## 5. Header Fields

All header fields use the `CRP-` prefix and are subject to Axiom 4 stripping before forwarding to LLM providers.

### 5.1 CRP-As-Of

**Direction:** REQ  
**Required:** OPTIONAL

**Definition:** Requests that retrieval use event-time as-of semantics. The value is an ISO 8601 timestamp.

**Syntax:**

```abnf
CRP-As-Of = date-time    ; ISO 8601, e.g. 2024-06-01T00:00:00Z
```

**Example:**

```
CRP-As-Of: 2024-06-01T00:00:00Z
```

If omitted, the gateway and CKF MUST default to current retrieval (`valid_to is None`).

### 5.2 CRP-Believed-At

**Direction:** REQ  
**Required:** OPTIONAL

**Definition:** Requests that retrieval use ingestion-time believed-at semantics, primarily for audit replay.

**Syntax:**

```abnf
CRP-Believed-At = date-time    ; ISO 8601
```

**Example:**

```
CRP-Believed-At: 2025-01-15T09:23:17Z
```

`CRP-As-Of` and `CRP-Believed-At` SHOULD NOT be supplied in the same request. If both are present, the implementation MUST prefer `CRP-As-Of` for fact retrieval and MAY log the `CRP-Believed-At` value for audit inspection.

---

## 6. Conformance Requirements

A conformant bi-temporal CKF implementation MUST satisfy all of the following requirements.

### 6.1 Fact Model

1. **MUST** represent a bi-temporal fact with `subject`, `predicate`, `object`, `valid_from`, `valid_to`, `ingested_at`, and `invalidated_at` fields.
2. **MUST** treat `valid_to = None` as "still true in the world".
3. **MUST** treat `invalidated_at = None` as "still believed by the system".
4. **SHOULD** store all timestamps with explicit timezone information, preferably UTC.

### 6.2 Supersession

5. **MUST** provide a supersede operation that closes the old fact's `valid_to` and `invalidated_at` and inserts a successor fact with new event-time and ingestion-time values.
6. **MUST NOT** delete or overwrite superseded facts.
7. **SHOULD** preserve the audit chain for every supersession.

### 6.3 Retrieval

8. **MUST** support `retrieve_as_of(subject, predicate, world_time)` returning the fact that was true in the world at `world_time`.
9. **MUST** support `current(subject, predicate)` returning the currently-valid fact.
10. **SHOULD** support `believed_at(subject, predicate, system_time)` returning the fact believed at `system_time`.
11. **MUST** default current queries to currently-valid facts when no temporal context is supplied.

### 6.4 Integrity

12. **MUST** detect and surface event-time overlaps for the same subject-predicate pair.
13. **MUST** reject or flag facts where `valid_to < valid_from` or `invalidated_at < ingested_at`.
14. **MUST** downgrade or reject facts that fail temporal consistency checks rather than returning them silently.

### 6.5 Gateway

15. **MUST** strip `CRP-As-Of` and `CRP-Believed-At` before forwarding requests to LLM providers (Axiom 4).
16. **SHOULD** translate `CRP-As-Of` into the CKF retrieval layer's `as_of` parameter.

### 6.6 Optional Markers

17. **MAY** annotate non-time-sensitive facts as always-valid (i.e., `valid_from` equals ingestion time and `valid_to` is `None`).
18. **MAY** omit bi-temporal fields for facts that are genuinely timeless, but such facts MUST still conform to the base CKF model.

---

## 7. Security Considerations

### 7.1 Temporal Spoofing

An attacker who can write arbitrary timestamps into the CKF can make false facts appear historically valid or can retroactively invalidate true facts. Implementations MUST protect the ingestion-time fields with the same access controls and audit-chain guarantees applied to other CKF mutations (CRP-SPEC-009, CRP-SPEC-011). Event-time values supplied by external sources SHOULD be treated as untrusted and, where possible, corroborated against authoritative logs.

### 7.2 Future-Dated Facts

Facts with `valid_from` set in the future can create confusion or be used to pre-position malicious ground truth. The retrieval layer SHOULD treat future-dated facts as suspicious and exclude them from current retrieval unless explicitly requested by an authorised audit operation.

### 7.3 Denial of Retrieval

Bi-temporal indexes add storage and query cost. Implementations SHOULD bound the number of historical facts returned per query and SHOULD rate-limit believed-at audit queries separately from ordinary retrieval to prevent resource exhaustion.

### 7.4 Audit Tampering

Because bi-temporality is often used to prove "we believed X at time T", the audit records for supersession and retrieval are high-value tampering targets. Every supersession MUST extend the HMAC chain, and consumers MUST be able to verify the chain integrity independently (CRP-SPEC-011).

### 7.5 Privacy

Historical fact sequences can reveal organisational change patterns (e.g., infrastructure migrations, personnel changes). Retention policies and erasure requests (CRP-SPEC-015) MUST apply to the full temporal history, not just the currently-valid fact.

---

## 8. References

- CRP-SPEC-001: Core Protocol
- CRP-SPEC-002: HTTP Headers
- CRP-SPEC-003: Context Envelope
- CRP-SPEC-007: Session Token
- CRP-SPEC-009: Contextual Knowledge Fabric
- CRP-SPEC-011: Audit Trail
- CRP-SPEC-015: Security and Privacy
- CRP-SPEC-016: Gateway Service
- CRP-SPEC-027: Retrieval Integrity
- CRP-SPEC-028: Conversational Context (Multi-Horizon)
- Zep / Graphiti. (2025). *Graphiti: Temporal knowledge graphs for agent memory* [Computer software]. https://github.com/getzep/graphiti

---

*End of CRP-SPEC-057.*
