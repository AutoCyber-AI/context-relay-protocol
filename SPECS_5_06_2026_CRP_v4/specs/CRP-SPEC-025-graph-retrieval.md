# CRP-SPEC-025: Coverage-Differential Graph Retrieval (CDGR)

**Document:** CRP-SPEC-025  
**Title:** Context Relay Protocol (CRP) — Coverage-Differential Graph Retrieval: Multi-Hop Context Assembly  
**Version:** 1.0.0  
**Status:** Final Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Amends:** CRP-SPEC-024 §2, CRP-SPEC-009 §5  
**Prerequisites:** CRP-SPEC-009, CRP-SPEC-024

---

## Abstract

This document closes the most significant gap in CRP's context layer: flat retrieval misses connector facts required for multi-hop reasoning. Coverage-Differential Retrieval (SPEC-024) ranks facts by similarity to the query and novelty against session history. But many correct answers require *chaining* facts — A relates to B relates to C — where the connector fact B has low similarity to the query and is relevant only because it bridges two otherwise-disconnected facts. Flat similarity retrieval cannot surface B. The model receives A and C with no bridge and either fabricates the connection or fails.

The irony CRP must resolve: the CKF already contains a knowledge graph — HNSW neighbour edges and Leiden community structure (SPEC-009) — and CDR ignores it, retrieving as if the facts were an unstructured bag. CDGR uses the graph CRP already built. It seeds with CDR-ranked anchor facts, walks the CKF graph to find high-value connector facts, scores connectors by their *bridging value* rather than query similarity, and assembles an envelope that contains not just relevant facts but the connective tissue between them. This is the difference between context retrieval and context reasoning, and it is achievable in sub-millisecond time because the graph already exists in memory.

---

## 1. The Multi-Hop Problem

### 1.1 Why Flat Retrieval Fails

Consider the query: *"Why does my Kubernetes pod fail to reach the database after a node restart?"*

The correct answer chains four facts:
```
A: "Pods receive new IPs when rescheduled after node restart"      sim=0.88
B: "Services use label selectors to track pod endpoints"           sim=0.61  ← connector
C: "kube-proxy updates iptables when endpoints change"             sim=0.59  ← connector
D: "Stale DNS cache can delay endpoint propagation"                sim=0.84
```

Flat CDR retrieval returns A and D (high similarity). It deprioritises B and C (similarity below the 0.55 threshold from SPEC-024 §2.6). But B and C are *the actual explanation* — they connect "pod got a new IP" to "connection fails." Without them, the model has the symptoms (A, D) but not the mechanism. It fabricates a plausible-sounding bridge or produces an incomplete answer.

### 1.2 The Connector Fact Definition

A **connector fact** is one whose value lies not in its similarity to the query but in its position on the path between two or more anchor facts in the knowledge graph. Connector facts are systematically invisible to similarity-based retrieval because their query similarity is, by definition, lower than the anchors they connect.

### 1.3 What CRP Already Has

SPEC-009 specifies the CKF as a graph:
- **HNSW index** — each fact has K nearest-neighbour edges (default K=20)
- **Similarity edges** — facts with cosine similarity ≥ 0.60 are connected (SPEC-009 §5.2)
- **Leiden communities** — facts clustered into semantic communities (SPEC-009 §5)

This is a fully-formed knowledge graph. CDR uses none of its edge structure — only the vector index for similarity lookup. CDGR uses the edges.

---

## 2. The CDGR Algorithm

### 2.1 Three Phases

```
Phase A — SEED:     Get anchor facts via CDR (SPEC-024)
Phase B — EXPAND:   Walk the CKF graph from anchors to find connectors
Phase C — ASSEMBLE: Score connectors by bridge value, pack seeds + bridges
```

### 2.2 Phase A — Seeding

Run the CDR ranking from SPEC-024 §7.1. Take the top-S facts (default S = ⌊0.7 × envelope_fact_budget⌋) as **anchor seeds**. These are the high-relevance, high-novelty facts CDR already surfaces well.

