# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for AdaptiveAllocator — efficiency-first pipeline tuning.

Philosophy: CRP is an EFFICIENCY protocol, not a speed protocol.
ML stages (GLiNER, UIE, Discourse) are core intelligence and are
NEVER disabled.  Under pressure, the system throttles throughput
(fewer facts per stage, larger batches) rather than cutting capability.

Covers:
  - Hardware detection
  - Overhead recording and EWMA smoothing
  - ML stages are NEVER disabled (core intelligence protection)
  - Throughput level adaptation (normal → throttled → constrained)
  - Extraction profile: stages always on, facts-per-stage throttled
  - Envelope profile: CKF always on, batch sizes adapted
  - Prompt efficiency (caching, dedup, connection reuse)
  - Protected intelligence features never shed
  - Feature shedding only for optimization features
  - Model unloading decisions
  - GC trigger decisions
  - Consecutive over-cap tracking
  - Overhead trend queries
  - Summary diagnostics
  - WindowMetrics allocator fields population
  - ResourceManager mark_unloaded / trigger_gc
"""

from __future__ import annotations

import pytest

from crp.resources.adaptive_allocator import (
    AdaptiveAllocator,
    EnvelopeProfile,
    ExtractionProfile,
    PromptEfficiency,
    WindowOverheadRecord,
    detect_hardware,
    THROUGHPUT_NORMAL,
    THROUGHPUT_THROTTLED,
    THROUGHPUT_CONSTRAINED,
)
from crp.resources.overhead_manager import (
    OverheadBudgetManager,
    PROTECTED_INTELLIGENCE,
    SHEDDING_CASCADE,
)
from crp.resources.resource_manager import ResourceManager


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def rm():
    """Fresh ResourceManager with 512 MB budget."""
    mgr = ResourceManager(budget_mb=512)
    return mgr


@pytest.fixture
def om():
    """Fresh OverheadBudgetManager with 15% cap."""
    return OverheadBudgetManager(max_overhead_pct=15.0)


@pytest.fixture
def alloc(rm, om):
    """AdaptiveAllocator with default configuration."""
    return AdaptiveAllocator(
        resource_manager=rm,
        overhead_manager=om,
        overhead_cap_pct=15.0,
        idle_model_timeout_s=300.0,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Hardware detection
# ═══════════════════════════════════════════════════════════════════════════

class TestHardwareDetection:
    def test_detect_hardware_returns_dict(self):
        hw = detect_hardware()
        assert isinstance(hw, dict)
        assert "cpu_count" in hw
        assert "total_ram_mb" in hw
        assert "available_ram_mb" in hw
        assert hw["cpu_count"] >= 1

    def test_allocator_exposes_hardware(self, alloc):
        hw = alloc.hardware
        assert isinstance(hw, dict)
        assert hw["cpu_count"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# Overhead recording
# ═══════════════════════════════════════════════════════════════════════════

class TestOverheadRecording:
    def test_record_window_returns_record(self, alloc):
        rec = alloc.record_window(total_ms=1000, llm_ms=850)
        assert isinstance(rec, WindowOverheadRecord)
        assert rec.window_index == 1
        assert rec.overhead_ms == 150.0
        assert rec.overhead_pct == 15.0

    def test_ewma_updates_on_first_window(self, alloc):
        alloc.record_window(total_ms=1000, llm_ms=800)
        assert alloc.ewma_overhead_pct == 20.0

    def test_ewma_smooths_over_time(self, alloc):
        alloc.record_window(total_ms=1000, llm_ms=800)  # 20%
        alloc.record_window(total_ms=1000, llm_ms=900)  # 10%
        # EWMA: 0.3 * 10 + 0.7 * 20 = 3 + 14 = 17
        assert abs(alloc.ewma_overhead_pct - 17.0) < 0.1

    def test_window_count_increments(self, alloc):
        assert alloc.window_count == 0
        alloc.record_window(total_ms=500, llm_ms=450)
        assert alloc.window_count == 1
        alloc.record_window(total_ms=500, llm_ms=450)
        assert alloc.window_count == 2

    def test_record_includes_envelope_extraction_ms(self, alloc):
        rec = alloc.record_window(
            total_ms=1000, llm_ms=850,
            envelope_ms=60, extraction_ms=40,
        )
        assert rec.envelope_ms == 60.0
        assert rec.extraction_ms == 40.0


# ═══════════════════════════════════════════════════════════════════════════
# Consecutive over-cap tracking
# ═══════════════════════════════════════════════════════════════════════════

class TestConsecutiveOverCap:
    def test_consecutive_over_resets_on_good_window(self, alloc):
        alloc.record_window(total_ms=1000, llm_ms=800)  # 20% > 15%
        alloc.record_window(total_ms=1000, llm_ms=800)  # 20% > 15%
        assert alloc.consecutive_over_cap == 2
        alloc.record_window(total_ms=1000, llm_ms=900)  # 10% < 15%
        assert alloc.consecutive_over_cap == 0

    def test_consecutive_over_triggers_constrained_throughput(self, alloc):
        # 3 consecutive windows over cap → constrained throughput
        for _ in range(3):
            alloc.record_window(total_ms=1000, llm_ms=800)
        assert alloc.consecutive_over_cap >= 3
        assert alloc.throughput_level == THROUGHPUT_CONSTRAINED


# ═══════════════════════════════════════════════════════════════════════════
# Extraction profile
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractionProfile:
    def test_default_profile_all_stages_enabled(self, alloc):
        profile = alloc.extraction_profile()
        assert profile.enable_stage_3 is True
        assert profile.enable_stage_4 is True
        assert profile.enable_stage_5 is True
        assert profile.enable_stage_6 is False  # always off
        assert profile.max_facts_per_stage == 200

    def test_stages_never_disabled_under_overhead(self, alloc):
        """ML stages stay ON even after sustained overhead — throttle, don't cut."""
        for _ in range(10):
            alloc.record_window(total_ms=1000, llm_ms=700,
                                extraction_ms=200)
        profile = alloc.extraction_profile()
        assert profile.enable_stage_3 is True  # GLiNER always on
        assert profile.enable_stage_4 is True  # UIE always on
        assert profile.enable_stage_5 is True  # Discourse always on
        # But facts-per-stage is throttled
        assert profile.max_facts_per_stage < 200

    def test_throttled_profile_reduces_facts(self, alloc):
        alloc.record_window(total_ms=1000, llm_ms=800)  # triggers throttle
        profile = alloc.extraction_profile()
        assert profile.max_facts_per_stage == 150

    def test_constrained_profile_reduces_facts_further(self, alloc):
        for _ in range(3):
            alloc.record_window(total_ms=1000, llm_ms=800)
        profile = alloc.extraction_profile()
        assert profile.max_facts_per_stage == 100


