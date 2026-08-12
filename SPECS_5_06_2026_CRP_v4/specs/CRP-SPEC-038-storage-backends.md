# CRP-SPEC-038: Pluggable Storage Backends — Bring Your Own Store

**Document:** CRP-SPEC-038  
**Title:** Context Relay Protocol (CRP) — Pluggable Storage Backends: User-Definable Locations, Backends, and Visibility for Every Storage Primitive  
**Version:** 1.0.0  
**Status:** Foundational — Deployment Flexibility  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Amends:** CRP-SPEC-035 (storage primitives), CRP-SPEC-037 (config)  
**Prerequisites:** CRP-SPEC-035, CRP-SPEC-037

---

## Abstract

SPEC-035 defines five storage primitives (CKF graph, rolling context log, hot cache, inverted index, pointer-based ephemeral store) but treats their physical storage as internal. This is a real limitation for the local-first, data-sovereign deployments CRP targets: a developer cannot say "put my CKF in my own Postgres/pgvector," "store the rolling log on this path," or "let me inspect what's in my knowledge fabric." This document makes every storage primitive **pluggable and locatable**: each has a defined backend interface, ships with a sensible default backend, and can be pointed at a user-provided store through the unified config. It also defines **visibility** — how a developer inspects, exports, and views the contents of each primitive. The principle: CRP owns the *access logic* (the router, the formulas, the lifecycle) but the developer owns the *data and its location*. This is what makes CRP genuinely local-first and sovereign — your knowledge lives where you choose, in a store you control, inspectable by you, while CRP provides the intelligence layer over it.

---

## 1. The Principle: CRP Owns Logic, You Own Data

```
┌─────────────────────────────────────────────────────────┐
│  CRP owns:  the ACCESS LOGIC                             │
│    - the router (which primitive per access, SPEC-035)   │
│    - CDR/CDGR formulas, lifecycle, promotion rules        │
│    - the protocol semantics                              │
├─────────────────────────────────────────────────────────┤
│  YOU own:   the DATA and its LOCATION                    │
│    - which backend stores each primitive                 │
│    - where it physically lives (your infra, your cloud)  │
│    - the ability to inspect, export, and delete it       │
└─────────────────────────────────────────────────────────┘
```

This separation is what "bring your own store" means: CRP is the intelligent
access layer; the storage is yours, wherever you want it, in whatever
supported backend you choose.

---

## 2. The Backend Interface Per Primitive

Each of the five primitives (SPEC-035) defines a backend interface. CRP ships
a default backend for each (works out of the box) and accepts any conforming
backend the developer configures.

### 2.1 CKF Graph Backend

```
CKFBackend interface:
    upsert_fact(fact, embedding, metadata)
    search(query_embedding, k) -> facts        # ANN
    neighbours(fact_id) -> fact_ids             # graph edges
    delete(fact_id)                             # GDPR erasure
    stats() -> {fact_count, communities, ...}
```

| Backend | When to use | How configured |
|---------|------------|----------------|
| `crp-native` (default) | zero-setup, embedded HNSW | nothing — works out of the box |
| `pgvector` | you already run Postgres | `backend: pgvector, dsn: ...` |
| `qdrant` / `weaviate` / `milvus` | dedicated vector DB at scale | `backend: qdrant, url: ...` |
| `pinecone` | managed vector cloud | `backend: pinecone, api_key: ...` |
| custom | your own store | implement `CKFBackend` |

### 2.2 Rolling Context Log Backend

```
RollingLogBackend interface:
    append(entry)
    read_recent(n) -> entries                   # pointer/offset read
    roll_off()                                  # evict tail
```

| Backend | When to use | Config |
|---------|------------|--------|
| `mmap-file` (default) | fast local, durable | `path: ./crp/rolling.log` |
| `memory` | ephemeral, fastest | `backend: memory` |
| `redis` | shared across instances | `backend: redis, url: ...` |

### 2.3 Hot Cache Backend

| Backend | When to use | Config |
|---------|------------|--------|
| `memory-lru` (default) | single instance | `size: 1000` |
| `redis` | shared cache, multi-instance | `backend: redis, url: ...` |

### 2.4 Inverted Index Backend

| Backend | When to use | Config |
|---------|------------|--------|
| `crp-native` (default) | embedded | nothing |
| `elasticsearch` / `opensearch` | existing search infra | `backend: elasticsearch, url: ...` |
| `sqlite-fts` | lightweight local | `path: ./crp/index.db` |

### 2.5 Pointer-Based Ephemeral Store Backend

| Backend | When to use | Config |
|---------|------------|--------|
| `local-disk` (default) | local blobs | `path: ./crp/scratch/` |
| `s3` / `gcs` / `azure-blob` | cloud blob storage | `backend: s3, bucket: ...` |
| `memory` | small, fastest | `backend: memory` |

---

## 3. Configuring Storage in the Unified Config

All storage locations and backends live in the `context.storage` section of
the unified config (SPEC-037), extended here:

