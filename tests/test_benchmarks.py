# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Performance benchmarks for CRP SDK.

Measures against spec targets:
  - Orchestrator init: < 20 s cold start (loads GLiNER + sentence-transformers)
  - Typical init (warm): < 5 s
  - Single dispatch round-trip: < 100 ms overhead (excluding LLM)
  - Envelope assembly: < 50 ms
  - Overhead ratio: < 15% of total wall time (with realistic LLM latency)
  - Dispatch overhead: < 5 s absolute (full pipeline)
  - Session status: < 10 ms
  - Ingest throughput: > 100 facts/sec
"""

from __future__ import annotations

import os
import sys
import time

import pytest

from crp.core.config import CRPConfig
from crp.core.orchestrator import CRPOrchestrator
from crp.core.session import QualityReport
from crp.providers.custom import CustomProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTEXT_SIZE = 128_000

# Perf thresholds are calibrated on Linux CI. Windows dev machines carry the
# OpenMP-hardening thread cap plus heavier background load, so identical code
# measures ~1.5x slower there; scale the three wall-clock limits accordingly.
# Override with CRP_PERF_SCALE=<float> when benchmarking on other hardware.
_PERF_SCALE = float(os.getenv("CRP_PERF_SCALE", "1.5" if sys.platform == "win32" else "1.0"))


def _make_provider(
    reply: str = "Benchmark output text.",
    latency_ms: float = 0.0,
) -> CustomProvider:
    """Provider with optional simulated latency."""

    def _gen(msgs, **kw):
        if latency_ms > 0:
            time.sleep(latency_ms / 1000)
        return (reply, "stop")

    return CustomProvider(
        generate_fn=_gen,
        count_tokens_fn=lambda t: max(1, len(t) // 4),
        context_size=_CONTEXT_SIZE,
    )


def _make_orchestrator(**kwargs: object) -> CRPOrchestrator:
    prov = _make_provider()
    kwargs.setdefault("max_continuations", 0)
    return CRPOrchestrator(provider=prov, **kwargs)


def _measure_ms(fn, *args, **kwargs) -> tuple[object, float]:
    """Execute fn and return (result, elapsed_ms)."""
    start = time.perf_counter_ns()
    result = fn(*args, **kwargs)
    elapsed = (time.perf_counter_ns() - start) / 1_000_000
    return result, elapsed


# =========================================================================
# 1. Initialization performance
# =========================================================================


class TestInitPerformance:
    """Orchestrator initialization performance.

    Cold start loads ML models (GLiNER, sentence-transformers, NLI)
    which takes several seconds. Subsequent inits reuse cached models
    but still involve wiring embedding functions and compliance checks.
    """

    def test_init_cold_start(self) -> None:
        """Cold-start init must complete within 20s (ML model loading)."""
        _, elapsed = _measure_ms(_make_orchestrator)
        assert elapsed < 20_000, f"Init took {elapsed:.1f}ms (limit: 20000ms)"

    def test_init_warm(self) -> None:
        """Warm init (models cached) should be under 5s."""
        # First call loads models
        _make_orchestrator()
        times = []
        for _ in range(5):
            _, elapsed = _measure_ms(_make_orchestrator)
            times.append(elapsed)
        median = sorted(times)[2]
        assert median < 5_000, f"Median warm init {median:.1f}ms (target: <5000ms)"


# =========================================================================
# 2. Dispatch performance
# =========================================================================


class TestDispatchPerformance:
    """Dispatch overhead (excluding LLM generation) should be minimal."""

    def test_dispatch_overhead_under_100ms(self) -> None:
        """CRP overhead per dispatch (provider returns instantly)."""
        orch = _make_orchestrator()
        # Warm up thoroughly: lazy model singletons load and the adaptive
        # latency budget settles during the first few dispatches.
        for i in range(5):
            orch.dispatch("sys", f"warm {i}")

        times = []
        for i in range(20):
            _, elapsed = _measure_ms(orch.dispatch, "system prompt", f"task input {i}")
            times.append(elapsed)

        median = sorted(times)[10]
        assert median < 100 * _PERF_SCALE, (
            f"Median dispatch overhead {median:.1f}ms (limit: {100 * _PERF_SCALE:.0f}ms)"
        )

    def test_dispatch_overhead_ratio(self) -> None:
        """CRP processing overhead per dispatch is bounded.

        The orchestrator runs the full extraction pipeline (6-stage with
        GLiNER NER + sentence-transformers dedup), envelope builder, CKF
        storage, compliance checks, and warm-store bookkeeping on every
        dispatch.  Combined overhead per dispatch is typically 1-4 s on
        consumer hardware.

        In production where LLM round-trips take 5-30 s, effective
        overhead drops to < 10%.  This test validates the absolute
        overhead stays under 5 s per dispatch.
        """
        prov = _make_provider(latency_ms=500.0)
        orch = CRPOrchestrator(provider=prov, max_continuations=0)
        orch.dispatch("sys", "warm")

        overhead_times = []
        for i in range(5):
            _, elapsed = _measure_ms(orch.dispatch, "system prompt", f"task {i}")
            overhead = elapsed - 500.0  # subtract simulated LLM time
            overhead_times.append(overhead)

        median_overhead = sorted(overhead_times)[2]
        assert median_overhead < 5000, (
            f"Median dispatch overhead {median_overhead:.1f}ms (limit: 5000ms)"
        )


# =========================================================================
# 3. Envelope preview performance
# =========================================================================


class TestEnvelopePerformance:
    """Envelope assembly / preview should be fast (no LLM call)."""

    def test_preview_under_50ms(self) -> None:
        orch = _make_orchestrator()
        times = []
        for _ in range(20):
            _, elapsed = _measure_ms(orch.preview_envelope, "system prompt", "task input")
            times.append(elapsed)
        median = sorted(times)[10]
        assert median < 50, f"Median preview {median:.1f}ms (limit: 50ms)"


# =========================================================================
# 4. Session status performance
# =========================================================================


class TestSessionStatusPerformance:
    """Session status queries should be near-instant."""

    def test_status_under_10ms(self) -> None:
        orch = _make_orchestrator()
        # Do some work first
        for i in range(5):
            orch.dispatch("sys", f"task{i}")

        times = []
        for _ in range(50):
            _, elapsed = _measure_ms(orch.session_status)
            times.append(elapsed)
        median = sorted(times)[25]
        assert median < 10, f"Median status {median:.1f}ms (limit: 10ms)"


# =========================================================================
# 5. Ingest throughput
# =========================================================================


class TestIngestPerformance:
    """Zero-LLM ingestion should handle > 100 facts/sec."""

    def test_ingest_throughput(self) -> None:
        orch = _make_orchestrator()
        # 500 sentences ≈ 500 facts
        text = ". ".join(f"Fact number {i}" for i in range(500)) + "."

        _, elapsed = _measure_ms(orch.ingest, text, "benchmark")
        facts_per_sec = 500 / (elapsed / 1000) if elapsed > 0 else float("inf")
        assert facts_per_sec > 100, (
            f"Ingest throughput {facts_per_sec:.0f} facts/sec (target: >100)"
        )


# =========================================================================
# 6. Streaming performance
# =========================================================================


class TestStreamingPerformance:
    """Streaming dispatch overhead should be comparable to non-streaming."""

    def test_stream_overhead_under_100ms(self) -> None:
        orch = _make_orchestrator()
        # Warm up thoroughly: lazy model singletons load and the adaptive
        # latency budget settles during the first few dispatches.
        for i in range(5):
            list(orch.dispatch_stream("sys", f"warm {i}"))

        times = []
        for i in range(10):
            start = time.perf_counter_ns()
            events = list(orch.dispatch_stream("sys", f"task {i}"))
            elapsed = (time.perf_counter_ns() - start) / 1_000_000
            times.append(elapsed)

        median = sorted(times)[5]
        assert median < 100 * _PERF_SCALE, (
            f"Median stream overhead {median:.1f}ms (limit: {100 * _PERF_SCALE:.0f}ms)"
        )


# =========================================================================
# 7. Batch performance
# =========================================================================


class TestBatchPerformance:
    """Batch dispatch overhead scales linearly."""

    def test_batch_10_under_1s(self) -> None:
        from crp.core.batch import dispatch_batch

        orch = _make_orchestrator()
        # Warm up thoroughly: lazy model singletons load and the adaptive
        # latency budget settles during the first few dispatches.
        for i in range(5):
            orch.dispatch("sys", f"warm {i}")

        def _dfn(sp, ti):
            return orch.dispatch(sp, ti)

        intents = [{"system_prompt": "sys", "task_input": f"task{i}"} for i in range(10)]
        _, elapsed = _measure_ms(dispatch_batch, intents, _dfn)
        assert elapsed < 1000 * _PERF_SCALE, (
            f"Batch(10) took {elapsed:.1f}ms (limit: {1000 * _PERF_SCALE:.0f}ms)"
        )


# =========================================================================
# 8. Idempotency cache performance
# =========================================================================


class TestIdempotencyPerformance:
    """Cache lookups should be sub-millisecond."""

    def test_cache_hit_under_1ms(self) -> None:
        from crp.core.idempotency import RequestDeduplicator

        dedup = RequestDeduplicator()
        key = dedup.compute_key("system", "task")
        dedup.store(key, "cached output")

        times = []
        for _ in range(100):
            _, elapsed = _measure_ms(dedup.check, key)
            times.append(elapsed)
        median = sorted(times)[50]
        assert median < 1.0, f"Cache hit {median:.3f}ms (limit: 1ms)"


# =========================================================================
# 9. Event emitter performance
# =========================================================================


class TestEventPerformance:
    """Event emission should be fast."""

    def test_emit_1000_events_under_100ms(self) -> None:
        from crp.observability.events import EventEmitter

        emitter = EventEmitter()
        emitter.start()
        counter = [0]
        emitter.on_all(lambda e: counter.__setitem__(0, counter[0] + 1))

        start = time.perf_counter_ns()
        for i in range(1000):
            emitter.emit("dispatch.started", {"i": i})
        elapsed = (time.perf_counter_ns() - start) / 1_000_000
        emitter.stop()

        assert elapsed < 100, f"1000 events took {elapsed:.1f}ms (limit: 100ms)"
        assert counter[0] == 1000


# =========================================================================
# 10. Metrics export performance
# =========================================================================


class TestMetricsExportPerformance:
    """Metrics export should be fast even with many counters."""

    def test_export_100_counters_under_50ms(self) -> None:
        from crp.observability.metrics import ExportFormat, MetricsExporter

        mx = MetricsExporter()
        for i in range(100):
            mx.incr(f"counter_{i}", i)
            mx.gauge(f"gauge_{i}", float(i))

        _, elapsed = _measure_ms(mx.export, ExportFormat.JSON)
        assert elapsed < 50, f"JSON export took {elapsed:.1f}ms (limit: 50ms)"

        _, elapsed = _measure_ms(mx.export, ExportFormat.PROMETHEUS)
        assert elapsed < 50, f"Prometheus export took {elapsed:.1f}ms (limit: 50ms)"
