# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Escalation ladder driven by observed failure signals (SPEC-050 §2.3.4).

Try the smallest/cheapest model first; climb the ladder only when the observed
quality tier or verification ratio falls below policy thresholds.  Escalation
is triggered by signals, not by a fixed retry count.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from crp.qsr.router import LearnedRouter, RoutingTask


def _tier_rank(tier: str) -> int:
    return {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}.get(tier.upper(), 0)


ESCALATION_LADDER = ["gemma3-4b", "qwen3-coder-7b", "cloud-large"]


def run_with_escalation(
    task: RoutingTask,
    execute_fn: Callable[[RoutingTask, str], dict[str, Any]],
    policy: dict[str, Any],
    router: LearnedRouter | None = None,
) -> dict[str, Any]:
    """Execute *task* with failure-driven escalation.

    Args:
        task: Routing task.
        execute_fn: ``fn(task, model_id) -> result_dict``.
        policy: Dict with keys ``escalate_on`` (``{"tier_below": "B",
            "vr_ratio_below": 0.9}``) and ``max_rungs``.
        router: Optional ``LearnedRouter``; a fresh one is created if omitted.

    Returns:
        The result dict from the final run, with an added ``escalated`` key.
    """
    router = router or LearnedRouter()
    first = router.route(task)
    ladder = [first] + [m for m in ESCALATION_LADDER if m != first]

    escalate_on = policy.get("escalate_on", {})
    tier_threshold = escalate_on.get("tier_below", "B")
    vr_threshold = escalate_on.get("vr_ratio_below", 0.9)
    max_rungs = policy.get("max_rungs", 2)

    result: dict[str, Any] = {}
    for rungs, model_id in enumerate(ladder):
        result = execute_fn(task, model_id)
        below_tier = _tier_rank(result.get("tier", "D")) < _tier_rank(tier_threshold)
        below_vr = result.get("vr_ratio", 1.0) < vr_threshold
        if not (below_tier or below_vr) or rungs >= max_rungs:
            result["escalated"] = rungs > 0
            return result

    result["escalated"] = True
    return result
