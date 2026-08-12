# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Response Quality Assurance composite score (CRP-SPEC-005 §18).

The RQA quality score is distinct from the safety hallucination score: safety
measures *truthfulness*, quality measures *usefulness*.  It fuses the four
RQA-stage signals — repetition (Stage 7), completeness (Stage 8), flow
(Stage 9), and cross-window coherence (Stage 6) — into one ``CRP-Quality-Score``
and can downgrade the emitted ``CRP-Context-Quality-Tier``.

    quality_score = 0.25·(1−repetition) + 0.35·completeness
                  + 0.25·flow          + 0.15·(1−contradiction)
"""

from __future__ import annotations

from dataclasses import dataclass

from ._types import ProvenanceConfig

# CRP-SPEC-005 §18.4 — quality-score → maximum quality tier.
_TIER_FLOORS: tuple[tuple[float, str], ...] = (
    (0.85, "S"),
    (0.70, "A"),
    (0.50, "B"),
    (0.30, "C"),
    (0.0, "D"),
)

_TIER_ORDER = ["S", "A", "B", "C", "D"]


@dataclass
class RQASignals:
    """The four RQA-stage inputs (all 0.0–1.0)."""

    repetition_ratio: float = 0.0      # Stage 7 — higher = more repetition (worse)
    completeness_score: float = 1.0    # Stage 8 — higher = more complete (better)
    flow_score: float = 1.0            # Stage 9 — higher = better flow (better)
    contradiction_ratio: float = 0.0   # Stage 6 — higher = more contradiction (worse)


@dataclass
class RQAResult:
    """The computed RQA quality score and resulting tier cap."""

    quality_score: float
    max_tier: str

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        return {"CRP-Quality-Score": f"{self.quality_score:.2f}"}


def max_tier_for_score(quality_score: float) -> str:
    """Return the best quality tier permitted by *quality_score* (§18.4)."""
    for floor, tier in _TIER_FLOORS:
        if quality_score >= floor:
            return tier
    return "D"


def compute_quality_score(
    signals: RQASignals,
    *,
    config: ProvenanceConfig | None = None,
) -> RQAResult:
    """Compute the RQA composite quality score (CRP-SPEC-005 §18.2)."""
    cfg = config or ProvenanceConfig()

    def clamp(x: float) -> float:
        """Execute clamp and return the result.
        
            Args:
                x (float): The x value.
        
            Returns:
                ``float``.
        """
        return max(0.0, min(1.0, x))

    score = (
        cfg.rqa_weight_repetition * (1.0 - clamp(signals.repetition_ratio))
        + cfg.rqa_weight_completeness * clamp(signals.completeness_score)
        + cfg.rqa_weight_flow * clamp(signals.flow_score)
        + cfg.rqa_weight_coherence * (1.0 - clamp(signals.contradiction_ratio))
    )
    score = round(clamp(score), 4)
    return RQAResult(quality_score=score, max_tier=max_tier_for_score(score))


def downgrade_tier(envelope_tier: str, quality_score: float) -> str:
    """Downgrade *envelope_tier* if the RQA quality score requires it (§18.4).

    The emitted tier is the *worse* of the envelope tier and the score-derived
    ceiling — e.g. envelope ``A`` with score 0.62 → emitted ``B``.
    """
    ceiling = max_tier_for_score(quality_score)
    try:
        worse_idx = max(_TIER_ORDER.index(envelope_tier), _TIER_ORDER.index(ceiling))
    except ValueError:
        return envelope_tier
    return _TIER_ORDER[worse_idx]
