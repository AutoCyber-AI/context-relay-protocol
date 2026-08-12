# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 9 tests — observability, metrics, audit, quality, telemetry, overhead.

Each test class maps to one spec item (9.1–9.7).
"""

from __future__ import annotations

import io
import json
import time

import pytest

# ═══════════════════════════════════════════════════════════════════════════
# 9.1 — Event type constants (30+)
# ═══════════════════════════════════════════════════════════════════════════
from crp.observability.events import (
    ALL_EVENT_TYPES,
    DISPATCH_COMPLETED,
    DISPATCH_STARTED,
    FACT_CREATED,
    FACT_SUPERSEDED,
    SESSION_CLOSED,
    SESSION_CREATED,
    WINDOW_COMPLETED,
    WINDOW_OPENED,
    CRPEvent,
    EventEmitter,
)


class TestEventTypeConstants:
    """9.1: CRPEventEmitter has 30+ concrete event types."""

    def test_at_least_30_event_types(self):
        assert len(ALL_EVENT_TYPES) >= 30

    def test_all_types_are_strings(self):
        for et in ALL_EVENT_TYPES:
            assert isinstance(et, str)
            assert "." in et, f"Event type should use dot notation: {et}"

    def test_core_session_events_exist(self):
        assert SESSION_CREATED in ALL_EVENT_TYPES
        assert SESSION_CLOSED in ALL_EVENT_TYPES

    def test_core_dispatch_events_exist(self):
        assert DISPATCH_STARTED in ALL_EVENT_TYPES
        assert DISPATCH_COMPLETED in ALL_EVENT_TYPES

    def test_core_fact_events_exist(self):
        assert FACT_CREATED in ALL_EVENT_TYPES
        assert FACT_SUPERSEDED in ALL_EVENT_TYPES

    def test_core_window_events_exist(self):
        assert WINDOW_OPENED in ALL_EVENT_TYPES
        assert WINDOW_COMPLETED in ALL_EVENT_TYPES

    def test_emitter_uses_named_constants(self):
        em = EventEmitter()
        em.start()
        received = []
        em.on(DISPATCH_STARTED, lambda e: received.append(e))
        em.emit(DISPATCH_STARTED, {"task": "hello"})
        assert len(received) == 1
        assert received[0].event_type == "dispatch.started"


# ═══════════════════════════════════════════════════════════════════════════
# 9.2 — MetricsExporter (Prometheus / OTLP / JSON)
# ═══════════════════════════════════════════════════════════════════════════

from crp.observability.metrics import ExportFormat, MetricsExporter


class TestMetricsExporter:
    """9.2: MetricsExporter collects and exports in 3 formats."""

    def test_counter_increment(self):
        mx = MetricsExporter()
        mx.incr("dispatch.count")
        mx.incr("dispatch.count")
        assert mx.get_counter("dispatch.count") == 2

    def test_gauge_set(self):
        mx = MetricsExporter()
        mx.gauge("overhead.ratio", 0.12)
        assert mx.get_gauge("overhead.ratio") == 0.12

    def test_histogram_observe(self):
        mx = MetricsExporter()
        mx.observe("latency_ms", 42.3)
        mx.observe("latency_ms", 10.1)
        hist = mx.get_histogram("latency_ms")
        assert len(hist) == 2
        assert 42.3 in hist

    def test_export_json(self):
        mx = MetricsExporter()
        mx.incr("a")
        mx.gauge("b", 1.5)
        raw = mx.export(ExportFormat.JSON)
        data = json.loads(raw)
        assert data["counters"]["a"] == 1
        assert data["gauges"]["b"] == 1.5

    def test_export_prometheus(self):
        mx = MetricsExporter()
        mx.incr("dispatch.count", 5)
        mx.gauge("overhead.ratio", 0.12)
        text = mx.export(ExportFormat.PROMETHEUS)
        assert "crp_dispatch_count 5" in text
        assert "crp_overhead_ratio 0.12" in text
        assert "# TYPE" in text

    def test_export_otlp_json(self):
        mx = MetricsExporter()
        mx.incr("x")
        raw = mx.export(ExportFormat.OTLP_JSON)
        data = json.loads(raw)
        assert "resource_metrics" in data
        metrics = data["resource_metrics"][0]["scope_metrics"][0]["metrics"]
        assert len(metrics) == 1
        assert metrics[0]["name"] == "crp.x"

    def test_reset_clears_all(self):
        mx = MetricsExporter()
        mx.incr("a")
        mx.gauge("b", 1.0)
        mx.observe("c", 2.0)
        mx.reset()
        assert mx.get_counter("a") == 0
        assert mx.get_gauge("b") is None
        assert mx.get_histogram("c") == []

    def test_missing_counter_returns_zero(self):
        mx = MetricsExporter()
        assert mx.get_counter("nonexistent") == 0

    def test_missing_gauge_returns_none(self):
        mx = MetricsExporter()
        assert mx.get_gauge("nonexistent") is None


# ═══════════════════════════════════════════════════════════════════════════
# 9.3 — AuditLog (query + session reconstruction)
# ═══════════════════════════════════════════════════════════════════════════

from crp.observability.audit import AuditLog


class TestAuditLog:
    """9.3: AuditLog stores events and reconstructs sessions."""

    def test_record_and_count(self):
        log = AuditLog()
        log.record(CRPEvent("session.created", data={"session_id": "s1"}))
        log.record(CRPEvent("dispatch.started", data={"session_id": "s1"}))
        assert log.count == 2

    def test_query_by_event_type(self):
        log = AuditLog()
        log.record(CRPEvent("session.created", data={"session_id": "s1"}))
        log.record(CRPEvent("dispatch.started", data={"session_id": "s1"}))
        results = log.query(event_type="dispatch.started")
        assert len(results) == 1

    def test_query_by_session_id(self):
        log = AuditLog()
        log.record(CRPEvent("x", data={"session_id": "s1"}))
        log.record(CRPEvent("x", data={"session_id": "s2"}))
        results = log.query(session_id="s1")
        assert len(results) == 1

    def test_query_by_time_range(self):
        log = AuditLog()
        t0 = time.time()
        log.record(CRPEvent("a", timestamp=t0 - 10))
        log.record(CRPEvent("b", timestamp=t0))
        log.record(CRPEvent("c", timestamp=t0 + 10))
        results = log.query(since=t0 - 1, until=t0 + 1)
        assert len(results) == 1
        assert results[0].event_type == "b"

    def test_reconstruct_session(self):
        log = AuditLog()
        sid = "test-session"
        log.record(CRPEvent("session.created", data={"session_id": sid}))
        log.record(CRPEvent("dispatch.completed", data={"session_id": sid}))
        log.record(CRPEvent("fact.created", data={"session_id": sid}))
        log.record(CRPEvent("fact.created", data={"session_id": sid}))
        log.record(CRPEvent("fact.superseded", data={"session_id": sid}))

        summary = log.reconstruct_session(sid)
        assert summary["session_id"] == sid
        assert summary["dispatch_count"] == 1
        assert summary["facts_created"] == 2
        assert summary["facts_superseded"] == 1
        assert len(summary["events"]) == 5

    def test_emitter_integration(self):
        """AuditLog can be wired to EventEmitter via on_all."""
        em = EventEmitter()
        em.start()
        log = AuditLog()
        em.on_all(log.record)
        em.emit("session.created", {"session_id": "s1"})
        em.emit("dispatch.completed", {"session_id": "s1"})
        assert log.count == 2

    def test_clear(self):
        log = AuditLog()
        log.record(CRPEvent("x"))
        log.clear()
        assert log.count == 0


# ═══════════════════════════════════════════════════════════════════════════
# 9.4 / 9.4a — QualityReporter (S/A/B/C/D tiers)
# ═══════════════════════════════════════════════════════════════════════════

from crp.observability.quality import QualityReporter, QualityTier


class TestQualityReporter:
    """9.4: Quality tier classification and degradation detection."""

    def test_tier_s(self):
        qr = QualityReporter()
        report = qr.assess(overhead_pct=3.0, fact_miss_pct=1.0)
        assert report.tier == QualityTier.S

    def test_tier_a(self):
        qr = QualityReporter()
        report = qr.assess(overhead_pct=8.0, fact_miss_pct=5.0)
        assert report.tier == QualityTier.A

    def test_tier_b(self):
        qr = QualityReporter()
        report = qr.assess(overhead_pct=14.0, fact_miss_pct=20.0)
        assert report.tier == QualityTier.B

    def test_tier_c(self):
        qr = QualityReporter()
        report = qr.assess(overhead_pct=25.0, fact_miss_pct=40.0)
        assert report.tier == QualityTier.C

    def test_tier_d(self):
        qr = QualityReporter()
        report = qr.assess(overhead_pct=50.0, fact_miss_pct=80.0)
        assert report.tier == QualityTier.D

    def test_degradation_detected(self):
        qr = QualityReporter()
        qr.assess(overhead_pct=3.0, fact_miss_pct=1.0)  # S
        report = qr.assess(overhead_pct=25.0, fact_miss_pct=40.0)  # C
        assert report.degraded

    def test_no_degradation_on_improvement(self):
        qr = QualityReporter()
        qr.assess(overhead_pct=14.0, fact_miss_pct=20.0)  # B
        report = qr.assess(overhead_pct=3.0, fact_miss_pct=1.0)  # S
        assert not report.degraded

    def test_history_tracked(self):
        qr = QualityReporter()
        qr.assess(overhead_pct=3.0, fact_miss_pct=1.0)
        qr.assess(overhead_pct=8.0, fact_miss_pct=5.0)
        assert len(qr.history) == 2

    def test_current_tier(self):
        qr = QualityReporter()
        assert qr.current_tier is None
        qr.assess(overhead_pct=8.0, fact_miss_pct=5.0)
        assert qr.current_tier == QualityTier.A

    def test_report_to_dict(self):
        qr = QualityReporter()
        report = qr.assess(overhead_pct=3.0, fact_miss_pct=1.0)
        d = report.to_dict()
        assert d["tier"] == "S"
        assert "overhead_pct" in d
        assert "fact_miss_pct" in d

    def test_tier_ordering(self):
        assert QualityTier.S < QualityTier.A
        assert QualityTier.A < QualityTier.B
        assert QualityTier.B < QualityTier.C
        assert QualityTier.C < QualityTier.D


# ═══════════════════════════════════════════════════════════════════════════
# 9.5 — TelemetryWriter (per-window JSONL)
# ═══════════════════════════════════════════════════════════════════════════

from crp.observability.telemetry import TelemetryWriter, WindowTelemetry


class TestTelemetryWriter:
    """9.5: TelemetryWriter outputs one JSON object per line."""

    def test_write_and_read_back(self):
        buf = io.StringIO()
        tw = TelemetryWriter(buf)
        tw.write(WindowTelemetry(
            session_id="s1", window_id="w0",
            input_tokens=100, output_tokens=50,
        ))
        tw.write(WindowTelemetry(
            session_id="s1", window_id="w1",
            input_tokens=200, output_tokens=100,
        ))

        buf.seek(0)
        lines = buf.read().strip().split("\n")
        assert len(lines) == 2

        rec0 = json.loads(lines[0])
        assert rec0["session_id"] == "s1"
        assert rec0["window_id"] == "w0"
        assert rec0["input_tokens"] == 100

    def test_extra_fields_flattened(self):
        buf = io.StringIO()
        tw = TelemetryWriter(buf)
        tw.write(WindowTelemetry(
            session_id="s1", window_id="w0",
            extra={"custom_metric": 42},
        ))
        buf.seek(0)
        data = json.loads(buf.read().strip())
        assert data["custom_metric"] == 42

    def test_records_written_counter(self):
        buf = io.StringIO()
        tw = TelemetryWriter(buf)
        assert tw.records_written == 0
        tw.write(WindowTelemetry(session_id="s1", window_id="w0"))
        assert tw.records_written == 1

    def test_context_manager(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        with TelemetryWriter(path) as tw:
            tw.write(WindowTelemetry(session_id="s1", window_id="w0"))

        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["session_id"] == "s1"

    def test_window_telemetry_to_dict(self):
        wt = WindowTelemetry(
            session_id="s1", window_id="w0",
            input_tokens=100, output_tokens=50,
            quality_tier="A",
        )
        d = wt.to_dict()
        assert d["session_id"] == "s1"
        assert d["quality_tier"] == "A"


# ═══════════════════════════════════════════════════════════════════════════
# 9.6 / 9.6a / 9.6b — OverheadBudgetManager (shedding + lazy embedding)
# ═══════════════════════════════════════════════════════════════════════════

from crp.resources.overhead_manager import (
    SHEDDING_CASCADE,
    OverheadBudgetManager,
)


class TestOverheadBudgetManager:
    """9.6: Shedding cascade and lazy embedding batch."""

    def test_all_features_enabled_initially(self):
        mgr = OverheadBudgetManager()
        for feat in SHEDDING_CASCADE:
            assert mgr.is_feature_enabled(feat)

    def test_shedding_cascade_order(self):
        """Features shed cheapest-first: community_detection first."""
        assert SHEDDING_CASCADE == [
            "community_detection",
            "cross_encoder",
            "gliner",
            "uie",
            "discourse",
        ]

    def test_shed_on_over_budget(self):
        mgr = OverheadBudgetManager(max_overhead_pct=15.0)
        changed = mgr.update_overhead(18.0)
        assert "community_detection" in changed
        assert not mgr.is_feature_enabled("community_detection")
        # Others still enabled
        assert mgr.is_feature_enabled("cross_encoder")

    def test_protected_intelligence_never_shed(self):
        """ML intelligence features (gliner, uie, discourse) must never be shed."""
        from crp.resources.overhead_manager import PROTECTED_INTELLIGENCE
        mgr = OverheadBudgetManager(max_overhead_pct=15.0)
        # Shed repeatedly with extreme overhead
        for _ in range(20):
            mgr.update_overhead(99.0)
        # Protected features must remain enabled
        for feat in PROTECTED_INTELLIGENCE:
            assert mgr.is_feature_enabled(feat), f"{feat} was shed but is protected"

    def test_multiple_sheds(self):
        """Repeated over-budget updates shed one sheddable feature at a time.

        Only community_detection and cross_encoder can be shed.
        ML intelligence features (gliner, uie, discourse) are protected.
        """
        mgr = OverheadBudgetManager(max_overhead_pct=10.0)
        mgr.update_overhead(20.0)
        assert not mgr.is_feature_enabled("community_detection")

        mgr.update_overhead(20.0)
        assert not mgr.is_feature_enabled("cross_encoder")

        # Further shedding attempts skip protected ML features
        mgr.update_overhead(20.0)
        assert mgr.is_feature_enabled("gliner")  # protected
        assert mgr.is_feature_enabled("uie")  # protected
        assert mgr.is_feature_enabled("discourse")  # protected

    def test_restore_when_under_budget(self):
        mgr = OverheadBudgetManager(max_overhead_pct=15.0)
        mgr.update_overhead(18.0)  # shed community_detection
        assert not mgr.is_feature_enabled("community_detection")

        mgr.update_overhead(10.0)  # under budget → restore
        assert mgr.is_feature_enabled("community_detection")

    def test_shed_log(self):
        mgr = OverheadBudgetManager(max_overhead_pct=10.0)
        mgr.update_overhead(20.0)
        assert len(mgr.shed_log) == 1
        assert "community_detection" in mgr.shed_log[0]

    def test_defer_embedding(self):
        mgr = OverheadBudgetManager(batch_size=3)
        assert not mgr.defer_embedding("f1", "text1")
        assert not mgr.defer_embedding("f2", "text2")
        assert mgr.defer_embedding("f3", "text3")  # batch full
        assert mgr.pending_embedding_count == 3

    def test_flush_embeddings(self):
        mgr = OverheadBudgetManager()
        mgr.defer_embedding("f1", "text1")
        mgr.defer_embedding("f2", "text2")
        batch = mgr.flush_embeddings()
        assert len(batch) == 2
        assert batch[0] == ("f1", "text1")
        assert mgr.pending_embedding_count == 0

    def test_summary(self):
        mgr = OverheadBudgetManager(max_overhead_pct=15.0)
        mgr.update_overhead(12.0)
        s = mgr.summary()
        assert s["current_overhead_pct"] == 12.0
        assert s["max_overhead_pct"] == 15.0
        assert "features" in s

    def test_enabled_features_dict(self):
        mgr = OverheadBudgetManager()
        feats = mgr.enabled_features
        assert len(feats) == len(SHEDDING_CASCADE)
        assert all(v is True for v in feats.values())


# ═══════════════════════════════════════════════════════════════════════════
# 9.7 — HealthMonitor (liveness + readiness)
# ═══════════════════════════════════════════════════════════════════════════

from crp.observability.metrics import HealthMonitor, HealthStatus


class TestHealthMonitor:
    """9.7: HealthMonitor provides liveness + readiness probes."""

    def test_default_healthy(self):
        hm = HealthMonitor()
        status = hm.probe()
        assert status.alive
        assert status.ready

    def test_add_passing_check(self):
        hm = HealthMonitor()
        hm.add_check("emitter", lambda: True)
        status = hm.probe()
        assert status.alive
        assert status.ready
        assert status.details["emitter"] is True

    def test_add_failing_check(self):
        hm = HealthMonitor()
        hm.add_check("store", lambda: False)
        status = hm.probe()
        assert status.alive  # still alive
        assert not status.ready  # not ready
        assert status.details["store"] is False

    def test_check_exception_treated_as_failure(self):
        hm = HealthMonitor()
        hm.add_check("broken", lambda: 1 / 0)
        status = hm.probe()
        assert status.alive
        assert not status.ready

    def test_set_alive_false(self):
        hm = HealthMonitor()
        hm.set_alive(False)
        status = hm.probe()
        assert not status.alive

    def test_remove_check(self):
        hm = HealthMonitor()
        hm.add_check("x", lambda: False)
        assert hm.remove_check("x")
        status = hm.probe()
        assert status.ready  # no checks = ready

    def test_remove_nonexistent_check(self):
        hm = HealthMonitor()
        assert not hm.remove_check("x")

    def test_status_to_dict(self):
        s = HealthStatus(alive=True, ready=False, details={"a": True})
        d = s.to_dict()
        assert d["alive"] is True
        assert d["ready"] is False
        assert d["details"]["a"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Cross-module integration: observability __init__ exports
# ═══════════════════════════════════════════════════════════════════════════


class TestObservabilityExports:
    """Verify observability package exposes all Phase 9 classes."""

    def test_all_exports_importable(self):
        from crp.observability import (
            ALL_EVENT_TYPES,
            AuditLog,
            CRPEvent,
            EventEmitter,
            ExportFormat,
            HealthMonitor,
            HealthStatus,
            MetricsExporter,
            QualityReport,
            QualityReporter,
            QualityTier,
            TelemetryWriter,
            WindowTelemetry,
        )

        assert len(ALL_EVENT_TYPES) >= 30
        assert AuditLog is not None
        assert QualityTier.S.value == "S"

    def test_resources_exports(self):
        from crp.resources import SHEDDING_CASCADE, OverheadBudgetManager

        assert len(SHEDDING_CASCADE) == 5
        assert OverheadBudgetManager is not None
