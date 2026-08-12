# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CKF Mode 3: Semantic fallback — ANN similarity retrieval (§3.8).

``semantic_fallback(query, facts, top_k)`` retrieves the *top_k* most
semantically similar facts to *query*.  Uses the ANN index provided by the
caller — a :class:`~crp.ckf.vector_index.VectorIndex` (faiss-first default
since CRPv6 Phase A) or a legacy ``HNSWIndex`` — when the store is large
enough, otherwise brute-force cosine similarity.

Adaptive top_k: 20 (default), scales up to 200 for large stores.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from crp.state.fact import StateFact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ANN backend detection
# ---------------------------------------------------------------------------

_HNSWLIB: Any = None
_HNSWLIB_CHECKED = False


def _check_hnswlib() -> Any:
    global _HNSWLIB, _HNSWLIB_CHECKED  # noqa: PLW0603
    if not _HNSWLIB_CHECKED:
        try:
            import hnswlib  # type: ignore[import-untyped]

            _HNSWLIB = hnswlib
        except ImportError:
            _HNSWLIB = None
        _HNSWLIB_CHECKED = True
    return _HNSWLIB


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class SemanticResult:
    """Result of a semantic similarity query."""

    facts: list[StateFact] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    used_ann: bool = False


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Adaptive top_k
# ---------------------------------------------------------------------------

MIN_TOP_K = 20
MAX_TOP_K = 200
ANN_THRESHOLD = 1000


def adaptive_top_k(fact_count: int, base_k: int = MIN_TOP_K) -> int:
    """Scale top_k based on store size: 20 for small, up to 200 for large."""
    if fact_count <= 100:
        return base_k
    # Linear scale between 100 and 10_000 facts
    scale = min(1.0, (fact_count - 100) / 9900)
    return min(MAX_TOP_K, base_k + int(scale * (MAX_TOP_K - base_k)))


# ---------------------------------------------------------------------------
# HNSW index wrapper
# ---------------------------------------------------------------------------


class HNSWIndex:
    """Thin wrapper around hnswlib for ANN queries."""

    def __init__(self, dim: int, max_elements: int = 10_000) -> None:
        lib = _check_hnswlib()
        if lib is None:
            raise RuntimeError("hnswlib not available")
        self._lib = lib
        self._dim = dim
        self._max_elements = max_elements
        self._index = lib.Index(space="cosine", dim=dim)
        self._index.init_index(max_elements=max_elements, ef_construction=200, M=16)
        self._index.set_ef(50)
        self._id_map: dict[int, str] = {}
        self._next_int: int = 0

    def _resize_if_needed(self) -> None:
        """Double capacity when nearing the limit."""
        if self._next_int >= self._max_elements:
            self._max_elements *= 2
            self._index.resize_index(self._max_elements)

    def add(self, fact_id: str, embedding: list[float]) -> None:
        """Add a fact embedding to the HNSW index.

        Args:
            fact_id: External identifier for the fact.
            embedding: Dense vector representing the fact.
        """
        self._resize_if_needed()
        int_id = self._next_int
        self._id_map[int_id] = fact_id
        self._index.add_items([embedding], [int_id])
        self._next_int += 1

    def query(self, embedding: list[float], k: int) -> list[tuple[str, float]]:
        """Return [(fact_id, distance), ...] for top-k nearest."""
        k = min(k, self._next_int)
        if k == 0:
            return []
        labels, distances = self._index.knn_query([embedding], k=k)
        results = []
        for label, dist in zip(labels[0], distances[0]):
            fid = self._id_map.get(int(label))
            if fid:
                # hnswlib cosine returns 1 - cos_sim
                results.append((fid, 1.0 - float(dist)))
        return results

    @property
    def count(self) -> int:
        """Return the current count count."""
        return self._next_int


# ---------------------------------------------------------------------------
# Brute-force fallback
# ---------------------------------------------------------------------------


def _brute_force_query(
    query_embedding: list[float],
    facts: dict[str, StateFact],
    top_k: int,
) -> list[tuple[str, float]]:
    """Brute-force cosine similarity search."""
    scored: list[tuple[str, float]] = []
    for fid, sf in facts.items():
        emb = sf.embedding
        if emb is not None:
            sim = _cosine_sim(query_embedding, emb)
            scored.append((fid, sim))
    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def semantic_fallback(
    query_embedding: list[float],
    facts: dict[str, StateFact],
    top_k: int | None = None,
    hnsw_index: HNSWIndex | Any | None = None,
) -> SemanticResult:
    """Retrieve the *top_k* most similar facts to *query_embedding*.

    Uses the ANN index (``VectorIndex`` or legacy ``HNSWIndex``) if provided
    and the store is large enough; otherwise brute-force. Adaptive top_k:
    20→200 based on store size.
    """
    if not query_embedding or not facts:
        return SemanticResult()

    k = top_k if top_k is not None else adaptive_top_k(len(facts))
    used_ann = False

    # Try ANN index if provided and large enough
    if hnsw_index is not None and hnsw_index.count >= ANN_THRESHOLD:
        try:
            raw = hnsw_index.query(query_embedding, k)
            used_ann = True
        except Exception:  # noqa: BLE001
            logger.warning("ANN query failed, falling back to brute-force")
            raw = _brute_force_query(query_embedding, facts, k)
    else:
        raw = _brute_force_query(query_embedding, facts, k)

    # Build result
    result_facts: list[StateFact] = []
    scores: dict[str, float] = {}
    for fid, sim in raw:
        sf = facts.get(fid)
        if sf and not sf.is_superseded:
            result_facts.append(sf)
            scores[fid] = sim

    return SemanticResult(facts=result_facts, scores=scores, used_ann=used_ann)
