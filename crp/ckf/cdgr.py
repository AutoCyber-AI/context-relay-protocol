# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Coverage-Differential Graph Retrieval (CDGR) — SPEC-025.

CDGR closes the gap that flat CDR leaves open: connector facts required for
multi-hop reasoning have low query similarity and are systematically invisible
to similarity-based retrieval.  CDGR seeds from CDR anchor facts, walks the
CKF graph to find connectors, and scores them by *bridge value* — how many
otherwise-disconnected anchor pairs they link.

Three-phase algorithm (SPEC-025 §2):
    Phase A — SEED:     CDR-ranked anchor facts (top 70% of budget)
    Phase B — EXPAND:   BFS walk ≤ MAX_HOPS hops to find connector candidates
    Phase C — ASSEMBLE: Score by bridge_value × novelty, pack seeds + bridges

The bridge_value function scores connectors by graph topology, not query
similarity — this is the key innovation (SPEC-025 §2.4).

Performance target: < 2 ms per call (SPEC-025 §6.1).
The graph is already in memory (built by graph_edges.py); no extra I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from crp.ckf.graph_edges import GraphEdgeStore
    from crp.state.coverage_set import CoverageSet


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


CDGR_MAX_HOPS: int = 2
CDGR_MIN_BRIDGE_VALUE: float = 0.30
CDGR_MAX_CONNECTOR_FACTS: int = 8
CDGR_ANCHOR_BUDGET_RATIO: float = 0.70   # top 70% of fact budget → anchors


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CDGRConnector:
    """A connector fact selected by CDGR bridge scoring.

    Attributes:
        fact_id: Connector fact identifier.
        fact: The actual Fact / StateFact object (may be None).
        bridge_value: SPEC-025 §2.4 bridge_value score.
        novelty: CDR novelty from the Coverage Set.
        combined_score: ``bridge_value × novelty``.
        touched_anchors: Anchor IDs linked through this connector.
    """

    fact_id: str
    fact: Any               # the actual Fact / StateFact object
    bridge_value: float     # SPEC-025 §2.4 bridge_value score
    novelty: float          # CDR novelty from Coverage Set
    combined_score: float   # bridge_value × novelty
    touched_anchors: list[str] = field(default_factory=list)


@dataclass
class CDGRResult:
    """Full output of ``cdgr_expand()``.

    Attributes:
        anchors: CDR-ranked anchor facts.
        connectors: Bridge-value-ranked connector records.
        assembled: Anchors + connectors merged for packing.
        anchor_count: Number of anchor facts.
        connector_count: Number of connector facts selected.
        candidates_explored: Number of BFS candidates examined.
    """

    anchors: list[Any]                      # CDR-ranked anchor facts
    connectors: list[CDGRConnector]         # bridge-value-ranked connectors
    assembled: list[Any]                    # anchors + connectors merged for packing
    anchor_count: int = 0
    connector_count: int = 0
    candidates_explored: int = 0


# ---------------------------------------------------------------------------
# Phase B — Graph Expansion
# ---------------------------------------------------------------------------


