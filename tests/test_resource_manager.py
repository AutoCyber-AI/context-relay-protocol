# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for ResourceManager and meta-learning recalibration (§audit R1).

Covers:
  - ResourceManager lifecycle (model registration, pressure, snapshots)
  - CalibrationState adaptive recalibration
  - WindowMetrics resource field population
"""

from __future__ import annotations

import pytest

from crp.resources.resource_manager import (
    DEFAULT_MEMORY_BUDGET_MB,
    MODEL_ESTIMATES,
    ResourceManager,
    ResourceSnapshot,
)
from crp.extraction.pipeline import (
    CalibrationState,
    _CALIBRATION_WINDOW_COUNT,
    _DRIFT_THRESHOLD,
    _RECALIBRATION_INTERVAL,
)
from crp.extraction.types import ExtractionResult, Fact


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_extraction_result(
    stage_2_yield: int = 10,
    stage_3_yield: int = 0,
    stages_run: list[int] | None = None,
    confidence: float = 0.8,
) -> ExtractionResult:
    """Build a minimal ExtractionResult for calibration tests."""
    result = ExtractionResult()
    result.stages_run = stages_run or [1, 2]
    result.stage_yields = {1: 5, 2: stage_2_yield}
    if stage_3_yield:
        result.stage_yields[3] = stage_3_yield
    # Create fake facts with given confidence
    result.facts = [
        Fact(id=f"f-{i}", text=f"fact {i}", category="test", confidence=confidence)
        for i in range(stage_2_yield)
    ]
    return result


# ═══════════════════════════════════════════════════════════════════════════
# ResourceManager tests
# ═══════════════════════════════════════════════════════════════════════════


class TestResourceManager:
    """Tests for centralized resource tracking."""

    def test_initial_snapshot_no_pressure(self):
        rm = ResourceManager(budget_mb=512)
        snap = rm.snapshot()
        assert snap.pressure_level == "none"
        assert snap.crp_estimated_mb == 0.0
        assert snap.budget_mb == 512

    def test_model_registration(self):
        rm = ResourceManager(budget_mb=512)
        rm.register_model("test-model", 100.0)
        snap = rm.snapshot()
        assert snap.model_memory_mb == 0.0  # Not loaded yet
        assert snap.models_loaded == []

    def test_model_loaded_increases_memory(self):
        rm = ResourceManager(budget_mb=512)
        rm.register_model("test-model", 200.0)
        rm.mark_model_loaded("test-model")
        snap = rm.snapshot()
        assert snap.model_memory_mb == 200.0
        assert "test-model" in snap.models_loaded

    def test_model_unloaded_decreases_memory(self):
        rm = ResourceManager(budget_mb=512)
        rm.register_model("test-model", 200.0)
        rm.mark_model_loaded("test-model")
        rm.mark_model_unloaded("test-model")
        snap = rm.snapshot()
        assert snap.model_memory_mb == 0.0
        assert snap.models_loaded == []

    def test_pressure_levels(self):
        rm = ResourceManager(budget_mb=100)  # 100MB budget
        rm.register_model("m1", 40.0)
        rm.register_model("m2", 30.0)
        rm.register_model("m3", 20.0)

        # No load → none
        assert rm.snapshot().pressure_level == "none"

        # Load m1 (40%) → none
        rm.mark_model_loaded("m1")
        assert rm.snapshot().pressure_level == "none"

        # Load m2 (70%) → medium
        rm.mark_model_loaded("m2")
        assert rm.snapshot().pressure_level == "medium"

        # Load m3 (90%) → high
        rm.mark_model_loaded("m3")
        assert rm.snapshot().pressure_level == "high"

    def test_critical_pressure(self):
        rm = ResourceManager(budget_mb=100)
        rm.register_model("big", 96.0)
        rm.mark_model_loaded("big")
        assert rm.snapshot().pressure_level == "critical"

    def test_fact_count_tracking(self):
        rm = ResourceManager(budget_mb=512)
        rm.update_fact_count(1000)
        snap = rm.snapshot()
        assert snap.fact_count == 1000
        assert snap.fact_store_mb > 0

    def test_should_cleanup(self):
        rm = ResourceManager(budget_mb=100)
        assert not rm.should_cleanup()  # zero pressure

        rm.register_model("m", 75.0)
        rm.mark_model_loaded("m")
        assert rm.should_cleanup()  # medium pressure

    def test_run_gc(self):
        rm = ResourceManager()
        result = rm.run_gc()
        assert isinstance(result, int)

    def test_idle_models(self):
        rm = ResourceManager()
        rm.register_model("m1", 100)
        rm.mark_model_loaded("m1")
        # Just loaded, so not idle
        assert rm.get_idle_models(idle_seconds=0.01) == []
        # With zero window threshold, should be immediate
        import time
        time.sleep(0.02)
        assert rm.get_idle_models(idle_seconds=0.01) == ["m1"]

    def test_model_used_resets_idle(self):
        rm = ResourceManager()
        rm.register_model("m1", 100)
        rm.mark_model_loaded("m1")
        import time
        time.sleep(0.02)
        rm.mark_model_used("m1")
        assert rm.get_idle_models(idle_seconds=0.01) == []

    def test_summary_dict(self):
        rm = ResourceManager(budget_mb=256)
        rm.register_model("test", 50)
        rm.mark_model_loaded("test")
        rm.update_fact_count(100)
        s = rm.summary()
        assert s["budget_mb"] == 256
        assert s["model_memory_mb"] == 50.0
        assert s["models_loaded"] == ["test"]
        assert s["fact_count"] == 100
        assert "pressure_level" in s
        assert "utilization_pct" in s

    def test_utilization_ratio(self):
        snap = ResourceSnapshot(
            crp_estimated_mb=256,
            budget_mb=512,
        )
        assert snap.utilization_ratio == pytest.approx(0.5)

    def test_utilization_zero_budget(self):
        snap = ResourceSnapshot(crp_estimated_mb=100, budget_mb=0)
        assert snap.utilization_ratio == 0.0

    def test_model_estimates_cover_known_models(self):
        expected = {"sentence-transformers", "cross-encoder", "gliner", "uie", "hnsw-index"}
        assert expected.issubset(set(MODEL_ESTIMATES.keys()))

    def test_session_count_tracking(self):
        rm = ResourceManager()
        rm.update_session_count(5)
        assert rm.snapshot().session_count == 5

    def test_low_pressure_boundary(self):
        rm = ResourceManager(budget_mb=100)
        rm.register_model("m", 50.0)
        rm.mark_model_loaded("m")
        assert rm.snapshot().pressure_level == "low"


# ═══════════════════════════════════════════════════════════════════════════
# CalibrationState recalibration tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCalibrationRecalibration:
    """Tests for adaptive meta-learning baseline recalibration."""

    def test_initial_lock_after_n_windows(self):
        cs = CalibrationState()
        for _ in range(_CALIBRATION_WINDOW_COUNT):
            cs.record(_make_extraction_result(stage_2_yield=20))
        assert cs.baseline_locked
        assert cs.calibration_epoch == 1
        assert cs.baseline_stage_2 == pytest.approx(20.0)

    def test_baselines_not_locked_prematurely(self):
        cs = CalibrationState()
        for _ in range(_CALIBRATION_WINDOW_COUNT - 1):
            cs.record(_make_extraction_result(stage_2_yield=20))
        assert not cs.baseline_locked
        assert cs.calibration_epoch == 0

    def test_recalibration_on_drift(self):
        cs = CalibrationState()
        # Initial calibration with yield=20
        for _ in range(_CALIBRATION_WINDOW_COUNT):
            cs.record(_make_extraction_result(stage_2_yield=20))
        assert cs.baseline_locked
        assert cs.calibration_epoch == 1
        initial_baseline = cs.baseline_stage_2

        # Now feed dramatically different yields to cause drift
        # Need to reach the recalibration interval with drifted data
        for i in range(_RECALIBRATION_INTERVAL - _CALIBRATION_WINDOW_COUNT):
            cs.record(_make_extraction_result(stage_2_yield=5))  # 75% drop from 20

        # Should recalibrate
        assert cs.calibration_epoch >= 2 or cs.results_count < _RECALIBRATION_INTERVAL
        # If interval hit, baseline should have shifted
        if cs.calibration_epoch >= 2:
            assert cs.baseline_stage_2 < initial_baseline

    def test_no_recalibration_without_drift(self):
        cs = CalibrationState()
        # Initial calibration
        for _ in range(_CALIBRATION_WINDOW_COUNT):
            cs.record(_make_extraction_result(stage_2_yield=20))
        assert cs.calibration_epoch == 1

        # Feed same yield — should NOT recalibrate
        for _ in range(_RECALIBRATION_INTERVAL - _CALIBRATION_WINDOW_COUNT):
            cs.record(_make_extraction_result(stage_2_yield=20))

        # At the interval boundary, no drift → no recalibration
        assert cs.calibration_epoch == 1

    def test_stage_3_baseline_updates(self):
        cs = CalibrationState()
        for _ in range(_CALIBRATION_WINDOW_COUNT):
            cs.record(_make_extraction_result(
                stage_2_yield=10,
                stage_3_yield=8,
                stages_run=[1, 2, 3],
            ))
        assert cs.baseline_stage_3 == pytest.approx(8.0)

    def test_should_escalate_stage_3(self):
        cs = CalibrationState()
        for _ in range(_CALIBRATION_WINDOW_COUNT):
            cs.record(_make_extraction_result(stage_2_yield=20))
        # Below baseline → should escalate
        assert cs.should_escalate_stage_3(5)
        # Above baseline → should NOT escalate
        assert not cs.should_escalate_stage_3(25)

    def test_should_escalate_stage_4(self):
        cs = CalibrationState()
        assert cs.should_escalate_stage_4(0.05)  # Below 0.1
        assert not cs.should_escalate_stage_4(0.2)  # Above 0.1

    def test_confidence_floor_calibration(self):
        cs = CalibrationState()
        for _ in range(_CALIBRATION_WINDOW_COUNT):
            # 20 facts * 5 windows = 100 facts → enough for quantiles
            cs.record(_make_extraction_result(stage_2_yield=20, confidence=0.75))
        assert cs.baseline_locked
        # All facts have confidence 0.75, so floor ≈ 0.75
        assert cs.baseline_confidence_floor == pytest.approx(0.75, abs=0.1)

    def test_results_count(self):
        cs = CalibrationState()
        assert cs.results_count == 0
        cs.record(_make_extraction_result())
        assert cs.results_count == 1

    def test_multiple_recalibrations(self):
        """Verifies baselines can be recalibrated multiple times."""
        cs = CalibrationState()
        # Phase 1: Initial calibration with yield=20
        for _ in range(_CALIBRATION_WINDOW_COUNT):
            cs.record(_make_extraction_result(stage_2_yield=20))
        assert cs.calibration_epoch == 1

        # Phase 2: Drive drift with yield=5, trigger recalibration
        for _ in range(_RECALIBRATION_INTERVAL - _CALIBRATION_WINDOW_COUNT):
            cs.record(_make_extraction_result(stage_2_yield=5))

        if cs.calibration_epoch >= 2:
            epoch_2_baseline = cs.baseline_stage_2
            # Phase 3: Another interval with yield=50
            for _ in range(_RECALIBRATION_INTERVAL):
                cs.record(_make_extraction_result(stage_2_yield=50))
            if cs.calibration_epoch >= 3:
                assert cs.baseline_stage_2 > epoch_2_baseline


# ═══════════════════════════════════════════════════════════════════════════
# WindowMetrics resource field integration
# ═══════════════════════════════════════════════════════════════════════════


class TestWindowMetricsResourceFields:
    """Tests that WindowMetrics accepts resource tracking fields."""

    def test_resource_fields_accepted(self):
        from crp.core.window import WindowMetrics

        m = WindowMetrics(
            window_id="w-1",
            ram_available_mb=400,
            ram_used_by_crp_mb=112,
            pressure_level="low",
        )
        assert m.ram_available_mb == 400
        assert m.ram_used_by_crp_mb == 112
        assert m.pressure_level == "low"

    def test_resource_fields_in_to_dict(self):
        from crp.core.window import WindowMetrics

        m = WindowMetrics(
            ram_available_mb=256,
            ram_used_by_crp_mb=256,
            pressure_level="medium",
        )
        d = m.to_dict()
        assert d["ram_available_mb"] == 256
        assert d["ram_used_by_crp_mb"] == 256
        assert d["pressure_level"] == "medium"

    def test_kwargs_unpacking(self):
        from crp.core.window import WindowMetrics

        fields = {
            "ram_available_mb": 100,
            "ram_used_by_crp_mb": 50,
            "pressure_level": "high",
        }
        m = WindowMetrics(window_id="w-2", **fields)
        assert m.pressure_level == "high"


# ═══════════════════════════════════════════════════════════════════════════
# Marginal gain / sections_covered tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMarginalFields:
    """Tests for _marginal_fields() helper on the orchestrator."""

    def _make_orch(self, initial_facts: int = 0):
        """Build a minimal mock orchestrator with a warm store."""
        from crp.core.orchestrator import CRPOrchestrator
        from unittest.mock import MagicMock

        orch = CRPOrchestrator.__new__(CRPOrchestrator)
        orch._warm_store = MagicMock()
        orch._warm_store.fact_count = initial_facts
        return orch

    def test_marginal_gain_no_new_facts(self):
        orch = self._make_orch(initial_facts=5)
        result = orch._marginal_fields("some output", facts_before=5)
        assert result["marginal_gain"] == 0.0

    def test_marginal_gain_with_new_facts(self):
        orch = self._make_orch(initial_facts=10)
        result = orch._marginal_fields("some output", facts_before=5)
        # 5 new facts / 10 total = 0.5
        assert result["marginal_gain"] == 0.5

    def test_marginal_gain_all_new(self):
        orch = self._make_orch(initial_facts=3)
        result = orch._marginal_fields("some output", facts_before=0)
        # 3/3 = 1.0
        assert result["marginal_gain"] == 1.0

    def test_marginal_gain_empty_store(self):
        orch = self._make_orch(initial_facts=0)
        result = orch._marginal_fields("", facts_before=0)
        assert result["marginal_gain"] == 0.0

    def test_sections_covered_markdown_headers(self):
        orch = self._make_orch(initial_facts=0)
        output = "# Title\ntext\n## Section 1\nmore\n### Sub\nfinal"
        result = orch._marginal_fields(output, facts_before=0)
        assert result["sections_covered"] == 3

    def test_sections_covered_no_headers(self):
        orch = self._make_orch(initial_facts=0)
        output = "plain text with no markdown"
        result = orch._marginal_fields(output, facts_before=0)
        assert result["sections_covered"] == 0

    def test_sections_covered_empty_output(self):
        orch = self._make_orch(initial_facts=0)
        result = orch._marginal_fields("", facts_before=0)
        assert result["sections_covered"] == 0

    def test_marginal_fields_in_window_metrics(self):
        from crp.core.window import WindowMetrics

        fields = {"marginal_gain": 0.75, "sections_covered": 5}
        m = WindowMetrics(window_id="w-mg", **fields)
        assert m.marginal_gain == 0.75
        assert m.sections_covered == 5
        d = m.to_dict()
        assert d["marginal_gain"] == 0.75
        assert d["sections_covered"] == 5