```yaml
context:
  storage:
    # CKF — your knowledge fabric, your location
    ckf:
      backend: pgvector
      dsn: "${DATABASE_URL}"
      table: "crp_facts"
      # view/inspect endpoint auto-exposed (§4)

    # Rolling context log — set your own location
    rolling_log:
      backend: mmap-file
      path: "./crp/rolling.log"
      size: 50                     # ring buffer entries

    # Hot cache
    hot_cache:
      backend: redis
      url: "${REDIS_URL}"

    # Inverted index
    inverted_index:
      backend: sqlite-fts
      path: "./crp/index.db"

    # Ephemeral scratch (tool outputs)
    scratch:
      backend: s3
      bucket: "my-crp-scratch"
      ttl: "5m"

    # default (omit everything): all crp-native/local, zero setup
```

Omit the whole section and everything uses the zero-setup defaults
(embedded native stores, local files). Specify only what you want to
relocate — e.g. just point the CKF at your pgvector and leave the rest
default.

---

## 4. Visibility — Inspect, View, Export Your Data

A developer must be able to see what's in each primitive. Every backend
exposes inspection through the SDK:

```python
# CKF — what does CRP know?
client.knowledge.stats()                 # counts, communities, coverage
client.knowledge.search("etcd")          # browse facts by query
client.knowledge.facts(source="manual.pdf")  # facts from a doc
client.knowledge.location()              # WHERE it's stored: "pgvector://...table=crp_facts"
client.knowledge.export("facts.jsonl")   # full export

# Rolling log — what's the recent context?
client.context.rolling.view()            # the current rolling window
client.context.rolling.location()        # "./crp/rolling.log"

# Scratch — what tool data is held?
client.context.scratch.list()            # active entries + summaries
client.context.scratch.location()        # "s3://my-crp-scratch/"

# Everything — one overview
client.storage.overview()
```

`client.storage.overview()` prints a map of every primitive, its backend,
its location, and its size:

```
CRP STORAGE MAP
  CKF graph       pgvector   postgres://…/crp_facts      12,840 facts
  Rolling log     mmap-file  ./crp/rolling.log           50 entries
  Hot cache       redis      redis://…                   312 cached
  Inverted index  sqlite-fts ./crp/index.db              8,201 terms
  Scratch store   s3         s3://my-crp-scratch/         7 blobs (2 pinned)
```

This answers the exact questions: *where is my CKF stored, where do I view
it, where is my vector store, where is my rolling log* — all visible,
located, and exportable.

---

## 5. The Local-First / Sovereignty Guarantee

For AutoCyber AI's local-first positioning, this is essential. A developer
can run CRP entirely on their own infrastructure:

```yaml
context:
  storage:
    ckf:            { backend: pgvector,   dsn: "${LOCAL_PG}" }
    rolling_log:    { backend: mmap-file,  path: "/data/crp/log" }
    inverted_index: { backend: sqlite-fts, path: "/data/crp/idx" }
    scratch:        { backend: local-disk, path: "/data/crp/scratch" }
deployment:
  mode: local        # no hosted gateway; CRP runs in-process
```

No data leaves the developer's infrastructure. CRP provides the access
intelligence; every byte of context lives in the developer's own stores.
This is the data-sovereignty promise made concrete: **your knowledge, your
location, your control — CRP is just the brain over it.**

---

## 6. Migration and Backend Switching

Switching backends (e.g. native → pgvector as you scale) is a config change
plus a re-index:

```python
client.storage.migrate(primitive="ckf", to="pgvector", dsn="...")
# re-embeds and re-indexes facts into the new backend; verifies count
```

Embedding-model consistency (SPEC-027 §2.5) is enforced across migration —
the same embedding model must be used or a full re-embed is triggered and
flagged.

---

## 7. Headers

| Header | Meaning |
|--------|---------|
| `CRP-Storage-CKF-Backend` | The active CKF backend (e.g. `pgvector`) |
| `CRP-Storage-Location-Hash` | Hash of the storage configuration (provenance) |

---

## 8. Honest Status & Limits

The backend interfaces are standard adapter patterns; shipping adapters for
every store (pgvector, qdrant, pinecone, redis, elasticsearch, s3, etc.) is
ongoing engineering — CRP ships the native defaults plus the most common
adapters first, and the interface lets the community or the developer add
others.

A user-provided backend is only as fast as that backend. The millisecond
guarantees (SPEC-035) assume the default local/native stores or a
low-latency configured store. Pointing the CKF at a slow remote vector DB
trades sovereignty/scale for latency — the developer's choice, surfaced via
`CRP-Context-Retrieval-Ms`.

Custom backends run in the retrieval path; they must meet the interface
contract and latency expectations or the developer's own deployment degrades.
CRP validates a configured backend on startup (connectivity, schema) and
fails fast with a clear error rather than degrading silently.

---

## 9. References

- CRP-SPEC-035 — Context Lifecycle & Access Tiering (the primitives)
- CRP-SPEC-037 — Unified Config (where storage is configured)
- CRP-SPEC-027 — Retrieval Integrity (embedding-model consistency on migration)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
