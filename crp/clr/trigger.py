# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Clarification trigger (CRP-SPEC-053 §5.3.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Risk weight scales DOWN the threshold for reversible actions and UP for risky ones.
_DEFAULT_RISK_WEIGHT: dict[str, float] = {
    "LOW": 0.3,
    "MEDIUM": 0.7,
    "HIGH": 1.0,
    "CRITICAL": 1.0,
}


@dataclass
class ClarificationPolicy:
    """Policy knobs for the clarification protocol."""

    threshold: float = 0.4
    risk_weights: dict[str, float] | None = None

    @classmethod
    def from_obj(cls, obj: Any) -> ClarificationPolicy:
        """Coerce a policy object or dict into a ClarificationPolicy."""
        if isinstance(obj, ClarificationPolicy):
            return obj
        if isinstance(obj, dict):
            return cls(
                threshold=float(obj.get("clarification_threshold", 0.4)),
                risk_weights=obj.get("clarification_risk_weights"),
            )
        threshold = getattr(obj, "clarification_threshold", 0.4)
        weights = getattr(obj, "clarification_risk_weights", None)
        return cls(threshold=float(threshold), risk_weights=weights)


def should_clarify(
    intent_confidence: float,
    parse_divergence: float,
    risk: str,
    policy: ClarificationPolicy | Any | None = None,
) -> bool:
    """Decide whether to ask rather than guess.

    Args:
        intent_confidence: Classifier confidence in [0, 1].
        parse_divergence: Divergence among candidate interpretations in [0, 1].
        risk: Risk tier (LOW, MEDIUM, HIGH, CRITICAL).
        policy: Policy with ``clarification_threshold`` and optional weights.

    Returns:
        True when the protocol should emit a clarification response.
    """
    policy = ClarificationPolicy.from_obj(policy)
    ambiguity = (1.0 - float(intent_confidence)) * 0.5 + float(parse_divergence) * 0.5
    weights = policy.risk_weights or _DEFAULT_RISK_WEIGHT
    risk_weight = weights.get(risk, _DEFAULT_RISK_WEIGHT["MEDIUM"])
    return ambiguity * risk_weight >= policy.threshold
