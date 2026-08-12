# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""DPE stage selection for Zero-CKF mode (CRP-SPEC-017 §2.1, §5.1).

In Zero-CKF mode there is no envelope to ground against, so some DPE stages run
in limited mode or are skipped entirely.  :func:`zero_ckf_stage_plan` returns
the stage execution plan so the pipeline can skip work that cannot produce a
meaningful result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .mode import ActivationMode


class StageMode(str, Enum):
    """How a DPE stage executes under the current activation mode."""

    FULL = "full"
    LIMITED = "limited"
    SKIPPED = "skipped"


# DPE stage numbers (CRP-SPEC-005) → labels, for readable plans.
_STAGE_LABELS: dict[int, str] = {
    1: "claim-segmentation",
    2: "attribution",
    3: "fidelity",
    4: "entailment",
    5: "hallucination-risk",
    6: "cross-window-coherence",
    7: "repetition",
    8: "completeness",
    9: "flow",
    10: "omission",
    11: "pii",
    12: "regulatory-classification",
    13: "provenance-hmac",
}


@dataclass
class StagePlan:
    """The execution plan for the 13 DPE stages under an activation mode."""

    mode: ActivationMode
    stages: dict[int, StageMode]
    force_grounding_mode: str | None = None

    def label(self, stage: int) -> str:
        """Return the human-readable label for a DPE stage number."""
        return _STAGE_LABELS.get(stage, f"stage-{stage}")

    def runs(self, stage: int) -> bool:
        """Return True if the stage is not marked as SKIPPED."""
        return self.stages.get(stage, StageMode.FULL) != StageMode.SKIPPED


def full_stage_plan(mode: ActivationMode = ActivationMode.FULL_CKF) -> StagePlan:
    """All 13 stages run fully (Partial/Full-CKF default)."""
    return StagePlan(mode=mode, stages={i: StageMode.FULL for i in range(1, 14)})


def zero_ckf_stage_plan() -> StagePlan:
    """The Zero-CKF stage plan (CRP-SPEC-017 §2.1).

    Stages 1, 2, 5, 6, 7, 8, 9, 11, 12, 13 run normally; Stage 3 (fidelity) is
    limited to common-knowledge fabrication detection; Stage 4 (entailment)
    runs against the query rather than the empty envelope; Stage 10 (omission)
    is skipped.  Grounding mode is forced to ``parametric-only``.
    """
    stages = {i: StageMode.FULL for i in range(1, 14)}
    stages[3] = StageMode.LIMITED   # fabrication-only; distortion needs sources
    stages[4] = StageMode.LIMITED   # entailment vs. query consistency
    stages[10] = StageMode.SKIPPED  # no envelope facts to compare against
    return StagePlan(
        mode=ActivationMode.ZERO_CKF,
        stages=stages,
        force_grounding_mode="parametric-only",
    )


def stage_plan_for(mode: ActivationMode) -> StagePlan:
    """Return the DPE stage plan appropriate for *mode*."""
    if mode == ActivationMode.ZERO_CKF:
        return zero_ckf_stage_plan()
    return full_stage_plan(mode)
