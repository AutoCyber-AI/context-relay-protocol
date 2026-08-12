# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Scale-mode selector — auto-configure session by quality tier (§8.3, §15).

Classifies input into quality tiers S/A/B/C/D based on token ratio,
then configures processing mode, validation tiers, review cycles, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

# ---------------------------------------------------------------------------
# Quality tiers (§10.2)
# ---------------------------------------------------------------------------


class QualityTier(IntEnum):
    """Quality tiers — S (single window) through D (>1000 windows at 128K ctx)."""

    S = 0  # ≤ C
    A = 1  # C–10C
    B = 2  # 10C–100C
    C = 3  # 100C–1000C
    D = 4  # >1000C


def classify_quality_tier(
    estimated_tokens: int, context_window: int,
) -> QualityTier:
    """Classify input into quality tier based on token-to-context ratio."""
    if context_window <= 0:
        return QualityTier.S
    ratio = estimated_tokens / context_window
    if ratio <= 1:
        return QualityTier.S
    if ratio <= 10:
        return QualityTier.A
    if ratio <= 100:
        return QualityTier.B
    if ratio <= 1000:
        return QualityTier.C
    return QualityTier.D


# ---------------------------------------------------------------------------
# Processing mode
# ---------------------------------------------------------------------------


def select_processing_mode(
    estimated_tokens: int, context_window: int,
) -> str:
    """Select processing mode based on windows needed."""
    if context_window <= 0:
        return "SERIAL"
    windows = estimated_tokens / context_window
    if windows <= 10:
        return "SERIAL"
    if windows <= 100:
        return "SERIAL_WITH_REGROUNDING"
    if windows <= 1000:
        return "HIERARCHICAL"
    return "HIERARCHICAL_MULTI_LEVEL"


# ---------------------------------------------------------------------------
# Session configuration
# ---------------------------------------------------------------------------


@dataclass
class SessionConfig:
    """Auto-configured session parameters."""

    quality_tier: QualityTier = QualityTier.S
    processing_mode: str = "SERIAL"
    cqs_enabled: bool = False
    validation_tiers: int = 1
    review_cycles_enabled: bool = False
    planning_window: bool = False
    hierarchical: bool = False
    re_grounding: bool = False
    model_review_capability: int = 1


class ScaleModeSelector:
    """Auto-configure session based on quality tier and model capability."""

    def __init__(
        self,
        context_window: int = 128_000,
    ) -> None:
        self._context_window = context_window

    def configure_session(
        self,
        estimated_tokens: int,
        model_capability: int = 1,
    ) -> SessionConfig:
        """Auto-configure session based on input size and model capability.

        Args:
            estimated_tokens: Total estimated input tokens.
            model_capability: Assessed model capability (1, 2, or 3).

        Returns:
            SessionConfig with all parameters set.
        """
        tier = classify_quality_tier(estimated_tokens, self._context_window)
        mode = select_processing_mode(estimated_tokens, self._context_window)

        return SessionConfig(
            quality_tier=tier,
            processing_mode=mode,
            cqs_enabled=tier >= QualityTier.A,
            validation_tiers=min(
                model_capability,
                3 if tier >= QualityTier.C else 2 if tier >= QualityTier.B else 1,
            ),
            review_cycles_enabled=(
                tier >= QualityTier.B and model_capability >= 3
            ),
            planning_window=tier >= QualityTier.B,
            hierarchical=tier >= QualityTier.C,
            re_grounding=tier >= QualityTier.B,
            model_review_capability=model_capability,
        )
