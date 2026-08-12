# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Compaction engine — deduplicate and summarize warm state (§3.6).

Trigger: fact_count > 5000 OR envelope_latency > 500ms.
Algorithm:
  1. Archive superseded facts
  2. Cluster remaining by cosine similarity (>0.80 threshold)
  3. TextRank summarize clusters
  4. Rebuild ANN index
  5. Compact graph
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from crp.extraction.types import Fact

from .event_log import FactEventLog
from .fact import StateFact
from .warm_store import WarmStateStore

# ---------------------------------------------------------------------------
# Compaction config
# ---------------------------------------------------------------------------

COMPACTION_FACT_THRESHOLD = 5000
COMPACTION_LATENCY_THRESHOLD_MS = 500.0
CLUSTER_SIMILARITY_THRESHOLD = 0.80


@dataclass
class CompactionConfig:
    """Tuneable compaction parameters."""

    fact_threshold: int = COMPACTION_FACT_THRESHOLD
    latency_threshold_ms: float = COMPACTION_LATENCY_THRESHOLD_MS
    cluster_sim_threshold: float = CLUSTER_SIMILARITY_THRESHOLD
    max_cluster_size: int = 20


@dataclass
class CompactionResult:
    """Result of a compaction pass."""

    facts_before: int = 0
    facts_after: int = 0
    superseded_archived: int = 0
    clusters_found: int = 0
    summaries_created: int = 0
    elapsed_ms: float = 0.0


# ---------------------------------------------------------------------------
# Simple cosine similarity (no ML deps)
# ---------------------------------------------------------------------------


def _cosine_sim_texts(a: str, b: str) -> float:
    """Word-overlap cosine similarity between two texts."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / (math.sqrt(len(words_a)) * math.sqrt(len(words_b)))


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def _cluster_facts(
    facts: list[StateFact],
    threshold: float,
    max_cluster_size: int,
) -> list[list[StateFact]]:
    """Simple greedy clustering by pairwise cosine similarity.

    When ML embeddings are available, uses them.  Fallback: word overlap.
    """
    clusters: list[list[StateFact]] = []
    assigned: set[str] = set()

    for sf in facts:
        if sf.id in assigned:
            continue
        cluster = [sf]
        assigned.add(sf.id)

        for other in facts:
            if other.id in assigned:
                continue
            if len(cluster) >= max_cluster_size:
                break

            # Use embeddings if both have them
            if sf.has_embedding() and other.has_embedding():
                emb_a = sf.embedding
                emb_b = other.embedding
                if emb_a and emb_b:
                    dot = sum(x * y for x, y in zip(emb_a, emb_b))
                    na = math.sqrt(sum(x * x for x in emb_a)) or 1e-12
                    nb = math.sqrt(sum(x * x for x in emb_b)) or 1e-12
                    sim = dot / (na * nb)
                else:
                    sim = _cosine_sim_texts(sf.text, other.text)
            else:
                sim = _cosine_sim_texts(sf.text, other.text)

            if sim >= threshold:
                cluster.append(other)
                assigned.add(other.id)

        clusters.append(cluster)

    return clusters


# ---------------------------------------------------------------------------
# TextRank-inspired summarization (single-fact reduction)
# ---------------------------------------------------------------------------


def _summarize_cluster(cluster: list[StateFact]) -> str:
    """Pick the most representative fact from a cluster.

    Uses a simple centrality heuristic: the fact with the highest average
    similarity to all others.  When ML embeddings are unavailable, uses the
    highest-confidence fact.
    """
    if len(cluster) == 1:
        return cluster[0].text

    # Try embedding-based centrality
    has_all_emb = all(sf.has_embedding() for sf in cluster)
    if has_all_emb:
        best_idx = 0
        best_score = -1.0
        for i, sf in enumerate(cluster):
            emb_i = sf.embedding
            if not emb_i:
                continue
            total_sim = 0.0
            for j, other in enumerate(cluster):
                if i == j:
                    continue
                emb_j = other.embedding
                if emb_j:
                    dot = sum(x * y for x, y in zip(emb_i, emb_j))
                    na = math.sqrt(sum(x * x for x in emb_i)) or 1e-12
                    nb = math.sqrt(sum(x * x for x in emb_j)) or 1e-12
                    total_sim += dot / (na * nb)
            if total_sim > best_score:
                best_score = total_sim
                best_idx = i
        return cluster[best_idx].text

    # Fallback: highest confidence
    return max(cluster, key=lambda sf: sf.confidence).text


# ---------------------------------------------------------------------------
# Compaction engine
# ---------------------------------------------------------------------------


def should_compact(
    store: WarmStateStore,
    last_envelope_latency_ms: float = 0.0,
    config: CompactionConfig | None = None,
) -> bool:
    """Check if compaction should run."""
    cfg = config or CompactionConfig()
    if store.fact_count > cfg.fact_threshold:
        return True
    return last_envelope_latency_ms > cfg.latency_threshold_ms


def compact(
    store: WarmStateStore,
    event_log: FactEventLog,
    window_id: str,
    config: CompactionConfig | None = None,
) -> CompactionResult:
    """Run a compaction pass on the warm store.

    1. Archive superseded facts → cold (emit ARCHIVED events)
    2. Cluster remaining active facts by similarity
    3. Summarize multi-fact clusters → single representative fact
    4. Update graph with summary facts
    """
    import time as _time
    import uuid

    cfg = config or CompactionConfig()
    t0 = _time.perf_counter()
    result = CompactionResult(facts_before=store.fact_count)

    # Step 1: Archive superseded
    all_facts = store.get_facts(include_superseded=True)
    superseded = [sf for sf in all_facts if sf.is_superseded]
    for sf in superseded:
        store.remove_fact(sf.id)
        event_log.record_archived(sf.id, window_id)
        result.superseded_archived += 1

    # Step 2: Cluster active facts
    active = store.get_facts()
    if len(active) <= cfg.fact_threshold // 2:
        # Not enough to bother clustering
        result.facts_after = store.fact_count
        result.elapsed_ms = (_time.perf_counter() - t0) * 1000
        return result

    clusters = _cluster_facts(active, cfg.cluster_sim_threshold, cfg.max_cluster_size)
    result.clusters_found = len(clusters)

    # Step 3: Summarize multi-fact clusters
    for cluster in clusters:
        if len(cluster) <= 1:
            continue
        summary_text = _summarize_cluster(cluster)
        summary_fact = Fact(
            id=str(uuid.uuid4()),
            text=summary_text,
            category="compacted_summary",
            source_window_id=window_id,
            confidence=max(sf.confidence for sf in cluster),
            extraction_stage=0,
        )

        # Remove cluster members, add summary
        for sf in cluster:
            store.remove_fact(sf.id)
            event_log.record_compaction(sf.id, window_id, summary_id=summary_fact.id)

        store.add_facts([summary_fact])
        event_log.record_fact_created(summary_fact, window_id)
        result.summaries_created += 1

    # Step 4: Clean up stale graph edges (§4D.5)
    _cleanup_stale_edges(store)

    result.facts_after = store.fact_count
    result.elapsed_ms = (_time.perf_counter() - t0) * 1000
    return result


def _cleanup_stale_edges(store: WarmStateStore) -> int:
    """Remove graph edges that reference non-existent facts (§4D.5)."""
    active_ids = {sf.id for sf in store.get_facts(include_superseded=True)}
    graph = store.graph
    stale = [
        e for e in graph.edges
        if e.source_id not in active_ids or e.target_id not in active_ids
    ]
    for edge in stale:
        graph.edges.remove(edge)
    return len(stale)
