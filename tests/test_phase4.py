# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 4 tests — State Management & CKF.

Covers:
- StateFact lifecycle (4A)
- CriticalState & StructuralState (4B)
- WarmStateStore CRUD (4B)
- FactEventLog temporal queries (4C)
- Snapshots & restore (4D)
- Compaction (4D)
- Cold storage round-trip (4E)
- FactGraphSerializer round-trip (4G)
- CKF graph_walk (4F.2)
- CKF pattern_query (4F.3)
- CKF semantic_fallback (4F.4)
- CKF community detection (4F.5/4F.7)
- CKF multi_mode_merge (4F.6)
- PubSubEventBus (4F.8)
- GarbageCollector (4F.9)
- ContextualKnowledgeFabric integration (4F.1)
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from crp.extraction.types import (
    Fact,
    FactEdge,
    FactGraph,
    RelationType,
)

# ====================================================================
# 4A: StateFact
# ====================================================================


class TestStateFact:
    def test_from_fact(self):
        from crp.state.fact import StateFact

        f = Fact(id="f1", text="hello", confidence=0.9, source_window_id="w0")
        sf = StateFact.from_fact(f)
        assert sf.id == "f1"
        assert sf.text == "hello"
        assert sf.confidence == 0.9
        assert sf.age_in_windows == 0
        assert sf.seen_count == 0

    def test_increment_age(self):
        from crp.state.fact import StateFact

        sf = StateFact.from_fact(Fact(id="f1", text="x"))
        sf.increment_age()
        sf.increment_age()
        assert sf.age_in_windows == 2

    def test_mark_seen(self):
        from crp.state.fact import StateFact

        sf = StateFact.from_fact(Fact(id="f1", text="x"))
        sf.mark_seen("w1")
        sf.mark_seen("w2")
        sf.mark_seen("w1")  # duplicate window
        assert sf.seen_count == 3
        assert sf.consumed_by_windows == ["w1", "w2"]

    def test_supersede(self):
        from crp.state.fact import StateFact

        sf = StateFact.from_fact(Fact(id="f1", text="old"))
        assert not sf.is_superseded
        sf.supersede("f2", confidence=0.85)
        assert sf.is_superseded
        assert sf.superseded_by == "f2"

    def test_to_dict_from_dict(self):
        from crp.state.fact import StateFact

        sf = StateFact.from_fact(
            Fact(id="f1", text="hello", confidence=0.9, category="entity")
        )
        sf.mark_seen("w0")
        sf.increment_age()
        d = sf.to_dict()
        assert d["fact_id"] == "f1"
        assert d["seen_count"] == 1

        sf2 = StateFact.from_dict(d)
        assert sf2.id == "f1"
        assert sf2.text == "hello"
        assert sf2.seen_count == 1
        assert sf2.age_in_windows == 1

    def test_lazy_embedding_without_function(self):
        from crp.state import fact as fact_module
        from crp.state.fact import StateFact

        # Ensure no leaked global embedding function from an earlier test.
        fact_module._EMBED_FN = None

        sf = StateFact.from_fact(Fact(id="f1", text="test"))
        assert sf.embedding is None
        assert not sf.has_embedding()

    def test_embedding_setter(self):
        from crp.state.fact import StateFact

        sf = StateFact.from_fact(Fact(id="f1", text="test"))
        sf.embedding = [0.1, 0.2, 0.3]
        assert sf.has_embedding()
        assert sf.embedding == [0.1, 0.2, 0.3]


# ====================================================================
# 4B: CriticalState & StructuralState
# ====================================================================