# ═══════════════════════════════════════════════════════════════════════════
# Envelope profile
# ═══════════════════════════════════════════════════════════════════════════

class TestEnvelopeProfile:
    def test_default_envelope_profile(self, alloc):
        profile = alloc.envelope_profile()
        assert profile.enable_ckf is True
        assert profile.max_packing_facts == 500
        assert profile.embedding_batch_size == 32

    def test_throttled_envelope_adapts_batch_and_packing(self, alloc):
        alloc.record_window(total_ms=1000, llm_ms=800)  # triggers throttle
        profile = alloc.envelope_profile()
        assert profile.enable_ckf is True
        assert profile.max_packing_facts == 350
        assert profile.embedding_batch_size == 48

    def test_constrained_envelope_tighter_limits(self, alloc):
        for _ in range(3):
            alloc.record_window(total_ms=1000, llm_ms=800)
        profile = alloc.envelope_profile()
        assert profile.enable_ckf is True  # CKF never disabled
        assert profile.max_packing_facts == 200
        assert profile.embedding_batch_size == 64

    def test_ckf_never_disabled_under_shedding(self, alloc):
        for _ in range(10):
            alloc.record_window(total_ms=1000, llm_ms=700)
        profile = alloc.envelope_profile()
        assert profile.enable_ckf is True
        assert isinstance(profile.enable_cross_encoder, bool)


# ═══════════════════════════════════════════════════════════════════════════
# ML stages NEVER disabled (core intelligence protection)
# ═══════════════════════════════════════════════════════════════════════════