The remaining 30% of the envelope fact budget is reserved for connectors found in Phase B.

### 2.3 Phase B — Graph Expansion

From each anchor seed, walk the CKF graph outward up to `MAX_HOPS` (default 2) along similarity edges. Collect all facts reachable within the hop limit that are NOT already anchors. These are **connector candidates**.

```python
def expand_connectors(anchors, ckf_graph, max_hops=2):
    connector_candidates = set()
    for anchor in anchors:
        frontier = {anchor.fact_id}
        for hop in range(max_hops):
            next_frontier = set()
            for fid in frontier:
                for neighbour_id in ckf_graph.neighbours(fid):
                    if neighbour_id not in {a.fact_id for a in anchors}:
                        connector_candidates.add(neighbour_id)
                    next_frontier.add(neighbour_id)
            frontier = next_frontier
    return connector_candidates
```

### 2.4 Phase C — Bridge Scoring

Each connector candidate is scored by its **bridge value** — how much it connects otherwise-disconnected anchors. This is the key innovation: connectors are scored on graph topology, not query similarity.

```python
def bridge_value(connector, anchors, ckf_graph):
    """
    A connector's value = how many anchor PAIRS it links that
    would otherwise be disconnected (or weakly connected) in the
    induced subgraph.
    """
    # Which anchors does this connector directly touch?
    touched_anchors = [
        a for a in anchors
        if ckf_graph.has_edge(connector, a.fact_id)
        or ckf_graph.path_length(connector, a.fact_id) <= 2
    ]
    
    if len(touched_anchors) < 2:
        return 0.0  # connects fewer than 2 anchors — no bridge value
    
    # Count anchor pairs this connector bridges that have NO
    # direct edge between them (genuine bridges, not redundant links)
    bridge_count = 0
    for i, a1 in enumerate(touched_anchors):
        for a2 in touched_anchors[i+1:]:
            if not ckf_graph.has_edge(a1.fact_id, a2.fact_id):
                bridge_count += 1   # this pair is ONLY connected via the connector
    
    # Normalise by edge strength along the bridge path
    avg_edge_strength = mean_edge_weight_through(connector, touched_anchors, ckf_graph)
    
    return bridge_count * avg_edge_strength
```

A connector that links two anchors with no direct edge between them scores high — it is the only path between them and therefore essential context. A connector that links anchors already directly connected scores zero — it is redundant.

### 2.5 The Combined CDGR Score

```
For anchor facts (Phase A):
    CDGR_score = CDR_score                       (from SPEC-024)

For connector facts (Phase B/C):
    CDGR_score = bridge_value(connector)
               × novelty(connector)              (still apply CDR novelty)
               × max(relevance, MIN_CONNECTOR_RELEVANCE)
    
    where MIN_CONNECTOR_RELEVANCE = 0.30
    (lower than CDR's 0.55 query-relevance floor, BECAUSE connectors
     are valued for bridging, not direct query relevance)
```

The lowered relevance floor for connectors (0.30 vs 0.55) is deliberate and is the heart of the fix: it allows genuinely useful connector facts that flat retrieval excludes to enter the envelope — but only if they have real bridge value. A low-relevance fact with zero bridge value still scores zero and stays out.

### 2.6 Envelope Assembly

```
envelope_facts = top_S_by_CDR(anchors)              ← ~70% of budget
               + top_C_by_bridge_value(connectors)  ← ~30% of budget
```

Connectors are placed in the envelope ADJACENT to the anchors they bridge — not in the primacy/recency positions (which stay reserved for highest-CDR anchors per SPEC-003), but positioned so the model reads anchor → connector → anchor as a coherent chain.

---

## 3. Why This Is Sub-Millisecond

The graph walk is bounded:
```
cost = |anchors| × avg_degree^max_hops
     = 35 anchors × 16 avg_degree × 2 hops
     ≈ 1,120 edge lookups
```