def _expand_connectors(
    anchor_ids: set[str],
    edge_store: GraphEdgeStore,
    max_hops: int = CDGR_MAX_HOPS,
    fact_lookup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """BFS walk from anchors up to *max_hops* hops.

    Args:
        anchor_ids: Set of anchor fact IDs.
        edge_store: Graph edge store for neighbour lookup.
        max_hops: Maximum expansion hops.
        fact_lookup: Optional id→fact map; facts not in the map are skipped.

    Returns:
        Mapping ``{fact_id: fact_object}`` of connector candidates (not anchors).
    """
    candidates: dict[str, Any] = {}
    frontier: set[str] = set(anchor_ids)
    visited: set[str] = set(anchor_ids)

    for _hop in range(max_hops):
        next_frontier: set[str] = set()
        for fid in frontier:
            for nb_id in edge_store.neighbours(fid):
                if nb_id not in visited:
                    visited.add(nb_id)
                    next_frontier.add(nb_id)
                    if nb_id not in anchor_ids and fact_lookup:
                        fact_obj = fact_lookup.get(nb_id)
                        if fact_obj is not None:
                            candidates[nb_id] = fact_obj
        frontier = next_frontier
        if not frontier:
            break

    return candidates


# ---------------------------------------------------------------------------
# Phase C — Bridge Value Scoring (SPEC-025 §2.4)
# ---------------------------------------------------------------------------


def _bridge_value(
    connector_id: str,
    anchor_ids: list[str],
    edge_store: GraphEdgeStore,
) -> tuple[float, list[str]]:
    """Compute bridge_value for a connector candidate.

    A connector's value is the number of anchor pairs it links that would
    otherwise be disconnected in the induced subgraph, normalised by path
    edge strength.

    Args:
        connector_id: Candidate connector fact ID.
        anchor_ids: List of anchor fact IDs.
        edge_store: Graph edge store for path/edge lookup.

    Returns:
        ``(bridge_value, touched_anchor_ids)``.
    """
    # Which anchors does this connector touch (directly or within 2 hops)?
    touched: list[str] = []
    for aid in anchor_ids:
        dist = edge_store.path_length(connector_id, aid, max_hops=2)
        if dist <= 2:
            touched.append(aid)

    if len(touched) < 2:
        return 0.0, touched  # connects fewer than 2 anchors — no bridge value

    # Count anchor pairs this connector bridges where the pair has NO direct edge
    bridge_count = 0
    for i, a1 in enumerate(touched):
        for a2 in touched[i + 1:]:
            if not edge_store.has_edge(a1, a2):
                bridge_count += 1

    if bridge_count == 0:
        return 0.0, touched  # connector is redundant — all pairs already connected

    # Average edge weight along connector→touched_anchor paths
    edge_strengths: list[float] = []
    for aid in touched:
        nb = edge_store.neighbours(connector_id)
        if aid in nb:
            edge_strengths.append(nb[aid])
        else:
            # Not directly connected — 2-hop path; use lighter weight
            edge_strengths.append(0.45)

    avg_strength = sum(edge_strengths) / len(edge_strengths) if edge_strengths else 0.5

    # Normalise: bridge_count (1..N pairs) × avg_strength (0..1) → (0..1)
    # Cap at 1.0 so single strong bridges aren't inflated
    raw = bridge_count * avg_strength
    # Normalise by max possible pairs (anchors choose 2)
    max_pairs = max(1, len(touched) * (len(touched) - 1) / 2)
    bv = min(1.0, raw / max_pairs)

    return bv, touched


# ---------------------------------------------------------------------------
# Main CDGR function
# ---------------------------------------------------------------------------


def cdgr_expand(
    anchor_facts: list[Any],
    edge_store: GraphEdgeStore,
    coverage_set: CoverageSet,
    fact_lookup: dict[str, Any] | None = None,
    *,
    max_hops: int = CDGR_MAX_HOPS,
    min_bridge_value: float = CDGR_MIN_BRIDGE_VALUE,
    max_connectors: int = CDGR_MAX_CONNECTOR_FACTS,
) -> CDGRResult:
    """CDGR three-phase expansion.

    Phase A: ``anchor_facts`` are the CDR-ranked anchors (already provided).
    Phase B: BFS from anchors up to ``max_hops`` to find connector candidates.
    Phase C: Score candidates by ``bridge_value × novelty``; take top connectors.

    Args:
        anchor_facts: CDR-ranked anchor facts.
        edge_store: Graph edge store for neighbour/path lookup.
        coverage_set: Session coverage set for novelty computation.
        fact_lookup: Optional ``{fact_id: fact_object}`` map for candidate lookup.
            If None, connectors are identified by ID only and the ``fact`` field
            of ``CDGRConnector`` will be None.
        max_hops: Maximum BFS expansion hops.
        min_bridge_value: Minimum bridge value for a connector to be kept.
        max_connectors: Maximum connectors to return.

    Returns:
        A ``CDGRResult`` with anchors, connectors, and assembled facts.
    """
    anchor_ids = [_get_fact_id(f) for f in anchor_facts]
    anchor_id_set = set(anchor_ids)

    # Phase B — Expand
    candidates = _expand_connectors(
        anchor_id_set, edge_store, max_hops=max_hops, fact_lookup=fact_lookup
    )

    # Phase C — Score
    scored_connectors: list[CDGRConnector] = []
    for cid, cfact in candidates.items():
        bv, touched = _bridge_value(cid, anchor_ids, edge_store)
        if bv < min_bridge_value:
            continue

        # Apply CDR novelty filter — connectors must also be novel
        c_emb = _get_embedding(cfact)
        if c_emb:
            novelty = coverage_set.novelty(c_emb)
        else:
            novelty = 0.5  # no embedding — neutral

        if novelty < 0.20:
            continue  # fully covered already; skip

        combined = bv * novelty
        scored_connectors.append(CDGRConnector(
            fact_id=cid,
            fact=cfact,
            bridge_value=bv,
            novelty=novelty,
            combined_score=combined,
            touched_anchors=touched,
        ))

    # Sort by combined score descending
    scored_connectors.sort(key=lambda c: c.combined_score, reverse=True)
    final_connectors = scored_connectors[:max_connectors]

    # Assemble: anchors first, then connectors (for packing priority)
    assembled = list(anchor_facts) + [c.fact for c in final_connectors if c.fact is not None]

    return CDGRResult(
        anchors=anchor_facts,
        connectors=final_connectors,
        assembled=assembled,
        anchor_count=len(anchor_facts),
        connector_count=len(final_connectors),
        candidates_explored=len(candidates),
    )


# ---------------------------------------------------------------------------
# Convenience: full CDR + CDGR pipeline
# ---------------------------------------------------------------------------


def cdr_cdgr_pipeline(
    facts: list[Any],
    query_embedding: list[float],
    coverage_set: CoverageSet,
    edge_store: GraphEdgeStore,
    *,
    fact_budget: int = 20,
    importance_fn: Any = None,
    min_relevance: float = 0.55,
    max_hops: int = CDGR_MAX_HOPS,
    max_connectors: int = CDGR_MAX_CONNECTOR_FACTS,
) -> CDGRResult:
    """Run CDR ranking then CDGR expansion in one call.

    The top 70% of ``fact_budget`` become CDR anchors; the remainder is
    reserved for CDGR connectors.

    Args:
        facts: Candidate facts.
        query_embedding: Query embedding for CDR ranking.
        coverage_set: Session coverage set.
        edge_store: Graph edge store for CDGR expansion.
        fact_budget: Total number of facts for the envelope.
        importance_fn: Optional importance-weight function for CDR.
        min_relevance: CDR minimum relevance gate.
        max_hops: Maximum CDGR expansion hops.
        max_connectors: Maximum connectors to return.

    Returns:
        A ``CDGRResult`` combining anchors and connectors.
    """
    from crp.envelope.cdr import cdr_rank

    # Phase A: CDR rank
    cdr_result = cdr_rank(
        facts,
        query_embedding,
        coverage_set,
        importance_fn=importance_fn,
        min_relevance=min_relevance,
    )

    anchor_budget = max(1, int(fact_budget * CDGR_ANCHOR_BUDGET_RATIO))
    connector_budget = fact_budget - anchor_budget
    anchors = [sf.fact for sf in cdr_result.ranked[:anchor_budget]]

    # Build fact lookup map for CDGR
    fact_lookup = {_get_fact_id(f): f for f in facts}

    # Phase B + C: CDGR expand
    return cdgr_expand(
        anchor_facts=anchors,
        edge_store=edge_store,
        coverage_set=coverage_set,
        fact_lookup=fact_lookup,
        max_hops=max_hops,
        max_connectors=min(max_connectors, connector_budget),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_fact_id(fact: Any) -> str:
    """Return a fact's ID, supporting nested ``fact.fact.id`` wrappers."""
    return getattr(fact, "id", "") or getattr(getattr(fact, "fact", None), "id", "")


def _get_embedding(fact: Any) -> list[float] | None:
    """Return a fact's embedding, supporting nested wrappers."""
    for attr in ("_embedding", "embedding"):
        val = getattr(fact, attr, None)
        if val is not None and len(val) > 0:
            return val
    inner = getattr(fact, "fact", None)
    if inner is not None:
        for attr in ("_embedding", "embedding"):
            val = getattr(inner, attr, None)
            if val is not None and len(val) > 0:
                return val
    return None