class TestMLStageProtection:
    """Core test: ML stages must NEVER be disabled, regardless of pressure."""

    def test_stages_always_enabled_under_sustained_overhead(self, alloc):
        for _ in range(10):
            alloc.record_window(total_ms=1000, llm_ms=700,
                                extraction_ms=200)
        profile = alloc.extraction_profile()
        assert profile.enable_stage_3 is True  # GLiNER
        assert profile.enable_stage_4 is True  # UIE
        assert profile.enable_stage_5 is True  # Discourse

    def test_stages_always_enabled_under_extreme_overhead(self, alloc):
        for _ in range(20):
            alloc.record_window(total_ms=1000, llm_ms=500,
                                extraction_ms=400)
        profile = alloc.extraction_profile()
        assert profile.enable_stage_3 is True
        assert profile.enable_stage_4 is True
        assert profile.enable_stage_5 is True

    def test_disabled_stages_always_empty(self, alloc):
        assert alloc.disabled_stages == set()
        for _ in range(10):
            alloc.record_window(total_ms=1000, llm_ms=700)
        assert alloc.disabled_stages == set()

    def test_ckf_always_enabled(self, alloc):
        for _ in range(10):
            alloc.record_window(total_ms=1000, llm_ms=700)
        profile = alloc.envelope_profile()
        assert profile.enable_ckf is True

    def test_record_never_shows_skipped_stages(self, alloc):
        for _ in range(10):
            rec = alloc.record_window(total_ms=1000, llm_ms=700)
        assert rec.stages_skipped == []


# ═══════════════════════════════════════════════════════════════════════════
# Protected intelligence features never shed
# ═══════════════════════════════════════════════════════════════════════════

class TestProtectedIntelligence:
    def test_protected_intelligence_set_exists(self):
        assert "gliner" in PROTECTED_INTELLIGENCE
        assert "uie" in PROTECTED_INTELLIGENCE
        assert "discourse" in PROTECTED_INTELLIGENCE

    def test_gliner_never_shed(self, om):
        for _ in range(20):
            om.update_overhead(99.0)
        assert om.is_feature_enabled("gliner") is True

    def test_uie_never_shed(self, om):
        for _ in range(20):
            om.update_overhead(99.0)
        assert om.is_feature_enabled("uie") is True

    def test_discourse_never_shed(self, om):
        for _ in range(20):
            om.update_overhead(99.0)
        assert om.is_feature_enabled("discourse") is True

    def test_only_optimization_features_shed(self, om):
        for _ in range(20):
            om.update_overhead(99.0)
        assert om.is_feature_enabled("community_detection") is False
        assert om.is_feature_enabled("cross_encoder") is False
        assert om.is_feature_enabled("gliner") is True
        assert om.is_feature_enabled("uie") is True
        assert om.is_feature_enabled("discourse") is True


# ═══════════════════════════════════════════════════════════════════════════
# Throughput level adaptation
# ═══════════════════════════════════════════════════════════════════════════

class TestThroughputAdaptation:
    def test_initial_throughput_is_normal(self, alloc):
        assert alloc.throughput_level == THROUGHPUT_NORMAL

    def test_overhead_spike_throttles(self, alloc):
        alloc.record_window(total_ms=1000, llm_ms=800)
        assert alloc.throughput_level == THROUGHPUT_THROTTLED

    def test_sustained_overhead_constrains(self, alloc):
        for _ in range(3):
            alloc.record_window(total_ms=1000, llm_ms=800)
        assert alloc.throughput_level == THROUGHPUT_CONSTRAINED

    def test_throughput_restores_when_overhead_drops(self, alloc):
        for _ in range(3):
            alloc.record_window(total_ms=1000, llm_ms=800)
        assert alloc.throughput_level == THROUGHPUT_CONSTRAINED
        for _ in range(5):
            alloc.record_window(total_ms=1000, llm_ms=950)
        assert alloc.throughput_level in (THROUGHPUT_THROTTLED, THROUGHPUT_NORMAL)

    def test_throughput_fully_restores(self, alloc):
        for _ in range(3):
            alloc.record_window(total_ms=1000, llm_ms=800)
        for _ in range(20):
            alloc.record_window(total_ms=1000, llm_ms=990)
        assert alloc.throughput_level == THROUGHPUT_NORMAL


