# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
"""Tests for Epistemic Profiles (CRP-SPEC-055)."""

from __future__ import annotations

from crp.ep import CalibrationProfile, epistemic_adjust, semantic_entropy


class TestSemanticEntropy:
    def test_single_sample_zero(self) -> None:
        assert semantic_entropy(["answer"]) == 0.0

    def test_identical_samples_zero(self) -> None:
        assert semantic_entropy(["a", "a", "a"]) == 0.0

    def test_diverse_samples_high(self) -> None:
        h = semantic_entropy(["yes", "no", "maybe"])
        assert h > 0.5


class TestCalibrationProfile:
    def test_observe_and_ece(self) -> None:
        p = CalibrationProfile("mock", "math")
        p.observe(0.9, True)
        p.observe(0.9, True)
        p.observe(0.9, False)
        assert p.expected_calibration_error() > 0.0

    def test_overconfident(self) -> None:
        p = CalibrationProfile("mock", "legal")
        for _ in range(10):
            p.observe(0.9, False)
        assert p.overconfident_on()


class TestEpistemicAdjust:
    def test_high_entropy_raises_risk(self) -> None:
        out = epistemic_adjust("A", "LOW", 0.9)
        assert out["risk"] == "MEDIUM"
        assert out["tier"] == "B"

    def test_overconfident_profile_hint(self) -> None:
        p = CalibrationProfile("mock", "math")
        for _ in range(20):
            p.observe(0.9, False)
        out = epistemic_adjust("A", "LOW", 0.1, profile=p)
        assert out["positioning_hint"] is not None
        assert out["risk"] == "MEDIUM"
