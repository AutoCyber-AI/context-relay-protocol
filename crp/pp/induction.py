# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""World-model rule induction over the Tier-E action log (SPEC-051 §3.3.1).

Induces symbolic transition rules of the form ``(state_pattern, action) →
outcome_pattern`` from logged ``(pre_state, action, post_state)`` transitions.
Rules record support count and confidence so callers can decide whether a rule
is strong enough to gate an action.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


def _hashable(value: Any) -> Any:
    """Convert a value into a hashable form for counting."""
    if isinstance(value, (list, tuple)):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, dict):
        return frozenset((k, _hashable(v)) for k, v in value.items())
    return value


@dataclass
class Transition:
    """One observed action-outcome transition."""

    pre: dict[str, Any]
    action: str
    post: dict[str, Any]


@dataclass
class Rule:
    """An induced transition rule."""

    action: str
    condition: dict[str, Any]
    predicts: dict[str, Any]
    support: int = 0
    confidence: float = 0.0


def induce_rules(
    transitions: list[Transition],
    min_support: int = 2,
    min_conf: float = 0.8,
) -> list[Rule]:
    """Induce rules from *transitions*.

    Args:
        transitions: Observed transitions.
        min_support: Minimum number of transitions required for a rule.
        min_conf: Minimum fraction of transitions that must agree on an
            outcome feature for it to be included in the rule's prediction.

    Returns:
        A list of induced ``Rule`` objects.
    """
    buckets: dict[tuple[str, frozenset[tuple[str, Any]]], list[dict[str, Any]]] = defaultdict(list)
    originals: dict[tuple[str, frozenset[tuple[str, Any]]], dict[str, Any]] = {}
    for t in transitions:
        key = (t.action, frozenset((k, _hashable(v)) for k, v in t.pre.items()))
        originals.setdefault(key, t.pre)
        buckets[key].append(t.post)

    rules: list[Rule] = []
    for key, posts in buckets.items():
        action, _ = key
        if len(posts) < max(1, min_support):
            continue
        feature_counts: dict[tuple[str, Any], int] = defaultdict(int)
        value_by_key: dict[tuple[str, Any], Any] = {}
        for post in posts:
            for k, v in post.items():
                h = _hashable(v)
                feature_counts[(k, h)] += 1
                value_by_key[(k, h)] = v

        predicted = {
            k: value_by_key[(k, h)]
            for (k, h), c in feature_counts.items()
            if c / len(posts) >= min_conf
        }
        if not predicted:
            continue
        conf = min(
            feature_counts[(k, _hashable(v))] / len(posts) for k, v in predicted.items()
        )
        rules.append(
            Rule(
                action=action,
                condition=dict(originals[key]),
                predicts=predicted,
                support=len(posts),
                confidence=round(conf, 3),
            )
        )
    return rules