# ═══════════════════════════════════════════════════════════════════════════
# Prompt efficiency
# ═══════════════════════════════════════════════════════════════════════════

class TestPromptEfficiency:
    def test_initial_no_caching(self, alloc):
        eff = alloc.prompt_efficiency()
        assert isinstance(eff, PromptEfficiency)
        assert eff.cache_system_prompt is False
        assert eff.estimated_cache_hit_pct == 0.0

    def test_caching_after_two_windows(self, alloc):
        alloc.record_window(total_ms=1000, llm_ms=900)
        alloc.record_window(total_ms=1000, llm_ms=900)
        eff = alloc.prompt_efficiency()
        assert eff.cache_system_prompt is True
        assert eff.estimated_cache_hit_pct > 0.0

    def test_dedup_always_on(self, alloc):
        assert alloc.prompt_efficiency().deduplicate_facts is True

    def test_connection_reuse_always_on(self, alloc):
        assert alloc.prompt_efficiency().reuse_connection is True

    def test_compression_on_when_constrained(self, alloc):
        for _ in range(3):
            alloc.record_window(total_ms=1000, llm_ms=800)
        assert alloc.prompt_efficiency().compress_envelope is True

    def test_cache_hit_capped_at_90(self, alloc):
        for _ in range(6):
            alloc.record_window(total_ms=1000, llm_ms=900)
        assert alloc.prompt_efficiency().estimated_cache_hit_pct == 90.0


# ═══════════════════════════════════════════════════════════════════════════
# Model lifecycle
# ═══════════════════════════════════════════════════════════════════════════

class TestModelLifecycle:
    def test_should_unload_models_low_pressure(self, alloc):
        # With no idle models and low pressure, should not unload
        result = alloc.should_unload_models()
        assert isinstance(result, bool)

    def test_idle_models_returns_list(self, alloc):
        result = alloc.idle_models()
        assert isinstance(result, list)

    def test_should_run_gc_at_normal_pressure(self, alloc):
        assert alloc.should_run_gc() is False  # default is "none" pressure


# ═══════════════════════════════════════════════════════════════════════════
# ResourceManager mark_unloaded / trigger_gc
# ═══════════════════════════════════════════════════════════════════════════

class TestResourceManagerExtensions:
    def test_mark_unloaded(self, rm):
        rm.register_model("test_model", 100)
        rm.mark_model_loaded("test_model")
        snap1 = rm.snapshot()
        assert len(snap1.models_loaded) > 0

        rm.mark_unloaded("test_model")
        snap2 = rm.snapshot()
        assert len(snap2.models_loaded) < len(snap1.models_loaded)

    def test_mark_unloaded_nonexistent_model(self, rm):
        # Should not raise
        rm.mark_unloaded("nonexistent")

    def test_trigger_gc_low_pressure(self, rm):
        # Low pressure = no GC triggered
        collected = rm.trigger_gc()
        assert collected == 0

    def test_trigger_gc_high_pressure(self, rm):
        # Force high pressure by registering huge models
        rm.register_model("huge_model", 500)
        rm.mark_model_loaded("huge_model")
        collected = rm.trigger_gc()
        assert isinstance(collected, int)


# ═══════════════════════════════════════════════════════════════════════════
# Overhead trend
# ═══════════════════════════════════════════════════════════════════════════

class TestOverheadTrend:
    def test_empty_trend(self, alloc):
        assert alloc.overhead_trend() == []

    def test_trend_tracks_recent_windows(self, alloc):
        for i in range(10):
            alloc.record_window(total_ms=1000, llm_ms=850 + i)
        trend = alloc.overhead_trend(last_n=5)
        assert len(trend) == 5


# ═══════════════════════════════════════════════════════════════════════════
# Summary / diagnostics
# ═══════════════════════════════════════════════════════════════════════════

