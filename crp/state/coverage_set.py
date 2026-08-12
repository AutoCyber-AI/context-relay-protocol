# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Coverage Set — session-scoped novelty tracker for CDR (SPEC-024 §2.1–3.2).

The Coverage Set is the CDR mechanism's memory of what has been addressed.
After each window the Coverage Set is updated with embeddings of the sub-queries
that window's output covered, weighted by how thoroughly they were covered.

CDR uses the Coverage Set to score each fact by how novel it is relative to
what has already been written — ensuring Window 5 receives different, fresh
material rather than the same facts that Window 1 received.

Embedding model consistency is enforced: every entry MUST use the same model
as the CKF facts. The model id is recorded on construction and mismatches are
rejected (SPEC-024 §2.5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Coverage entry
# ---------------------------------------------------------------------------


@dataclass
class CoverageEntry:
    """A single addressed sub-query, embedded and weighted (SPEC-024 §2.1).

    ``embedding`` — dense vector of the sub-query text.  MUST use the same
    model as the CKF fact embeddings (hard requirement, see §2.5).

    ``depth_weight`` — how thoroughly this sub-query was addressed (0.0–1.0).
    See the depth weight table in §3.2:
        0.90  thorough  (dedicated section, multiple paragraphs)
        0.70  adequate  (full paragraph)
        0.40  partial   (single sentence or brief mention)
        0.15  marginal  (passing reference only)

    ``window_number`` — which window addressed it.
    ``text`` — the sub-query text (kept for debugging / introspection).
    """

    embedding: list[float]
    depth_weight: float       # 0.0–1.0
    window_number: int
    text: str = ""


# ---------------------------------------------------------------------------
# Residual sub-query
# ---------------------------------------------------------------------------


@dataclass
class ResidualItem:
    """A sub-query that has NOT yet been addressed.

    Built by subtracting Coverage Set topics from the original task
    decomposition (SPEC-024 §3.1).
    """

    text: str
    embedding: list[float]
    sub_query_id: str = ""


# ---------------------------------------------------------------------------
# Coverage Set
# ---------------------------------------------------------------------------


_COVERAGE_PENALTY_CAP = 0.80   # SPEC-024 §2.2
_MIN_NOVELTY_FLOOR = 0.20      # SPEC-024 §2.4


class CoverageSet:
    """Session-scoped list of covered sub-query embeddings with depth weights.

    This is the core state the CDR formula reads every time it ranks a fact.
    Updated after each window via ``update()``.

    Embedding model consistency: all embeddings (Coverage Set + CKF facts)
    MUST use the same model.  Record the model id when creating the session
    coverage set and reject mismatched updates.
    """

    def __init__(self, embedding_model_id: str = "") -> None:
        self._entries: list[CoverageEntry] = []
        self._residual: list[ResidualItem] = []
        self.embedding_model_id: str = embedding_model_id

    # ------------------------------------------------------------------
    # Core scoring (called from CDR formula)
    # ------------------------------------------------------------------

    def coverage_score(self, fact_embedding: list[float]) -> float:
        """Weighted mean cosine similarity to all Coverage Set entries.

        Args:
            fact_embedding: Dense embedding vector for the fact.

        Returns:
            0.0 if the Coverage Set is empty (Window 1 behaviour — every fact
            is fully novel at Window 1). Otherwise the weighted mean cosine
            similarity over all entries. Uses weighted mean, NOT maximum —
            see SPEC-024 §2.3.
        """
        if not self._entries:
            return 0.0

        total_weight = sum(e.depth_weight for e in self._entries) or 1e-12
        weighted_sum = 0.0
        for entry in self._entries:
            sim = _cosine_sim(fact_embedding, entry.embedding)
            weighted_sum += entry.depth_weight * sim

        return weighted_sum / total_weight

    def residual_pull(self, fact_embedding: list[float]) -> float:
        """Maximum cosine similarity to any residual (unaddressed) sub-query.

        Args:
            fact_embedding: Dense embedding vector for the fact.

        Returns:
            0.0 if the Residual Set is empty. Otherwise the maximum cosine
            similarity, implementing the "pull toward what has not yet been
            written" signal from SPEC-024 §2.2.
        """
        if not self._residual:
            return 0.0
        return max(
            _cosine_sim(fact_embedding, r.embedding)
            for r in self._residual
        )

    def novelty(self, fact_embedding: list[float]) -> float:
        """Compute novelty score for a fact (SPEC-024 §2.2–2.4).

        Args:
            fact_embedding: Dense embedding vector for the fact.

        Returns:
            Novelty score in [0.0, 1.0]. Computes
            ``max(1.0 - coverage_penalty, MIN_NOVELTY_FLOOR)`` where
            ``coverage_penalty = min(coverage_score, COVERAGE_PENALTY_CAP)``.
            Adds a ``0.20 × residual_pull`` boost for facts aligned with
            still-unaddressed topics. Returns 1.0 when Coverage Set is empty
            (Window 1 — all fresh).
        """
        cov = self.coverage_score(fact_embedding)
        penalty = min(cov, _COVERAGE_PENALTY_CAP)
        base_novelty = max(1.0 - penalty, _MIN_NOVELTY_FLOOR)

        # Bidirectional: also pull toward residual topics
        res = self.residual_pull(fact_embedding)
        boosted = min(1.0, base_novelty + 0.20 * res)
        return boosted

    def mean_novelty(self, sample_embeddings: list[list[float]]) -> float:
        """Average novelty across a sample of fact embeddings.

        Args:
            sample_embeddings: List of fact embedding vectors.

        Returns:
            Average novelty score. Used by CDR exhaustion detection: if
            ``mean_novelty < 0.15``, the CKF has run out of fresh material
            for this session (SPEC-024 §5.2).
        """
        if not sample_embeddings:
            return 1.0
        return sum(self.novelty(e) for e in sample_embeddings) / len(sample_embeddings)

    # ------------------------------------------------------------------
    # Update (called after each window completes)
    # ------------------------------------------------------------------

    def update(
        self,
        addressed_sub_queries: list[dict[str, Any]],
        all_sub_queries: list[dict[str, Any]] | None = None,
        window_number: int = 0,
        embedding_model_id: str = "",
    ) -> None:
        """Add coverage entries for all addressed sub-queries in this window.

        Args:
            addressed_sub_queries: List of dicts with keys:
                ``text`` (str), ``embedding`` (list[float]),
                ``depth_weight`` (float, optional — defaults to 0.5),
                ``id`` (str, optional).
            all_sub_queries: If provided, updates the Residual Set by removing
                addressed sub-queries (SPEC-024 §3.1).
            window_number: Window that addressed the sub-queries.
            embedding_model_id: Embedding model id. Must match
                ``self.embedding_model_id`` or a ``ValueError`` is raised
                (SPEC-024 §2.5).

        Raises:
            ValueError: If ``embedding_model_id`` conflicts with the Coverage
                Set's recorded model id.
        """
        if embedding_model_id and self.embedding_model_id:
            if embedding_model_id != self.embedding_model_id:
                raise ValueError(
                    f"Embedding model mismatch: Coverage Set uses "
                    f"'{self.embedding_model_id}' but update provides "
                    f"'{embedding_model_id}'. SPEC-024 §2.5 requires "
                    "all embeddings to use the same model."
                )

        for sq in addressed_sub_queries:
            emb = sq.get("embedding", [])
            if not emb:
                continue
            self._entries.append(CoverageEntry(
                embedding=emb,
                depth_weight=float(sq.get("depth_weight", 0.5)),
                window_number=window_number,
                text=sq.get("text", ""),
            ))

        # Update Residual Set
        if all_sub_queries is not None:
            addressed_ids = {
                sq.get("id", sq.get("text", ""))
                for sq in addressed_sub_queries
            }
            self._residual = [
                ResidualItem(
                    text=sq.get("text", ""),
                    embedding=sq.get("embedding", []),
                    sub_query_id=sq.get("id", sq.get("text", "")),
                )
                for sq in all_sub_queries
                if sq.get("id", sq.get("text", "")) not in addressed_ids
                and sq.get("embedding")
            ]

    def set_residual(self, residual_items: list[ResidualItem]) -> None:
        """Directly replace the Residual Set (e.g. on session restore).

        Args:
            residual_items: New residual items.

        Returns:
            None.
        """
        self._residual = list(residual_items)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def entry_count(self) -> int:
        """Number of coverage entries."""
        return len(self._entries)

    def residual_count(self) -> int:
        """Number of residual (unaddressed) sub-queries."""
        return len(self._residual)

    def entries(self) -> list[CoverageEntry]:
        """Return a copy of all coverage entries."""
        return list(self._entries)

    def residuals(self) -> list[ResidualItem]:
        """Return a copy of all residual items."""
        return list(self._residual)

    def reset(self) -> None:
        """Clear all state (e.g. on session reset).

        Returns:
            None.
        """
        self._entries.clear()
        self._residual.clear()

    def __repr__(self) -> str:
        """Return a concise debug representation."""
        return (
            f"CoverageSet(entries={len(self._entries)}, "
            f"residual={len(self._residual)}, "
            f"model='{self.embedding_model_id}')"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two dense vectors.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        Cosine similarity in [-1.0, 1.0], or 0.0 for invalid inputs.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-12
    nb = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (na * nb)