class TestCriticalState:
    def test_create_and_update(self):
        from crp.state.critical_state import CriticalState

        cs = CriticalState(goal="Write report", phase="planning")
        assert cs.goal == "Write report"
        cs.update(phase="executing", window_id="w5")
        assert cs.phase == "executing"
        assert cs.window_id == "w5"

    def test_to_dict_from_dict(self):
        from crp.state.critical_state import CriticalState

        cs = CriticalState(goal="g", phase="p", blockers=["b1"])
        d = cs.to_dict()
        cs2 = CriticalState.from_dict(d)
        assert cs2.goal == "g"
        assert cs2.blockers == ["b1"]

    def test_to_sections(self):
        from crp.state.critical_state import CriticalState

        cs = CriticalState(goal="Build X", phase="design", constraints=["no GPU"])
        sections = cs.to_sections()
        assert "GOAL" in sections
        assert sections["GOAL"] == "Build X"


class TestStructuralState:
    def test_create_and_serialize(self):
        from crp.state.critical_state import StructuralState

        ss = StructuralState(
            current_section="Introduction",
            markdown_depth=2,
            last_heading="Background",
        )
        d = ss.to_dict()
        ss2 = StructuralState.from_dict(d)
        assert ss2.current_section == "Introduction"
        assert ss2.markdown_depth == 2


# ====================================================================
# 4B: WarmStateStore
# ====================================================================


class TestWarmStateStore:
    def test_add_and_get_facts(self):
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        f1 = Fact(id="f1", text="Python is great", confidence=0.9)
        f2 = Fact(id="f2", text="Rust is fast", confidence=0.8)
        added = store.add_facts([f1, f2])
        assert len(added) == 2
        assert store.get_fact("f1") is not None
        assert store.get_fact("f1").text == "Python is great"

    def test_mark_seen(self):
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        store.add_facts([Fact(id="f1", text="x")])
        store.mark_seen(["f1"], "w1")
        sf = store.get_fact("f1")
        assert sf.seen_count == 1

    def test_supersede(self):
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        store.add_facts([Fact(id="f1", text="old")])
        store.supersede("f1", "f2")
        sf = store.get_fact("f1")
        assert sf.is_superseded

    def test_advance_window(self):
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        store.add_facts([Fact(id="f1", text="x")])
        store.advance_window("w1")
        sf = store.get_fact("f1")
        assert sf.age_in_windows == 1

    def test_critical_state(self):
        from crp.state.critical_state import CriticalState
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        store.update_critical_state(goal="Analyze data", phase="extract")
        cs = store.get_critical_state()
        assert cs.goal == "Analyze data"

    def test_to_dict_load_from_dict(self):
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        store.add_facts(
            [Fact(id="f1", text="a", confidence=0.5)]
        )
        store.update_critical_state(goal="G")
        d = store.to_dict()
        assert len(d["facts"]) == 1

        store2 = WarmStateStore()
        store2.load_from_dict(d)
        assert store2.get_fact("f1").text == "a"

    def test_get_active_facts(self):
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        f1 = Fact(id="f1", text="active", confidence=0.9)
        f2 = Fact(id="f2", text="old", confidence=0.8)
        store.add_facts([f1, f2])
        store.supersede("f2", "f1")
        active = store.get_active_facts_as_extraction()
        assert len(active) == 1
        assert active[0].id == "f1"

    def test_remove_fact(self):
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        store.add_facts([Fact(id="f1", text="x")])
        store.remove_fact("f1")
        assert store.get_fact("f1") is None


# ====================================================================
# 4C: FactEventLog
# ====================================================================


