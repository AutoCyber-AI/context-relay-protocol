# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Contradiction detection — identifies and handles superseded facts (§3.4).

Detection rule: cosine similarity > 0.85 AND normalised edit distance > 0.3.
Action: mark earlier fact as superseded, 0.5× score multiplier in envelope.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from crp.extraction.types import Contradiction, Fact, FactEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Similarity helpers (pure-Python, no ML)
# ---------------------------------------------------------------------------

def _normalise_text(text: str) -> str:
    """Lowercase and strip extra whitespace."""
    return " ".join(text.lower().split())


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (word-level for efficiency)."""
    wa, wb = a.split(), b.split()
    m, n = len(wa), len(wb)
    if m == 0:
        return n
    if n == 0:
        return m
    # Single-row optimisation
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if wa[i - 1] == wb[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[n]


def _normalised_edit_distance(a: str, b: str) -> float:
    """Word-level edit distance normalised by max length."""
    na, nb = _normalise_text(a), _normalise_text(b)
    max_len = max(len(na.split()), len(nb.split()), 1)
    return _edit_distance(na, nb) / max_len


def _word_overlap_similarity(a: str, b: str) -> float:
    """Jaccard-based word overlap (fast proxy for cosine similarity).

    Real cosine similarity requires embeddings (Phase 4). This serves as
    a reasonable stand-in for Phase 2.
    """
    wa = set(_normalise_text(a).split())
    wb = set(_normalise_text(b).split())
    if not wa or not wb:
        return 0.0
    intersection = len(wa & wb)
    union = len(wa | wb)
    return intersection / union


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_contradictions(
    new_facts: Sequence[Fact],
    existing_facts: Sequence[Fact],
    similarity_threshold: float = 0.85,
    content_diff_threshold: float = 0.30,
) -> list[Contradiction]:
    """Detect contradictions between new and existing facts.

    A contradiction occurs when two facts are semantically very similar
    (sim > *similarity_threshold*) but textually different enough
    (edit distance > *content_diff_threshold*) to suggest conflicting info.
    """
    contradictions: list[Contradiction] = []

    for new_fact in new_facts:
        for existing in existing_facts:
            sim = _word_overlap_similarity(new_fact.text, existing.text)
            if sim < similarity_threshold:
                continue

            diff = _normalised_edit_distance(new_fact.text, existing.text)
            if diff > content_diff_threshold:
                contradictions.append(Contradiction(
                    fact_a=existing,
                    fact_b=new_fact,
                    similarity=round(sim, 4),
                    content_diff=round(diff, 4),
                    confidence=round(sim * diff, 4),
                ))

    return contradictions


def apply_supersessions(
    contradictions: list[Contradiction],
) -> list[FactEvent]:
    """Mark fact_a as superseded by fact_b for each contradiction.

    Returns a list of FactEvent records for the audit log.
    """
    events: list[FactEvent] = []
    for c in contradictions:
        if c.fact_a is None or c.fact_b is None:
            continue
        c.fact_a.superseded_by = c.fact_b.id
        c.fact_a.supersession_confidence = c.confidence
        events.append(FactEvent(
            event_type="superseded",
            fact_id=c.fact_a.id,
            payload={
                "superseded_by": c.fact_b.id,
                "similarity": c.similarity,
                "content_diff": c.content_diff,
            },
        ))
        logger.debug(
            "Fact %s superseded by %s (sim=%.2f, diff=%.2f)",
            c.fact_a.id[:8], c.fact_b.id[:8], c.similarity, c.content_diff,
        )
    return events
