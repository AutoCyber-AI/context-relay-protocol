# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Per-model capability profiles for heterogeneous local-SLM fleets (SPEC-050 §2.3.2).

Profiles are benchmark-derived (SQB, SPEC-026) and drive cold-start routing as
well as eligibility filtering for the learned router.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CapabilityProfile:
    """Capability profile for a single model in the fleet."""

    model_id: str
    competence: dict[str, float] = field(default_factory=dict)
    ctx_window: int = 8192
    schema_complexity_ceiling: int = 3
    tokens_per_sec: float = 40.0
    cost_per_1k: float = 0.0

    def score_for(self, task_kind: str) -> float:
        """Return measured competence for *task_kind* (defaults to 0.5)."""
        return self.competence.get(task_kind, 0.5)


# A sample fleet used for cold-start routing when no custom fleet is supplied.
# Real deployments override this with profiles derived from sealed SQB runs.
FLEET: dict[str, CapabilityProfile] = {
    "qwen3-coder-7b": CapabilityProfile(
        "qwen3-coder-7b",
        competence={"code": 0.86, "math": 0.63, "prose": 0.55, "extract": 0.60},
        ctx_window=32768,
        schema_complexity_ceiling=5,
        tokens_per_sec=55.0,
    ),
    "phi4-math-4b": CapabilityProfile(
        "phi4-math-4b",
        competence={"code": 0.58, "math": 0.84, "prose": 0.60, "extract": 0.65},
        schema_complexity_ceiling=3,
        tokens_per_sec=75.0,
    ),
    "gemma3-4b": CapabilityProfile(
        "gemma3-4b",
        competence={"code": 0.52, "math": 0.55, "prose": 0.81, "extract": 0.58},
        schema_complexity_ceiling=2,
        tokens_per_sec=90.0,
    ),
}


def register_profile(model_id: str, profile: CapabilityProfile) -> None:
    """Add or replace a profile in the default fleet."""
    FLEET[model_id] = profile
