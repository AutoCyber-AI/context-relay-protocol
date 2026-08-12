# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CKF Mode 2: Pattern query — structured matching by entity/relation type (§3.8).

``pattern_query(graph, entity_type, relationship_type)`` filters facts
and edges by category and relation type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crp.extraction.types import Fact, FactEdge, FactGraph, RelationType

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class PatternQueryResult:
    """Result of a pattern query."""

    facts: list[Fact] = field(default_factory=list)
    edges: list[FactEdge] = field(default_factory=list)
    match_count: int = 0


# ---------------------------------------------------------------------------
# Pattern query
# ---------------------------------------------------------------------------


def pattern_query(
    graph: FactGraph,
    entity_type: str | None = None,
    relationship_type: str | RelationType | None = None,
    min_confidence: float = 0.0,
    max_results: int = 200,
    metadata_filter: dict[str, Any] | None = None,
) -> PatternQueryResult:
    """Structured query: filter facts by category and edges by relation type.

    Parameters
    ----------
    graph : FactGraph
    entity_type : str | None
        Filter facts whose ``category`` matches (case-insensitive).
    relationship_type : str | RelationType | None
        Filter edges whose ``relation_type`` matches.
    min_confidence : float
        Minimum confidence threshold for both facts and edges.
    max_results : int
        Cap on returned facts.
    metadata_filter : dict | None
        Key-value pairs that must all appear in ``fact.metadata``.
    """
    # Normalise relationship type for comparison
    rel_str: str | None = None
    if relationship_type is not None:
        rel_str = (
            relationship_type.value
            if isinstance(relationship_type, RelationType)
            else str(relationship_type)
        ).upper()

    ent_upper = entity_type.upper() if entity_type else None

    # --- Filter edges first (to collect connected fact IDs) ---
    matched_edges: list[FactEdge] = []
    edge_fact_ids: set[str] = set()

    if rel_str is not None:
        for edge in graph.edges:
            edge_rel = edge.relation_type
            if isinstance(edge_rel, RelationType):
                edge_rel = edge_rel.value
            if str(edge_rel).upper() == rel_str and edge.confidence >= min_confidence:
                matched_edges.append(edge)
                edge_fact_ids.add(edge.source_id)
                edge_fact_ids.add(edge.target_id)

    # --- Filter facts ---
    matched_facts: list[Fact] = []
    for fact in graph.nodes.values():
        # Confidence gate
        if fact.confidence < min_confidence:
            continue
        # Skip superseded
        if fact.superseded_by is not None:
            continue

        include = True

        # Category filter
        if ent_upper is not None and fact.category.upper() != ent_upper:
            include = False

        # Metadata filter
        if metadata_filter:
            for k, v in metadata_filter.items():
                if fact.metadata.get(k) != v:
                    include = False
                    break

        # If relationship filter given, fact must be connected by matching edge
        if rel_str is not None and fact.id not in edge_fact_ids:
            include = False

        if include:
            matched_facts.append(fact)

    # Sort by confidence desc
    matched_facts.sort(key=lambda f: -(f.confidence or 0.0))
    matched_facts = matched_facts[:max_results]

    return PatternQueryResult(
        facts=matched_facts,
        edges=matched_edges,
        match_count=len(matched_facts),
    )
