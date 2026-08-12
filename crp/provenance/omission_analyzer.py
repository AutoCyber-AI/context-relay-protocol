# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Omission Analyzer — detect when the model silently ignores important facts.

15 high-priority facts went into the envelope.  The model used 4 and
ignored 11.  If Fact #3 was "Product has a known safety defect" and the
model never mentioned it — that is a **material omission**.

This module identifies which envelope facts received NO attribution
from any output claim and ranks them by importance (original packing
score).  High-importance omissions are flagged for manual review.
"""

from __future__ import annotations

from collections.abc import Sequence

from crp.envelope.packer import PackedFact

from ._types import (
    ClaimAttribution,
    OmissionResult,
    OmissionSeverity,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_omissions(
    attributions: list[ClaimAttribution],
    packed_facts: Sequence[PackedFact],
    *,
    attribution_floor: float = 0.20,
) -> list[OmissionResult]:
    """Identify envelope facts that the model ignored.

    For each packed fact, finds the maximum attribution score any output
    claim gave it.  Facts with a maximum score below ``attribution_floor``
    are considered omitted.

    Results are sorted by fact relevance score descending — the most
    important omissions first.

    Args:
        attributions: Scored claim attributions from the attribution scorer.
        packed_facts: All facts that were packed into the envelope.
        attribution_floor: Maximum composite score below which a fact
                           is considered "not used" (default 0.20).

    Returns:
        List of OmissionResult sorted by importance (highest first).
    """
    if not packed_facts:
        return []

    # Build a map: fact_id → max composite score from any claim
    max_scores: dict[str, float] = {pf.fact_id: 0.0 for pf in packed_facts}

    for attr in attributions:
        for fs in attr.attributed_facts:
            if fs.fact_id in max_scores:
                max_scores[fs.fact_id] = max(
                    max_scores[fs.fact_id], fs.composite_score
                )

    # Determine relevance quartiles for severity classification
    scores_list = sorted(
        (pf.score for pf in packed_facts), reverse=True
    )
    n = len(scores_list)
    q1_threshold = scores_list[n // 4] if n >= 4 else scores_list[0]
    q2_threshold = scores_list[n // 2] if n >= 2 else scores_list[0]

    results: list[OmissionResult] = []

    for pf in packed_facts:
        max_attr = max_scores.get(pf.fact_id, 0.0)

        if max_attr >= attribution_floor:
            continue  # Fact was adequately used

        # Classify severity based on packing relevance score
        if pf.score >= q1_threshold:
            severity = OmissionSeverity.CRITICAL
        elif pf.score >= q2_threshold:
            severity = OmissionSeverity.HIGH
        elif pf.score > 0.0:
            severity = OmissionSeverity.MEDIUM
        else:
            severity = OmissionSeverity.LOW

        results.append(OmissionResult(
            fact_id=pf.fact_id,
            fact_text_preview=pf.text[:120],
            fact_relevance_score=round(pf.score, 4),
            max_attribution_score=round(max_attr, 4),
            severity=severity,
        ))

    # Sort by relevance (most important omissions first)
    results.sort(key=lambda r: r.fact_relevance_score, reverse=True)

    return results
