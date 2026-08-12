# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Per-model, per-task calibration curves (CRP-SPEC-055 §7.3.2)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CalibrationProfile:
    """Reliability curve for one (model, task-kind) pair."""

    model_id: str
    task_kind: str
    bins: dict[float, list[int]] = field(
        default_factory=lambda: defaultdict(lambda: [0, 0])
    )

    def observe(self, confidence: float, correct: bool) -> None:
        """Record one verified outcome."""
        b = round(float(confidence), 1)
        self.bins[b][1] += 1
        if correct:
            self.bins[b][0] += 1

    def expected_calibration_error(self) -> float:
        """Return ECE — average gap between confidence and empirical accuracy."""
        total = sum(t for _, t in self.bins.values())
        if not total:
            return 0.0
        ece = 0.0
        for conf, (correct, n) in self.bins.items():
            if n:
                acc = correct / n
                ece += (n / total) * abs(acc - conf)
        return round(ece, 3)

    def overconfident_on(self, threshold: float = 0.15) -> bool:
        """True when the model is systematically overconfident."""
        return self.expected_calibration_error() >= threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "task_kind": self.task_kind,
            "bins": {str(k): v for k, v in self.bins.items()},
            "ece": self.expected_calibration_error(),
        }
