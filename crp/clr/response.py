# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Structured clarification response (CRP-SPEC-053 §5.3.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Interpretation:
    """One candidate reading of an ambiguous turn."""

    reading: str            # plain-language paraphrase
    operations: list[str]   # what the agent would do under this reading
    probability: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "reading": self.reading,
            "operations": list(self.operations),
            "probability": self.probability,
        }


@dataclass
class ClarificationRequired:
    """Typed ``CRP-Clarification-Required`` response."""

    kind: str = "CRP-Clarification-Required"
    reason: str = ""
    interpretations: list[Interpretation] = field(default_factory=list)
    default: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "reason": self.reason,
            "interpretations": [i.to_dict() for i in self.interpretations],
            "default": self.default,
        }


def build_clarification(
    candidates: list[Interpretation], reason: str = "ambiguous-target"
) -> ClarificationRequired:
    """Sort candidates and choose a safe default (or none).

    A default is only offered when the top reading clearly dominates the next,
    so HIGH-risk actions are not executed on a guessed default.
    """
    sorted_candidates = sorted(candidates, key=lambda c: -c.probability)
    default: int | None = None
    if len(sorted_candidates) >= 2:
        gap = sorted_candidates[0].probability - sorted_candidates[1].probability
        if gap > 0.25:
            default = 0
    return ClarificationRequired(
        reason=reason,
        interpretations=sorted_candidates,
        default=default,
    )
