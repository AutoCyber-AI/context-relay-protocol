# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Regulatory amplifiers for the hallucination composite (CRP-SPEC-005 §17).

After the base composite hallucination score is computed, regulatory amplifiers
multiply it upward when the regulatory context raises the stakes of a given
risk level (PII exposure, EU AI Act HIGH-risk domain, financial/medical sector,
deep agent chains, cross-window contradictions, severe repetition).  The
amplified score is capped at ``1.0`` and may push the window into a higher
:class:`HallucinationRisk` band.

Amplifier *values* are configuration (kept symbolic in the public spec); the
*conditions* are specified.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ._types import HallucinationRisk, ProvenanceConfig


@dataclass
class AmplifierContext:
    """The regulatory/agentic signals that may amplify the composite score."""

    gdpr_pii: bool = False
    eu_ai_act_high: bool = False
    sector_regulated: bool = False  # financial or medical domain
    agent_loop_depth: int = 0
    cross_window_contradiction: bool = False
    severe_repetition: bool = False


@dataclass
class AmplifierResult:
    """The outcome of applying amplifiers to a base composite score."""

    base_score: float
    amplified_score: float
    total_multiplier: float
    applied: list[tuple[str, float]] = field(default_factory=list)
    risk_level: HallucinationRisk = HallucinationRisk.LOW

    @property
    def amplified(self) -> bool:
        """Return whether the amplified condition holds."""
        return self.total_multiplier > 1.0


def _risk_band(score: float) -> HallucinationRisk:
    if score >= 0.75:
        return HallucinationRisk.CRITICAL
    if score >= 0.50:
        return HallucinationRisk.HIGH
    if score >= 0.25:
        return HallucinationRisk.MEDIUM
    return HallucinationRisk.LOW


def apply_amplifiers(
    base_score: float,
    context: AmplifierContext,
    *,
    config: ProvenanceConfig | None = None,
) -> AmplifierResult:
    """Apply regulatory amplifiers to *base_score* (CRP-SPEC-005 §17).

    Amplifiers are multiplicative and compound; the result is clamped to
    ``[0.0, 1.0]``.  Returns an :class:`AmplifierResult` recording which
    amplifiers fired and the resulting risk band.
    """
    cfg = config or ProvenanceConfig()
    base = max(0.0, min(1.0, base_score))

    if not cfg.amplifiers_enabled:
        return AmplifierResult(
            base_score=base,
            amplified_score=base,
            total_multiplier=1.0,
            risk_level=_risk_band(base),
        )

    applied: list[tuple[str, float]] = []
    multiplier = 1.0

    def fire(name: str, factor: float) -> None:
        """Execute fire and return the result.
        
            Args:
                name (str): The name value.
                factor (float): The factor value.
        
            Returns:
                ``None``.
        """
        nonlocal multiplier
        multiplier *= factor
        applied.append((name, factor))

    if context.gdpr_pii:
        fire("gdpr-pii", cfg.amplifier_gdpr_pii)
    if context.eu_ai_act_high:
        fire("eu-ai-act-high", cfg.amplifier_eu_ai_act_high)
    if context.sector_regulated:
        fire("sector-regulated", cfg.amplifier_sector)
    if context.agent_loop_depth > 2:
        fire("agent-depth", cfg.amplifier_agent_depth)
    if context.cross_window_contradiction:
        fire("cross-window-contradiction", cfg.amplifier_cross_window)
    if context.severe_repetition:
        fire("severe-repetition", cfg.amplifier_severe_repetition)

    amplified = min(1.0, round(base * multiplier, 4))
    return AmplifierResult(
        base_score=base,
        amplified_score=amplified,
        total_multiplier=round(multiplier, 4),
        applied=applied,
        risk_level=_risk_band(amplified),
    )
