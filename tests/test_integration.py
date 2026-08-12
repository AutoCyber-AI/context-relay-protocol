# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""SDK-internal end-to-end integration tests.

These tests verify cross-module interactions using a CustomProvider
with controlled generate_fn — no external APIs or LLM calls required.
"""

from __future__ import annotations

import time

import pytest

from crp.core.config import CRPConfig
from crp.core.errors import (
    BudgetExhaustedError,
    SessionClosedError,
    SessionExpiredError,
)
from crp.core.orchestrator import (
    CRPOrchestrator,
    ExtractionResult,
    StreamEvent,
)
from crp.core.session import (
    CostEstimate,
    EnvelopePreview,
    QualityReport,
    SessionStatus,
)
from crp.core.task_intent import TaskIntent
from crp.providers.custom import CustomProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(
    reply: str = "Hello, world!",
    finish: str = "stop",
    context_size: int = 8192,
) -> CustomProvider:
    """Create a CustomProvider with a fixed reply."""
    return CustomProvider(
        generate_fn=lambda msgs, **kw: (reply, finish),
        count_tokens_fn=lambda t: max(1, len(t) // 4),
        context_size=context_size,
    )


def _make_orchestrator(
    reply: str = "Hello, world!",
    finish: str = "stop",
    context_size: int = 8192,
    **config_kwargs: object,
) -> CRPOrchestrator:
    """Create an orchestrator with a mock provider."""
    prov = _make_provider(reply=reply, finish=finish, context_size=context_size)
    # Disable continuations by default for mock providers — the gap analyzer
    # will always detect high gap scores with fixed-reply mocks, triggering
    # unwanted continuation windows that duplicate the output.
    config_kwargs.setdefault("max_continuations", 0)
    return CRPOrchestrator(provider=prov, **config_kwargs)


def _make_streaming_continuation_provider() -> CustomProvider:
    """Provider that returns 'length' on the first stream and 'stop' on the second."""
    calls: list[list[dict[str, str]]] = []

    def generate_fn(messages: list[dict[str, str]]) -> tuple[str, str]:
        calls.append(messages)
        if len(calls) == 1:
            return ("first segment ", "length")
        return ("second segment", "stop")

    return CustomProvider(
        generate_fn=generate_fn,
        count_tokens_fn=lambda t: max(1, len(t) // 4),
        context_size=8192,
        name="streaming-continuation-mock",
    )


# =========================================================================
# 1. End-to-end dispatch
# =========================================================================


class TestE2EDispatch:
    """Full dispatch → output + QualityReport lifecycle."""

    def test_dispatch_returns_output_and_report(self) -> None:
        orch = _make_orchestrator(reply="The answer is 42.")
        output, report = orch.dispatch("You are a calculator.", "What is 6 * 7?")
        assert output == "The answer is 42."
        assert isinstance(report, QualityReport)

    def test_report_contains_session_id(self) -> None:
        orch = _make_orchestrator()
        _, report = orch.dispatch("sys", "task")
        assert report.session_id == orch.session.session_id

    def test_report_contains_window_id(self) -> None:
        orch = _make_orchestrator()
        _, report = orch.dispatch("sys", "task")
        assert report.window_id  # non-empty

    def test_report_telemetry_has_metrics(self) -> None:
        orch = _make_orchestrator()
        _, report = orch.dispatch("sys", "task")
        assert report.telemetry is not None
        assert "system_tokens" in report.telemetry
        assert "task_tokens" in report.telemetry
        assert "wall_time_ms" in report.telemetry

    def test_output_matches_provider(self) -> None:
        orch = _make_orchestrator(reply="EXACT_OUTPUT")
        output, _ = orch.dispatch("s", "t")
        assert output == "EXACT_OUTPUT"  # Axiom 9: unmodified

    def test_dispatch_intent_matches_dispatch(self) -> None:
        orch = _make_orchestrator(reply="intent output")
        intent = TaskIntent(system_prompt="sys", task_input="task")
        output, report = orch.dispatch_intent(intent)
        assert output == "intent output"
        assert isinstance(report, QualityReport)

    def test_multiple_dispatches_increment_counters(self) -> None:
        orch = _make_orchestrator()
        orch.dispatch("sys", "task1")
        orch.dispatch("sys", "task2")
        orch.dispatch("sys", "task3")
        status = orch.session_status()
        assert status.windows_completed == 3
        assert status.total_input_tokens > 0
        assert status.total_output_tokens > 0


# =========================================================================
# 2. End-to-end session lifecycle
# =========================================================================


class TestE2ESessionLifecycle:
    """Init → dispatch → status → preview → reset → close lifecycle."""

    def test_fresh_session_has_zero_counters(self) -> None:
        orch = _make_orchestrator()
        status = orch.session_status()
        assert status.windows_completed == 0
        assert status.total_input_tokens == 0
        assert status.total_output_tokens == 0

    def test_dispatch_updates_session_status(self) -> None:
        orch = _make_orchestrator()
        orch.dispatch("sys", "task")
        status = orch.session_status()
        assert status.windows_completed == 1
        assert status.total_input_tokens > 0

    def test_preview_before_dispatch(self) -> None:
        orch = _make_orchestrator()
        preview = orch.preview_envelope("sys", "task")
        assert isinstance(preview, EnvelopePreview)
        assert preview.total_tokens > 0
        assert preview.generation_reserve > 0

    def test_estimate_before_dispatch(self) -> None:
        orch = _make_orchestrator()
        est = orch.estimate_session("sys", "task")
        assert isinstance(est, CostEstimate)
        assert est.estimated_windows == 1
        assert est.estimated_input_tokens > 0

    def test_reset_clears_counters(self) -> None:
        orch = _make_orchestrator(default_role="ADMIN")
        orch.dispatch("sys", "task1")
        orch.dispatch("sys", "task2")
        assert orch.session_status().windows_completed == 2
        orch.reset_session()
        status = orch.session_status()
        assert status.windows_completed == 0
        assert status.total_input_tokens == 0

    def test_close_prevents_dispatch(self) -> None:
        orch = _make_orchestrator()
        orch.dispatch("sys", "first")
        orch.close()
        with pytest.raises(SessionClosedError):
            orch.dispatch("sys", "second")

    def test_close_prevents_status(self) -> None:
        orch = _make_orchestrator()
        orch.close()
        with pytest.raises(SessionClosedError):
            orch.session_status()

    def test_close_is_idempotent(self) -> None:
        orch = _make_orchestrator()
        orch.close()
        orch.close()  # should not raise

    def test_full_lifecycle(self) -> None:
        """Complete lifecycle: create → preview → dispatch → status → reset → dispatch → close."""
        orch = _make_orchestrator(reply="lifecycle test", default_role="ADMIN")

        # Preview
        preview = orch.preview_envelope("sys", "task")
        assert preview.total_tokens > 0

        # First dispatch
        output, report = orch.dispatch("sys", "task")
        assert output == "lifecycle test"

        # Status
        status = orch.session_status()
        assert status.windows_completed == 1

        # Reset
        orch.reset_session()
        assert orch.session_status().windows_completed == 0

        # Second dispatch
        orch.dispatch("sys", "task2")
        assert orch.session_status().windows_completed == 1

        # Close
        orch.close()
        with pytest.raises(SessionClosedError):
            orch.dispatch("sys", "task3")


# =========================================================================
# 3. End-to-end ingest (zero-LLM)
# =========================================================================


class TestE2EIngest:
    """Zero-LLM ingestion pipeline tests."""

    def test_ingest_returns_extraction_result(self) -> None:
        orch = _make_orchestrator()
        result = orch.ingest("First fact. Second fact. Third fact.")
        assert isinstance(result, ExtractionResult)
        # Graduated pipeline: Stage 2 (key_sentence) + Stage 5 (discourse_unit)
        assert result.facts_extracted >= 3

    def test_ingest_assigns_source_label(self) -> None:
        orch = _make_orchestrator()
        result = orch.ingest("Some text.", source_label="my_source")
        assert result.source_label == "my_source"

    def test_ingest_default_label(self) -> None:
        orch = _make_orchestrator()
        result = orch.ingest("Some text.")
        assert result.source_label == "unnamed"

    def test_ingest_updates_warm_state(self) -> None:
        orch = _make_orchestrator()
        orch.ingest("Fact one. Fact two.")
        status = orch.session_status()
        assert status.facts_in_warm_state == 2

    def test_ingest_empty_text(self) -> None:
        orch = _make_orchestrator()
        result = orch.ingest("")
        assert result.facts_extracted == 0

    def test_ingest_then_dispatch(self) -> None:
        """Ingest followed by dispatch — both work in same session."""
        orch = _make_orchestrator(reply="response after ingest")
        orch.ingest("Background knowledge. More facts.")
        output, report = orch.dispatch("sys", "task")
        assert output == "response after ingest"
        status = orch.session_status()
        assert status.windows_completed == 1
        # 2 from ingest + 1 from dispatch output extraction
        assert status.facts_in_warm_state >= 2

    def test_multiple_ingests_accumulate(self) -> None:
        orch = _make_orchestrator()
        orch.ingest("The server is running on port 443. It uses TLS encryption.")
        orch.ingest("Open port 22 detected. SSH service is active. Banner is OpenSSH.")
        status = orch.session_status()
        # Graduated pipeline extracts from both ingests; count must grow
        assert status.facts_in_warm_state >= 2

    def test_ingest_after_close_raises(self) -> None:
        orch = _make_orchestrator()
        orch.close()
        with pytest.raises(SessionClosedError):
            orch.ingest("text")


# =========================================================================
# 4. End-to-end streaming dispatch
# =========================================================================


class TestE2EStreaming:
    """Streaming dispatch tests (§6.10.5)."""

    def test_stream_yields_events(self) -> None:
        orch = _make_orchestrator(reply="streamed output")
        events = list(orch.dispatch_stream("sys", "task"))
        assert len(events) >= 2  # at least one token + done
        assert all(isinstance(e, StreamEvent) for e in events)

    def test_stream_token_concatenation_matches(self) -> None:
        """Token concatenation MUST produce the same string as dispatch()."""
        orch = _make_orchestrator(reply="Hello streaming world!")
        events = list(orch.dispatch_stream("sys", "task"))
        tokens = [e.data for e in events if e.event_type == "token"]
        assert "".join(tokens) == "Hello streaming world!"

    def test_stream_ends_with_done(self) -> None:
        orch = _make_orchestrator(reply="done test")
        events = list(orch.dispatch_stream("sys", "task"))
        assert events[-1].event_type == "done"

    def test_stream_done_contains_report(self) -> None:
        orch = _make_orchestrator(reply="report test")
        events = list(orch.dispatch_stream("sys", "task"))
        done_event = events[-1]
        assert isinstance(done_event.data, QualityReport)

    def test_stream_has_window_complete(self) -> None:
        orch = _make_orchestrator(reply="window test")
        events = list(orch.dispatch_stream("sys", "task"))
        types = [e.event_type for e in events]
        assert "window_complete" in types

    def test_stream_updates_counters(self) -> None:
        orch = _make_orchestrator(reply="counter test")
        list(orch.dispatch_stream("sys", "task"))
        status = orch.session_status()
        assert status.windows_completed == 1

    def test_stream_continues_on_length(self) -> None:
        """Streaming dispatch must continue when the provider hits the token wall."""
        prov = _make_streaming_continuation_provider()
        orch = CRPOrchestrator(provider=prov, max_continuations=2)
        orch._continuation_config.l3_extractor = None  # disable LLM-assisted extraction in tests
        events = list(orch.dispatch_stream("sys", "Write 5 sections about testing"))
        done = events[-1]
        assert done.event_type == "done"
        assert isinstance(done.data, QualityReport)
        assert done.data.continuation_windows >= 1
        # Token concatenation must include both segments
        tokens = [e.data for e in events if e.event_type == "token"]
        assert "first segment " in "".join(tokens)
        assert "second segment" in "".join(tokens)

    def test_stream_token_concat_across_continuation(self) -> None:
        """All token events concatenated must equal the stitched final output."""
        prov = _make_streaming_continuation_provider()
        orch = CRPOrchestrator(provider=prov, max_continuations=2)
        orch._continuation_config.l3_extractor = None  # disable LLM-assisted extraction in tests
        events = list(orch.dispatch_stream("sys", "Write 5 sections about testing"))
        tokens = [e.data for e in events if e.event_type == "token"]
        concatenated = "".join(tokens)
        done = events[-1]
        assert isinstance(done.data, QualityReport)
        assert concatenated == done.data.output

    def test_stream_augmented_continues_on_length(self) -> None:
        """Stream-augmented dispatch must continue when the stream hits length."""
        prov = _make_streaming_continuation_provider()
        orch = CRPOrchestrator(provider=prov, max_continuations=2)
        orch._continuation_config.l3_extractor = None
        output, report = orch.dispatch_stream_augmented(
            "sys", "Write 5 sections about testing"
        )
        assert report.continuation_windows >= 1
        assert "first segment" in output
        assert "second segment" in output


# =========================================================================
# 5. Budget enforcement end-to-end
# =========================================================================


class TestE2EBudgetEnforcement:
    """Budget caps work across multiple dispatches."""

    def test_window_budget_stops_dispatch(self) -> None:
        orch = _make_orchestrator(max_windows_per_session=2)
        orch.dispatch("sys", "task1")
        orch.dispatch("sys", "task2")
        with pytest.raises(BudgetExhaustedError):
            orch.dispatch("sys", "task3")

    def test_input_token_budget_stops_dispatch(self) -> None:
        orch = _make_orchestrator(max_total_input_tokens=10)
        # "sys" = ~1 token, "task" = 1 token → ~2 input tokens per dispatch
        # After enough dispatches it should exceed 10
        with pytest.raises(BudgetExhaustedError):
            for i in range(100):
                orch.dispatch("system prompt here", f"task input number {i}")

    def test_budget_remaining_in_status(self) -> None:
        orch = _make_orchestrator(max_windows_per_session=5)
        orch.dispatch("sys", "task")
        status = orch.session_status()
        assert status.remaining_budget is not None
        assert status.remaining_budget.windows_remaining == 4

    def test_no_budget_means_unlimited(self) -> None:
        orch = _make_orchestrator()
        for i in range(20):
            orch.dispatch("sys", f"task{i}")
        assert orch.session_status().windows_completed == 20


# =========================================================================
# 6. Configuration integration
# =========================================================================


class TestE2EConfiguration:
    """Configuration flows through to orchestrator behavior."""

    def test_config_accessible(self) -> None:
        orch = _make_orchestrator(session_timeout=7200)
        assert orch.config.session_timeout == 7200

    def test_configure_mutable_at_runtime(self) -> None:
        orch = _make_orchestrator()
        orch.configure(max_dispatch_rate=120)
        assert orch.config.get("max_dispatch_rate") == 120

    def test_explicit_config_object(self) -> None:
        cfg = CRPConfig()
        cfg.update({"session_timeout": 3600})
        prov = _make_provider()
        orch = CRPOrchestrator(provider=prov, config=cfg)
        assert orch.config.session_timeout == 3600


# =========================================================================
# 7. DAG and window tracking integration
# =========================================================================


class TestE2EDAG:
    """WindowDAG records dispatch history."""

    def test_dag_grows_with_dispatches(self) -> None:
        orch = _make_orchestrator()
        assert orch.dag.window_count() == 0
        orch.dispatch("sys", "task1")
        assert orch.dag.window_count() == 1
        orch.dispatch("sys", "task2")
        assert orch.dag.window_count() == 2

    def test_dag_cleared_on_reset(self) -> None:
        orch = _make_orchestrator(default_role="ADMIN")
        orch.dispatch("sys", "task")
        assert orch.dag.window_count() > 0
        orch.reset_session()
        assert orch.dag.window_count() == 0


# =========================================================================
# 8. State export integration
# =========================================================================


class TestE2EStateExport:
    """State export after dispatches."""

    def test_export_returns_bytes(self) -> None:
        orch = _make_orchestrator()
        orch.dispatch("sys", "task")
        data = orch.export_state()
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_export_works_before_dispatch(self) -> None:
        orch = _make_orchestrator()
        data = orch.export_state()
        assert isinstance(data, bytes)


# =========================================================================
# 9. Cross-module: batch + orchestrator
# =========================================================================


class TestE2EBatch:
    """Batch operations using orchestrator dispatch as the dispatch_fn."""

    def test_dispatch_batch_with_mock(self) -> None:
        from crp.core.batch import BatchResult, dispatch_batch

        orch = _make_orchestrator(reply="batch output")

        def _dispatch_fn(sp: str, ti: str) -> tuple[str, object]:
            return orch.dispatch(sp, ti)

        results = dispatch_batch(
            intents=[
                {"system_prompt": "sys", "task_input": "task1"},
                {"system_prompt": "sys", "task_input": "task2"},
            ],
            dispatch_fn=_dispatch_fn,
        )
        assert len(results) == 2
        assert all(isinstance(r, BatchResult) for r in results)
        assert all(r.success for r in results)
        assert results[0].output == "batch output"

    def test_ingest_batch_with_extraction(self) -> None:
        from crp.core.batch import ingest_batch

        results = ingest_batch(
            texts=["Alpha fact. Beta fact.", "Gamma fact."],
            extract_fn=lambda text, intent: [{"fact": s.strip()} for s in text.split(".") if s.strip()],
        )
        assert len(results) == 2
        assert results[0].facts_extracted == 2
        assert results[1].facts_extracted == 1


# =========================================================================
# 10. Cross-module: idempotency + dispatch
# =========================================================================


class TestE2EIdempotency:
    """Request deduplication wrapping dispatch."""

    def test_dedup_prevents_duplicate_calls(self) -> None:
        from crp.core.idempotency import RequestDeduplicator

        call_count = 0

        def _counting_gen(msgs, **kw):
            nonlocal call_count
            call_count += 1
            return ("deduped output", "stop")

        prov = CustomProvider(
            generate_fn=_counting_gen,
            count_tokens_fn=lambda t: max(1, len(t) // 4),
            context_size=8192,
        )
        orch = CRPOrchestrator(provider=prov, max_continuations=0)
        dedup = RequestDeduplicator()

        key = dedup.compute_key("sys", "task")
        cached = dedup.check(key)
        assert cached is None

        # First call — miss
        output, report = orch.dispatch("sys", "task")
        dedup.store(key, output, report)
        assert call_count == 1

        # Second call — hit
        cached = dedup.check(key)
        assert cached is not None
        assert cached.output == "deduped output"
        assert call_count == 1  # provider NOT called again


# =========================================================================
# 11. Cross-module: observability integration
# =========================================================================


class TestE2EObservabilityEvents:
    """Event emitter records dispatch events."""

    def test_emitter_captures_events(self) -> None:
        from crp.observability.events import EventEmitter

        emitter = EventEmitter()
        emitter.start()
        captured: list = []
        emitter.on_all(lambda e: captured.append(e))
        emitter.emit("dispatch.started", {"system_prompt": "sys"})
        emitter.emit("dispatch.completed", {"output_tokens": 42})
        emitter.stop()
        assert len(captured) == 2
        assert captured[0].event_type == "dispatch.started"
        assert captured[1].event_type == "dispatch.completed"


class TestE2EObservabilityAudit:
    """AuditLog records and queries events."""

    def test_audit_log_record_and_query(self) -> None:
        from crp.observability.audit import AuditLog
        from crp.observability.events import CRPEvent

        audit = AuditLog()
        sid = "test-session-001"
        audit.record(CRPEvent("dispatch.started", data={"session_id": sid}))
        audit.record(CRPEvent("dispatch.completed", data={"session_id": sid}))
        audit.record(CRPEvent("dispatch.started", data={"session_id": "other"}))

        results = audit.query(event_type="dispatch.started")
        assert len(results) == 2

        results = audit.query(session_id=sid)
        assert len(results) == 2

    def test_audit_reconstruct_session(self) -> None:
        from crp.observability.audit import AuditLog
        from crp.observability.events import CRPEvent

        audit = AuditLog()
        sid = "test-session-recon"
        audit.record(CRPEvent("session.created", data={"session_id": sid}))
        audit.record(CRPEvent("dispatch.completed", data={"session_id": sid}))
        audit.record(CRPEvent("fact.created", data={"session_id": sid}))
        audit.record(CRPEvent("fact.superseded", data={"session_id": sid}))
        audit.record(CRPEvent("session.closed", data={"session_id": sid}))

        recon = audit.reconstruct_session(sid)
        assert recon["session_id"] == sid
        assert recon["dispatch_count"] == 1
        assert recon["facts_created"] == 1
        assert recon["facts_superseded"] == 1


class TestE2EObservabilityMetrics:
    """MetricsExporter captures dispatch metrics."""

    def test_metrics_counter_and_export(self) -> None:
        from crp.observability.metrics import ExportFormat, MetricsExporter

        mx = MetricsExporter()
        mx.incr("dispatch.total", 3)
        mx.gauge("session.active", 1.0)
        mx.observe("dispatch.latency_ms", 42.5)

        assert mx.get_counter("dispatch.total") == 3

        json_str = mx.export(ExportFormat.JSON)
        assert "dispatch.total" in json_str

        prom_str = mx.export(ExportFormat.PROMETHEUS)
        assert "dispatch_total" in prom_str or "dispatch.total" in prom_str

    def test_health_monitor_probe(self) -> None:
        from crp.observability.metrics import HealthMonitor, HealthStatus

        hm = HealthMonitor()
        hm.add_check("always_ok", lambda: True)
        status = hm.probe()
        assert isinstance(status, HealthStatus)
        assert status.alive is True


# =========================================================================
# 12. Cross-module: quality tier assessment
# =========================================================================


class TestE2EQualityReporter:
    """QualityReporter assigns tiers to dispatch results."""

    def test_assess_quality_tier(self) -> None:
        from crp.observability.quality import QualityReporter

        reporter = QualityReporter()
        report = reporter.assess(overhead_pct=5.0, fact_miss_pct=2.0)
        assert report.tier.value in {"S", "A", "B", "C", "D"}


# =========================================================================
# 13. Provider adapter imports
# =========================================================================


class TestProviderAdapterImports:
    """Verify new provider adapters are importable."""

    def test_import_openai_adapter(self) -> None:
        from crp.providers.openai import OpenAIAdapter
        assert OpenAIAdapter is not None

    def test_import_llamacpp_adapter(self) -> None:
        from crp.providers.llamacpp import LlamaCppAdapter
        assert LlamaCppAdapter is not None

    def test_openai_adapter_inherits_llmprovider(self) -> None:
        from crp.providers.base import LLMProvider
        from crp.providers.openai import OpenAIAdapter
        assert issubclass(OpenAIAdapter, LLMProvider)

    def test_llamacpp_adapter_inherits_llmprovider(self) -> None:
        from crp.providers.base import LLMProvider
        from crp.providers.llamacpp import LlamaCppAdapter
        assert issubclass(LlamaCppAdapter, LLMProvider)


# =========================================================================
# 14. Session expiration integration
# =========================================================================


class TestE2ESessionExpiry:
    """Session expiration enforced across operations."""

    def test_expired_session_blocks_dispatch(self) -> None:
        orch = _make_orchestrator(session_timeout=0)
        # timeout=0 → session already expired
        with pytest.raises(SessionExpiredError):
            orch.dispatch("sys", "task")

    def test_expired_session_blocks_ingest(self) -> None:
        orch = _make_orchestrator(session_timeout=0)
        with pytest.raises(SessionExpiredError):
            orch.ingest("text")

    def test_expired_session_blocks_status(self) -> None:
        orch = _make_orchestrator(session_timeout=0)
        with pytest.raises(SessionExpiredError):
            orch.session_status()
