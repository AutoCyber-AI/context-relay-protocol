# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 2 — Bi-encoder scoring (§3.2).

Computes composite relevance scores for facts against task aspects.
Formula (02_CORE §3.2, authoritative):

    sim   = 0.7 × max(cos(fact_emb, aspect_emb)) + 0.3 × cos(fact_emb, full_emb)
    score = sim × recency × novelty + dep_bonus

Falls back to word-overlap cosine when sentence-transformers is unavailable.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from crp.extraction.types import Fact, FactGraph

from .decomposer import _EMBED_DIM, DecompositionResult, _bag_vector, _build_vocab, _tokenize

# ---------------------------------------------------------------------------
# HNSW ANN index support (lazy, optional)
# ---------------------------------------------------------------------------

_HNSWLIB_AVAILABLE: bool | None = None
ANN_THRESHOLD = 1000  # Use ANN when facts > this; brute-force below


def _check_hnswlib() -> bool:
    global _HNSWLIB_AVAILABLE  # noqa: PLW0603
    if _HNSWLIB_AVAILABLE is not None:
        return _HNSWLIB_AVAILABLE
    try:
        import hnswlib  # type: ignore[import-untyped]  # noqa: F401

        _HNSWLIB_AVAILABLE = True
    except ImportError:
        _HNSWLIB_AVAILABLE = False
    return _HNSWLIB_AVAILABLE


def _ann_query(
    fact_embeddings_list: list[list[float]],
    query_vectors: list[list[float]],
    top_k: int,
) -> list[list[int]]:
    """Use HNSW ANN index to find top-K nearest facts per query vector.

    Returns list of index lists (one per query vector).
    Falls back to brute-force if hnswlib unavailable.
    """
    import numpy as np  # type: ignore[import-untyped]

    if _check_hnswlib() and len(fact_embeddings_list) > ANN_THRESHOLD:
        import hnswlib  # type: ignore[import-untyped]

        dim = len(fact_embeddings_list[0])
        index = hnswlib.Index(space="cosine", dim=dim)
        index.init_index(max_elements=len(fact_embeddings_list), ef_construction=200, M=16)
        data = np.array(fact_embeddings_list, dtype=np.float32)
        index.add_items(data)
        index.set_ef(max(top_k * 2, 50))

        results: list[list[int]] = []
        for qv in query_vectors:
            labels, _ = index.knn_query(np.array([qv], dtype=np.float32), k=min(top_k, len(fact_embeddings_list)))
            results.append(labels[0].tolist())
        return results

    # Brute-force fallback (always works)
    results = []
    for qv in query_vectors:
        sims = []
        for i, fv in enumerate(fact_embeddings_list):
            sims.append((i, cosine_similarity(qv, fv)))
        sims.sort(key=lambda x: x[1], reverse=True)
        results.append([idx for idx, _ in sims[:top_k]])
    return results

# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1e-12
    norm_b = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Scored fact result
# ---------------------------------------------------------------------------


@dataclass
class ScoredFact:
    """A fact with its composite relevance score."""

    fact: Fact
    similarity: float = 0.0
    recency_weight: float = 1.0
    novelty_weight: float = 1.0
    dependency_bonus: float = 0.0
    composite_score: float = 0.0


# ---------------------------------------------------------------------------
# Fact embedding helpers
# ---------------------------------------------------------------------------


def embed_fact_ml(fact: Fact, model: object) -> list[float]:
    """Embed a single fact using a sentence-transformers model."""
    return model.encode([fact.text], show_progress_bar=False).tolist()[0]  # type: ignore[attr-defined]


def embed_fact_fallback(fact: Fact, vocab: dict[str, int]) -> list[float]:
    """Embed a fact using bag-of-words fallback."""
    return _bag_vector(_tokenize(fact.text), vocab, _EMBED_DIM)


# ---------------------------------------------------------------------------
# Recency weight: w = e^(-λ × age_in_windows)
# ---------------------------------------------------------------------------


def recency_weight(age_in_windows: int, decay_lambda: float = 0.1) -> float:
    """Exponential recency decay.  λ=0.1 → ~20 window half-life."""
    return math.exp(-decay_lambda * age_in_windows)


# ---------------------------------------------------------------------------
# Novelty weight
# ---------------------------------------------------------------------------


def novelty_weight(seen_count: int) -> float:
    """Novelty multiplier per spec: 0→1.5×, 1-2→1.0×, ≥3→0.5×."""
    if seen_count == 0:
        return 1.5
    if seen_count <= 2:
        return 1.0
    return 0.5


# ---------------------------------------------------------------------------
# Dependency bonus
# ---------------------------------------------------------------------------

_DEP_BONUS_CAP = 0.5


def dependency_bonus(
    fact: Fact,
    graph: FactGraph,
    recent_scored: dict[str, float],
) -> float:
    """Sum of score × edge.confidence × 0.3 for graph-connected scored facts, capped 0.5."""
    bonus = 0.0
    for edge in graph.edges_from(fact.id):
        neighbour_score = recent_scored.get(edge.target_id, 0.0)
        conf = edge.confidence if isinstance(edge.confidence, (int, float)) else 0.0
        bonus += neighbour_score * conf * 0.3
    for edge in graph.edges_to(fact.id):
        neighbour_score = recent_scored.get(edge.source_id, 0.0)
        conf = edge.confidence if isinstance(edge.confidence, (int, float)) else 0.0
        bonus += neighbour_score * conf * 0.3
    return min(bonus, _DEP_BONUS_CAP)


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

