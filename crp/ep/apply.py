# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Wire epistemic signals into tier/risk/positioning (CRP-SPEC-055 §7.3.3)."""

from __future__ import annotations

from typing import Any

from crp.ep.calibration import CalibrationProfile

_TIER_RANK: dict[str, int] = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}
_RISK_RANK: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _cap(tier: str, ceiling: str) -> str:
    """Cap a tier at ``ceiling``."""
    if _TIER_RANK.get(tier, 0) > _TIER_RANK.get(ceiling, 0):
        return ceiling
    return tier


def _raise_risk(risk: str) -> str:
    """Raise risk one step."""
    rank = _RISK_RANK.get(risk, 0)
    for r, i in _RISK_RANK.items():
        if i == min(rank + 1, 3):
            return r
    return risk


def epistemic_adjust(
    base_tier: str,
    risk: str,
    entropy: float,
    profile: CalibrationProfile | None = None,
) -> dict[str, Any]:
    """Adjust tier/risk/positioning using epistemic signals.

    Args:
        base_tier: Starting quality tier (S/A/B/C/D).
        risk: Starting risk level.
        entropy: Normalised semantic entropy in [0, 1].
        profile: Optional calibration profile for the model/task.

    Returns:
        Dict with adjusted ``tier``, ``risk``, and optional ``positioning_hint``.
    """
    out: dict[str, Any] = {
        "tier": base_tier,
        "risk": risk,
        "positioning_hint": None,
        "entropy": entropy,
    }
    if entropy > 0.6:
        out["risk"] = _raise_risk(out["risk"])
        out["tier"] = _cap(out["tier"], "B")
    if profile is not None and profile.overconfident_on():
        out["positioning_hint"] = (
            f"{profile.model_id} is overconfident on {profile.task_kind}; "
            "apply stricter grounding thresholds"
        )
        out["risk"] = _raise_risk(out["risk"])
    return out
