# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Causal edge support for the CKF (SPEC-051 §3.3.3).

Adds ``causes`` / ``enables`` / ``prevents`` edge types to a fact graph and
provides counterfactual (causal-upstream) retrieval.  The implementation is
graph-agnostic: it operates on any object exposing ``add_fact``/``add_edge``
and ``edges_to`` methods, such as ``crp.extraction.types.FactGraph``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class CausalEdge(str, Enum):
    """Causal edge kinds."""

    CAUSES = "causes"
    ENABLES = "enables"
    PREVENTS = "prevents"


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def add_causal_edge(
    graph: Any,
    src: Any,
    dst: Any,
    kind: CausalEdge,
    textual_conf: float,
    interventional_support: int = 0,
) -> None:
    """Add a causal edge between facts.

    Args:
        graph: Fact graph with ``add_fact`` and ``add_edge`` methods.
        src: Source fact (or fact id).
        dst: Target fact (or fact id).
        kind: Causal edge kind.
        textual_conf: Confidence from textual extraction (reported causality).
        interventional_support: Number of action-log transitions that support
            the edge (verified causal evidence).
    """
    try:
        from crp.extraction.types import Fact, FactEdge
    except Exception:  # pragma: no cover - defensive
        return

    src_id = src.id if hasattr(src, "id") else src
    dst_id = dst.id if hasattr(dst, "id") else dst

    # Ensure nodes exist.
    if hasattr(graph, "add_fact"):
        for node in (src, dst):
            if hasattr(graph, "nodes") and (node if isinstance(node, str) else node.id) not in graph.nodes:
                if isinstance(node, Fact):
                    graph.add_fact(node)

    conf = _clamp(textual_conf + 0.05 * interventional_support)
    edge = FactEdge(
        source_id=src_id,
        target_id=dst_id,
        relation_type=kind.value,
        confidence=conf,
        metadata={
            "textual": textual_conf,
            "interventional": interventional_support,
            "edge_kind": kind.value,
        },
    )
    graph.add_edge(edge)


def causal_upstream(
    graph: Any,
    node: Any,
    max_depth: int = 3,
    kinds: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return causal upstream nodes for *node* up to *max_depth* hops.

    Args:
        graph: Fact graph with ``edges_to`` method.
        node: Target fact or fact id.
        max_depth: Maximum traversal depth.
        kinds: Edge relation types to follow (defaults to ``causes`` and
            ``enables``).

    Returns:
        List of edge dicts: ``cause``, ``effect``, ``kind``, ``conf``.
    """
    if kinds is None:
        kinds = {CausalEdge.CAUSES.value, CausalEdge.ENABLES.value}
    node_id = node if isinstance(node, str) else node.id
    frontier: list[tuple[str, int]] = [(node_id, 0)]
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    edges_to = getattr(graph, "edges_to", None)
    if edges_to is None:
        return out

    while frontier:
        n, d = frontier.pop()
        if n in seen or d > max_depth:
            continue
        seen.add(n)
        for edge in edges_to(n):
            relation = getattr(edge, "relation_type", "")
            if relation not in kinds:
                continue
            src = getattr(edge, "source_id", "")
            conf = getattr(edge, "confidence", 0.0)
            out.append({"cause": src, "effect": n, "kind": relation, "conf": conf})
            frontier.append((src, d + 1))
    return out
