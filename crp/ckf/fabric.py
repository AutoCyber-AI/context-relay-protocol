# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Contextual Knowledge Fabric — unified 4-mode retrieval interface (§3.8).

The CKF is the top-level interface for fact storage, retrieval, community
detection, pub/sub events, and cross-session persistence. It combines
graph walk, pattern query, semantic fallback, and community summary modes
into a single merged result.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from crp.extraction.types import Fact, FactEdge, RelationType
from crp.state.cold_storage import persist_to_cold, restore_from_cold
from crp.state.event_log import FactEventLog
from crp.state.warm_store import WarmStateStore, WarmStoreConfig

from .community import Community, CommunityDetector, CommunityResult
from .gc import GarbageCollector, GCResult
from .graph_walk import GraphWalkResult, graph_walk
from .merge import MergeResult, multi_mode_merge
from .pattern_query import PatternQueryResult, pattern_query
from .pubsub import CKFEvent, CKFEventType, EventCallback, PubSubEventBus
from .semantic import semantic_fallback
from .vector_index import VectorIndex

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class CKFConfig:
    """Configuration for the Contextual Knowledge Fabric.

    Attributes:
        max_facts: Maximum facts retained in the warm store.
        hnsw_threshold: Minimum facts before building a vector ANN index.
        persist_path: Optional path for cold-state persistence.
        gc_budget_bytes: Memory budget for garbage collection.
        gc_trigger_ratio: Ratio of budget that triggers GC.
        gc_target_ratio: Ratio of budget GC aims to reclaim to.
        community_detect_enabled: Whether community detection runs.
    """

    max_facts: int = 10_000
    hnsw_threshold: int = 1000
    persist_path: str = ""
    gc_budget_bytes: int = 500 * 1024 * 1024
    gc_trigger_ratio: float = 0.80
    gc_target_ratio: float = 0.70
    community_detect_enabled: bool = True


# ---------------------------------------------------------------------------
# Health report
# ---------------------------------------------------------------------------


@dataclass
class CKFHealth:
    """Health snapshot for monitoring.

    Attributes:
        fact_count: Number of facts in the warm store.
        edge_count: Number of edges in the graph.
        community_count: Number of detected communities.
        event_count: Number of events in the event log.
        tombstoned_count: Facts marked for removal by GC.
        estimated_bytes: Estimated memory footprint.
        hnsw_active: Whether a vector ANN index is currently built.
        leiden_available: Whether the leidenalg library is installed.
    """

    fact_count: int = 0
    edge_count: int = 0
    community_count: int = 0
    event_count: int = 0
    tombstoned_count: int = 0
    estimated_bytes: int = 0
    hnsw_active: bool = False
    leiden_available: bool = False


# ---------------------------------------------------------------------------
# ContextualKnowledgeFabric
# ---------------------------------------------------------------------------


