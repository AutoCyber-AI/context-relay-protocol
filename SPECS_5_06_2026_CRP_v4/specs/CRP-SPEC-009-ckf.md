# CRP-SPEC-009: Contextual Knowledge Fabric (CKF) Specification

**Document:** CRP-SPEC-009  
**Title:** Context Relay Protocol (CRP) — Contextual Knowledge Fabric  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Date:** 2026-05-25  
**License:** CC BY 4.0 (specification text)  
**Prerequisites:** CRP-SPEC-001, CRP-SPEC-003

---

## Abstract

This document specifies the Contextual Knowledge Fabric (CKF) — CRP's persistent knowledge graph that serves as Tier 3 (cold storage) in the four-tier memory hierarchy. The CKF stores facts as graph-embedded nodes with vector representations, connected by semantic edges, and organised into communities via the Leiden algorithm. It is the long-term memory from which Context Envelopes are assembled, and the persistence layer that enables cross-session knowledge reuse, conditional dispatch via ETag caching, and knowledge staleness tracking.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                 Contextual Knowledge Fabric              │
│                                                          │
│  ┌───────────┐   ┌───────────┐   ┌───────────────────┐ │
│  │ Fact Store │   │ HNSW Index│   │ Community Graph   │ │
│  │ (nodes)   │◄──│ (vectors) │──►│ (Leiden clusters) │ │
│  └───────────┘   └───────────┘   └───────────────────┘ │
│        │                                    │            │
│  ┌─────▼──────┐                   ┌────────▼────────┐  │
│  │ Source      │                   │ State Hash      │  │
│  │ Registry   │                   │ (ETag source)   │  │
│  └────────────┘                   └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Fact Node Schema

Each fact in the CKF is stored as a node with the following fields:

```
FactNode {
  fact_id:             string       // UUID — immutable after creation
  content:             string       // The fact text (1–2048 tokens max)
  content_hash:        string       // SHA-256 of content (change detection)
  embedding:           float[]      // Vector embedding (model-specific dimensionality)
  source_id:           string       // Reference to originating document in Source Registry
  source_location:     string       // Page number, paragraph, URL fragment
  importance_weight:   float        // 0.0–1.0, intrinsic to the fact
  community_label:     string       // Leiden community assignment
  ingested_at:         ISO 8601     // Timestamp of initial ingestion
  modified_at:         ISO 8601     // Timestamp of last modification
  access_count:        integer      // Number of times included in an envelope
  last_accessed_at:    ISO 8601     // Timestamp of most recent envelope inclusion
  ttl:                 ISO 8601 dur // Optional time-to-live (e.g., P90D)
  status:              enum         // ACTIVE | STALE | DELETED | QUARANTINED
  metadata:            map          // Arbitrary key-value pairs
}
```

### 2.1 Fact Size Constraints

- Minimum content length: 10 tokens
- Maximum content length: 2,048 tokens
- Facts exceeding 2,048 tokens MUST be chunked during ingestion (see §4)

### 2.2 Fact Status Lifecycle

```
ACTIVE ──→ STALE (ttl expired, manual flag, or source document updated)
ACTIVE ──→ DELETED (source document removed, GDPR erasure request)
ACTIVE ──→ QUARANTINED (flagged by DPE as producing fabrication/distortion)
STALE  ──→ ACTIVE (re-ingested from updated source)
STALE  ──→ DELETED (manual cleanup)
DELETED ──→ (permanent removal from HNSW index after 30 days)
```

Facts with status `STALE` MAY still be retrieved during envelope construction but receive a freshness penalty in the ranking phase (CRP-SPEC-003 §6.4). Facts with status `DELETED` or `QUARANTINED` MUST NOT be retrieved.

---

## 3. HNSW Vector Index

### 3.1 Purpose

The Hierarchical Navigable Small World (HNSW) index provides sub-linear approximate nearest-neighbour search over fact embeddings, enabling fast retrieval during envelope construction Phase 1 (CRP-SPEC-003 §5).