class TestFactEventLog:
    def test_record_and_query(self):
        from crp.state.event_log import FactEventLog

        log = FactEventLog()
        f1 = Fact(id="f1", text="a", confidence=0.5)
        f2 = Fact(id="f2", text="b", confidence=0.6)
        log.record_fact_created(f1, "w0")
        log.record_fact_created(f2, "w0")
        log.record_supersession("f1", "f2", "w1")

        assert len(log._events) == 3
        events = log.events_for_fact("f1")
        assert len(events) == 2

    def test_state_at_window(self):
        from crp.state.event_log import FactEventLog

        log = FactEventLog()
        log.record_fact_created(Fact(id="f1", text="a"), "w0")
        log.record_fact_created(Fact(id="f2", text="b"), "w1")
        log.record_supersession("f1", "f2", "w2")

        active = log.state_at_window("w1")
        assert "f1" in active
        assert "f2" in active

        active2 = log.state_at_window("w2")
        assert "f1" not in active2  # superseded
        assert "f2" in active2

    def test_facts_between(self):
        from crp.state.event_log import FactEventLog

        log = FactEventLog()
        log.record_fact_created(Fact(id="f1", text="a"), "w0")
        log.record_fact_created(Fact(id="f2", text="b"), "w1")
        log.record_fact_created(Fact(id="f3", text="c"), "w2")

        between = log.facts_between("w0", "w1")
        between_ids = [e.fact_id for e in between]
        assert "f1" in between_ids
        assert "f2" in between_ids
        assert "f3" not in between_ids

    def test_supersession_chain(self):
        from crp.state.event_log import FactEventLog

        log = FactEventLog()
        log.record_fact_created(Fact(id="f1", text="a"), "w0")
        log.record_supersession("f1", "f2", "w1")
        chain = log.supersession_chain("f1")
        assert len(chain) >= 1

    def test_events_since(self):
        from crp.state.event_log import FactEventLog

        log = FactEventLog()
        t0 = time.time()
        log.record_fact_created(Fact(id="f1", text="a"), "w0")
        events = log.events_since(t0 - 1)
        assert len(events) == 1

    def test_truncate_before(self):
        from crp.state.event_log import FactEventLog

        log = FactEventLog()
        log.record_fact_created(Fact(id="f1", text="a"), "w0")
        log.record_fact_created(Fact(id="f2", text="b"), "w1")
        # Get the event ID of the second event
        eid = log._events[1].event_id
        log.truncate_before(eid)
        assert len(log._events) == 1

    def test_serialization(self):
        from crp.state.event_log import FactEventLog

        log = FactEventLog()
        log.record_fact_created(Fact(id="f1", text="a"), "w0")
        log.record_edge_added(FactEdge(source_id="f1", target_id="f2"), "w0")
        data = log.to_list()
        assert len(data) == 2

        log2 = FactEventLog()
        log2.load_from_list(data)
        assert len(log2._events) == 2


# ====================================================================
# 4D: Snapshots
# ====================================================================


class TestSnapshot:
    def test_snapshot_and_restore(self):
        from crp.state.event_log import FactEventLog
        from crp.state.snapshot import SnapshotManager
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        store.add_facts([Fact(id="f1", text="snap", confidence=0.9)])
        log = FactEventLog()
        log.record_fact_created(Fact(id="f1", text="snap", confidence=0.9), "w0")

        mgr = SnapshotManager(store, log)
        snap = mgr.snapshot(window_id="w0")
        assert snap.window_id == "w0"
        assert snap.checksum != ""

        # Restore into a fresh store
        store2 = WarmStateStore()
        log2 = FactEventLog()
        mgr2 = SnapshotManager(store2, log2)
        warnings = mgr2.restore_from_snapshot(snap)
        # May warn about missing critical state — that's expected
        assert store2.get_fact("f1").text == "snap"

    def test_snapshot_file_roundtrip(self, tmp_path):
        from crp.state.event_log import FactEventLog
        from crp.state.snapshot import SnapshotManager
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        store.add_facts([Fact(id="f1", text="persist", confidence=0.7)])
        log = FactEventLog()
        log.record_fact_created(Fact(id="f1", text="persist", confidence=0.7), "w0")

        mgr = SnapshotManager(store, log)
        snap = mgr.snapshot("w0")

        path = tmp_path / "snap.json"
        mgr.save_to_file(path)
        warnings = mgr.restore_from_file(path)
        # File roundtrip should succeed
        assert isinstance(warnings, list)


# ====================================================================
# 4D: Compaction
# ====================================================================


