# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Operating-mode detection + per-call coverage (CRP-SPEC-017 §2, §3, §7).

Determines whether a tenant is in **Zero-CKF**, **Partial-CKF**, or **Full-CKF**
mode from the active fact count and community count, applies sticky transition
rules to prevent flapping, and computes the per-call coverage adjustment used
in Partial-CKF mode.

Relevant specifications:
  - CRP-SPEC-017: Zero-CKF Mode
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# CRP-SPEC-017 §2 — fact-count thresholds.
PARTIAL_MIN_FACTS = 1
FULL_MIN_FACTS = 1000
FULL_MIN_COMMUNITIES = 3

# CRP-SPEC-017 §3.3 — stickiness windows (seconds).
PROMOTE_STICKY_SECONDS = 60
DEMOTE_STICKY_SECONDS = 300

# CRP-SPEC-017 §7.1 — per-call coverage relevance floor.
COVERAGE_RELEVANCE_FLOOR = 0.60


class ActivationMode(str, Enum):
    """The three CRP operating modes (CRP-SPEC-017 §2).

    Attributes:
        ZERO_CKF: No active facts; CRP operates without a Contextual Knowledge
            Fabric.
        PARTIAL_CKF: Some facts exist but thresholds for Full-CKF are not met.
        FULL_CKF: Large, well-clustered knowledge fabric available for retrieval.
    """

    ZERO_CKF = "zero-ckf"
    PARTIAL_CKF = "partial-ckf"
    FULL_CKF = "full-ckf"


def detect_mode(fact_count: int, community_count: int = 0) -> ActivationMode:
    """Classify the operating mode from CKF state (CRP-SPEC-017 §2).

    Full-CKF requires both 1000+ facts AND 3+ detected communities.

    Args:
        fact_count: Number of facts currently in the CKF.
        community_count: Number of detected CKF communities.

    Returns:
        The matching ``ActivationMode``.
    """
    if fact_count <= 0:
        return ActivationMode.ZERO_CKF
    if fact_count >= FULL_MIN_FACTS and community_count >= FULL_MIN_COMMUNITIES:
        return ActivationMode.FULL_CKF
    return ActivationMode.PARTIAL_CKF


@dataclass
class ModeState:
    """Sticky mode tracker (CRP-SPEC-017 §3.3).

    Holds the currently *effective* mode plus the timestamp at which a candidate
    transition was first observed, so brief reindexing does not flap the mode.

    Attributes:
        mode: Effective operating mode.
        candidate: Candidate mode currently being observed, or None if stable.
        candidate_since: Unix timestamp when the current candidate was first
            observed, or None.
    """

    mode: ActivationMode = ActivationMode.ZERO_CKF
    candidate: ActivationMode | None = None
    candidate_since: float | None = None

    def update(self, fact_count: int, community_count: int, now: float) -> ModeTransition:
        """Re-evaluate the mode given current CKF state and wall-clock ``now``.

        Args:
            fact_count: Current number of CKF facts.
            community_count: Current number of CKF communities.
            now: Current Unix timestamp.

        Returns:
            A ``ModeTransition``; ``transitioned`` is ``True`` only when a
            sticky transition actually fires.
        """
        target = detect_mode(fact_count, community_count)
        previous = self.mode

        if target == self.mode:
            # Stable — clear any pending candidate.
            self.candidate = None
            self.candidate_since = None
            return ModeTransition(previous, self.mode, False)

        # A different target — start or continue the sticky timer.
        if self.candidate != target:
            self.candidate = target
            self.candidate_since = now
            return ModeTransition(previous, self.mode, False)

        # Same candidate as before — has it persisted long enough?
        promoting = _rank(target) > _rank(self.mode)
        required = PROMOTE_STICKY_SECONDS if promoting else DEMOTE_STICKY_SECONDS
        elapsed = now - (self.candidate_since or now)
        if elapsed >= required:
            self.mode = target
            self.candidate = None
            self.candidate_since = None
            return ModeTransition(previous, self.mode, True)

        return ModeTransition(previous, self.mode, False)


def _rank(mode: ActivationMode) -> int:
    """Return the numeric rank of an activation mode for promotion comparison.

    Args:
        mode: Operating mode to rank.

    Returns:
        Integer rank where higher values represent more capable modes.
    """
    return {
        ActivationMode.ZERO_CKF: 0,
        ActivationMode.PARTIAL_CKF: 1,
        ActivationMode.FULL_CKF: 2,
    }[mode]


