# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Quality tier classification and reporting (§05, §10).

Each CRP session runs at a quality tier that tells the user how well
the context pipeline is performing:

    S  — all signals green, overhead < 5 %
    A  — minor gaps, overhead < 10 %
    B  — acceptable, overhead < 15 %
    C  — degraded, hierarchical processing needed
    D  — minimal / fallback mode

QualityReporter takes a handful of easily-computed metrics and maps
them to one of these tiers.  It can also detect *degradation* (tier
dropping below a previous high-water mark).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class QualityTier(Enum):
    """CRP quality tiers (best → worst)."""

    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"

    def __lt__(self, other: QualityTier) -> bool:
        order = ["S", "A", "B", "C", "D"]
        return order.index(self.value) < order.index(other.value)


# Threshold rules: (max_overhead_pct, max_fact_miss_pct, tier)
# Checked in order — first match wins.
_TIER_RULES: list[tuple[float, float, QualityTier]] = [
    (5.0, 2.0, QualityTier.S),
    (10.0, 10.0, QualityTier.A),
    (15.0, 25.0, QualityTier.B),
    (30.0, 50.0, QualityTier.C),
    # Everything else → D
]


@dataclass
class QualityReport:
    """Result of a quality assessment."""

    tier: QualityTier
    overhead_pct: float
    fact_miss_pct: float
    degraded: bool = False  # True if tier dropped below previous high
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the quality report as a plain dict.

        Returns:
            Dict with ``tier``, ``overhead_pct``, ``fact_miss_pct``,
            ``degraded``, and ``details`` fields.
        """
        return {
            "tier": self.tier.value,
            "overhead_pct": round(self.overhead_pct, 2),
            "fact_miss_pct": round(self.fact_miss_pct, 2),
            "degraded": self.degraded,
            "details": self.details or {},
        }


class QualityReporter:
    """Classify and track quality tiers across a session.

    Usage::

        qr = QualityReporter()
        report = qr.assess(overhead_pct=4.2, fact_miss_pct=1.0)
        assert report.tier == QualityTier.S

        # Later, if overhead rises:
        report2 = qr.assess(overhead_pct=18.0, fact_miss_pct=30.0)
        assert report2.tier == QualityTier.C
        assert report2.degraded  # dropped from S → C
    """

    def __init__(self) -> None:
        self._high_water: QualityTier | None = None
        self._history: list[QualityReport] = []

    def assess(
        self,
        overhead_pct: float,
        fact_miss_pct: float,
        details: dict[str, Any] | None = None,
    ) -> QualityReport:
        """Compute the current quality tier and check for degradation.

        Args:
            overhead_pct:  Current overhead as a percentage (0-100).
            fact_miss_pct: Percentage of available facts *not* included
                           in the envelope (0-100).
            details:       Optional opaque dict attached to the report.
        """
        tier = self._classify(overhead_pct, fact_miss_pct)
        degraded = self._high_water is not None and self._high_water < tier

        # Update high-water mark.
        if self._high_water is None or tier < self._high_water:
            self._high_water = tier

        report = QualityReport(
            tier=tier,
            overhead_pct=overhead_pct,
            fact_miss_pct=fact_miss_pct,
            degraded=degraded,
            details=details,
        )
        self._history.append(report)
        return report

    @property
    def current_tier(self) -> QualityTier | None:
        """Most recently assessed tier, or ``None`` if never assessed."""
        return self._history[-1].tier if self._history else None

    @property
    def history(self) -> list[QualityReport]:
        """Return the history."""
        return list(self._history)

    @staticmethod
    def _classify(overhead_pct: float, fact_miss_pct: float) -> QualityTier:
        for max_oh, max_fm, tier in _TIER_RULES:
            if overhead_pct <= max_oh and fact_miss_pct <= max_fm:
                return tier
        return QualityTier.D