class TestCompaction:
    def test_should_compact(self):
        from crp.state.compaction import CompactionConfig, should_compact
        from crp.state.warm_store import WarmStateStore

        config = CompactionConfig(fact_threshold=3)
        store = WarmStateStore()
        for i in range(5):
            store.add_facts([Fact(id=f"f{i}", text=f"fact {i}")])
        assert should_compact(store, 100.0, config) is True

        store2 = WarmStateStore()
        store2.add_facts([Fact(id="f0", text="x"), Fact(id="f1", text="y")])
        assert should_compact(store2, 100.0, config) is False

    def test_compact_superseded(self):
        from crp.state.compaction import compact
        from crp.state.event_log import FactEventLog
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        f1 = Fact(id="f1", text="old fact", confidence=0.5)
        f2 = Fact(id="f2", text="new fact", confidence=0.9)
        store.add_facts([f1, f2])
        store.supersede("f1", "f2")

        log = FactEventLog()
        log.record_fact_created(f1, "w0")
        log.record_fact_created(f2, "w0")

        result = compact(store, log, "w0")
        assert result.superseded_archived >= 1


# ====================================================================
# 4E: Cold Storage
# ====================================================================


class TestColdStorage:
    def test_roundtrip(self, tmp_path):
        from crp.state.cold_storage import persist_to_cold, restore_from_cold
        from crp.state.event_log import FactEventLog
        from crp.state.warm_store import WarmStateStore

        store = WarmStateStore()
        f1 = Fact(id="f1", text="cold", confidence=0.8)
        store.add_facts([f1])
        store.update_critical_state(goal="Test cold")
        log = FactEventLog()
        log.record_fact_created(f1, "w0")

        path = str(tmp_path / "cold.json")
        persist_to_cold(store, log, path)

        store2 = WarmStateStore()
        log2 = FactEventLog()
        header, warnings, community_map = restore_from_cold(store2, log2, path)
        assert store2.get_fact("f1").text == "cold"
        assert len(log2._events) == 1
        assert len(warnings) == 0
        assert community_map == {}


# ====================================================================
# 4G: FactGraph Serialization
# ====================================================================


class TestFactGraphSerializer:
    def test_roundtrip(self):
        from crp.state.serialization import FactGraphSerializer

        g = FactGraph()
        g.add_fact(Fact(id="a", text="alpha", confidence=0.9, category="entity"))
        g.add_fact(Fact(id="b", text="beta", confidence=0.8))
        g.add_edge(
            FactEdge(id="e1", source_id="a", target_id="b", relation_type=RelationType.CAUSE_EFFECT)
        )

        data = FactGraphSerializer.serialize(g)
        assert data["header"]["node_count"] == 2
        assert data["header"]["edge_count"] == 1

        g2, warnings = FactGraphSerializer.deserialize(data)
        assert len(warnings) == 0
        assert len(g2.nodes) == 2
        assert len(g2.edges) == 1
        assert g2.nodes["a"].text == "alpha"

    def test_file_roundtrip(self, tmp_path):
        from crp.state.serialization import FactGraphSerializer

        g = FactGraph()
        g.add_fact(Fact(id="x", text="test"))
        g.add_edge(FactEdge(source_id="x", target_id="x"))

        path = tmp_path / "graph.json"
        FactGraphSerializer.save_to_file(g, path)
        g2, warnings = FactGraphSerializer.load_from_file(path)
        assert len(g2.nodes) == 1

    def test_missing_file(self):
        from crp.state.serialization import FactGraphSerializer

        g, warnings = FactGraphSerializer.load_from_file("/nonexistent/path.json")
        assert len(warnings) > 0
        assert len(g.nodes) == 0

    def test_orphaned_edge_warning(self):
        from crp.state.serialization import FactGraphSerializer

        data = {
            "header": {"schema_version": 1, "node_count": 1, "edge_count": 1, "checksum": ""},
            "nodes": [{"id": "a", "text": "alpha"}],
            "edges": [{"source_id": "a", "target_id": "MISSING"}],
        }
        g, warnings = FactGraphSerializer.deserialize(data)
        assert any("Orphaned edge target" in w for w in warnings)