On an in-memory adjacency structure (the CKF graph is already resident for HNSW search), 1,120 edge lookups plus bridge scoring is well under 1 millisecond. Bridge value computation is O(connectors × anchors²) but both are small (connectors ≤ 200, anchors ≤ 50) and capped. Total CDGR overhead over flat CDR: **< 2ms**. Still Core. Still no extra inference.

---

## 4. Worked Example

Query: *"Why does my pod fail to reach the database after a node restart?"*

**Phase A — CDR seeds (anchors):**
```
A: "Pods receive new IPs when rescheduled"          CDR=0.81
D: "Stale DNS cache delays endpoint propagation"    CDR=0.77
```

**Phase B — graph expansion from A and D finds:**
```
B: "Services use label selectors to track endpoints"  (neighbour of A)
C: "kube-proxy updates iptables on endpoint change"   (neighbour of B and D)
```

**Phase C — bridge scoring:**
```
B: bridges A↔C, A↔D (no direct A-D edge) → bridge_value=2.1 → INCLUDED
C: bridges B↔D, A↔D → bridge_value=1.8 → INCLUDED
```

**Assembled envelope (in reading order):**
```
A → B → C → D
"Pods get new IPs" → "Services track via selectors" →
"kube-proxy updates iptables" → "DNS cache delays propagation"
```

The model now has the complete causal chain. It can explain the *mechanism*, not just list the symptoms. This is the multi-hop answer flat retrieval could never assemble.

---

## 5. Headers

### 5.1 CRP-Context-Graph-Hops

**Direction:** RES  
**Definition:** Maximum hop depth walked during connector expansion.

```
CRP-Context-Graph-Hops: 2
```

### 5.2 CRP-Context-Connectors-Included

**Direction:** RES  
**Definition:** Number of connector facts included via bridge scoring (vs anchor facts from CDR), as `connectors/total`.

```
CRP-Context-Connectors-Included: 6/35
```

### 5.3 CRP-Context-Bridge-Score

**Direction:** RES  
**Definition:** Mean bridge value of included connector facts. Higher means the envelope contains stronger connective tissue between anchors.

```
CRP-Context-Bridge-Score: 1.94
```

---

## 6. Interaction With CDR and Safety Policy

CDGR is a strict superset of CDR. When the CKF graph has no edges (a fresh or sparse CKF), Phase B finds no connectors and CDGR degrades gracefully to pure CDR. CDGR therefore never performs worse than CDR — it only adds connector facts when the graph supports them.

Safety Policy directive:
```
CRP-Safety-Policy: ...; graph-retrieval=on; max-hops=2; connector-budget=0.30
```

| Directive | Values | Meaning |
|-----------|--------|---------|
| `graph-retrieval` | `on`, `off` | Enable/disable connector expansion. Default: on. |
| `max-hops` | 1–3 | Graph walk depth. Default: 2. Higher = more connectors, more cost. |
| `connector-budget` | 0.0–0.5 | Fraction of envelope reserved for connectors. Default: 0.30. |

---

## 7. What CDGR Does Not Solve

CDGR finds connectors that exist in the CKF graph. If the connecting fact was never ingested, no graph walk can surface it — the knowledge gap is real, not a retrieval failure. CDGR also depends on the quality of the CKF edge structure: if the similarity edges are poorly calibrated (wrong embedding model, bad threshold), the graph walk follows bad edges. These are CKF-construction concerns (SPEC-009), upstream of CDGR.

CDGR makes CRP's retrieval graph-aware. It does not make the CKF's graph correct — that is the ingestion pipeline's responsibility.

---

## 8. References

- CRP-SPEC-009 — Contextual Knowledge Fabric (graph structure)
- CRP-SPEC-024 — Coverage-Differential Retrieval (seeding)
- CRP-SPEC-003 — Context Envelope & Packing (assembly)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