@dataclass
class ModeTransition:
    """Result of a :meth:`ModeState.update` call.

    Attributes:
        previous: Mode before the update.
        current: Mode after the update.
        transitioned: True if the sticky timer fired and the mode changed.
    """

    previous: ActivationMode
    current: ActivationMode
    transitioned: bool

    @property
    def headers(self) -> dict[str, str]:
        """CRP headers describing the mode and any transition.

        Returns:
            Dictionary containing ``CRP-Context-Mode`` and, when a transition
            occurred, ``CRP-Context-Mode-Transition``.
        """
        out = {"CRP-Context-Mode": self.current.value}
        if self.transitioned:
            out["CRP-Context-Mode-Transition"] = f"{self.previous.value} -> {self.current.value}"
        return out


@dataclass
class CoverageResult:
    """Per-call coverage outcome in Partial-CKF mode (CRP-SPEC-017 §7).

    Attributes:
        coverage: Ratio of retrieved facts to expected facts needed.
        effective_mode: Mode implied by the coverage level.
        tier_cap: Quality-tier cap to apply, or None if no cap.
        reason: Human-readable reason for a cache miss, or None.
    """

    coverage: float
    effective_mode: ActivationMode
    tier_cap: str | None = None
    reason: str | None = None

    @property
    def headers(self) -> dict[str, str]:
        """CRP headers describing coverage and any tier cap.

        Returns:
            Dictionary containing ``CRP-Context-Coverage`` and, when
            applicable, ``CRP-Context-Cache-Status``.
        """
        out: dict[str, str] = {}
        if self.tier_cap is not None:
            out["CRP-Context-Coverage"] = f"{self.coverage:.2f}; cap={self.tier_cap}"
        else:
            out["CRP-Context-Coverage"] = f"{self.coverage:.2f}"
        if self.reason:
            out["CRP-Context-Cache-Status"] = f"MISS; reason={self.reason}"
        return out


def assess_coverage(matching_facts: int, expected_facts_needed: int) -> CoverageResult:
    """Compute per-call coverage and the resulting tier cap (CRP-SPEC-017 §7.1).

    Args:
        matching_facts: Facts retrieved at relevance ≥ 0.60 for this query.
        expected_facts_needed: Estimated facts required to answer the query.

    Returns:
        A ``CoverageResult`` describing the coverage ratio, effective mode,
        and any quality-tier cap.
    """
    coverage = matching_facts / max(1, expected_facts_needed)
    coverage = min(1.0, coverage)

    if coverage == 0.0:
        return CoverageResult(0.0, ActivationMode.ZERO_CKF, reason="no-relevant-facts")
    if coverage < 0.30:
        return CoverageResult(coverage, ActivationMode.PARTIAL_CKF, tier_cap="B")
    if coverage < 0.60:
        return CoverageResult(coverage, ActivationMode.PARTIAL_CKF, tier_cap="A")
    return CoverageResult(coverage, ActivationMode.FULL_CKF)


# Quality tiers ordered best → worst, for cap application.
_TIER_ORDER = ["S", "A", "B", "C", "D"]


def apply_tier_cap(tier: str, cap: str | None) -> str:
    """Clamp *tier* so it is no better than *cap* (None = no cap).

    Args:
        tier: Proposed quality tier.
        cap: Maximum allowed tier, or None to allow any tier.

    Returns:
        The original tier if it is no better than *cap*, otherwise *cap*.
        Unknown tiers fall back to the original tier.
    """
    if cap is None:
        return tier
    try:
        return tier if _TIER_ORDER.index(tier) >= _TIER_ORDER.index(cap) else cap
    except ValueError:
        return tier


@dataclass
class PartialModeCaps:
    """Partial-CKF mode default caps (CRP-SPEC-017 §2.2).

    Attributes:
        max_tier: Maximum quality tier allowed while in Partial-CKF mode.
        feature_milestones: Optional mapping of fact-count milestones to
            unlocked feature identifiers.
    """

    #: Quality tier is capped at B until the tenant reaches Full-CKF.
    max_tier: str = "B"
    feature_milestones: dict[int, str] = field(default_factory=dict)