# ====================================================================
# 4F.2: Graph Walk
# ====================================================================


class TestGraphWalk:
    def test_bfs_walk(self):
        from crp.ckf.graph_walk import graph_walk

        g = FactGraph()
        g.add_fact(Fact(id="a", text="start", confidence=0.9))
        g.add_fact(Fact(id="b", text="hop1", confidence=0.8))
        g.add_fact(Fact(id="c", text="hop2", confidence=0.7))
        g.add_fact(Fact(id="d", text="isolated", confidence=0.6))
        g.add_edge(FactEdge(source_id="a", target_id="b"))
        g.add_edge(FactEdge(source_id="b", target_id="c"))

        result = graph_walk(g, {"a"}, max_hops=2)
        ids = [f.id for f in result.facts]
        assert "a" in ids
        assert "b" in ids
        assert "c" in ids
        assert "d" not in ids
        assert result.distances["a"] == 0
        assert result.distances["b"] == 1
        assert result.distances["c"] == 2

    def test_empty_seeds(self):
        from crp.ckf.graph_walk import graph_walk

        g = FactGraph()
        g.add_fact(Fact(id="a", text="x"))
        result = graph_walk(g, set())
        assert len(result.facts) == 0

    def test_max_hops_1(self):
        from crp.ckf.graph_walk import graph_walk

        g = FactGraph()
        for i in range(4):
            g.add_fact(Fact(id=f"n{i}", text=f"node {i}"))
        g.add_edge(FactEdge(source_id="n0", target_id="n1"))
        g.add_edge(FactEdge(source_id="n1", target_id="n2"))
        g.add_edge(FactEdge(source_id="n2", target_id="n3"))

        result = graph_walk(g, {"n0"}, max_hops=1)
        ids = [f.id for f in result.facts]
        assert "n0" in ids
        assert "n1" in ids
        assert "n2" not in ids


# ====================================================================
# 4F.3: Pattern Query
# ====================================================================


class TestPatternQuery:
    def test_by_category(self):
        from crp.ckf.pattern_query import pattern_query

        g = FactGraph()
        g.add_fact(Fact(id="a", text="Python 3.12", category="entity", confidence=0.9))
        g.add_fact(Fact(id="b", text="is fast", category="attribute", confidence=0.8))

        result = pattern_query(g, entity_type="entity")
        assert len(result.facts) == 1
        assert result.facts[0].id == "a"

    def test_by_relation(self):
        from crp.ckf.pattern_query import pattern_query

        g = FactGraph()
        g.add_fact(Fact(id="a", text="X", category="e", confidence=0.9))
        g.add_fact(Fact(id="b", text="Y", category="e", confidence=0.8))
        g.add_edge(
            FactEdge(
                source_id="a",
                target_id="b",
                relation_type=RelationType.CAUSE_EFFECT,
                confidence=0.7,
            )
        )

        result = pattern_query(g, relationship_type=RelationType.CAUSE_EFFECT)
        assert len(result.edges) == 1
        assert len(result.facts) == 2

    def test_min_confidence(self):
        from crp.ckf.pattern_query import pattern_query

        g = FactGraph()
        g.add_fact(Fact(id="a", text="high", confidence=0.9))
        g.add_fact(Fact(id="b", text="low", confidence=0.2))

        result = pattern_query(g, min_confidence=0.5)
        assert len(result.facts) == 1
        assert result.facts[0].id == "a"

    def test_superseded_excluded(self):
        from crp.ckf.pattern_query import pattern_query

        g = FactGraph()
        g.add_fact(Fact(id="a", text="old", confidence=0.9, superseded_by="b"))
        g.add_fact(Fact(id="b", text="new", confidence=0.9))

        result = pattern_query(g)
        ids = [f.id for f in result.facts]
        assert "a" not in ids
        assert "b" in ids


# ====================================================================
# 4F.4: Semantic Fallback
# ====================================================================


