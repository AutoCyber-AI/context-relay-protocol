# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 3 — Cross-encoder reranking (§3.2).

Reranks the top-K bi-encoder scored facts using a cross-encoder for higher
accuracy.  Falls back to bi-encoder scores when the cross-encoder model is
unavailable.

Blended score: 0.6 × CE_score + 0.4 × bi_encoder_score
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field, replace as _dc_replace

from crp.core.task_intent import TaskIntent

from .scoring import ScoredFact

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOP_K_RERANK = 200
MIN_FACTS_FOR_RERANK = 10
CE_WEIGHT = 0.6
BI_WEIGHT = 0.4
IDLE_UNLOAD_WINDOWS = 10

# ---------------------------------------------------------------------------
# Cross-encoder model management (lazy load, idle unload)
# ---------------------------------------------------------------------------

_CE_MODEL: object | None = None
_CE_AVAILABLE: bool | None = None  # None = not yet attempted
_CE_LAST_USED_WINDOW: int = 0
# Guards the module-global model lifecycle (audit U-C11): without it, two
# threads could lazy-load the model twice (double RAM spike) and
# maybe_unload_cross_encoder could free it mid-predict in another thread.
_CE_LOCK = threading.RLock()


def _try_load_cross_encoder() -> bool:
    """Attempt lazy load of cross-encoder model.  Returns True on success."""
    global _CE_MODEL, _CE_AVAILABLE  # noqa: PLW0603
    with _CE_LOCK:
        if _CE_AVAILABLE is True:
            return True
        if _CE_AVAILABLE is False:
            return False
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]

            _CE_MODEL = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2")
            _CE_AVAILABLE = True
        except Exception:  # noqa: BLE001
            _CE_AVAILABLE = False
        return _CE_AVAILABLE or False


def maybe_unload_cross_encoder(current_window: int) -> None:
    """Unload cross-encoder if idle for > IDLE_UNLOAD_WINDOWS."""
    global _CE_MODEL, _CE_AVAILABLE, _CE_LAST_USED_WINDOW  # noqa: PLW0603
    with _CE_LOCK:
        if _CE_MODEL is not None and (current_window - _CE_LAST_USED_WINDOW) > IDLE_UNLOAD_WINDOWS:
            _CE_MODEL = None
            _CE_AVAILABLE = None


def preload_cross_encoder() -> bool:
    """Eagerly load the cross-encoder model at startup to avoid cold-start delay.

    Returns True if the model was loaded successfully, False otherwise.
    Called from CRPOrchestrator.__init__() to pay the ~5s load cost once
    at protocol start rather than during the first rerank operation.
    """
    return _try_load_cross_encoder()


# ---------------------------------------------------------------------------
# CrossEncoderCache
# ---------------------------------------------------------------------------


def _task_hash(task_intent: TaskIntent) -> str:
    """Deterministic hash of the task for cache keying."""
    parts = (task_intent.system_prompt or "") + "|" + (task_intent.task_input or "")
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


@dataclass
class CrossEncoderCache:
    """Per-session cache for cross-encoder scores.

    Key: (task_hash, fact_id).  Invalidation rules:
    - Full clear on compaction.
    - Remove entry on fact supersession.
    - Full clear when the task hash changes (exact-match invalidation;
      the retired ``TASK_SIM_INVALIDATION_THRESHOLD`` similarity constant
      was never wired in — audit U-C11 — and has been removed).
    """

    _cache: dict[tuple[str, str], float] = field(default_factory=dict)
    _last_task_hash: str = ""

    def get(self, t_hash: str, fact_id: str) -> float | None:
        """Return the cached cross-encoder score, if any.

        Args:
            t_hash: Task hash for the cache key.
            fact_id: Fact identifier for the cache key.

        Returns:
            Cached score or ``None`` when no entry exists.
        """
        return self._cache.get((t_hash, fact_id))

    def put(self, t_hash: str, fact_id: str, score: float) -> None:
        """Store a cross-encoder score for the given task and fact.

        Args:
            t_hash: Task hash for the cache key.
            fact_id: Fact identifier for the cache key.
            score: Cross-encoder score to cache.
        """
        self._cache[(t_hash, fact_id)] = score

    def invalidate_fact(self, fact_id: str) -> None:
        """Remove all entries for a superseded fact."""
        keys = [k for k in self._cache if k[1] == fact_id]
        for k in keys:
            del self._cache[k]

    def invalidate_all(self) -> None:
        """Full cache clear (compaction or task change)."""
        self._cache.clear()
        self._last_task_hash = ""

    def check_task_change(self, new_task_hash: str) -> None:
        """If task hash changed, invalidate entire cache."""
        if self._last_task_hash and self._last_task_hash != new_task_hash:
            self.invalidate_all()
        self._last_task_hash = new_task_hash

    @property
    def size(self) -> int:
        """Return the current size count."""
        return len(self._cache)


