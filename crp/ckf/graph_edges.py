# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CKF Similarity Edges — prerequisite for CDGR multi-hop graph walk (SPEC-025 §1.3).

Builds and maintains bidirectional similarity edges between CKF fact nodes.
SPEC-009 §5.2 specifies that facts with cosine similarity ≥ 0.60 are connected
by similarity edges. These edges are the foundation for the CDGR graph walk.

This module is intentionally dependency-light so it can be imported early
without triggering heavy subsystem initialisation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Edge types
# ---------------------------------------------------------------------------


class EdgeType:
    """Edge type constants used in the CKF graph."""

    SIMILARITY = "similarity"      # cosine sim ≥ threshold
    DERIVED = "derived"            # one fact derived from another
    CONTRADICTION = "contradiction"  # facts contradict each other
    SEQUENCE = "sequence"          # temporal / ordered sequence


# ---------------------------------------------------------------------------
# Edge record
# ---------------------------------------------------------------------------


@dataclass
class CKFEdge:
    """Bidirectional similarity edge between two CKF fact nodes (SPEC-009 §5.2).

    Stored once per pair (source < target lexicographically) but accessible
    from either end via ``GraphEdgeStore``.
    """

    source_id: str
    target_id: str
    similarity: float        # cosine similarity — the edge weight
    edge_type: str = EdgeType.SIMILARITY
    created_at: float = 0.0  # epoch seconds; set by builder

    def __post_init__(self) -> None:
        # Normalise direction so source_id < target_id for dedup
        if self.source_id > self.target_id:
            self.source_id, self.target_id = self.target_id, self.source_id


# ---------------------------------------------------------------------------
# Graph edge store
# ---------------------------------------------------------------------------


class GraphEdgeStore:
    """Adjacency index for fast neighbour lookup.

    Stores edges in both directions so ``neighbours(fact_id)`` is O(degree)
    regardless of which end of the edge was requested.
    """

    def __init__(self) -> None:
        # fact_id → {neighbour_id: similarity_score}
        self._adj: dict[str, dict[str, float]] = {}
        # canonical edge store: frozenset({a,b}) → CKFEdge
        self._edges: dict[frozenset[str], CKFEdge] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_edge(self, edge: CKFEdge) -> None:
        """Add (or update) an edge in the adjacency index."""
        key: frozenset[str] = frozenset({edge.source_id, edge.target_id})
        self._edges[key] = edge

        # Both directions
        self._adj.setdefault(edge.source_id, {})[edge.target_id] = edge.similarity
        self._adj.setdefault(edge.target_id, {})[edge.source_id] = edge.similarity

    def remove_fact(self, fact_id: str) -> None:
        """Remove all edges involving *fact_id* (called on tombstone/GC)."""
        neighbours = list(self._adj.pop(fact_id, {}).keys())
        for nb in neighbours:
            self._adj.get(nb, {}).pop(fact_id, None)
            self._edges.pop(frozenset({fact_id, nb}), None)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def neighbours(self, fact_id: str) -> dict[str, float]:
        """Return {neighbour_id: similarity} for all edges from *fact_id*."""
        return dict(self._adj.get(fact_id, {}))

    def has_edge(self, a: str, b: str) -> bool:
        """True if an edge exists between *a* and *b*."""
        return frozenset({a, b}) in self._edges

    def edge(self, a: str, b: str) -> CKFEdge | None:
        """Return the edge between *a* and *b*, or None."""
        return self._edges.get(frozenset({a, b}))

    def edge_count(self) -> int:
        """Return the number of unique edges in the store."""
        return len(self._edges)

    def node_count(self) -> int:
        """Return the number of distinct nodes with at least one edge."""
        return len(self._adj)

    # ------------------------------------------------------------------
    # Path length (BFS, used by CDGR bridge_value)
    # ------------------------------------------------------------------

    def path_length(self, start: str, end: str, max_hops: int = 4) -> int:
        """BFS shortest path length, capped at *max_hops*.

        Returns ``max_hops + 1`` if no path found within the hop limit.
        """
        if start == end:
            return 0
        visited: set[str] = {start}
        frontier: set[str] = {start}
        for hop in range(1, max_hops + 1):
            next_f: set[str] = set()
            for nid in frontier:
                for nb in self._adj.get(nid, {}):
                    if nb == end:
                        return hop
                    if nb not in visited:
                        visited.add(nb)
                        next_f.add(nb)
            frontier = next_f
            if not frontier:
                break
        return max_hops + 1


