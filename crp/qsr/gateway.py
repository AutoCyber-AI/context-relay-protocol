# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Gateway integration for the Quality-Tier-Supervised Router (SPEC-050).

When a request asks for learned model selection (``model: crp-learned`` or the
``crp-model-selection: learned`` header), this module builds a ``RoutingTask``
from the request and uses ``LearnedRouter`` to pick a concrete model_id.  The
Gateway then dispatches to that model through the normal provider router.
"""

from __future__ import annotations

from typing import Any

from crp.qsr.router import LearnedRouter, RoutingTask


def _schema_depth(tools: list[dict[str, Any]]) -> int:
    """Estimate the deepest JSON schema nesting among *tools*."""

    def _depth(obj: Any) -> int:
        if not isinstance(obj, dict):
            return 0
        props = obj.get("properties", {})
        if not props:
            return 0
        return 1 + max((_depth(v) for v in props.values()), default=0)

    return max((_depth(t.get("function", {}).get("parameters", {})) for t in tools), default=0)


def _estimate_tokens(messages: list[Any]) -> int:
    """Rough token estimate from message content."""
    total = 0
    for m in messages:
        content = getattr(m, "content", m.get("content", "")) if isinstance(m, dict) else getattr(m, "content", "")
        total += len(str(content).split())
    return total


def resolve_model(
    request: Any,
    headers: dict[str, str] | None = None,
    fleet: dict[str, Any] | None = None,
) -> str:
    """Return the concrete model_id to dispatch for *request*.

    If the request does not request learned routing, the existing
    ``request.model`` is returned unchanged.

    Args:
        request: A Gateway ``ChatRequest``.
        headers: Optional raw request headers (used to read ``crp-model-selection``).
        fleet: Optional custom fleet for ``LearnedRouter``.

    Returns:
        Model identifier string (may be unchanged).
    """
    model = getattr(request, "model", "")
    hdrs = headers or getattr(request, "_raw_headers", {}) or {}
    selection = (
        hdrs.get("crp-model-selection", "")
        or hdrs.get("CRP-Model-Selection", "")
    )
    if model != "crp-learned" and selection.lower() != "learned":
        return model

    task = RoutingTask(
        kind="prose",
        complexity="NARRATIVE",
        est_tokens=_estimate_tokens(getattr(request, "messages", [])),
        tool_count=len(getattr(request, "tools", [])),
        depth=getattr(request, "crp_depth", "standard"),
        schema_depth=_schema_depth(getattr(request, "tools", [])),
    )
    router = LearnedRouter(fleet=fleet)
    return router.route(task)
