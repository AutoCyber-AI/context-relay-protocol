# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CKF Mode 4: Community detection — Leiden cluster summaries (§3.8).

Batch community detection per window.  Incremental update for <10% change,
full rebuild for ≥30%.  Falls back to connected components when leidenalg
is unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from crp.extraction.types import FactGraph

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency check
# ---------------------------------------------------------------------------

_IGRAPH: Any = None
_LEIDENALG: Any = None
_CHECKED = False


def _check_leiden() -> bool:
    """Return True if igraph + leidenalg are available."""
    global _IGRAPH, _LEIDENALG, _CHECKED  # noqa: PLW0603
    if not _CHECKED:
        try:
            import igraph  # type: ignore[import-untyped]
            import leidenalg  # type: ignore[import-untyped]

            _IGRAPH = igraph
            _LEIDENALG = leidenalg
        except ImportError:
            _IGRAPH = None
            _LEIDENALG = None
        _CHECKED = True
    return _IGRAPH is not None and _LEIDENALG is not None


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Community:
    """A cluster of semantically related facts."""

    community_id: int
    fact_ids: list[str] = field(default_factory=list)
    summary: str = ""
    centroid_id: str = ""
    coherence: float = 0.0

    @property
    def size(self) -> int:
        """Return the current size count."""
        return len(self.fact_ids)


@dataclass
class CommunityResult:
    """Result from community detection."""

    communities: list[Community] = field(default_factory=list)
    fact_to_community: dict[str, int] = field(default_factory=dict)
    used_leiden: bool = False
    modularity: float = 0.0


# ---------------------------------------------------------------------------
# Leiden detection (full)
# ---------------------------------------------------------------------------


def _leiden_detect(graph: FactGraph) -> CommunityResult:
    """Full Leiden community detection using igraph + leidenalg."""
    if not graph.nodes:
        return CommunityResult()

    ig = _IGRAPH
    la = _LEIDENALG

    # Build igraph graph
    node_ids = list(graph.nodes.keys())
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}

    g = ig.Graph(n=len(node_ids), directed=False)
    edge_list = []
    for edge in graph.edges:
        src = id_to_idx.get(edge.source_id)
        tgt = id_to_idx.get(edge.target_id)
        if src is not None and tgt is not None and src != tgt:
            edge_list.append((src, tgt))
    if edge_list:
        g.add_edges(edge_list)

    # Run Leiden
    partition = la.find_partition(g, la.ModularityVertexPartition)

    # Build communities
    communities: dict[int, list[str]] = {}
    fact_to_community: dict[str, int] = {}

    for idx, comm_id in enumerate(partition.membership):
        fid = node_ids[idx]
        communities.setdefault(comm_id, []).append(fid)
        fact_to_community[fid] = comm_id

    result_communities = []
    for cid, fids in sorted(communities.items()):
        centroid = _pick_centroid(graph, fids)
        summary = _summarize_community(graph, fids)
        result_communities.append(
            Community(
                community_id=cid,
                fact_ids=fids,
                summary=summary,
                centroid_id=centroid,
            )
        )

    return CommunityResult(
        communities=result_communities,
        fact_to_community=fact_to_community,
        used_leiden=True,
        modularity=partition.modularity,
    )


# ---------------------------------------------------------------------------
# Fallback: connected components
# ---------------------------------------------------------------------------