# ---------------------------------------------------------------------------
# Reranking
# ---------------------------------------------------------------------------


def rerank(
    scored_facts: list[ScoredFact],
    task_intent: TaskIntent,
    *,
    cache: CrossEncoderCache | None = None,
    current_window: int = 0,
) -> list[ScoredFact]:
    """Rerank *scored_facts* using the cross-encoder.

    - Only top TOP_K_RERANK facts are reranked.
    - If fewer than MIN_FACTS_FOR_RERANK facts, skip reranking entirely.
    - Falls back to bi-encoder scores if the model is unavailable.

    Returns all facts sorted by blended score descending.
    """
    global _CE_LAST_USED_WINDOW  # noqa: PLW0603

    if not scored_facts:
        return []

    # If too few facts, skip reranking — bi-encoder is sufficient
    if len(scored_facts) < MIN_FACTS_FOR_RERANK:
        return scored_facts  # already sorted by bi-encoder score

    # Already-blended input (audit U-C11): a second rerank would compound
    # the CE weighting and reshuffle tie order, so treat flagged input as
    # final — stable re-sort only, which is a fixed point.
    if all(sf.rerank_blend_applied for sf in scored_facts):
        return sorted(scored_facts, key=lambda s: s.composite_score, reverse=True)

    # Select candidates for reranking
    candidates = scored_facts[:TOP_K_RERANK]
    remainder = scored_facts[TOP_K_RERANK:]

    # Attempt cross-encoder
    if not _try_load_cross_encoder() or _CE_MODEL is None:
        return scored_facts  # fallback: bi-encoder order preserved

    _CE_LAST_USED_WINDOW = current_window

    t_hash = _task_hash(task_intent)
    if cache is not None:
        cache.check_task_change(t_hash)

    # Build query text
    query = (task_intent.system_prompt or "") + " " + (task_intent.task_input or "")
    query = query.strip()

    # Score pairs (using cache where available)
    pairs_to_score: list[tuple[int, str]] = []  # (index_in_candidates, fact_text)
    ce_scores: dict[int, float] = {}

    for i, sf in enumerate(candidates):
        cached = cache.get(t_hash, sf.fact.id) if cache else None
        if cached is not None:
            ce_scores[i] = cached
        else:
            pairs_to_score.append((i, sf.fact.text))

    # Batch predict uncached pairs — hold the lifecycle lock so the model
    # cannot be unloaded mid-predict by maybe_unload_cross_encoder (U-C11).
    if pairs_to_score:
        input_pairs = [(query, text) for _, text in pairs_to_score]
        try:
            with _CE_LOCK:
                model = _CE_MODEL
                if model is None:  # pragma: no cover - raced unload
                    return scored_facts
                raw_scores = model.predict(input_pairs)  # type: ignore[attr-defined]
            for (idx, _), raw in zip(pairs_to_score, raw_scores):
                score_val = float(raw)
                ce_scores[idx] = score_val
                if cache is not None:
                    cache.put(t_hash, candidates[idx].fact.id, score_val)
        except Exception:  # noqa: BLE001
            # Model failure — fall back to bi-encoder scores
            return scored_facts

    # Compute blended scores into NEW ScoredFact objects (audit U-C11): the
    # pre-6.2.2 code wrote the blend into the caller's input objects, so a
    # second rerank of the same list compounded the CE weighting (0.4 × 0.4 …)
    # and the mutation leaked into the caller's envelope state.
    blended = [
        _dc_replace(
            sf,
            composite_score=CE_WEIGHT * ce_scores.get(i, 0.0)
            + BI_WEIGHT * sf.composite_score,
            rerank_blend_applied=True,
        )
        for i, sf in enumerate(candidates)
    ]

    # Re-sort candidates by blended score
    blended.sort(key=lambda s: s.composite_score, reverse=True)

    # Append remainder (already below top-K, keep original order)
    return blended + remainder
