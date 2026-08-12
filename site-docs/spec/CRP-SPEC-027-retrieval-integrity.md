# CRP-SPEC-027: Retrieval Integrity - Concurrency, Conflict Resolution & Recency

**Document:** CRP-SPEC-027  
**Title:** Context Relay Protocol (CRP) - Retrieval Integrity: Parallel Coverage Isolation, Fact Authority Resolution, and Recency Weighting  
**Version:** 1.0.0  
**Status:** Final Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Amends:** CRP-SPEC-024 §2 (CDR formula), CRP-SPEC-004 §6 (fan-out), CRP-SPEC-009 §8 (fact lifecycle)  
**Prerequisites:** CRP-SPEC-004, CRP-SPEC-009, CRP-SPEC-024, CRP-SPEC-025

---

## Abstract

This document closes three correctness gaps in CRP's retrieval layer that, left unaddressed, produce duplicate content, contradictory context, and stale-fact selection. Each is a real defect in the CDR/CDGR retrieval path as specified, and each has a precise, low-cost fix:

- **Gap 3 (Concurrency):** Parallel fan-out windows share a mutable Coverage Set, creating a race condition where two branches both retrieve the same "novel" facts and produce duplicate content. Fixed by pre-partitioning disjoint coverage scopes before fan-out.
- **Gap 4 (Contradiction):** The CKF can hold mutually contradictory facts (a current value and a superseded stale value). CDR ranks by relevance and novelty with no truth arbitration, handing the model both. Fixed by Fact Authority Resolution at retrieval time.
- **Gap 5 (Recency):** The CDR formula has no recency term, so a stale-but-novel fact can outrank a fresh-but-covered one. Fixed by adding a recency decay factor to the CDR score.

Gaps 4 and 5 are connected: recency is a component of fact authority. All three fixes preserve the sub-millisecond, Core-tier, no-extra-inference properties of the retrieval path.

---

## 1. Gap 3 - Parallel Coverage Isolation

### 1.1 The Race Condition

CDR maintains a session-scoped Coverage Set (SPEC-024 §2.1) updated after each window. Fan-out dispatch (SPEC-004 §6) runs multiple windows in parallel. The defect:

```
Time T0: Coverage Set = {topics A, B covered}
Time T1: Branch 1 reads Coverage Set → sees A,B covered → retrieves fact about C (novel)
Time T1: Branch 2 reads Coverage Set → sees A,B covered → retrieves fact about C (novel)
         ↑ Branch 2 has NOT seen Branch 1's retrieval - neither has updated coverage
Time T2: Branch 1 writes about C
Time T2: Branch 2 writes about C
Result:  DUPLICATE CONTENT - both branches independently chose the same "novel" topic
```

This is a classic read-modify-write race on shared mutable state. CDR was designed assuming sequential windows; fan-out violates that assumption.

### 1.2 Rejected Fix: Locking

Serialising Coverage Set access with a lock would eliminate the race but also eliminate the parallelism that fan-out exists to provide. Branches would block on each other's coverage updates, reducing fan-out to sequential execution. Rejected.

### 1.3 The Fix: Pre-Partitioned Coverage Scopes

The correct fix removes the shared mutable state entirely by partitioning the task into disjoint coverage scopes BEFORE fan-out, so no two branches can collide.

```
1. Before fan-out, decompose the remaining task (ResidualSet, SPEC-024)
   into N disjoint partitions - one per fan-out branch.
2. Each partition is a non-overlapping subset of remaining sub-queries.
3. Each branch receives:
     - A SNAPSHOT of the Coverage Set (immutable, read-only)
     - Its assigned partition (the sub-queries it is responsible for)
     - A partition-scoped novelty constraint: retrieve facts novel
       w.r.t. the snapshot AND relevant to THIS partition only
4. Branches run fully in parallel. They cannot collide because their
   partitions are disjoint - Branch 1 works on topics {C,D},
   Branch 2 works on topics {E,F}. No shared write target.
5. On fan-in, merge the branch Coverage Sets (union) and run one
   cross-branch dedup pass (DPE Stage 6 cross-window coherence,
   SPEC-005 §8) to catch any incidental overlap.
```

### 1.4 Partition Assignment

Partitioning uses the ResidualSet sub-query embeddings. Sub-queries are clustered into N groups (N = fan-out width) by embedding similarity, so each branch gets a thematically coherent partition:

```python
def partition_residual_for_fanout(residual_set, fanout_width):
    if len(residual_set) <= fanout_width:
        # Fewer remaining sub-queries than branches: one each
        return [[sq] for sq in residual_set]
    # Cluster sub-queries into fanout_width coherent groups
    embeddings = [sq.embedding for sq in residual_set]
    clusters = kmeans(embeddings, k=fanout_width)
    return [[residual_set[i] for i in cluster] for cluster in clusters]
```

### 1.5 Snapshot Immutability

The Coverage Set snapshot passed to each branch MUST be immutable for the duration of the branch's execution. Branches accumulate their own coverage additions locally; these are merged only at fan-in. This guarantees no branch observes another branch's mid-flight coverage changes - the source of the race.

