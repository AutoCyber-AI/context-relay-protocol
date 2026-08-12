# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Symbolic world model for predictive positioning (SPEC-051 §3.3.2).

Given a proposed action and current state, predicts the outcome by matching
against induced rules.  The model is intentionally rule-first and
gradient-free: rules are inspectable, sample-efficient, and cheap to update
as the action log grows.
"""

from __future__ import annotations

from typing import Any

from crp.pp.induction import Rule


class WorldModel:
    """Predict outcomes from induced transition rules."""

    def __init__(self, rules: list[Rule]) -> None:
        """Index *rules* by action for fast lookup."""
        self._by_action: dict[str, list[Rule]] = {}
        for rule in rules:
            self._by_action.setdefault(rule.action, []).append(rule)

    def predict(self, state: dict[str, Any], action: str) -> dict[str, Any] | None:
        """Return the best predicted outcome for *action* in *state*.

        Returns:
            A dict with keys ``predicted``, ``confidence``, ``support``,
            ``source`` when a rule matches; ``None`` otherwise.
        """
        best: Rule | None = None
        for rule in self._by_action.get(action, []):
            if all(state.get(k) == v for k, v in rule.condition.items()):
                if best is None or rule.confidence > best.confidence:
                    best = rule
        if best is None:
            return None
        return {
            "predicted": best.predicts,
            "confidence": best.confidence,
            "support": best.support,
            "source": "symbolic_rule",
        }
