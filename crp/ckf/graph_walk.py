# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CKF Mode 1: Graph walk — BFS traversal from seed facts (§3.8).

``graph_walk(seed_facts, max_hops=2)`` returns a ranked list of facts
reachable within *max_hops* of the seed set, ordered by proximity.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from crp.extraction.types import Fact, FactGraph

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class GraphWalkResult:
    """Result of a graph walk query."""

    facts: list[Fact] = field(default_factory=list)
    distances: dict[str, int] = field(default_factory=dict)
    visited_count: int = 0


# ---------------------------------------------------------------------------
# BFS graph walk
# ---------------------------------------------------------------------------


def graph_walk(
    graph: FactGraph,
    seed_ids: set[str],
    max_hops: int = 2,
    max_results: int = 200,
) -> GraphWalkResult:
    """BFS walk from *seed_ids* up to *max_hops*.

    Returns facts ordered by hop distance (closer first), then by confidence.
    Seed facts themselves are included at distance 0.
    """
    if not seed_ids or not graph.nodes:
        return GraphWalkResult()

    # Build adjacency index for O(1) neighbour lookup
    adj: dict[str, set[str]] = {}
    for edge in graph.edges:
        adj.setdefault(edge.source_id, set()).add(edge.target_id)
        adj.setdefault(edge.target_id, set()).add(edge.source_id)

    distances: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque()

    # Seed nodes
    for sid in seed_ids:
        if sid in graph.nodes:
            distances[sid] = 0
            queue.append((sid, 0))

    # BFS
    while queue:
        node_id, dist = queue.popleft()
        if dist >= max_hops:
            continue
        for neighbour in adj.get(node_id, set()):
            if neighbour not in distances and neighbour in graph.nodes:
                distances[neighbour] = dist + 1
                queue.append((neighbour, dist + 1))

    # Collect and rank: sort by distance asc, then confidence desc
    ranked: list[tuple[int, float, str]] = []
    for fid, dist in distances.items():
        fact = graph.nodes.get(fid)
        if fact:
            ranked.append((dist, -(fact.confidence or 0.0), fid))

    ranked.sort()
    facts = [graph.nodes[fid] for _, _, fid in ranked[:max_results]]
    return GraphWalkResult(
        facts=facts,
        distances={fid: distances[fid] for _, _, fid in ranked[:max_results]},
        visited_count=len(distances),
    )