# ---------------------------------------------------------------------------
# Edge builder
# ---------------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two embedding vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-12
    nb = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (na * nb)


def build_edges(
    facts: list[Any],
    threshold: float = 0.60,
    *,
    embedding_attr: str = "_embedding",
) -> GraphEdgeStore:
    """Build similarity edges for a list of fact objects.

    ``facts`` must have ``id`` (str) and an embedding accessible via
    ``embedding_attr`` (list[float] | None).

    Facts whose embedding is None are skipped.

    This is an O(N²) pairwise scan — acceptable up to ~5000 facts.
    For larger CKFs the HNSW index should be used for ANN-based edge
    construction (see ``build_edges_from_hnsw``).
    """
    import time

    store = GraphEdgeStore()
    now = time.time()

    # Collect facts that have embeddings
    embedded: list[tuple[str, list[float]]] = []
    for f in facts:
        emb = getattr(f, embedding_attr, None)
        if emb is not None and len(emb) > 0:
            embedded.append((f.id, emb))

    # Pairwise cosine similarity
    n = len(embedded)
    for i in range(n):
        fid_i, emb_i = embedded[i]
        for j in range(i + 1, n):
            fid_j, emb_j = embedded[j]
            sim = _cosine_similarity(emb_i, emb_j)
            if sim >= threshold:
                store.add_edge(CKFEdge(
                    source_id=fid_i,
                    target_id=fid_j,
                    similarity=sim,
                    edge_type=EdgeType.SIMILARITY,
                    created_at=now,
                ))

    return store


def build_edges_from_hnsw(
    fact_ids: list[str],
    hnsw_index: Any,
    threshold: float = 0.60,
    k_neighbours: int = 20,
) -> GraphEdgeStore:
    """Build similarity edges using an existing HNSW index for scalability.

    For each fact, query HNSW for k nearest neighbours and add edges for
    those meeting the similarity threshold. O(N × K) instead of O(N²).

    ``hnsw_index`` must support:
        index.get_items([id_int]) → list[embedding]
        index.knn_query(embedding, k) → (labels, distances)

    Distances from hnswlib cosine space are (1 - cosine_sim), so
    similarity = 1 - distance.
    """
    import time

    import numpy as np  # type: ignore[import-untyped]

    store = GraphEdgeStore()
    now = time.time()
    n = len(fact_ids)

    for i, fid in enumerate(fact_ids):
        try:
            emb = hnsw_index.get_items([i])
            if not emb:
                continue
            labels, distances = hnsw_index.knn_query(
                np.array([emb[0]], dtype=np.float32),
                k=min(k_neighbours + 1, n),
            )
        except Exception:
            continue

        for label, dist in zip(labels[0], distances[0]):
            if label == i:
                continue
            sim = 1.0 - float(dist)
            if sim >= threshold and label < len(fact_ids):
                store.add_edge(CKFEdge(
                    source_id=fid,
                    target_id=fact_ids[label],
                    similarity=sim,
                    edge_type=EdgeType.SIMILARITY,
                    created_at=now,
                ))

    return store


def get_neighbours(
    fact_id: str,
    store: GraphEdgeStore,
) -> dict[str, float]:
    """Convenience wrapper — return neighbours from a ``GraphEdgeStore``.

    Returns ``{neighbour_id: similarity_score}``.
    """
    return store.neighbours(fact_id)
