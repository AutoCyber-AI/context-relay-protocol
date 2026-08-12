# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Harvest router training examples from the audit chain (SPEC-050 §2.3.1).

Each completed dispatch already writes an audit record (SPEC-011).  The QSR
projects those records into ``RoutingExample`` tuples — the free supervision
signal that drives the learned router.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RoutingExample:
    """A single labelled routing decision."""

    # Features (known before dispatch)
    task_kind: str
    complexity: str
    est_tokens: int
    tool_count: int
    depth: str
    schema_depth: int = 0

    schema_depth: int = 0

    # Decision
    model_id: str = ""

    # Labels (observed after dispatch)
    quality_tier: str = ""
    vr_ratio: float = 1.0
    escalated: bool = False
    latency_ms: int = 0
    cost: float = 0.0


def harvest(audit_records: list[dict[str, Any]]) -> list[RoutingExample]:
    """Build ``RoutingExample``

    Args:
        audit_records: Audit records from SPEC-011.

    Returns:
        Filtered list of routing examples derived from ``dispatch_complete`` records.
    """
    out: list[RoutingExample] = []
    for r in audit_records:
        if r.get("stage") != "dispatch_complete":
            continue
        task = r.get("task", {})
        decision = r.get("decision", {})
        result = r.get("result", {})
        out.append(
            RoutingExample(
                task_kind=task.get("kind", "unknown"),
                complexity=task.get("complexity", "NARRATIVE"),
                est_tokens=task.get("est_tokens", 0),
                tool_count=len(task.get("tools", [])),
                depth=task.get("depth", "standard"),
                schema_depth=task.get("schema_depth", 0),
                model_id=decision.get("model_id", "unknown"),
                quality_tier=result.get("tier", "D"),
                vr_ratio=result.get("vr_ratio", 1.0),
                escalated=result.get("escalated", False),
                latency_ms=result.get("latency_ms", 0),
                cost=result.get("cost", 0.0),
            )
        )
    return out