### 3.2 Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `M` | 16 | Max connections per node per layer |
| `ef_construction` | 200 | Size of dynamic candidate list during construction |
| `ef_search` | 100 | Size of dynamic candidate list during search |
| `distance_metric` | `cosine` | Distance function for similarity |
| `dimensions` | Model-dependent | Embedding vector dimensionality (e.g., 1536 for text-embedding-3-small) |

### 3.3 Index Maintenance

- New facts are added to the index immediately upon ingestion
- Deleted facts are marked in a deletion set and excluded from search results; physical removal occurs during periodic index compaction
- Modified facts (content_hash changed) trigger re-embedding and index update
- Index is rebuilt fully if >20% of nodes have been modified/deleted since last rebuild

### 3.4 Multi-Model Embeddings

If the CRP deployment changes embedding models (e.g., upgrading from text-embedding-3-small to text-embedding-3-large):
- All existing facts MUST be re-embedded with the new model
- The HNSW index MUST be rebuilt
- During migration, dual indexes MAY run in parallel
- The CKF state hash (ETag) changes on embedding model change — all client ETags are invalidated

---

## 4. Document Ingestion Pipeline

### 4.1 Ingestion Flow

```
Source Document → Chunking → Fact Extraction → Embedding → HNSW Insert → Community Update
```

### 4.2 Chunking Strategy

Documents are chunked using a semantic-aware chunking strategy:

1. **Paragraph-level splitting:** Split on paragraph boundaries first
2. **Sentence-level refinement:** If a paragraph exceeds 512 tokens, split at sentence boundaries
3. **Overlap:** 10% token overlap between adjacent chunks to preserve cross-boundary context
4. **Metadata preservation:** Each chunk retains: source_id, page number, section heading

### 4.3 Fact Extraction

Each chunk becomes one or more facts:
- Simple chunks (single coherent assertion) → 1 fact
- Complex chunks (multiple assertions) → decomposed into N facts using the claim segmentation model (same as DPE Stage 1, CRP-SPEC-005 §3)

### 4.4 Importance Weight Assignment

Importance weight is assigned based on source metadata:

| Source Type | Base Weight | Modifiers |
|------------|-------------|-----------|
| Regulatory text (laws, standards) | 0.90 | +0.05 for specific articles |
| Official documentation | 0.80 | +0.05 for version-specific content |
| Peer-reviewed research | 0.75 | +0.10 for meta-analyses |
| Internal company documents | 0.70 | Varies by classification |
| Web content | 0.50 | +0.10 for authoritative domains |
| User-provided context | 0.60 | Configurable |

### 4.5 Source Registry

Every ingested document is recorded in the Source Registry:

```
SourceRecord {
  source_id:           string       // UUID
  title:               string       
  uri:                 string       // Original document location
  document_hash:       string       // SHA-256 of document content
  ingested_at:         ISO 8601
  fact_count:          integer      // Number of facts extracted
  status:              enum         // ACTIVE | UPDATED | REMOVED
}
```

When a source document is updated:
1. New version is ingested alongside old version
2. Old facts are marked `STALE`
3. New facts reference the same source_id with updated content_hash
4. DPE is notified of source changes for cross-window coherence validation

---

## 5. Community Detection (Leiden Algorithm)

### 5.1 Purpose

The Leiden algorithm clusters semantically related facts into communities. Communities enable:
- Targeted retrieval expansion (CRP-SPEC-003 §5.2 Step 1.3)
- Knowledge domain identification (emitted as `CRP-Memory-CKF-Community`)
- Diversity scoring in the ranking phase

### 5.2 Graph Construction

Before running Leiden, a similarity graph is constructed:
1. For each fact, find K nearest neighbours in the HNSW index (default K=20)
2. Create edges between facts with cosine similarity ≥ 0.60
3. Edge weight = cosine similarity value

### 5.3 Leiden Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `resolution` | 1.0 | Controls community granularity (higher = more communities) |
| `n_iterations` | 10 | Optimisation iterations |
| `min_community_size` | 3 | Minimum facts per community |

### 5.4 Community Labels

Each community is assigned a human-readable label by sampling the 5 highest-importance facts and extracting the dominant topic via keyword extraction.

### 5.5 Reclustering Schedule