class TestSemanticFallback:
    def test_brute_force(self):
        from crp.ckf.semantic import semantic_fallback
        from crp.state.fact import StateFact

        facts = {}
        for i in range(5):
            sf = StateFact.from_fact(Fact(id=f"f{i}", text=f"fact {i}"))
            sf.embedding = [float(i) / 5.0] * 3
            facts[f"f{i}"] = sf

        result = semantic_fallback([0.8, 0.8, 0.8], facts, top_k=3)
        assert len(result.facts) <= 3
        assert not result.used_ann

    def test_empty_facts(self):
        from crp.ckf.semantic import semantic_fallback

        result = semantic_fallback([0.1, 0.2], {})
        assert len(result.facts) == 0

    def test_adaptive_top_k(self):
        from crp.ckf.semantic import adaptive_top_k

        assert adaptive_top_k(10) == 20
        assert adaptive_top_k(100) == 20
        assert adaptive_top_k(10000) >= 200


# ====================================================================
# 4F.5/4F.7: Community Detection
# ====================================================================


class TestCommunity:
    def test_connected_components(self):
        from crp.ckf.community import CommunityDetector

        g = FactGraph()
        g.add_fact(Fact(id="a", text="cluster1-a", confidence=0.9))
        g.add_fact(Fact(id="b", text="cluster1-b", confidence=0.8))
        g.add_fact(Fact(id="c", text="isolated", confidence=0.7))
        g.add_edge(FactEdge(source_id="a", target_id="b"))

        detector = CommunityDetector()
        result = detector.detect(g)
        assert len(result.communities) >= 2  # at least 2 components
        assert len(result.fact_to_community) == 3

    def test_community_summary_search(self):
        from crp.ckf.community import CommunityDetector

        g = FactGraph()
        g.add_fact(Fact(id="a", text="Python programming language", confidence=0.9))
        g.add_fact(Fact(id="b", text="JavaScript web framework", confidence=0.8))
        g.add_edge(FactEdge(source_id="a", target_id="b"))

        detector = CommunityDetector()
        detector.detect(g)
        matches = detector.community_summary(g, "Python")
        assert len(matches) >= 1

    def test_incremental_update(self):
        from crp.ckf.community import CommunityDetector

        g = FactGraph()
        for i in range(20):
            g.add_fact(Fact(id=f"f{i}", text=f"fact {i}", confidence=0.5))
        for i in range(19):
            g.add_edge(FactEdge(source_id=f"f{i}", target_id=f"f{i+1}"))

        detector = CommunityDetector()
        r1 = detector.detect(g)

        # Add one node (< 10% change)
        g.add_fact(Fact(id="fnew", text="new fact", confidence=0.6))
        g.add_edge(FactEdge(source_id="f19", target_id="fnew"))
        r2 = detector.detect(g)
        assert "fnew" in r2.fact_to_community


# ====================================================================
# 4F.6: Multi-Mode Merge
# ====================================================================


class TestMultiModeMerge:
    def test_basic_merge(self):
        from crp.ckf.merge import multi_mode_merge

        f1 = Fact(id="a", text="alpha", confidence=0.9)
        f2 = Fact(id="b", text="beta", confidence=0.8)
        f3 = Fact(id="c", text="gamma", confidence=0.7)

        mode_results = {
            "graph_walk": [(f1, 0.9), (f2, 0.5)],
            "semantic": [(f2, 0.8), (f3, 0.6)],
        }

        result = multi_mode_merge(mode_results)
        assert len(result.facts) == 3
        # b appears in both modes, should have highest merged score
        ids = [mf.fact.id for mf in result.facts]
        assert "b" in ids
        # Check dedup: total_candidates=4, unique=3
        assert result.total_candidates == 4

    def test_community_boost(self):
        from crp.ckf.merge import multi_mode_merge

        f1 = Fact(id="a", text="x", confidence=0.9)
        f2 = Fact(id="b", text="y", confidence=0.8)

        mode_results = {"semantic": [(f1, 0.9), (f2, 0.1)]}
        fact_to_comm = {"a": 0, "b": 0}

        result = multi_mode_merge(mode_results, fact_to_community=fact_to_comm)
        # b should get community boost since it's in same community as top fact
        b_merged = [mf for mf in result.facts if mf.fact.id == "b"]
        assert len(b_merged) == 1
        assert b_merged[0].community_boosted


