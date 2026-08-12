# CRP-SPEC-035: Context Lifecycle & Access Tiering — The Storage Engine

**Document:** CRP-SPEC-035  
**Title:** Context Relay Protocol (CRP) — Context Lifecycle & Access Tiering: Millisecond Retrieval Through Purpose-Built Storage Primitives  
**Version:** 1.0.0  
**Status:** Foundational — Performance Architecture  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Amends:** CRP-SPEC-009 (CKF storage), CRP-SPEC-028/029 (tier stores)  
**Prerequisites:** CRP-SPEC-009, CRP-SPEC-028, CRP-SPEC-029

---

## Abstract

CRP retrieves context from several stores, but the *storage and access strategy* has been treated as an implementation detail. It is not — it is the difference between millisecond context assembly and second-scale latency. Standard RAG indexes everything into one vector store and queries it the same way for every access pattern. This is inefficient: a vector search is the wrong tool for "what did the last turn say" (that's a pointer read) and overkill for "append this fact" (that's a log write). This document defines CRP's **multi-primitive storage engine**: a set of purpose-built storage and access primitives, each optimal for a specific access pattern, plus a **decision model** specifying exactly when and why each is used. The contribution is not a single new data structure but a *tiered access architecture* — the CKF graph for associative recall, a rolling context log for sequential recency, a hot cache for repeat access, an inverted index for exact-match lookup, and pointer-based ephemeral files for high-volume working data — unified by a router that selects the right primitive per access in microseconds. The result is millisecond retrieval across every context type, because each access uses the storage matched to it rather than forcing everything through one vector index.

---

## 1. Why One Store Is the Wrong Answer

### 1.1 The RAG Default and Its Cost

Standard RAG indexes all content into a vector store and runs an approximate-nearest-neighbour search for every retrieval. This is correct for one access pattern — *associative semantic recall* ("find content similar in meaning to this query") — and wrong or wasteful for the others CRP actually needs:

