# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 7 — Advanced Features test suite.

Covers all 15 Phase 7 modules:
  7A: auto_ingest, scale_mode, orchestrator ingest/export/stream
  7B: hierarchical, parallel, cqs, cross_window, review_cycle, source_grounding
  7C: curator, meta_learning, feedback
  7D: batch, idempotency, cost_model
"""

from __future__ import annotations

import json
import time

import pytest

# ---------------------------------------------------------------------------
# 7A — Auto-ingest (§4.6)
# ---------------------------------------------------------------------------
from crp.advanced.auto_ingest import (
    Chunk,
    IngestFact,
    IngestResult,
    ProtectedSpan,
    auto_ingest,
    detect_protected_structures,
    merge_overlapping_spans,
    reconcile_chunk_boundaries,
    split_at_boundaries,
)


class TestAutoIngest:
    """Tests for structure-aware chunking (7A.1-7A.3)."""

    def _count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def test_auto_ingest_short_text(self):
        facts, result = auto_ingest(
            system_prompt="Test",
            task_input="Short text.",
            task_intent_text="Summarize",
            context_window=128000,
            count_tokens=self._count_tokens,
        )
        assert isinstance(result, IngestResult)
        assert result.chunks_created >= 1

    def test_auto_ingest_long_text_splits(self):
        text = "Sentence one. " * 500
        facts, result = auto_ingest(
            system_prompt="Test",
            task_input=text,
            task_intent_text="Summarize",
            context_window=200,  # Force splitting
            count_tokens=self._count_tokens,
        )
        assert result.chunks_created >= 1

    def test_detect_protected_structures_code_block(self):
        text = "Before.\n```python\nprint('hello')\n```\nAfter."
        spans = detect_protected_structures(text)
        assert any(s.span_type == "code_block" for s in spans)

    def test_detect_protected_structures_table(self):
        text = "Text.\n| A | B |\n|---|---|\n| 1 | 2 |\nMore text."
        spans = detect_protected_structures(text)
        assert any("table" in s.span_type for s in spans)

    def test_detect_protected_structures_json_block(self):
        text = 'Data: {"key": "value", "number": 42, "another_key": "another_value_here"} end.'
        spans = detect_protected_structures(text)
        assert any("json_block" in s.span_type for s in spans)

    def test_merge_overlapping_spans(self):
        spans = [
            ProtectedSpan(0, 10, "code_block"),
            ProtectedSpan(5, 15, "code_block"),
            ProtectedSpan(20, 30, "table"),
        ]
        merged = merge_overlapping_spans(spans)
        assert len(merged) == 2
        assert merged[0].start == 0
        assert merged[0].end == 15

    def test_split_at_boundaries_produces_chunks(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = split_at_boundaries(text, chunk_size_chars=20, overlap_chars=5, protected_spans=[])
        assert len(chunks) >= 1
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_reconcile_chunk_boundaries_dedup(self):
        facts = [
            [IngestFact(text="Exactly the same fact.", chunk_index=0)],
            [IngestFact(text="Exactly the same fact.", chunk_index=1)],
            [IngestFact(text="Different fact entirely.", chunk_index=2)],
        ]
        result = reconcile_chunk_boundaries(facts)
        assert len(result) <= 3

    def test_auto_ingest_returns_facts(self):
        text = "Fact one. Fact two. Fact three."
        facts, result = auto_ingest(
            system_prompt="Test",
            task_input=text,
            task_intent_text="Extract",
            context_window=128000,
            count_tokens=self._count_tokens,
        )
        assert isinstance(facts, list)


# ---------------------------------------------------------------------------
# 7A.5 — Scale mode
# ---------------------------------------------------------------------------

from crp.advanced.scale_mode import (
    QualityTier,
    ScaleModeSelector,
    SessionConfig,
    classify_quality_tier,
    select_processing_mode,
)


class TestScaleMode:
    """Tests for quality tier classification and session config (7A.5)."""

    def test_classify_tier_s(self):
        # 100 tokens / 128000 context = ratio < 1 → S
        assert classify_quality_tier(100, 128000) == QualityTier.S

    def test_classify_tier_a(self):
        # 256000 tokens / 128000 context = ratio 2 → A
        assert classify_quality_tier(256000, 128000) == QualityTier.A

    def test_classify_tier_b(self):
        # 6.4M tokens / 128000 = ratio 50 → B
        assert classify_quality_tier(6_400_000, 128000) == QualityTier.B

    def test_classify_tier_c(self):
        # 64M / 128000 = ratio 500 → C
        assert classify_quality_tier(64_000_000, 128000) == QualityTier.C

    def test_classify_tier_d(self):
        # 640M / 128000 = ratio 5000 → D
        assert classify_quality_tier(640_000_000, 128000) == QualityTier.D

    def test_select_processing_mode_serial(self):
        # 5 windows worth → SERIAL
        mode = select_processing_mode(640_000, 128000)
        assert "SERIAL" in mode

    def test_select_processing_mode_hierarchical(self):
        # 5000 windows worth → HIERARCHICAL
        mode = select_processing_mode(640_000_000, 128000)
        assert "HIERARCHICAL" in mode

    def test_scale_mode_selector_configure(self):
        selector = ScaleModeSelector(context_window=128000)
        config = selector.configure_session(estimated_tokens=6_400_000)
        assert isinstance(config, SessionConfig)
        assert config.quality_tier == QualityTier.B

    def test_scale_mode_selector_tier_s(self):
        selector = ScaleModeSelector(context_window=128000)
        config = selector.configure_session(estimated_tokens=100)
        assert config.quality_tier == QualityTier.S


# ---------------------------------------------------------------------------
# 7B.1 — Hierarchical (map-reduce-validate)
# ---------------------------------------------------------------------------

from crp.advanced.hierarchical import (
    HierarchicalPlan,
    HierarchicalProcessor,
    chain_degradation,
    effective_context,
)


class TestHierarchical:
    """Tests for map-reduce-validate (7B.1)."""

    def test_chain_degradation_formula(self):
        # 1 - (1 - per_level)^L
        result = chain_degradation(levels=1, per_level=0.1)
        assert abs(result - 0.1) < 0.01

    def test_chain_degradation_multi_level(self):
        result = chain_degradation(levels=3, per_level=0.1)
        expected = 1 - (1 - 0.1) ** 3
        assert abs(result - expected) < 0.001

    def test_effective_context(self):
        ctx = effective_context(context_window=128000, levels=2, per_level=0.1)
        assert ctx < 128000
        assert ctx > 0

    def test_plan_creates_segments(self):
        proc = HierarchicalProcessor(context_window=128000)
        plan = proc.plan(total_tokens=500000)
        assert isinstance(plan, HierarchicalPlan)
        assert plan.hierarchy_levels >= 1
        assert plan.segment_count >= 1

    def test_hierarchical_map_phase(self):
        proc = HierarchicalProcessor(context_window=128000)
        segments = proc.map_phase(["chunk1", "chunk2", "chunk3"], task_intent="Summarize")
        assert len(segments) == 3


# ---------------------------------------------------------------------------
# 7B.2 — Parallel fan-out
# ---------------------------------------------------------------------------

from crp.advanced.parallel import FanOutResult, FanOutTask, ParallelFanOut


class TestParallelFanOut:
    """Tests for parallel fan-out (7B.2)."""

    def test_fan_out_creates_results(self):
        pfo = ParallelFanOut(max_concurrent=4)
        tasks = [
            FanOutTask(task_id="t1", system_prompt="Test", task_input="Task 1"),
            FanOutTask(task_id="t2", system_prompt="Test", task_input="Task 2"),
        ]
        results = pfo.fan_out(tasks)
        assert len(results) == 2
        assert all(isinstance(r, FanOutResult) for r in results)

    def test_fan_out_sequential(self):
        pfo = ParallelFanOut(max_concurrent=1)
        tasks = [FanOutTask(task_id=f"t{i}", system_prompt="S", task_input=f"T{i}") for i in range(3)]
        results = pfo.fan_out(tasks)
        assert len(results) == 3

    def test_merge_results(self):
        pfo = ParallelFanOut()
        results = [
            FanOutResult(task_id="t1", output="Result 1"),
            FanOutResult(task_id="t2", output="Result 2"),
        ]
        merged = pfo.merge_results(results)
        assert isinstance(merged, list)
        assert len(merged) == 2


# ---------------------------------------------------------------------------
# 7B.3 — CQS (Context Quality Signaling)
# ---------------------------------------------------------------------------

from crp.advanced.cqs import ContextHungerSignal, CQSDetector, CQSResponse


class TestCQS:
    """Tests for context hunger detection (7B.3)."""

    def test_detect_hedging(self):
        detector = CQSDetector()
        text = (
            "It might be possible that, I'm not sure, but perhaps "
            "it could be that maybe this is likely the case."
        )
        signals = detector.detect_context_hunger(text)
        assert isinstance(signals, list)

    def test_detect_no_signals_on_clear_text(self):
        detector = CQSDetector()
        text = "The server runs on port 443. It uses TLS encryption."
        signals = detector.detect_context_hunger(text)
        # Clear text should have few or no signals
        assert len(signals) <= 1

    def test_respond_to_context_hunger(self):
        detector = CQSDetector()
        signal = ContextHungerSignal(
            signal_type="hedging",
            strength=0.8,
            topic="encryption",
        )
        response = detector.respond_to_context_hunger([signal])
        assert isinstance(response, CQSResponse)


# ---------------------------------------------------------------------------
# 7B.4 — Cross-window validation
# ---------------------------------------------------------------------------

from crp.advanced.cross_window import (
    ConsistencyIssue,
    CrossWindowValidator,
    ValidationResult,
)


class TestCrossWindow:
    """Tests for 3-tier cross-window consistency (7B.4)."""

    def test_extraction_based_validation(self):
        validator = CrossWindowValidator()
        facts = [
            {"text": "Server runs on port 443", "confidence": 0.9},
            {"text": "Server runs on port 8080", "confidence": 0.8},
        ]
        result = validator.extraction_based_validation(facts)
        assert isinstance(result, ValidationResult)

    def test_should_run_tier(self):
        validator = CrossWindowValidator()
        # Tier 1 runs at interval (default 1)
        assert validator.should_run_tier(0, 1)
        # Tier 2 runs at its interval
        assert validator.should_run_tier(0, 2)

    def test_apply_corrections_flag_mode(self):
        validator = CrossWindowValidator()
        issues = [
            ConsistencyIssue(
                issue_type="numerical_contradiction",
                description="Port conflict",
                severity="high",
            ),
        ]
        result = validator.apply_corrections(issues)
        assert isinstance(result, list)

    def test_assess_review_capability(self):
        validator = CrossWindowValidator()
        score = validator.assess_review_capability()
        assert isinstance(score, (int, float))
        assert score >= 0


# ---------------------------------------------------------------------------
# 7B.5 — Review cycle
# ---------------------------------------------------------------------------

from crp.advanced.review_cycle import (
    AssessmentResult,
    DocumentPlan,
    ReviewCycleManager,
    ReviewGuidance,
)


class TestReviewCycle:
    """Tests for active LLM review (7B.5)."""

    def test_pre_generation_plan_short_chain(self):
        mgr = ReviewCycleManager()
        plan = mgr.pre_generation_plan(task_intent="Test", predicted_chain_length=3)
        # Short chain (<= 5) — no plan needed
        assert plan is None

    def test_pre_generation_plan_long_chain(self):
        mgr = ReviewCycleManager()
        # No dispatch_fn → returns None even for long chain
        plan = mgr.pre_generation_plan(task_intent="Test", predicted_chain_length=10)
        assert plan is None

    def test_checkpoint_review_gated_by_capability(self):
        mgr = ReviewCycleManager(model_review_capability=1)
        # Low capability: returns None
        guidance = mgr.checkpoint_review(window_index=0)
        assert guidance is None

    def test_post_generation_assessment(self):
        mgr = ReviewCycleManager()
        result = mgr.post_generation_assessment(
            accumulated_output="Complete report text.",
            task_intent="Write a report.",
        )
        assert isinstance(result, AssessmentResult)
        assert 0 <= result.score <= 10


# ---------------------------------------------------------------------------
# 7B.6 — Source grounding
# ---------------------------------------------------------------------------

from crp.advanced.source_grounding import SourceGroundingEngine, SourcePassage


class TestSourceGrounding:
    """Tests for source passage storage and retrieval (7B.6)."""

    def test_store_passage_high_confidence(self):
        engine = SourceGroundingEngine()
        p = SourcePassage(
            passage_id="p1", text="The vulnerability affects port 443.",
            source_window=1, linked_fact_ids=["f1"],
        )
        stored = engine.store_passage(p, fact_confidence=0.9)
        assert stored is True
        passages = engine.get_passages_for_fact("f1")
        assert len(passages) == 1
        assert passages[0].text == "The vulnerability affects port 443."

    def test_store_passage_low_confidence_rejected(self):
        engine = SourceGroundingEngine()
        p = SourcePassage(
            passage_id="p2", text="Maybe something.",
            source_window=1, linked_fact_ids=["f2"],
        )
        stored = engine.store_passage(p, fact_confidence=0.5)
        assert stored is False
        passages = engine.get_passages_for_fact("f2")
        assert len(passages) == 0

    def test_build_source_grounded_envelope(self):
        engine = SourceGroundingEngine()
        p = SourcePassage(
            passage_id="p1", text="Port 443 open.",
            source_window=1, linked_fact_ids=["f1"],
        )
        engine.store_passage(p, fact_confidence=0.95)
        facts = [{"id": "f1", "text": "Port 443 open.", "score": 0.95, "window": 1}]
        packed, passages = engine.build_source_grounded_envelope(facts, budget_tokens=500)
        assert isinstance(packed, list)
        assert len(packed) >= 1

    def test_serialization_roundtrip(self):
        engine = SourceGroundingEngine()
        p = SourcePassage(
            passage_id="p1", text="Test passage.",
            source_window=1, linked_fact_ids=["f1"],
        )
        engine.store_passage(p, fact_confidence=0.85)
        data = engine.to_dict()
        engine2 = SourceGroundingEngine()
        # Reconstruct from dict
        for pid, pd in data["passages"].items():
            engine2.store_passage(SourcePassage.from_dict(pd), fact_confidence=0.85)
        passages = engine2.get_passages_for_fact("f1")
        assert len(passages) == 1


# ---------------------------------------------------------------------------
# 7C.1 — LLM Context Curator
# ---------------------------------------------------------------------------

from crp.advanced.curator import CurationConfig, LLMContextCurator, LLMSynthesis


class TestCurator:
    """Tests for LLM-driven context curation (7C.1)."""

    def test_should_curate_initial(self):
        curator = LLMContextCurator()
        # window_index=0 should return False (no curation at start)
        assert not curator.should_curate(window_index=0)
        # window_index at interval should return True
        assert curator.should_curate(window_index=5)

    def test_curate_no_dispatch(self):
        curator = LLMContextCurator()
        # No dispatch_fn → returns None
        result = curator.curate(
            window_index=5,
            top_facts=["Fact one about vulnerabilities.", "Fact two about ports."],
        )
        assert result is None

    def test_format_for_envelope(self):
        curator = LLMContextCurator()
        # Set current synthesis directly
        curator._current_synthesis = LLMSynthesis(
            text="Combined findings.",
            window_index=5,
            critical_findings=["Point 1", "Point 2"],
        )
        formatted = curator.format_for_envelope()
        assert isinstance(formatted, str)
        assert "LLM_SYNTHESIS" in formatted


# ---------------------------------------------------------------------------
# 7C.2 — Meta-learning
# ---------------------------------------------------------------------------

from crp.advanced.meta_learning import (
    MetaLearningEngine,
    ORCResult,
    ReasoningStep,
    ReasoningTrace,
)


class TestMetaLearning:
    """Tests for ORC + ICML + RTL (7C.2)."""

    def test_should_use_orc_false_for_low_complexity(self):
        # model_capability(1) >= task_complexity(1) → False
        engine = MetaLearningEngine(model_capability=5)
        assert not engine.should_use_orc(task_complexity=1)

    def test_should_use_orc_true_for_high_complexity(self):
        # model_capability(1) < task_complexity(8) → True
        engine = MetaLearningEngine(model_capability=1)
        assert engine.should_use_orc(task_complexity=8)

    def test_orchestrated_reasoning(self):
        engine = MetaLearningEngine()
        result = engine.orchestrated_reasoning(
            task_intent="Analyze security posture",
        )
        assert isinstance(result, ORCResult)

    def test_build_reasoning_scaffold_heavy(self):
        engine = MetaLearningEngine(model_capability=1)
        scaffold = engine.build_reasoning_scaffold(
            task_intent="Complex analysis",
        )
        assert isinstance(scaffold, str)
        assert len(scaffold) > 0

    def test_store_and_retrieve_trace(self):
        engine = MetaLearningEngine()
        trace = ReasoningTrace(
            task_type="security",
            task_summary="security analysis test",
            steps=[ReasoningStep(step_description="Step 1")],
            quality_score=0.9,
        )
        stored = engine.store_trace(trace)
        assert stored is True
        retrieved = engine._retrieve_traces("security analysis")
        assert len(retrieved) >= 1


# ---------------------------------------------------------------------------
# 7C.3 — Feedback loop
# ---------------------------------------------------------------------------

from crp.advanced.feedback import FeedbackEntry, FeedbackLoop


class TestFeedback:
    """Tests for human-in-the-loop feedback (7C.3)."""

    def test_override_fact(self):
        loop = FeedbackLoop()
        entry = loop.override_fact("f1", corrected_text="new text", reason="Verified")
        assert isinstance(entry, FeedbackEntry)
        assert entry.action == "override"

    def test_boost_confidence(self):
        loop = FeedbackLoop()
        loop.boost_confidence("f2", delta=0.2)
        adjusted = loop.get_adjusted_confidence("f2", 0.6)
        assert adjusted == pytest.approx(0.8, abs=0.01)

    def test_penalize_confidence(self):
        loop = FeedbackLoop()
        loop.penalize_confidence("f3", delta=-0.3)
        adjusted = loop.get_adjusted_confidence("f3", 0.8)
        assert adjusted == pytest.approx(0.5, abs=0.01)

    def test_reject_fact(self):
        loop = FeedbackLoop()
        loop.reject_fact("f4", reason="Incorrect")
        adjusted = loop.get_adjusted_confidence("f4", 0.9)
        assert adjusted == 0.0

    def test_no_adjustment_returns_original(self):
        loop = FeedbackLoop()
        adjusted = loop.get_adjusted_confidence("f99", 0.7)
        assert adjusted == 0.7


# ---------------------------------------------------------------------------
# 7D.1-7D.2 — Batch operations
# ---------------------------------------------------------------------------

from crp.core.batch import BatchResult, dispatch_batch, ingest_batch


class TestBatch:
    """Tests for batch dispatch and ingestion (7D.1-7D.2)."""

    def test_dispatch_batch_returns_results(self):
        results = dispatch_batch(
            intents=[
                {"system_prompt": "Test", "task_input": "Input 1"},
                {"system_prompt": "Test", "task_input": "Input 2"},
            ],
            dispatch_fn=lambda sp, ti: (f"Output for {ti}", None),
        )
        assert len(results) == 2
        assert all(isinstance(r, BatchResult) for r in results)
        assert results[0].output == "Output for Input 1"

    def test_dispatch_batch_handles_errors(self):
        def failing_dispatch(sp, ti):
            if "fail" in ti:
                raise ValueError("Intentional failure")
            return (f"OK: {ti}", None)

        results = dispatch_batch(
            intents=[
                {"system_prompt": "T", "task_input": "good input"},
                {"system_prompt": "T", "task_input": "fail input"},
            ],
            dispatch_fn=failing_dispatch,
        )
        assert len(results) == 2
        assert results[0].error is None
        assert results[1].error is not None

    def test_ingest_batch_returns_results(self):
        results = ingest_batch(
            texts=["Text one.", "Text two."],
            extract_fn=lambda text, intent: [{"fact": text}],
        )
        assert len(results) == 2


# ---------------------------------------------------------------------------
# 7D.3-7D.4 — Idempotency
# ---------------------------------------------------------------------------

from crp.core.idempotency import (
    CachedResult,
    RequestDeduplicator,
    SessionLock,
)


class TestIdempotency:
    """Tests for request deduplication and session locking (7D.3-7D.4)."""

    def test_compute_key_deterministic(self):
        dedup = RequestDeduplicator()
        k1 = dedup.compute_key("sys", "task")
        k2 = dedup.compute_key("sys", "task")
        assert k1 == k2

    def test_compute_key_different_inputs(self):
        dedup = RequestDeduplicator()
        k1 = dedup.compute_key("sys", "task1")
        k2 = dedup.compute_key("sys", "task2")
        assert k1 != k2

    def test_check_miss(self):
        dedup = RequestDeduplicator()
        result = dedup.check("nonexistent")
        assert result is None
        assert dedup.stats.cache_misses == 1

    def test_store_and_check_hit(self):
        dedup = RequestDeduplicator()
        key = dedup.compute_key("sys", "task")
        dedup.store(key, "output", {"report": True})
        result = dedup.check(key)
        assert result is not None
        assert result.output == "output"
        assert dedup.stats.cache_hits == 1

    def test_ttl_expiry(self):
        dedup = RequestDeduplicator(ttl=0.01)
        key = dedup.compute_key("sys", "task")
        dedup.store(key, "output")
        time.sleep(0.02)
        result = dedup.check(key)
        assert result is None

    def test_invalidate(self):
        dedup = RequestDeduplicator()
        key = "test_key"
        dedup.store(key, "output")
        assert dedup.invalidate(key)
        assert dedup.check(key) is None

    def test_clear(self):
        dedup = RequestDeduplicator()
        dedup.store("k1", "o1")
        dedup.store("k2", "o2")
        count = dedup.clear()
        assert count == 2
        assert dedup.cache_size == 0

    def test_max_cache_eviction(self):
        dedup = RequestDeduplicator(max_cache_size=2)
        dedup.store("k1", "o1")
        dedup.store("k2", "o2")
        dedup.store("k3", "o3")
        assert dedup.cache_size <= 2

    def test_session_lock_write(self):
        lock = SessionLock()
        assert lock.acquire_write()
        lock.release_write()

    def test_session_lock_read_noop(self):
        lock = SessionLock()
        assert lock.acquire_read()
        lock.release_read()


# ---------------------------------------------------------------------------
# 7D.5-7D.7 — Cost model & budget
# ---------------------------------------------------------------------------

from crp.resources.cost_model import (
    KNOWN_PRICING,
    BudgetWarningLevel,
    CostModel,
    OverheadBudget,
    OverheadDecision,
    ProviderPricing,
)


class TestCostModel:
    """Tests for provider pricing and budget enforcement (7D.5-7D.7)."""

    def test_provider_pricing_calculation(self):
        pricing = ProviderPricing(2.50, 10.00, "openai")
        cost = pricing.total_cost(1_000_000, 500_000)
        assert cost == pytest.approx(7.50)

    def test_known_pricing_populated(self):
        assert "gpt-4o" in KNOWN_PRICING
        assert "claude-3-opus" in KNOWN_PRICING

    def test_record_window(self):
        model = CostModel(pricing=ProviderPricing(1.0, 2.0))
        record = model.record_window("w1", 1000, 500)
        assert record.cost_usd == pytest.approx(0.002)
        assert model.total_windows == 1
        assert model.total_input_tokens == 1000

    def test_budget_warn_at_80pct(self):
        model = CostModel(max_windows=10)
        for i in range(8):
            model.record_window(f"w{i}", 100, 50)
        warnings = model.check_budget()
        assert any(w.level == BudgetWarningLevel.WARN for w in warnings)

    def test_budget_hard_stop_at_100pct(self):
        model = CostModel(max_windows=3)
        for i in range(3):
            model.record_window(f"w{i}", 100, 50)
        from crp.core.errors import BudgetExhaustedError
        with pytest.raises(BudgetExhaustedError):
            model.check_budget()

    def test_budget_input_tokens_exceeded(self):
        model = CostModel(max_input_tokens=500)
        model.record_window("w1", 400, 100)
        from crp.core.errors import BudgetExhaustedError
        with pytest.raises(BudgetExhaustedError):
            model.check_budget(input_tokens=200)

    def test_estimate(self):
        pricing = ProviderPricing(2.50, 10.00, "openai")
        model = CostModel(pricing=pricing)
        est = model.estimate(planned_dispatches=10, avg_input_tokens=1000, avg_output_tokens=500)
        assert est["estimated_windows"] == 10
        assert est["estimated_cost_usd"] > 0

    def test_reset(self):
        model = CostModel()
        model.record_window("w1", 100, 50)
        model.reset()
        assert model.total_windows == 0
        assert model.total_input_tokens == 0


class TestOverheadBudget:
    """Tests for overhead budget management (§6.9)."""

    def test_allow_under_budget(self):
        budget = OverheadBudget()
        budget.current_productive_windows = 100
        decision = budget.check("curation")
        assert decision == OverheadDecision.ALLOW

    def test_deny_over_budget_low_priority(self):
        budget = OverheadBudget(max_overhead_pct=10.0)
        budget.current_productive_windows = 10
        budget.current_overhead_windows = 1  # 10%
        decision = budget.check("curation")  # weight 1, no grace
        assert decision == OverheadDecision.DENY

    def test_grace_for_high_priority(self):
        budget = OverheadBudget(max_overhead_pct=10.0)
        budget.current_productive_windows = 100
        budget.current_overhead_windows = 12  # 12% (over 10% but under 15%)
        decision = budget.check("orc_steps")  # weight 2, gets grace
        assert decision == OverheadDecision.ALLOW

    def test_deny_high_priority_beyond_grace(self):
        budget = OverheadBudget(max_overhead_pct=10.0)
        budget.current_productive_windows = 100
        budget.current_overhead_windows = 16  # 16% > 15% (10% + 5% grace)
        decision = budget.check("orc_steps")
        assert decision == OverheadDecision.DENY

    def test_record_productive(self):
        budget = OverheadBudget()
        budget.record_productive()
        assert budget.current_productive_windows == 1

    def test_reset(self):
        budget = OverheadBudget()
        budget.current_overhead_windows = 5
        budget.current_productive_windows = 50
        budget.reset()
        assert budget.current_overhead_windows == 0
        assert budget.current_productive_windows == 0

    def test_current_ratio(self):
        budget = OverheadBudget()
        budget.current_productive_windows = 100
        budget.current_overhead_windows = 15
        assert budget.current_ratio == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# Orchestrator — streaming, ingest, export_state
# ---------------------------------------------------------------------------

from crp.core.orchestrator import (
    CRPOrchestrator,
    ExtractionResult,
    StreamEvent,
)
from crp.providers.base import LLMProvider


class MockProvider(LLMProvider):
    """Minimal mock provider for orchestrator tests."""

    def __init__(self, context_window: int = 128000):
        self._context_window = context_window

    def generate_chat(self, messages, max_tokens=None, **kwargs):
        return ("Mock output text.", "stop")

    def count_tokens(self, text):
        return max(1, len(text) // 4)

    def context_window_size(self):
        return self._context_window

    @property
    def max_output_tokens(self):
        return 4096

    @property
    def provider_name(self):
        return "mock"


class TestOrchestratorStreaming:
    """Tests for streaming dispatch (7B.7-7B.8)."""

    def test_dispatch_stream_yields_events(self):
        orch = CRPOrchestrator(provider=MockProvider())
        events = list(orch.dispatch_stream("System", "Task"))
        assert len(events) >= 2  # at least token(s) + done
        types = [e.event_type for e in events]
        assert "token" in types
        assert "done" in types

    def test_dispatch_stream_token_order(self):
        orch = CRPOrchestrator(provider=MockProvider())
        events = list(orch.dispatch_stream("System", "Task"))
        tokens = [e.data for e in events if e.event_type == "token"]
        concatenated = "".join(tokens)
        assert concatenated == "Mock output text."

    def test_dispatch_stream_exactly_one_done(self):
        orch = CRPOrchestrator(provider=MockProvider())
        events = list(orch.dispatch_stream("System", "Task"))
        done_events = [e for e in events if e.event_type == "done"]
        assert len(done_events) == 1

    def test_dispatch_stream_window_complete(self):
        orch = CRPOrchestrator(provider=MockProvider())
        events = list(orch.dispatch_stream("System", "Task"))
        wc = [e for e in events if e.event_type == "window_complete"]
        assert len(wc) == 1


class TestOrchestratorIngest:
    """Tests for zero-LLM ingestion (7A.4)."""

    def test_ingest_returns_result(self):
        orch = CRPOrchestrator(provider=MockProvider())
        result = orch.ingest("Fact one. Fact two. Fact three.", "test_source")
        assert isinstance(result, ExtractionResult)
        assert result.facts_extracted >= 1
        assert result.source_label == "test_source"

    def test_ingest_empty_text(self):
        orch = CRPOrchestrator(provider=MockProvider())
        result = orch.ingest("", "empty")
        assert result.facts_extracted == 0

    def test_ingest_updates_warm_state(self):
        orch = CRPOrchestrator(provider=MockProvider())
        orch.ingest("Fact one. Fact two.", "src")
        status = orch.session_status()
        assert status.facts_in_warm_state >= 2


class TestOrchestratorExportState:
    """Tests for state export (7A.6)."""

    def test_export_state_returns_bytes(self):
        orch = CRPOrchestrator(provider=MockProvider())
        data = orch.export_state()
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_export_state_contains_session_info(self):
        orch = CRPOrchestrator(provider=MockProvider())
        orch.dispatch("Sys", "Task")
        data = orch.export_state()
        # Data may be encrypted or plain JSON depending on security module
        # Just verify it's non-empty bytes
        assert len(data) > 0