# ====================================================================
# 4F.8: PubSub
# ====================================================================


class TestPubSub:
    def test_subscribe_and_publish(self):
        from crp.ckf.pubsub import CKFEvent, CKFEventType, PubSubEventBus

        bus = PubSubEventBus()
        received = []
        bus.subscribe(CKFEventType.FACT_CREATED, lambda e: received.append(e))
        bus.publish(CKFEvent(CKFEventType.FACT_CREATED, {"id": "f1"}))
        assert len(received) == 1
        assert received[0].data["id"] == "f1"

    def test_subscribe_all(self):
        from crp.ckf.pubsub import CKFEvent, CKFEventType, PubSubEventBus

        bus = PubSubEventBus()
        received = []
        bus.subscribe_all(lambda e: received.append(e))
        bus.publish(CKFEvent(CKFEventType.FACT_CREATED))
        bus.publish(CKFEvent(CKFEventType.EDGE_ADDED))
        assert len(received) == 2

    def test_unsubscribe(self):
        from crp.ckf.pubsub import CKFEvent, CKFEventType, PubSubEventBus

        bus = PubSubEventBus()
        cb = lambda e: None  # noqa: E731
        bus.subscribe(CKFEventType.FACT_CREATED, cb)
        assert bus.subscriber_count(CKFEventType.FACT_CREATED) == 1
        bus.unsubscribe(CKFEventType.FACT_CREATED, cb)
        assert bus.subscriber_count(CKFEventType.FACT_CREATED) == 0

    def test_error_in_handler_does_not_crash(self):
        from crp.ckf.pubsub import CKFEvent, CKFEventType, PubSubEventBus

        bus = PubSubEventBus()

        def bad_handler(e):
            raise RuntimeError("boom")

        bus.subscribe(CKFEventType.FACT_CREATED, bad_handler)
        # Should not raise
        bus.publish(CKFEvent(CKFEventType.FACT_CREATED))


# ====================================================================
# 4F.9: Garbage Collection
# ====================================================================


class TestGarbageCollector:
    def test_gc_score(self):
        from crp.ckf.gc import gc_score
        from crp.state.fact import StateFact

        sf = StateFact.from_fact(Fact(id="f1", text="important", confidence=0.9))
        sf.seen_count = 5
        sf.graph_edges = ["e1", "e2", "e3"]
        score = gc_score(sf)
        assert score > 0.5  # high-value fact

        sf2 = StateFact.from_fact(Fact(id="f2", text="meh", confidence=0.1))
        sf2.age_in_windows = 100
        score2 = gc_score(sf2)
        assert score2 < score  # lower value

    def test_should_gc(self):
        from crp.ckf.gc import GarbageCollector

        gc = GarbageCollector(budget_bytes=1000, trigger_ratio=0.8)
        assert gc.should_gc(800) is True
        assert gc.should_gc(500) is False

    def test_tombstone_and_purge(self):
        from crp.ckf.gc import TOMBSTONE_AGE_WINDOWS, GarbageCollector
        from crp.state.fact import StateFact

        gc = GarbageCollector(budget_bytes=1000, trigger_ratio=0.1, target_ratio=0.05)
        facts = {
            "f1": StateFact.from_fact(Fact(id="f1", text="a" * 200, confidence=0.1)),
            "f2": StateFact.from_fact(Fact(id="f2", text="b" * 200, confidence=0.9)),
        }
        # First run — should tombstone low-value facts
        result = gc.run(facts, 900, current_window=0)
        assert len(result.tombstoned) >= 1
        assert gc.is_tombstoned("f1")

        # Purge after enough windows
        result2 = gc.run(facts, 900, current_window=TOMBSTONE_AGE_WINDOWS + 1)
        assert len(result2.purged) >= 1