def _connected_components_detect(graph: FactGraph) -> CommunityResult:
    """Fallback community detection using BFS connected components."""
    if not graph.nodes:
        return CommunityResult()

    # Build adjacency
    adj: dict[str, set[str]] = {nid: set() for nid in graph.nodes}
    for edge in graph.edges:
        if edge.source_id in adj and edge.target_id in adj:
            adj[edge.source_id].add(edge.target_id)
            adj[edge.target_id].add(edge.source_id)

    visited: set[str] = set()
    communities: list[Community] = []
    fact_to_community: dict[str, int] = {}
    comm_id = 0

    for start in graph.nodes:
        if start in visited:
            continue
        # BFS
        component: list[str] = []
        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neighbour in adj.get(node, set()):
                if neighbour not in visited:
                    queue.append(neighbour)

        centroid = _pick_centroid(graph, component)
        summary = _summarize_community(graph, component)
        for fid in component:
            fact_to_community[fid] = comm_id
        communities.append(
            Community(
                community_id=comm_id,
                fact_ids=component,
                summary=summary,
                centroid_id=centroid,
            )
        )
        comm_id += 1

    return CommunityResult(
        communities=communities,
        fact_to_community=fact_to_community,
        used_leiden=False,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick_centroid(graph: FactGraph, fact_ids: list[str]) -> str:
    """Pick the fact with highest confidence as community centroid."""
    best_id = ""
    best_conf = -1.0
    for fid in fact_ids:
        fact = graph.nodes.get(fid)
        if fact and (fact.confidence or 0.0) > best_conf:
            best_conf = fact.confidence or 0.0
            best_id = fid
    return best_id


def _summarize_community(graph: FactGraph, fact_ids: list[str]) -> str:
    """Build a short summary from the top-3 facts by confidence."""
    facts = []
    for fid in fact_ids:
        fact = graph.nodes.get(fid)
        if fact:
            facts.append(fact)
    facts.sort(key=lambda f: -(f.confidence or 0.0))
    top = facts[:3]
    if not top:
        return ""
    return "; ".join(f.text for f in top if f.text)


# ---------------------------------------------------------------------------
# Incremental update manager
# ---------------------------------------------------------------------------

# Thresholds for incremental vs full rebuild
INCREMENTAL_THRESHOLD = 0.10  # <10% change → incremental
FULL_REBUILD_THRESHOLD = 0.30  # ≥30% change → full rebuild


class CommunityDetector:
    """Manages community detection with incremental updates.

    Tracks the previous community state and decides whether to run
    a full rebuild or incremental update based on the change ratio.
    """

    def __init__(self) -> None:
        self._last_result: CommunityResult | None = None
        self._last_node_count: int = 0
        self._last_edge_count: int = 0

    def detect(self, graph: FactGraph) -> CommunityResult:
        """Run community detection, choosing strategy based on change ratio."""
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)

        if self._last_result is None:
            # First run — always full
            result = self._full_detect(graph)
        else:
            change_ratio = self._compute_change_ratio(node_count, edge_count)
            if change_ratio >= FULL_REBUILD_THRESHOLD:
                result = self._full_detect(graph)
            elif change_ratio < INCREMENTAL_THRESHOLD:
                # Very small change — reuse previous result with minor updates
                result = self._incremental_update(graph)
            else:
                # Between thresholds — full rebuild
                result = self._full_detect(graph)

        self._last_result = result
        self._last_node_count = node_count
        self._last_edge_count = edge_count
        return result

    def _compute_change_ratio(self, node_count: int, edge_count: int) -> float:
        """Compute approximate change ratio since last detection."""
        if self._last_node_count == 0:
            return 1.0
        node_delta = abs(node_count - self._last_node_count)
        edge_delta = abs(edge_count - self._last_edge_count)
        return max(
            node_delta / max(self._last_node_count, 1),
            edge_delta / max(self._last_edge_count, 1),
        )

    def _full_detect(self, graph: FactGraph) -> CommunityResult:
        """Full detection — Leiden if available, else connected components."""
        if _check_leiden():
            try:
                return _leiden_detect(graph)
            except Exception:  # noqa: BLE001
                logger.warning("Leiden detection failed, falling back to connected components")
        return _connected_components_detect(graph)

    def _incremental_update(self, graph: FactGraph) -> CommunityResult:
        """Reuse previous communities, only assigning new nodes to nearest community."""
        if self._last_result is None:
            return self._full_detect(graph)

        prev = self._last_result
        new_nodes = set(graph.nodes.keys()) - set(prev.fact_to_community.keys())
        removed_nodes = set(prev.fact_to_community.keys()) - set(graph.nodes.keys())

        if not new_nodes and not removed_nodes:
            return prev

        # Copy existing assignments (removing deleted nodes)
        fact_to_comm = {
            fid: cid
            for fid, cid in prev.fact_to_community.items()
            if fid not in removed_nodes
        }

        # Assign new nodes to community of their best-connected neighbour
        for fid in new_nodes:
            # Find connected existing nodes
            neighbour_comms: dict[int, int] = {}
            for edge in graph.edges:
                peer = None
                if edge.source_id == fid and edge.target_id in fact_to_comm:
                    peer = edge.target_id
                elif edge.target_id == fid and edge.source_id in fact_to_comm:
                    peer = edge.source_id
                if peer:
                    cid = fact_to_comm[peer]
                    neighbour_comms[cid] = neighbour_comms.get(cid, 0) + 1

            if neighbour_comms:
                # Assign to most frequent community
                best_cid = max(neighbour_comms, key=lambda c: neighbour_comms[c])
                fact_to_comm[fid] = best_cid
            else:
                # Isolated new node — create a new community
                max_cid = max(fact_to_comm.values()) + 1 if fact_to_comm else 0
                fact_to_comm[fid] = max_cid

        # Rebuild community objects
        communities_dict: dict[int, list[str]] = {}
        for fid, cid in fact_to_comm.items():
            communities_dict.setdefault(cid, []).append(fid)

        communities = []
        for cid, fids in sorted(communities_dict.items()):
            centroid = _pick_centroid(graph, fids)
            summary = _summarize_community(graph, fids)
            communities.append(
                Community(
                    community_id=cid,
                    fact_ids=fids,
                    summary=summary,
                    centroid_id=centroid,
                )
            )

        return CommunityResult(
            communities=communities,
            fact_to_community=fact_to_comm,
            used_leiden=prev.used_leiden,
        )

    def community_summary(self, graph: FactGraph, topic: str) -> list[Community]:
        """Return communities matching *topic* (substring or keyword match)."""
        if self._last_result is None:
            self.detect(graph)
        if self._last_result is None:
            return []

        topic_lower = topic.lower()
        matched = []
        for comm in self._last_result.communities:
            # Check if topic appears in any fact text or summary
            if topic_lower in comm.summary.lower():
                matched.append(comm)
                continue
            for fid in comm.fact_ids:
                fact = graph.nodes.get(fid)
                if fact and topic_lower in fact.text.lower():
                    matched.append(comm)
                    break

        return matched