| Access pattern | Vector search is... | Right primitive |
|---------------|--------------------|-----------------| 
| "Content similar in meaning to X" | correct | vector / graph |
| "What did the last 3 turns say" | wrong (it's sequential) | rolling log (pointer read) |
| "The fact named `budget_q3`" | wasteful (it's exact-match) | inverted index / key lookup |
| "The same query I ran 2s ago" | wasteful (it's a repeat) | hot cache |
| "These 5,000 tool-output rows" | catastrophic (volume) | pointer-based ephemeral file |
| "Facts connected to X via reasoning" | incomplete (needs edges) | graph walk (CDGR) |

Forcing all six through a vector index means five of them pay vector-search cost (embedding + ANN traversal) for an access that a simpler primitive would serve in microseconds. **Millisecond retrieval requires using the right primitive per access, not the same primitive for all.**

---

## 2. The Five Storage Primitives

CRP's storage engine provides five primitives, each owning the access patterns it is optimal for.

### 2.1 The CKF Graph (Associative Recall) — SPEC-009/025

**Owns:** semantic similarity retrieval and multi-hop connector recall.  
**Structure:** HNSW vector index + similarity-edge graph + Leiden communities.  
**Access cost:** sub-millisecond ANN lookup; ~2ms for graph walk (CDGR).  
**When used:** the query needs facts *related in meaning* to it, including connector facts (the core CDR/CDGR path).  
**Lifecycle:** persistent, slow TTL decay (months–years), per-tenant.

### 2.2 The Rolling Context Log (Sequential Recency) — NEW

**Owns:** recent, ordered context — conversation turns, recent operations, the "what just happened" window.  
**Structure:** an append-only ring buffer backed by an **ephemeral disk-stored file with a pointer index**. New entries append; a head pointer marks the most recent; old entries roll off the tail. Reading "the last N" is a pointer-offset read — no search, no embedding.  
**Access cost:** microseconds (pointer arithmetic + sequential read).  
**When used:** recency-ordered access — the Turn Log (SPEC-028), recent operations, the immediate prior window. This is the "rolling context.txt" pattern: a compact, append-only, pointer-addressed file that always holds the most recent context for instant sequential access.  
**Lifecycle:** ephemeral, ring-buffered (fixed size; oldest rolls off), session-scoped.  
**Why a file with a pointer, not a vector store:** recency access is *positional*, not semantic. "The last 3 turns" is offsets [head, head-1, head-2] — a file seek, returned in microseconds. Embedding and ANN-searching for this would be absurd overhead. The rolling log makes recency access effectively free.

### 2.3 The Hot Cache (Repeat Access) — NEW

**Owns:** identical or near-identical repeat retrievals.  
**Structure:** an in-memory LRU keyed by a hash of (query embedding bucket + CKF state hash). If the same (or semantically bucketed) query is issued while the CKF state is unchanged, the prior assembled envelope is returned directly.  
**Access cost:** microseconds (hash lookup).  
**When used:** the same question asked twice, retries, multi-agent branches querying the same thing, conditional dispatch (the ETag path, SPEC-003 §11).  
**Lifecycle:** in-memory, invalidated on CKF state change (ETag), short TTL.  
**Why:** repeat retrieval is common (retries, parallel branches, follow-ups) and re-running CDR/CDGR for an identical query against unchanged knowledge is pure waste. The cache turns the second access into a hash hit.

### 2.4 The Inverted Index (Exact Match) — NEW

**Owns:** exact-match and keyed lookup — named facts, entities, identifiers, structured fields.  
**Structure:** a term→fact and key→fact inverted index alongside the vector store.  
**Access cost:** microseconds (hash/index lookup).  
**When used:** "the fact named X", "facts mentioning entity Y exactly", "the value of field Z", reference resolution to named entities (SPEC-028 §4).  
**Lifecycle:** persistent, rebuilt incrementally with the CKF.  
**Why:** exact-match is a solved problem (inverted indexes) and vastly cheaper than semantic search for it. When the access is "this exact name/key", an index lookup beats ANN by orders of magnitude.

### 2.5 The Pointer-Based Ephemeral Store (High-Volume Working Data) — NEW

**Owns:** large, structured, transient data — tool outputs, intermediate results, anything too big for the envelope and too transient for the CKF.  
**Structure:** the Scratch Buffer (SPEC-029) backed by disk-stored blobs addressed by pointer (scratch_id). The *summary* lives in memory/envelope; the *full blob* lives on ephemeral disk, fetched by pointer only when specifically referenced.  
**Access cost:** microseconds for the summary (in-memory); single disk read for the full blob on demand.  
**When used:** tool results (a 5,000-row query), intermediate computations, anything high-volume and short-lived (SPEC-029).  
**Lifecycle:** ephemeral, freshness-gated, evicted by TTL/LRU (SPEC-029 §4–5).  
**Why:** high-volume data must not enter the envelope (it blows the window) nor the CKF (it's transient and would pollute persistent knowledge). A pointer to a disk blob, with only the summary in context, gives O(1) reference and on-demand full access without ever loading the volume into the model's context unless explicitly needed.

---

## 3. The Access Router — Choosing the Primitive Per Access

### 3.1 The Decision Model

For every context access, the router selects the primitive in microseconds based on the access *type*, which is known from the calling context (the STL operation type, SPEC-031, or the retrieval intent, SPEC-028):

```
ACCESS REQUEST
   │
   ├─ Is it a repeat of a recent identical access (unchanged CKF)?
   │     → HOT CACHE (microseconds)              [check first, always]
   │
   ├─ Is it recency-ordered ("last N", "recent", sequential)?
   │     → ROLLING CONTEXT LOG (pointer read)
   │
   ├─ Is it an exact name/key/entity lookup?
   │     → INVERTED INDEX (index lookup)
   │
   ├─ Is it a reference to high-volume working data (tool output)?
   │     → POINTER-BASED EPHEMERAL STORE (pointer → summary, blob on demand)
   │
   ├─ Does it need facts related in MEANING (+ connectors)?
   │     → CKF GRAPH via CDR/CDGR (ANN + graph walk)
   │
   └─ Complex/blended? → router composes multiple primitives,
        merges results (e.g. recent turns from the log + semantic
        facts from the graph + a named value from the index)
```

### 3.2 The Router Is Driven by Known Intent, Not Guessing

Crucially, the router rarely has to *infer* the access type — it is told. The STL (SPEC-031) knows each operation's frame requirement: a RETRIEVE operation on a named entity routes to the inverted index; a SYNTHESISE operation routes to the CKF graph; a conversational DRILL_DOWN (SPEC-028) routes to the rolling log + reference resolution. The access type falls out of the operation/intent classification already happening upstream. The router is a fast dispatch on a known type, not an expensive classification.

### 3.3 Composition for Blended Access

Real envelopes often blend primitives. The STL building a frame for "summarise what we discussed about the query results" composes:
- rolling log → the recent conversational turns ("what we discussed")
- pointer store → the tool-output summary ("the query results")
- CKF graph → any domain facts needed for "summarise"

The router fetches from each in parallel (each microseconds-to-low-ms) and the envelope assembler (SPEC-003) packs the merged result. Total: still milliseconds, because no single primitive is slow and they run concurrently.

---

## 4. The Lifecycle Model — When Data Moves Between Primitives

### 4.1 Data Flows Across Primitives Over Its Lifetime

A piece of context is not bound to one store forever — it flows to the primitive matching its current access pattern and lifecycle stage:

```
TOOL OUTPUT arrives (high volume, transient)
   → Pointer-based ephemeral store (blob + summary)
   │
   │ if referenced repeatedly / user pins it (SPEC-029 §5)
   ▼
   → promoted: summary becomes a fact in the CKF graph (durable)
   │   + indexed in the inverted index (if it has a name/key)
   │
CONVERSATION TURN happens (recent, sequential)
   → Rolling context log (append)
   │
   │ as it ages past the recency window
   ▼
   → rolls off the log; if it established a durable fact,
     that fact is already in the CKF (promoted at the time)
   │
QUERY RESULT assembled
   → Hot cache (in case it repeats)
   │
   │ on CKF state change (ETag)
   ▼
   → cache invalidated; next access re-assembles from source
```

### 4.2 The Promotion Rule (Ephemeral → Persistent)

The single most important lifecycle transition: when transient data proves durable, it is **promoted** from an ephemeral primitive (rolling log, pointer store) into the persistent CKF graph (and indexed). Promotion triggers (from SPEC-029 §5 and SPEC-030):
- A tool result that is pinned or referenced ≥2 times
- A conversational turn that establishes a fact reused across threads
- A computed value the user names ("call that the budget figure")

Promotion is how a session's working context becomes durable knowledge without polluting the CKF with transient noise. Most ephemeral data is *never* promoted — it rolls off or is evicted. Only what proves durable graduates.

### 4.3 The Demotion / Eviction Rule (cleanup)

- Rolling log entries roll off the tail (fixed ring size).
- Hot cache entries evict on CKF state change or TTL.
- Pointer-store blobs evict by freshness TTL / LRU (SPEC-029 §4).
- CKF facts decay by recency (SPEC-027 §3); stale facts are deprioritised, archived, or erased.

Every primitive has a defined cleanup so storage never grows unbounded.

---

## 5. Why This Achieves Millisecond Retrieval

| Access | Primitive | Cost |
|--------|-----------|------|
| Repeat query | hot cache | ~microseconds (hash) |
| Last N turns | rolling log | ~microseconds (pointer read) |
| Named fact | inverted index | ~microseconds (index) |
| Tool-output reference | pointer store | ~microseconds (summary) / 1 disk read (blob) |
| Semantic recall | CKF ANN | sub-millisecond |
| Multi-hop | CKF graph walk | ~2ms |
| Blended | composed, parallel | bounded by slowest (~2ms) |

No access path forces unnecessary work. The expensive operation (semantic vector search + graph walk) runs *only* when the access genuinely needs associative recall. Everything else uses a primitive that answers in microseconds. This is how CRP assembles context in milliseconds where naive single-store RAG pays vector-search cost for every access.

---

## 6. Headers

| Header | Meaning |
|--------|---------|
| `CRP-Context-Store-Used` | Which primitive(s) served this access: `cache`/`log`/`index`/`pointer`/`graph` or a blend |
| `CRP-Context-Cache-Hit` | `true` if the hot cache served the retrieval |
| `CRP-Context-Retrieval-Ms` | Wall-clock retrieval time (should be low single-digit ms) |
| `CRP-Context-Promotions` | Count of ephemeral items promoted to the CKF this turn |

`CRP-Context-Retrieval-Ms` makes the millisecond claim measurable and auditable per call.

---

## 7. Honest Status & Limits

The five primitives are individually standard (vector index, ring buffer, LRU cache, inverted index, blob store with pointers) — none is a novel data structure. The contribution is the *integrated tiered architecture and the router that selects per access by known intent*, applied to LLM context management. This is a systems-design contribution (right tool per access pattern, with defined lifecycle flow and promotion), not a new algorithm — and it should be claimed as such: CRP is efficient because it stopped forcing everything through a vector index, not because it invented a new index.

The rolling-context-log-as-file approach assumes fast local disk (or memory-mapped); on slow storage the microsecond claim degrades to disk-latency. Production deployments should back the rolling log with memory-mapped files or in-memory ring buffers, spilling to disk only for durability.

The promotion rule's "is this durable?" judgment is heuristic (reference count, pinning, naming). Mis-promotion (promoting transient noise) pollutes the CKF; under-promotion (dropping durable data) loses it. The heuristics (SPEC-029 §5) are conservative — bias toward not polluting the CKF — but are a tunable trade-off.

---

## 8. References

- CRP-SPEC-009 — CKF (the graph primitive)
- CRP-SPEC-025 — CDGR (graph-walk access)
- CRP-SPEC-027 — Retrieval Integrity (recency decay feeding lifecycle)
- CRP-SPEC-028 — Multi-Horizon (the Turn Log → rolling log)
- CRP-SPEC-029 — Ephemeral/Tool (the pointer store)
- CRP-SPEC-031 — STL (drives the access router by operation type)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