_ASPECT_WEIGHT = 0.7
_FULL_WEIGHT = 0.3


@dataclass
class ScoringConfig:
    """Tuneable parameters for bi-encoder scoring."""

    decay_lambda: float = 0.1
    aspect_weight: float = _ASPECT_WEIGHT
    full_weight: float = _FULL_WEIGHT
    dep_bonus_cap: float = _DEP_BONUS_CAP


def score_facts(
    facts: list[Fact],
    decomposition: DecompositionResult,
    graph: FactGraph,
    *,
    current_window_index: int = 0,
    seen_counts: dict[str, int] | None = None,
    fact_window_indices: dict[str, int] | None = None,
    config: ScoringConfig | None = None,
    coverage_set: Any = None,
) -> list[ScoredFact]:
    """Score *facts* against the decomposed task aspects.

    Returns a list of ScoredFact sorted by composite_score descending.

    Parameters
    ----------
    facts : list[Fact]
        Facts to score (from warm state).
    decomposition : DecompositionResult
        Task decomposition output (aspects + embeddings).
    graph : FactGraph
        Fact graph for dependency bonus computation.
    current_window_index : int
        Current window number in the session (for recency).
    seen_counts : dict[str, int] | None
        fact_id → number of times included in previous envelopes.
    fact_window_indices : dict[str, int] | None
        fact_id → window index when the fact was created.
    config : ScoringConfig | None
        Override default scoring parameters.
    """
    if not facts or not decomposition.aspects:
        return []

    cfg = config or ScoringConfig()
    _seen = seen_counts or {}
    _window_idx = fact_window_indices or {}

    # -- Compute fact embeddings ------------------------------------------------
    fact_embeddings: dict[str, list[float]] = {}

    if decomposition.used_ml_model:
        # Import here so we don't fail if sentence-transformers absent
        try:
            from .decomposer import _EMBED_MODEL

            if _EMBED_MODEL is not None:
                texts = [f.text for f in facts]
                embs = _EMBED_MODEL.encode(texts, show_progress_bar=False).tolist()  # type: ignore[attr-defined]
                for f_obj, emb in zip(facts, embs):
                    fact_embeddings[f_obj.id] = emb
        except Exception:  # noqa: BLE001
            pass

    if not fact_embeddings:
        # Fallback: bag-of-words
        all_tokens: list[str] = []
        for a in decomposition.aspects:
            all_tokens.extend(_tokenize(a))
        for f_obj in facts:
            all_tokens.extend(_tokenize(f_obj.text))
        vocab = _build_vocab(all_tokens)
        for f_obj in facts:
            fact_embeddings[f_obj.id] = embed_fact_fallback(f_obj, vocab)

    # -- Score each fact --------------------------------------------------------
    aspect_embs = decomposition.aspect_embeddings
    full_emb = decomposition.full_embedding
    scored: list[ScoredFact] = []
    recent_scored: dict[str, float] = {}  # for dependency bonus (last 50)

    for f_obj in facts:
        f_emb = fact_embeddings.get(f_obj.id)
        if f_emb is None:
            continue

        # Similarity: 0.7 × max(cos(fact, aspect)) + 0.3 × cos(fact, full)
        if aspect_embs:
            max_aspect_sim = max(cosine_similarity(f_emb, a_emb) for a_emb in aspect_embs)
        else:
            max_aspect_sim = 0.0
        full_sim = cosine_similarity(f_emb, full_emb) if full_emb else 0.0
        sim = cfg.aspect_weight * max_aspect_sim + cfg.full_weight * full_sim

        # Recency
        age = max(0, current_window_index - _window_idx.get(f_obj.id, 0))
        rec = recency_weight(age, cfg.decay_lambda)

        # Novelty — CDR if coverage_set provided, else legacy seen-count weight
        if coverage_set is not None:
            # CDR: novelty from session Coverage Set (SPEC-024 §7.1)
            nov = coverage_set.novelty(f_emb)
            # CDR minimum relevance gate: exclude if below threshold
            from .cdr import CDR_MIN_RELEVANCE
            if sim < CDR_MIN_RELEVANCE:
                continue
        else:
            nov = novelty_weight(_seen.get(f_obj.id, 0))

        # Dependency bonus (uses last 50 scored facts)
        dep = dependency_bonus(f_obj, graph, recent_scored)

        composite = sim * rec * nov + dep

        sf = ScoredFact(
            fact=f_obj,
            similarity=sim,
            recency_weight=rec,
            novelty_weight=nov,
            dependency_bonus=dep,
            composite_score=composite,
        )
        scored.append(sf)

        # Track for dependency bonus of subsequent facts (rolling window of 50)
        recent_scored[f_obj.id] = composite
        if len(recent_scored) > 50:
            # Remove oldest (first inserted) — dict preserves insertion order
            oldest_key = next(iter(recent_scored))
            del recent_scored[oldest_key]

    # Sort descending by composite score
    scored.sort(key=lambda s: s.composite_score, reverse=True)
    return scored