Communities are recomputed:
- After every ingestion batch of ≥50 new facts
- On a scheduled basis (default: weekly)
- When explicitly triggered by the operator
- Reclustering changes the CKF state hash → invalidates all client ETags

---

## 6. CKF State Hash (ETag Source)

### 6.1 Computation

```
state_components = SORT([
  f.fact_id + ":" + f.content_hash + ":" + f.status
  for f in all_active_facts
])
ckf_state_hash = SHA-256("|".join(state_components))
```

### 6.2 Change Detection

The state hash changes when:
- Any fact is added, modified, or deleted
- Any fact's status changes
- Community reclustering occurs (labels change)

It does NOT change when:
- Facts are accessed (read-only)
- Access counts are updated
- No structural changes occur

### 6.3 ETag Emission

The CKF state hash is the source for `CRP-Context-ETag` (CRP-SPEC-002 §4.8).

---

## 7. Cache-Control Semantics for CKF

### 7.1 CRP-Context-Cache Directives (CKF-Specific)

| Directive | CKF Behaviour |
|-----------|--------------|
| `reuse-ckf` | Read from CKF but do not trigger source re-ingestion |
| `no-store` | Do not write this session's facts to CKF. Read is still permitted. |
| `no-cache` | Ignore cached envelope; force full Phase 1 retrieval from CKF |
| `only-if-ckf` | Fail with 424 if CKF has no facts with relevance ≥ 0.50 for this query |
| `max-age=N` | Facts with `ingested_at` older than N seconds are treated as STALE for ranking |

### 7.2 GDPR-Specific Cache Behaviour

When `CRP-Context-Cache: no-store` is set:
- Session-generated facts are held in Tier 1 (hot session cache) only
- On session end, all Tier 1 facts for this session are purged
- No CKF graph mutations occur
- The CKF state hash does not change

When `CRP-Compliance-Data-Residency` is set:
- CKF reads are restricted to facts stored in the specified region
- CKF writes are directed to the specified region's storage

---

## 8. Fact Lifecycle Management

### 8.1 TTL-Based Staleness

Facts with a `ttl` field are automatically marked `STALE` when `current_time > ingested_at + ttl`. Stale facts receive a freshness penalty in ranking but are not deleted.

### 8.2 Access-Based Eviction

Facts not accessed within a configurable period (default: 180 days) MAY be archived to cold storage (reducing HNSW index size). Archived facts can be restored on demand.

### 8.3 GDPR Right to Erasure

When a customer requests erasure (GDPR Art. 17):
1. All facts with the specified `source_id` are marked `DELETED`
2. The HNSW index excludes deleted facts from search results immediately
3. Deleted facts are physically removed from storage within 30 days
4. The CKF state hash is recomputed → all ETags invalidated
5. The audit trail records the erasure event (the fact that erasure occurred is retained; the erased content is not)

### 8.4 Fact Quarantine

If the DPE detects that a specific CKF fact consistently produces fabrications or distortions when included in envelopes (tracked via the audit trail):
1. The fact is marked `QUARANTINED`
2. Quarantined facts are excluded from retrieval
3. The operator is notified to review the source document
4. Quarantine can be lifted manually after review

---

## 9. Multi-Tenant CKF Isolation

### 9.1 Tenant Isolation Model

In multi-tenant CRP Gateway deployments:
- Each tenant has a separate CKF namespace
- HNSW indexes are per-tenant (no cross-tenant vector search)
- Community detection runs per-tenant
- CKF state hashes are per-tenant
- Cross-tenant fact access is architecturally impossible

### 9.2 Shared Knowledge Bases

Operators MAY configure shared CKF namespaces accessible by multiple tenants (e.g., regulatory knowledge). Shared namespaces:
- Are read-only for tenants
- Are managed by the platform operator
- Have their own state hash (included in the combined ETag computation)

---

## 10. References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-003 — Context Envelope & Packing
- CRP-SPEC-015 — Security & Privacy
- Malkov, Y. and Yashunin, D. (2018). "Efficient and robust approximate nearest neighbor using Hierarchical Navigable Small World graphs"
- Traag, V.A., Waltman, L. and van Eck, N.J. (2019). "From Louvain to Leiden: guaranteeing well-connected communities"

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