class ContextualKnowledgeFabric:
    """Unified interface for fact storage and 4-mode retrieval (§3.8).

    Methods (per spec 4F.1a):
    - store(facts) / retrieve(query, modes, budget)
    - query(pattern) / persist(path) / restore(path)
    - fact_count() / health()
    - temporal_query(window_range)
    - graph_walk(seeds, hops) / community_summary(topic)
    - subscribe(event, callback)
    """

    def __init__(self, config: CKFConfig | None = None) -> None:
        self._config = config or CKFConfig()

        # Core stores
        self._warm = WarmStateStore(
            WarmStoreConfig(max_facts=self._config.max_facts)
        )
        self._event_log = FactEventLog()

        # CKF subsystems
        self._bus = PubSubEventBus()
        self._community = CommunityDetector()
        self._gc = GarbageCollector(
            budget_bytes=self._config.gc_budget_bytes,
            trigger_ratio=self._config.gc_trigger_ratio,
            target_ratio=self._config.gc_target_ratio,
        )

        # Vector ANN index (faiss-first, built lazily when needed)
        self._vector_index: VectorIndex | None = None
        self._vector_index_dirty: bool = True

        # Community cache
        self._community_result: CommunityResult | None = None

        # Cooldown for community detection to avoid excessive re-computation
        self._last_community_detect: float = 0.0
        _COMMUNITY_COOLDOWN_SECONDS = 30.0
        self._community_cooldown = _COMMUNITY_COOLDOWN_SECONDS

    # ====================================================================
    # Store
    # ====================================================================

    def store(self, facts: list[Fact], window_id: str = "") -> None:
        """Ingest facts into the warm store and emit events.

        Args:
            facts: Facts to store.
            window_id: Optional source window ID to stamp on facts.
        """
        # Set source_window_id on facts if not already set
        for f in facts:
            if not f.source_window_id and window_id:
                f.source_window_id = window_id
        added = self._warm.add_facts(facts)
        for sf in added:
            self._event_log.record_fact_created(sf.fact, window_id)
            self._bus.publish(
                CKFEvent(CKFEventType.FACT_CREATED, {"fact_id": sf.id, "window_id": window_id})
            )
        self._vector_index_dirty = True

        # Auto-trigger community detection when fact count crosses thresholds
        # (every 50 new facts or when first reaching 20 facts). This ensures
        # community mode is usable during retrieval without explicit calls.
        if self._config.community_detect_enabled and added:
            fact_count = len(self._warm._facts)
            prev_count = fact_count - len(added)
            should_detect = (
                (prev_count < 20 <= fact_count)
                or (fact_count >= 20 and fact_count // 50 > prev_count // 50)
            )
            if should_detect:
                if time.monotonic() - self._last_community_detect < self._community_cooldown:
                    logger.debug("Community detection skipped (cooldown active)")
                else:
                    try:
                        self.detect_communities()
                        self._last_community_detect = time.monotonic()
                    except Exception:
                        logger.warning("Auto community detection failed", exc_info=True)

    def store_edges(self, edges: list[FactEdge]) -> None:
        """Add edges to the fact graph.

        Args:
            edges: Edges to add.
        """
        for edge in edges:
            self._warm._graph.add_edge(edge)
            self._event_log.record_edge_added(edge, "")
            self._bus.publish(
                CKFEvent(
                    CKFEventType.EDGE_ADDED,
                    {"source_id": edge.source_id, "target_id": edge.target_id},
                )
            )
        self._vector_index_dirty = True

    # ====================================================================
    # Retrieve — 4-mode merge
    # ====================================================================

    def retrieve(
        self,
        query_embedding: list[float] | None = None,
        seed_ids: set[str] | None = None,
        entity_type: str | None = None,
        relationship_type: str | RelationType | None = None,
        topic: str | None = None,
        modes: list[str] | None = None,
        budget: int = 200,
    ) -> MergeResult:
        """Retrieve facts using up to 4 modes, merged and ranked.

        Args:
            query_embedding: Query embedding for semantic mode.
            seed_ids: Seed fact IDs for graph-walk mode.
            entity_type: Entity type filter for pattern mode.
            relationship_type: Relation type filter for pattern mode.
            topic: Topic string for community mode.
            modes: Subset of ["graph_walk", "pattern", "semantic", "community"].
                Defaults to all applicable modes.
            budget: Maximum facts to return.

        Returns:
            A merged and ranked ``MergeResult``.
        """
        if modes is None:
            modes = self._infer_modes(query_embedding, seed_ids, entity_type, topic)

        graph = self._warm._graph
        mode_results: dict[str, list[tuple[Fact, float]]] = {}

        # Mode 1: Graph walk
        if "graph_walk" in modes and seed_ids:
            gw = graph_walk(graph, seed_ids, max_hops=2, max_results=budget)
            mode_results["graph_walk"] = [
                (f, 1.0 / (1.0 + gw.distances.get(f.id, 3))) for f in gw.facts
            ]

        # Mode 2: Pattern query
        if "pattern" in modes and (entity_type or relationship_type):
            pq = pattern_query(graph, entity_type, relationship_type, max_results=budget)
            mode_results["pattern"] = [(f, f.confidence or 0.5) for f in pq.facts]

        # Mode 3: Semantic fallback
        if "semantic" in modes and query_embedding:
            self._ensure_vector_index()
            sem = semantic_fallback(
                query_embedding,
                self._warm._facts,
                top_k=budget,
                hnsw_index=self._vector_index,
            )
            mode_results["semantic"] = [
                (sf.fact, sem.scores.get(sf.id, 0.0)) for sf in sem.facts
            ]

        # Mode 4: Community summary
        if "community" in modes and topic:
            comms = self.community_summary(topic)
            comm_facts: list[tuple[Fact, float]] = []
            for comm in comms:
                for fid in comm.fact_ids:
                    fact = graph.nodes.get(fid)
                    if fact:
                        comm_facts.append((fact, fact.confidence or 0.5))
            mode_results["community"] = comm_facts[:budget]

        # Merge
        # Validate facts from all modes before merging (§audit G6)
        for mode_name in list(mode_results):
            mode_results[mode_name] = [
                (f, s) for f, s in mode_results[mode_name]
                if f.id and f.text and len(f.text.strip()) >= 3
            ]

        fact_to_comm = (
            self._community_result.fact_to_community
            if self._community_result
            else None
        )
        merged = multi_mode_merge(
            mode_results,
            fact_to_community=fact_to_comm,
            max_results=budget,
        )

        # CRP 2.2 — stamp CKF_RETRIEVAL provenance on every returned fact
        # whose source is unset. Preserves prior stamps (e.g. WARM_STORE)
        # set upstream. Trust is UNKNOWN: CKF merges facts from multiple
        # retrieval modes, any of which may carry untrusted upstream
        # origin; CRP will not silently upgrade trust here.
        from crp.core.context_source import (
            ContextSource,
            SourceKind,
            SourceOrigin,
            TrustLevel,
        )

        for mf in merged.facts:
            if mf.fact.source is None:
                mf.fact.source = ContextSource(
                    kind=SourceKind.CKF_RETRIEVAL,
                    source_id=f"ckf://fact/{mf.fact.id}",
                    origin=SourceOrigin.OBSERVED,
                    trust_level=TrustLevel.UNKNOWN,
                    metadata={"modes": ",".join(modes), "score": round(mf.score, 4)},
                )
        return merged

    # ====================================================================
    # Query (pattern shorthand)
    # ====================================================================

    def query(
        self,
        entity_type: str | None = None,
        relationship_type: str | RelationType | None = None,
        min_confidence: float = 0.0,
        max_results: int = 200,
    ) -> PatternQueryResult:
        """Convenience: pattern query on the fact graph.

        Args:
            entity_type: Entity type filter.
            relationship_type: Relation type filter.
            min_confidence: Minimum fact confidence.
            max_results: Maximum facts to return.

        Returns:
            A ``PatternQueryResult``.
        """
        return pattern_query(
            self._warm._graph, entity_type, relationship_type,
            min_confidence=min_confidence, max_results=max_results,
        )

    # ====================================================================
    # Graph walk
    # ====================================================================

    def graph_walk(
        self,
        seed_ids: set[str],
        max_hops: int = 2,
        max_results: int = 200,
    ) -> GraphWalkResult:
        """BFS traversal from seed facts.

        Args:
            seed_ids: Seed fact IDs.
            max_hops: Maximum graph hops.
            max_results: Maximum facts to return.

        Returns:
            A ``GraphWalkResult``.
        """
        return graph_walk(self._warm._graph, seed_ids, max_hops, max_results)

    # ====================================================================
    # Community
    # ====================================================================

    def community_summary(self, topic: str) -> list[Community]:
        """Return communities matching *topic*.

        Args:
            topic: Topic string to match against community summaries.

        Returns:
            Matching communities.
        """
        if self._community_result is None and self._config.community_detect_enabled:
            self._community_result = self._community.detect(self._warm._graph)
            self._bus.publish(
                CKFEvent(CKFEventType.COMMUNITY_UPDATED, {"community_count": len(self._community_result.communities)})
            )
        return self._community.community_summary(self._warm._graph, topic)

    def detect_communities(self) -> CommunityResult:
        """Force a community detection run.

        Returns:
            The community detection result.
        """
        self._community_result = self._community.detect(self._warm._graph)
        self._bus.publish(
            CKFEvent(CKFEventType.COMMUNITY_UPDATED, {"community_count": len(self._community_result.communities)})
        )
        return self._community_result

    # ====================================================================
    # Temporal query
    # ====================================================================

    def temporal_query(
        self,
        start_window: str,
        end_window: str,
    ) -> list[str]:
        """Return fact IDs active between two windows.

        Args:
            start_window: Start window identifier.
            end_window: End window identifier.

        Returns:
            List of fact IDs created between the two windows.
        """
        return self._event_log.facts_between(start_window, end_window)  # type: ignore[return-value]

    # ====================================================================
    # Persistence
    # ====================================================================

    def persist(self, path: str | Path) -> None:
        """Persist full state to cold storage, including community IDs.

        Args:
            path: Destination file path.
        """
        community_map = {}
        if self._community_result:
            community_map = dict(self._community_result.fact_to_community)
        persist_to_cold(
            self._warm, self._event_log, str(path),
            community_map=community_map,
        )

    def restore(self, path: str | Path) -> list[str]:
        """Restore state from cold storage.

        Args:
            path: Source file path.

        Returns:
            List of restore warnings.
        """
        _header, warnings, community_map = restore_from_cold(
            self._warm, self._event_log, str(path)
        )
        self._vector_index_dirty = True
        self._community_result = None
        return warnings

    # ====================================================================
    # Subscribe (pub/sub)
    # ====================================================================

    def subscribe(self, event_type: CKFEventType, callback: EventCallback) -> None:
        """Register a callback for CKF events.

        Args:
            event_type: Event type to subscribe to.
            callback: Function called when the event fires.
        """
        self._bus.subscribe(event_type, callback)

    # ====================================================================
    # Introspection
    # ====================================================================

    def fact_count(self) -> int:
        """Return the number of facts in the warm store."""
        return len(self._warm._facts)

    def health(self) -> CKFHealth:
        """Return a health snapshot."""
        from .community import _check_leiden

        return CKFHealth(
            fact_count=len(self._warm._facts),
            edge_count=len(self._warm._graph.edges),
            community_count=(
                len(self._community_result.communities)
                if self._community_result
                else 0
            ),
            event_count=len(self._event_log._events),
            tombstoned_count=self._gc.tombstone_count(),
            estimated_bytes=GarbageCollector.estimate_store_bytes(self._warm._facts),
            hnsw_active=self._vector_index is not None,
            leiden_available=_check_leiden(),
        )

    # ====================================================================
    # GC
    # ====================================================================

    def run_gc(self, current_window: int = 0) -> GCResult:
        """Run cross-session garbage collection.

        Args:
            current_window: Current window number for recency-aware GC.

        Returns:
            The GC result.
        """
        estimated = GarbageCollector.estimate_store_bytes(self._warm._facts)
        return self._gc.run(self._warm._facts, estimated, current_window)

    def should_gc(self) -> bool:
        """Check if GC should be triggered based on memory budget."""
        estimated = GarbageCollector.estimate_store_bytes(self._warm._facts)
        return self._gc.should_gc(estimated)

    # ====================================================================
    # Internal helpers
    # ====================================================================

    def _infer_modes(
        self,
        query_embedding: list[float] | None,
        seed_ids: set[str] | None,
        entity_type: str | None,
        topic: str | None,
    ) -> list[str]:
        """Auto-detect which retrieval modes to activate based on inputs."""
        modes: list[str] = []
        if seed_ids:
            modes.append("graph_walk")
        if entity_type:
            modes.append("pattern")
        if query_embedding:
            modes.append("semantic")
        if topic:
            modes.append("community")
        return modes  # return empty if no inputs match any mode

    def _ensure_vector_index(self) -> None:
        """Build or rebuild the vector ANN index if needed (faiss-first).

        The :class:`VectorIndex` probes faiss → hnswlib → numpy → pure Python
        internally, so a usable index is always produced once the store
        crosses ``hnsw_threshold``; below the threshold the semantic fallback
        brute-forces directly over fact embeddings.
        """
        if not self._vector_index_dirty:
            return
        if len(self._warm._facts) < self._config.hnsw_threshold:
            self._vector_index = None
            self._vector_index_dirty = False
            return

        # Determine embedding dimension from first available embedding
        dim = 0
        for sf in self._warm._facts.values():
            if sf.has_embedding() and sf.embedding:
                dim = len(sf.embedding)
                break
        if dim == 0:
            self._vector_index = None
            self._vector_index_dirty = False
            return

        try:
            idx = VectorIndex(dim=dim, max_elements=len(self._warm._facts) + 1000)
            for sf in self._warm._facts.values():
                emb = sf.embedding
                if emb is not None:
                    idx.add(sf.id, emb)
            self._vector_index = idx
        except Exception:  # noqa: BLE001
            logger.warning("Failed to build vector index, using brute-force")
            self._vector_index = None
        self._vector_index_dirty = False