# ====================================================================
# 4F.1: CKF Integration
# ====================================================================


class TestContextualKnowledgeFabric:
    def test_store_and_retrieve_pattern(self):
        from crp.ckf.fabric import ContextualKnowledgeFabric

        ckf = ContextualKnowledgeFabric()
        ckf.store(
            [
                Fact(id="f1", text="Python", category="language", confidence=0.9),
                Fact(id="f2", text="Rust", category="language", confidence=0.8),
                Fact(id="f3", text="is fast", category="attribute", confidence=0.7),
            ],
            window_id="w0",
        )
        assert ckf.fact_count() == 3

        result = ckf.query(entity_type="language")
        assert len(result.facts) == 2

    def test_store_edges(self):
        from crp.ckf.fabric import ContextualKnowledgeFabric

        ckf = ContextualKnowledgeFabric()
        ckf.store([Fact(id="a", text="x"), Fact(id="b", text="y")], "w0")
        ckf.store_edges([FactEdge(source_id="a", target_id="b")])
        result = ckf.graph_walk({"a"}, max_hops=1)
        assert len(result.facts) == 2

    def test_pubsub_integration(self):
        from crp.ckf.fabric import ContextualKnowledgeFabric
        from crp.ckf.pubsub import CKFEventType

        ckf = ContextualKnowledgeFabric()
        events = []
        ckf.subscribe(CKFEventType.FACT_CREATED, lambda e: events.append(e))
        ckf.store([Fact(id="f1", text="test")], "w0")
        assert len(events) == 1

    def test_health(self):
        from crp.ckf.fabric import ContextualKnowledgeFabric

        ckf = ContextualKnowledgeFabric()
        ckf.store([Fact(id="f1", text="x")], "w0")
        h = ckf.health()
        assert h.fact_count == 1
        assert h.estimated_bytes > 0

    def test_persist_and_restore(self, tmp_path):
        from crp.ckf.fabric import ContextualKnowledgeFabric

        ckf = ContextualKnowledgeFabric()
        ckf.store(
            [Fact(id="f1", text="persistent", confidence=0.9)], "w0"
        )

        path = tmp_path / "ckf_state.json"
        ckf.persist(path)

        ckf2 = ContextualKnowledgeFabric()
        warnings = ckf2.restore(path)
        assert len(warnings) == 0
        assert ckf2.fact_count() == 1

    def test_temporal_query(self):
        from crp.ckf.fabric import ContextualKnowledgeFabric

        ckf = ContextualKnowledgeFabric()
        ckf.store([Fact(id="f1", text="a")], "w0")
        ckf.store([Fact(id="f2", text="b")], "w1")
        between = ckf.temporal_query("w0", "w0")
        between_ids = [e.fact_id for e in between]
        assert "f1" in between_ids

    def test_gc_integration(self):
        from crp.ckf.fabric import CKFConfig, ContextualKnowledgeFabric

        ckf = ContextualKnowledgeFabric(CKFConfig(gc_budget_bytes=100))
        # Store enough facts to exceed tiny budget
        for i in range(20):
            ckf.store([Fact(id=f"f{i}", text="x" * 50, confidence=0.1)], f"w{i}")
        assert ckf.should_gc()
        result = ckf.run_gc()
        assert result.tombstoned or result.purged or result.facts_before > 0

    def test_community_detect(self):
        from crp.ckf.fabric import ContextualKnowledgeFabric

        ckf = ContextualKnowledgeFabric()
        ckf.store(
            [
                Fact(id="a", text="Python programming", confidence=0.9),
                Fact(id="b", text="Python libraries", confidence=0.8),
                Fact(id="c", text="Rust performance", confidence=0.7),
            ],
            "w0",
        )
        ckf.store_edges([FactEdge(source_id="a", target_id="b")])
        result = ckf.detect_communities()
        assert len(result.communities) >= 1