### 1.6 Fan-In Merge and Dedup

```python
def fanin_merge_coverage(parent_session, branch_sessions):
    # Union all branch coverage additions
    for branch in branch_sessions:
        parent_session.coverage_set.extend(branch.coverage_additions)
    # Cross-branch dedup: DPE Stage 6 detects any duplicate content
    # that slipped through despite disjoint partitions (rare edge case
    # where two partitions both legitimately needed a shared fact)
    dedup_report = dpe_cross_window_coherence(branch_sessions)
    return dedup_report.deduplicated_output
```

### 1.7 Header

```
CRP-Context-Coverage-Partitions: 3
```

**Direction:** RES. Number of disjoint coverage partitions created for fan-out. Present only when fan-out with CDR is active.

---

## 2. Gap 4 - Fact Authority Resolution

### 2.1 The Contradiction Problem

The CKF accumulates facts over time from multiple sources and document versions (SPEC-009 §4.5). It can therefore hold mutually contradictory facts:

```
Fact F1: "etcd default client port is 2379"   (current, source: official docs v3.5)
Fact F2: "etcd default client port is 4001"    (stale, source: legacy docs v2.x)
```

Both are high-relevance to a query about etcd ports. CDR might retrieve both (they cover slightly different phrasings, so novelty doesn't fully suppress the second). The model receives contradictory context and either picks arbitrarily, hedges confusingly, or states both. DPE Stage 6 detects contradictions BETWEEN windows but not WITHIN a single envelope sourced from the CKF.

### 2.2 Contradiction Detection at Retrieval

During envelope assembly, after CDR/CDGR ranking, a contradiction check runs over the selected fact set:

```python
def detect_envelope_contradictions(selected_facts):
    contradictions = []
    for i, f1 in enumerate(selected_facts):
        for f2 in selected_facts[i+1:]:
            # High topical similarity but conflicting content
            if cosine_similarity(f1.embedding, f2.embedding) > 0.85:
                if values_conflict(f1.content, f2.content):
                    contradictions.append((f1, f2))
    return contradictions
```

`values_conflict` reuses the DPE distortion-detection logic (SPEC-005 §3b): it detects when two facts assert different values for the same attribute (NUMBER_CHANGED, ENTITY_SUBSTITUTED, NEGATION_FLIP patterns applied pairwise).

### 2.3 Authority Arbitration

When a contradiction is detected, the higher-authority fact is kept and the lower-authority fact is suppressed from the envelope:

```
authority(fact) = source_authority_weight      (SPEC-009 §4.4)
                × recency_factor(fact)          (§3 below)
                × importance_weight             (SPEC-009 §2)
```

```python
def resolve_contradiction(f1, f2):
    a1 = authority(f1)
    a2 = authority(f2)
    if a1 >= a2:
        return f1, f2   # keep f1, suppress f2
    else:
        return f2, f1   # keep f2, suppress f1
```

Source authority weights (from SPEC-009 §4.4): regulatory (0.90), official-documentation (baseline), community (−0.05), unverified (−0.10). A current official-docs fact beats a stale legacy fact decisively because it wins on both source authority AND recency.

### 2.4 Transparency: Conflicts Are Logged, Not Hidden

Suppressed contradictions are recorded in the audit trail (a `CONTRADICTION_RESOLVED` event) and surfaced in a header. The protocol does not silently discard information - it records that a conflict existed and which fact won.

```
CRP-Context-Conflicts-Resolved: 2
```

**Direction:** RES. Number of intra-envelope contradictions detected and arbitrated during assembly. A non-zero value signals the CKF contains conflicting facts the operator may wish to clean up (e.g., remove the stale source).

### 2.5 When Authority Is Tied

If two contradictory facts have equal authority (same source authority, same recency, same importance - rare but possible), neither is suppressed. Instead, both are included with an explicit annotation injected into the envelope:

```
NOTE: The following two facts conflict and could not be automatically
arbitrated. Treat with caution and prefer the more specific:
  [Fact A]
  [Fact B]
```

This hands the conflict to the model transparently rather than picking arbitrarily, and flags it for the operator via `CRP-Context-Conflicts-Resolved` with an `unresolved` suffix:

```
CRP-Context-Conflicts-Resolved: 1; unresolved=1
```

---

## 3. Gap 5 - Recency Weighting in CDR

### 3.1 The Stale-but-Novel Problem

The CDR formula (SPEC-024 §2.2) scores on relevance and novelty. It has no recency term. Consequence: a stale fact that happens to be novel (not yet covered this session) can outrank a fresh fact that has been covered. Since staleness often correlates with incorrectness (superseded values, outdated procedures), this selects for wrong content.

### 3.2 The Recency Factor

Add a recency factor to the CDR score:

```
recency_factor(fact) = 
    1.0                                    if age <= fresh_threshold
    linear_decay(age, ttl)                 if fresh_threshold < age < ttl
    STALE_FLOOR (0.30)                      if age >= ttl

where:
    age = now - fact.modified_at
    ttl = fact.ttl (SPEC-009 §2, optional per-fact; default by source type)
    fresh_threshold = 0.5 × ttl
    linear_decay(age, ttl) = 1.0 - 0.7 × ((age - 0.5×ttl) / (0.5×ttl))
        → decays from 1.0 down to 0.30 across the second half of TTL
```

A fact within the first half of its TTL is fully fresh (factor = 1.0). Between half-TTL and full-TTL it decays linearly to the stale floor. Past TTL it sits at the floor (0.30) - heavily penalised but, like the novelty floor, never fully excluded (a stale fact may still be the only available fact on a topic).

### 3.3 The Complete CDR Formula (Final)

Integrating recency into the SPEC-024 formula:

```
CDR_score(fact) = importance_weight
                × max(relevance, residual_pull)        ← SPEC-024
                × novelty                               ← SPEC-024 (floor 0.20)
                × recency_factor                        ← SPEC-027 (floor 0.30)
                × (1.0 - ngram_penalty)                 ← SPEC-024 §5
```

For CDGR connector facts (SPEC-025 §2.5), recency applies identically:

```
CDGR_connector_score = bridge_value
                     × novelty
                     × recency_factor                   ← SPEC-027
                     × max(relevance, MIN_CONNECTOR_RELEVANCE)
```

### 3.4 Recency and Authority Are the Same Signal

The recency_factor defined here is reused directly in the authority computation for Gap 4 (§2.3). This is deliberate: a fact's recency is a component of its authority. The two fixes share one decay function. A stale fact is both lower-authority (loses contradiction arbitration) and lower-CDR-scored (less likely to be retrieved at all). The defences compound correctly.

### 3.5 Facts Without TTL

Many facts have no explicit TTL (SPEC-009 §2.2 makes TTL optional). For these, a default TTL is applied by source type:

| Source type | Default TTL |
|-------------|-------------|
| Regulatory text | 5 years (slow-changing) |
| Official documentation | 1 year |
| Version-specific technical | 6 months |
| News / time-sensitive | 30 days |
| User-provided | No expiry (factor always 1.0 unless explicitly set) |

Facts the operator marks as timeless (definitions, historical facts) can set `ttl=none`, giving them a permanent recency_factor of 1.0.

### 3.6 Header

```
CRP-Context-Recency-Penalised: 4
```

**Direction:** RES. Number of facts in the candidate set that received a recency penalty (factor < 1.0). High values suggest the CKF contains aging content that should be refreshed.

---

## 4. Combined Retrieval Pipeline (Final Form)

With SPEC-024, SPEC-025, and SPEC-027 integrated, the complete retrieval pipeline is:

```
1. CANDIDATE GATHERING (CKF / HNSW)
   → top-K by raw similarity, filtered by CDR_MIN_RELEVANCE (0.55)

2. CDR SCORING (SPEC-024 + SPEC-027 recency)
   → importance × max(relevance, residual_pull) × novelty 
     × recency_factor × (1 - ngram_penalty)

3. CDGR GRAPH EXPANSION (SPEC-025)
   → seed with top CDR anchors, walk graph, score connectors by 
     bridge_value × novelty × recency_factor

4. CONTRADICTION RESOLUTION (SPEC-027 §2)
   → detect intra-envelope contradictions, arbitrate by authority
     (authority includes recency), suppress losers, log conflicts

5. PARALLEL ISOLATION (SPEC-027 §1, only if fan-out)
   → partition into disjoint coverage scopes, snapshot Coverage Set,
     dispatch branches, merge + dedup on fan-in

6. PACKING (SPEC-003)
   → primacy-recency sandwich, connectors adjacent to their anchors
```

Total added latency over the original flat retrieval: under 3 milliseconds. The entire pipeline remains Core-tier, single-inference, sub-50ms-overhead, model-agnostic.

---

## 5. What These Fixes Do Not Address

**Gap 3** assumes the task can be partitioned into disjoint sub-queries. For tasks that are genuinely non-decomposable (a single indivisible question), fan-out is inappropriate regardless, and the partitioning simply returns one partition (sequential behaviour). This is correct.

**Gap 4** resolves contradictions it can detect via value-conflict patterns. Subtle semantic contradictions (two facts that are technically consistent but misleading together) are not detected - that requires deeper reasoning than retrieval-time arbitration. These remain the model's responsibility, flagged by DPE if they produce output contradictions.

**Gap 5** assumes `modified_at` timestamps are accurate. If the ingestion pipeline does not set timestamps correctly, recency weighting operates on bad data. This is an ingestion-quality concern (SPEC-009), upstream of retrieval.

---

## 6. References

- CRP-SPEC-004 - Window Continuation & DAG (fan-out)
- CRP-SPEC-005 - Decision Provenance Engine (contradiction/distortion detection)
- CRP-SPEC-009 - Contextual Knowledge Fabric (fact lifecycle, source authority, TTL)
- CRP-SPEC-024 - Coverage-Differential Retrieval (CDR formula)
- CRP-SPEC-025 - Coverage-Differential Graph Retrieval (connector scoring)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