class TestSummary:
    def test_summary_returns_all_expected_keys(self, alloc):
        alloc.record_window(total_ms=1000, llm_ms=850)
        s = alloc.summary()
        assert "overhead_cap_pct" in s
        assert "ewma_overhead_pct" in s
        assert "window_count" in s
        assert "consecutive_over_cap" in s
        assert "disabled_stages" in s
        assert "throughput_level" in s
        assert "hardware" in s
        assert "feature_shedding" in s
        assert "resource_pressure" in s
        assert "overhead_trend" in s
        assert "prompt_efficiency" in s
        assert s["window_count"] == 1
        assert s["disabled_stages"] == []  # ML stages never disabled

    def test_summary_includes_throughput_level(self, alloc):
        s = alloc.summary()
        assert s["throughput_level"] == THROUGHPUT_NORMAL
        for _ in range(3):
            alloc.record_window(total_ms=1000, llm_ms=800)
        s = alloc.summary()
        assert s["throughput_level"] == THROUGHPUT_CONSTRAINED

    def test_summary_reflects_state_changes(self, alloc):
        for _ in range(5):
            alloc.record_window(total_ms=1000, llm_ms=700)
        s = alloc.summary()
        assert s["window_count"] == 5
        assert len(s["overhead_trend"]) == 5

    def test_summary_prompt_efficiency(self, alloc):
        for _ in range(3):
            alloc.record_window(total_ms=1000, llm_ms=900)
        s = alloc.summary()
        assert s["prompt_efficiency"]["cache_system_prompt"] is True
        assert s["prompt_efficiency"]["estimated_cache_hit_pct"] > 0.0


# ═══════════════════════════════════════════════════════════════════════════
# History capping
# ═══════════════════════════════════════════════════════════════════════════

class TestHistoryCapping:
    def test_history_does_not_exceed_max(self):
        rm = ResourceManager(budget_mb=512)
        om = OverheadBudgetManager(max_overhead_pct=15.0)
        alloc = AdaptiveAllocator(
            resource_manager=rm,
            overhead_manager=om,
            max_history=5,
        )
        for _ in range(20):
            alloc.record_window(total_ms=1000, llm_ms=850)
        assert alloc.window_count == 20
        trend = alloc.overhead_trend(last_n=100)
        assert len(trend) <= 5


# ═══════════════════════════════════════════════════════════════════════════
# WindowMetrics integration
# ═══════════════════════════════════════════════════════════════════════════

class TestWindowMetricsFields:
    def test_window_metrics_has_allocator_fields(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics(
            adaptive_ewma_overhead_pct=12.5,
            adaptive_features_shed=2,
            adaptive_stages_disabled="",
            adaptive_consecutive_over=3,
        )
        assert m.adaptive_ewma_overhead_pct == 12.5
        assert m.adaptive_features_shed == 2
        assert m.adaptive_stages_disabled == ""
        assert m.adaptive_consecutive_over == 3

    def test_window_metrics_to_dict_includes_allocator_fields(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics(
            adaptive_ewma_overhead_pct=10.3,
            adaptive_features_shed=1,
            adaptive_stages_disabled="",
            adaptive_consecutive_over=0,
        )
        d = m.to_dict()
        assert d["adaptive_ewma_overhead_pct"] == 10.3
        assert d["adaptive_features_shed"] == 1
        assert d["adaptive_stages_disabled"] == ""
        assert d["adaptive_consecutive_over"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Zero-division safety
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_zero_total_ms_does_not_crash(self, alloc):
        rec = alloc.record_window(total_ms=0, llm_ms=0)
        assert rec.overhead_pct == 0.0

    def test_negative_overhead_handled(self, alloc):
        # llm_ms > total_ms shouldn't happen, but should not crash
        rec = alloc.record_window(total_ms=100, llm_ms=200)
        assert isinstance(rec.overhead_pct, float)

    def test_custom_overhead_cap(self):
        rm = ResourceManager(budget_mb=512)
        om = OverheadBudgetManager(max_overhead_pct=10.0)
        alloc = AdaptiveAllocator(
            resource_manager=rm,
            overhead_manager=om,
            overhead_cap_pct=10.0,
        )
        alloc.record_window(total_ms=1000, llm_ms=850)  # 15% > 10% cap
        assert alloc.consecutive_over_cap == 1
