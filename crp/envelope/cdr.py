# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Coverage-Differential Retrieval (CDR) — SPEC-024 §7.1.

CDR is the primary fix for the quality-quantity problem identified in the v3.1.1
benchmark (Window 5 repetition: 2.08%).  It modifies Phase 2 fact ranking so
that each window receives the most relevant material that has NOT yet been
addressed, rather than the same top-K facts every window.

The CDR score for a fact is:

    CDR_score(fact) =
        importance_weight(fact)
        × max(relevance(fact, query), residual_pull(fact))
        × novelty(fact)                             — SPEC-024 §2.2

Where:
    relevance   = cosine_sim(fact_embedding, query_embedding)
    novelty     = max(1 - coverage_penalty, MIN_NOVELTY_FLOOR)
                  + 0.20 × residual_pull             — bidirectional signal
    coverage_penalty = min(coverage_score(fact), 0.80)

Minimum relevance gate: facts with relevance < CDR_MIN_RELEVANCE (0.55) are
excluded entirely, regardless of novelty (SPEC-024 §2.6).

Window 1 behaviour: when the Coverage Set is empty, CDR_score = importance ×
relevance — identical to the current SPEC-003 Phase 2 score.  No regression.

CKF exhaustion detection: after ranking, if mean novelty of top-10 candidates
falls below CDR_EXHAUSTION_THRESHOLD (0.15), the session is flagged as
ckf-exhausted (SPEC-024 §5.2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from crp.state.coverage_set import CoverageSet

# ---------------------------------------------------------------------------
# Constants (all configurable at call site)
# ---------------------------------------------------------------------------


CDR_MIN_RELEVANCE: float = 0.55
MIN_NOVELTY_FLOOR: float = 0.20
COVERAGE_PENALTY_CAP: float = 0.80
CDR_EXHAUSTION_THRESHOLD: float = 0.15


# ---------------------------------------------------------------------------
# Scored fact result
# ---------------------------------------------------------------------------


@dataclass
class CDRScoredFact:
    """A fact ranked by CDR with its decomposed score components."""

    fact: Any                       # crp.extraction.types.Fact or StateFact
    relevance: float = 0.0
    novelty: float = 1.0
    residual_pull: float = 0.0
    importance: float = 1.0
    cdr_score: float = 0.0
    excluded: bool = False          # True if below CDR_MIN_RELEVANCE

    @property
    def components(self) -> dict[str, float]:
        """Expose the raw scoring signals for introspection and tests."""
        return {
            "relevance": self.relevance,
            "novelty": self.novelty,
            "residual_pull": self.residual_pull,
            "importance": self.importance,
            "effective_relevance": max(self.relevance, self.residual_pull),
            "cdr_score": self.cdr_score,
        }


# ---------------------------------------------------------------------------
# CDR ranking result
# ---------------------------------------------------------------------------


@dataclass
class CDRRankResult:
    """Full output of cdr_rank(), including exhaustion diagnosis."""

    ranked: list[CDRScoredFact] = field(default_factory=list)
    ckf_exhausted: bool = False
    mean_novelty_top10: float = 1.0
    candidate_count: int = 0
    excluded_count: int = 0


# ---------------------------------------------------------------------------
# Core CDR score
# ---------------------------------------------------------------------------


def cdr_score(
    fact: Any,
    query_embedding: list[float],
    coverage_set: CoverageSet,
    *,
    importance_weight: float = 1.0,
    min_relevance: float = CDR_MIN_RELEVANCE,
) -> CDRScoredFact:
    """Compute the CDR score for a single fact (SPEC-024 §7.1).

    ``fact`` must expose ``id`` (str) and an embedding accessible as
    ``fact._embedding`` or ``fact.embedding`` (``list[float]``).

    Args:
        fact: Fact-like object with an embedding.
        query_embedding: Embedding of the current query / task aspects.
        coverage_set: Session coverage set for novelty computation.
        importance_weight: Multiplicative importance factor.
        min_relevance: Minimum relevance gate (facts below are excluded).

    Returns:
        A ``CDRScoredFact``. If the fact has no embedding or fails the
        minimum relevance gate, ``excluded=True`` and ``cdr_score=0.0``.
    """
    fact_embedding = _get_embedding(fact)
    if not fact_embedding:
        return CDRScoredFact(fact=fact, excluded=True)

    relevance = _cosine_sim(fact_embedding, query_embedding)

    # Minimum relevance gate — SPEC-024 §2.6
    if relevance < min_relevance:
        return CDRScoredFact(fact=fact, relevance=relevance, excluded=True)

    # Novelty from Coverage Set (handles Window 1 empty-set case)
    novelty = coverage_set.novelty(fact_embedding)
    residual = coverage_set.residual_pull(fact_embedding)

    # CDR formula: importance × max(relevance, residual_pull) × novelty
    effective_relevance = max(relevance, residual)
    score = importance_weight * effective_relevance * novelty

    return CDRScoredFact(
        fact=fact,
        relevance=relevance,
        novelty=novelty,
        residual_pull=residual,
        importance=importance_weight,
        cdr_score=score,
        excluded=False,
    )


# ---------------------------------------------------------------------------
# CDR ranking (replace SPEC-003 Phase 2 ordering)
# ---------------------------------------------------------------------------


def cdr_rank(
    facts: list[Any],
    query_embedding: list[float],
    coverage_set: CoverageSet,
    *,
    importance_fn: Any = None,
    min_relevance: float = CDR_MIN_RELEVANCE,
    exhaustion_threshold: float = CDR_EXHAUSTION_THRESHOLD,
) -> CDRRankResult:
    """Rank *facts* by CDR score and detect CKF exhaustion.

    ``importance_fn(fact) -> float`` is an optional function returning the
    importance weight for a fact (e.g. from ``StateFact.seen_count`` novelty
    weights). Defaults to 1.0 if not provided.

    Args:
        facts: Candidate facts to rank.
        query_embedding: Embedding of the current query / task aspects.
        coverage_set: Session coverage set for novelty computation.
        importance_fn: Optional importance-weight function.
        min_relevance: Minimum relevance gate.
        exhaustion_threshold: Mean novelty threshold for CKF exhaustion.

    Returns:
        A ``CDRRankResult`` with ranked facts and exhaustion diagnosis.
    """
    scored: list[CDRScoredFact] = []
    excluded_count = 0

    for f in facts:
        w = importance_fn(f) if importance_fn else 1.0
        sf = cdr_score(
            f, query_embedding, coverage_set,
            importance_weight=w,
            min_relevance=min_relevance,
        )
        if sf.excluded:
            excluded_count += 1
        else:
            scored.append(sf)

    # Sort descending by CDR score
    scored.sort(key=lambda s: s.cdr_score, reverse=True)

    # CKF exhaustion check: mean novelty of top-10 candidates
    top10 = scored[:10]
    mean_novelty = (
        sum(s.novelty for s in top10) / len(top10) if top10 else 1.0
    )
    exhausted = mean_novelty < exhaustion_threshold

    return CDRRankResult(
        ranked=scored,
        ckf_exhausted=exhausted,
        mean_novelty_top10=mean_novelty,
        candidate_count=len(scored) + excluded_count,
        excluded_count=excluded_count,
    )


# ---------------------------------------------------------------------------
# Post-window coverage update helper
# ---------------------------------------------------------------------------


def update_coverage_after_window(
    coverage_set: CoverageSet,
    dpe_report: Any,
    window_number: int,
    all_sub_queries: list[dict[str, Any]] | None = None,
) -> None:
    """Update the Coverage Set from a DPE report after a window completes.

    Extracts ``addressed_sub_queries`` from the DPE report, which must expose
    a list of dicts with ``text``, ``embedding``, and optionally ``depth_weight``
    and ``id``.

    Args:
        coverage_set: Session coverage set to update.
        dpe_report: Decision-provenance report or dict.
        window_number: Window number that produced the report.
        all_sub_queries: Optional full list of sub-queries for residual tracking.
    """
    # DPE reports may use different field names — try both
    addressed: list[dict[str, Any]] = []
    if hasattr(dpe_report, "addressed_sub_queries"):
        raw = dpe_report.addressed_sub_queries
        if isinstance(raw, list):
            for sq in raw:
                if isinstance(sq, dict):
                    addressed.append(sq)
                elif hasattr(sq, "__dict__"):
                    addressed.append(sq.__dict__)
    elif isinstance(dpe_report, dict):
        addressed = dpe_report.get("addressed_sub_queries", [])

    coverage_set.update(
        addressed_sub_queries=addressed,
        all_sub_queries=all_sub_queries,
        window_number=window_number,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_embedding(fact: Any) -> list[float] | None:
    """Try multiple attribute names for the fact embedding.

    Supports ``fact._embedding``, ``fact.embedding``, and the nested
    ``fact.fact.*`` wrappers used by ``StateFact``.

    Args:
        fact: Fact-like object.

    Returns:
        The embedding vector, or None if none is found.
    """
    for attr in ("_embedding", "embedding"):
        val = getattr(fact, attr, None)
        if val is not None and len(val) > 0:
            return val
    # StateFact wraps inner Fact — check fact.fact._embedding
    inner = getattr(fact, "fact", None)
    if inner is not None:
        for attr in ("_embedding", "embedding"):
            val = getattr(inner, attr, None)
            if val is not None and len(val) > 0:
                return val
    return None


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        Cosine similarity in [-1, 1], or 0.0 for invalid inputs.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-12
    nb = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (na * nb)
