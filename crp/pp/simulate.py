# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Simulation-before-action gating for HIGH-risk operations (SPEC-051 §3.3.4).

Predicts the outcome of a proposed action using a world model; if the
prediction violates policy with sufficient confidence, the action is blocked
and a checkpoint is returned instead.  This turns reactive oversight into
anticipatory oversight.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from crp.pp.world_model import WorldModel


@dataclass
class SimulationResult:
    """Outcome of a guarded-dispatch simulation."""

    allowed: bool
    prediction: dict[str, Any] | None
    reason: str
    executed: bool


def guarded_dispatch(
    state: dict[str, Any],
    action: str,
    risk: str,
    world: WorldModel,
    policy: Any,
    execute_fn: Callable[[dict[str, Any], str, dict[str, Any] | None], dict[str, Any]],
    checkpoint_fn: Callable[[str, dict[str, Any] | None, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Dispatch *action* after optional simulation for HIGH-risk operations.

    Args:
        state: Current state features.
        action: Action to take.
        risk: Risk level string (e.g. ``LOW``, ``MEDIUM``, ``HIGH``).
        world: World model for outcome prediction.
        policy: Object with ``check_predicted_outcome(predicted)`` and
            ``sim_confidence_floor`` attributes.
        execute_fn: ``fn(state, action, prediction) -> result``.
        checkpoint_fn: ``fn(reason, prediction, state) -> result``.

    Returns:
        The result of execution or checkpoint.
    """
    prediction: dict[str, Any] | None = None
    simulate_levels = getattr(policy, "simulate_risk_levels", {"HIGH"})
    if risk in simulate_levels:
        prediction = world.predict(state, action)
        if prediction is not None:
            violation = None
            checker = getattr(policy, "check_predicted_outcome", None)
            if callable(checker):
                violation = checker(prediction["predicted"])
            floor = getattr(policy, "sim_confidence_floor", 0.75)
            if violation and prediction["confidence"] >= floor:
                reason = (
                    f"predicted {violation} "
                    f"(conf {prediction['confidence']}, n={prediction['support']})"
                )
                return {
                    **checkpoint_fn(reason, prediction, state),
                    "_simulation": SimulationResult(
                        allowed=False,
                        prediction=prediction,
                        reason=reason,
                        executed=False,
                    ).__dict__,
                }

    return {
        **execute_fn(state, action, prediction),
        "_simulation": SimulationResult(
            allowed=True,
            prediction=prediction,
            reason="",
            executed=True,
        ).__dict__,
    }
