# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Learned, capability-aware router with cold-start fallback (SPEC-050 §2.3.3).

Trains a small classifier on ``RoutingExample``

Args:
    task: The routing task.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from crp.qsr.harvest import RoutingExample
from crp.qsr.profiles import FLEET, CapabilityProfile

logger = logging.getLogger(__name__)


try:
    from sklearn.ensemble import GradientBoostingClassifier  # type: ignore[import]

    _HAS_SKLEARN = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_SKLEARN = False


@dataclass
class RoutingTask:
    """Task description used as router input."""

    kind: str = "prose"
    complexity: str = "NARRATIVE"
    est_tokens: int = 0
    tool_count: int = 0
    depth: str = "standard"
    schema_depth: int = 0


class LearnedRouter:
    """Route tasks to the model most likely to hit tier A/S at least cost.

    Args:
        fleet: Mapping of model_id → ``CapabilityProfile``.  Defaults to
            ``FLEET``.
        min_train_examples: Minimum tier-A/S examples required before the
            learned model is used.  Defaults to 200 (SPEC-050 §2.5).
    """

    def __init__(
        self,
        fleet: dict[str, CapabilityProfile] | None = None,
        min_train_examples: int = 200,
    ):
        self.fleet = fleet if fleet is not None else FLEET
        self._models = list(self.fleet.keys())
        self._clf: Any | None = None
        self._min_train_examples = min_train_examples

    # ------------------------------------------------------------------
    # Feature encoding
    # ------------------------------------------------------------------
    _KINDS = ["code", "math", "prose", "extract"]
    _COMPLEXITY = {"ENTITY_RICH": 0, "REASONING_DENSE": 1, "NARRATIVE": 2}
    _DEPTH = {"quick": 0, "standard": 1, "thorough": 2, "exhaustive": 3}

    def _featurize(self, task: RoutingTask) -> list[float]:
        """Encode a task as a numeric feature vector."""
        kind_bits = [1.0 if task.kind == k else 0.0 for k in self._KINDS]
        complexity = self._COMPLEXITY.get(task.complexity, 0)
        depth = self._DEPTH.get(task.depth, 1)
        return [
            *kind_bits,
            float(complexity),
            task.est_tokens / 1000.0,
            float(task.tool_count),
            float(depth),
            float(task.schema_depth),
        ]

    def _featurize_ex(self, example: RoutingExample) -> list[float]:
        """Encode a training example as a feature vector."""
        return self._featurize(
            RoutingTask(
                kind=example.task_kind,
                complexity=example.complexity,
                est_tokens=example.est_tokens,
                tool_count=example.tool_count,
                depth=example.depth,
                schema_depth=example.schema_depth,
            )
        )

    # ------------------------------------------------------------------
    # Training / routing
    # ------------------------------------------------------------------
    def train(self, examples: list[RoutingExample]) -> bool:
        """Train the classifier on tier-A/S examples.

        Returns:
            True if training succeeded and the router will use the learned model.
        """
        if not _HAS_SKLEARN:
            logger.debug("sklearn not installed; router remains in cold-start mode")
            return False

        good = [e for e in examples if e.quality_tier in ("S", "A")]
        if len(good) < self._min_train_examples:
            logger.debug(
                "Only %d tier-A/S examples (< %d); staying in cold-start mode",
                len(good),
                self._min_train_examples,
            )
            return False

        X = [self._featurize_ex(e) for e in good]
        y = [self._models.index(e.model_id) for e in good]
        if any(idx < 0 or idx >= len(self._models) for idx in y):
            raise ValueError("example refers to a model_id not in the fleet")

        self._clf = GradientBoostingClassifier(max_depth=3)
        self._clf.fit(X, y)
        return True

    def route(self, task: RoutingTask) -> str:
        """Pick the best model for *task*.

        Capability-aware pre-filtering excludes models whose
        ``schema_complexity_ceiling`` is below the task's schema depth.  If a
        learned model is available it is used; otherwise the fleet profile with
        the highest competence for the task kind wins.
        """
        eligible = [
            m
            for m, p in self.fleet.items()
            if p.schema_complexity_ceiling >= task.schema_depth
        ]
        if not eligible:
            # No model can handle the schema depth; fall back to the largest ceiling.
            eligible = [
                max(self.fleet, key=lambda m: self.fleet[m].schema_complexity_ceiling)
            ]

        if self._clf is not None:
            try:
                probs = self._clf.predict_proba([self._featurize(task)])[0]
                ranked = sorted(zip(self._models, probs), key=lambda t: -t[1])
                for model_id, _ in ranked:
                    if model_id in eligible:
                        return model_id
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Learned routing failed: %s", exc)

        return max(eligible, key=lambda m: self.fleet[m].score_for(task.kind))
