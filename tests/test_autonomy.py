# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for autonomy-by-measurement (SPEC-026)."""

from __future__ import annotations

import pytest

from crp.agent.autonomy import (
    AutonomyAction,
    AutonomyDecision,
    AutonomyGovernor,
    AutonomyMetrics,
    AutonomyTier,
)
from crp.security.kill_switch import KillSwitch, KillSwitchReason


class TestAutonomyGovernor:
    def test_t3_autonomous(self) -> None:
        gov = AutonomyGovernor()
        metrics = AutonomyMetrics(
            asr=0.0,
            pass_k=0.95,
            verification_rate=0.95,
            n_samples=40,
        )
        assert gov.assign_tier(metrics) == AutonomyTier.T3_AUTONOMOUS

    def test_t0_due_to_asr(self) -> None:
        gov = AutonomyGovernor()
        metrics = AutonomyMetrics(asr=0.10, pass_k=0.95, verification_rate=0.95, n_samples=40)
        assert gov.assign_tier(metrics) == AutonomyTier.T0_SUPERVISED

    def test_t1_due_to_low_pass_k(self) -> None:
        gov = AutonomyGovernor()
        metrics = AutonomyMetrics(asr=0.0, pass_k=0.80, verification_rate=0.95, n_samples=40)
        assert gov.assign_tier(metrics) == AutonomyTier.T1_CONSTRAINED

    def test_t2_conditional(self) -> None:
        gov = AutonomyGovernor()
        metrics = AutonomyMetrics(asr=0.0, pass_k=0.95, verification_rate=0.80, n_samples=40)
        assert gov.assign_tier(metrics) == AutonomyTier.T2_CONDITIONAL

    def test_t0_due_to_small_sample(self) -> None:
        gov = AutonomyGovernor()
        metrics = AutonomyMetrics(asr=0.0, pass_k=1.0, verification_rate=1.0, n_samples=5)
        assert gov.assign_tier(metrics) == AutonomyTier.T0_SUPERVISED

    def test_t0_read_allowed(self) -> None:
        gov = AutonomyGovernor()
        decision = gov.authorize(AutonomyTier.T0_SUPERVISED, AutonomyAction.READ)
        assert decision.allowed is True

    def test_t0_tool_blocked(self) -> None:
        gov = AutonomyGovernor()
        decision = gov.authorize(AutonomyTier.T0_SUPERVISED, AutonomyAction.TOOL)
        assert decision.allowed is False

    def test_t1_tool_allowed(self) -> None:
        gov = AutonomyGovernor()
        decision = gov.authorize(AutonomyTier.T1_CONSTRAINED, AutonomyAction.TOOL)
        assert decision.allowed is True

    def test_t1_high_risk_blocked(self) -> None:
        gov = AutonomyGovernor()
        decision = gov.authorize(AutonomyTier.T1_CONSTRAINED, AutonomyAction.HIGH_RISK)
        assert decision.allowed is False

    def test_t2_write_allowed(self) -> None:
        gov = AutonomyGovernor()
        decision = gov.authorize(AutonomyTier.T2_CONDITIONAL, AutonomyAction.WRITE)
        assert decision.allowed is True

    def test_t2_delegate_blocked(self) -> None:
        gov = AutonomyGovernor()
        decision = gov.authorize(AutonomyTier.T2_CONDITIONAL, AutonomyAction.DELEGATE)
        assert decision.allowed is False

    def test_t3_all_allowed(self) -> None:
        gov = AutonomyGovernor()
        for action in AutonomyAction:
            decision = gov.authorize(AutonomyTier.T3_AUTONOMOUS, action)
            assert decision.allowed is True

    def test_enforce_fires_kill_switch_on_high_asr(self) -> None:
        ks = KillSwitch()
        gov = AutonomyGovernor()
        metrics = AutonomyMetrics(asr=0.15, pass_k=0.95, verification_rate=0.95, n_samples=40)
        decision = gov.enforce(metrics, AutonomyAction.READ, kill_switch=ks)
        assert ks.is_fired
        assert ks.latest_incident().reason == KillSwitchReason.RUNTIME_ANOMALY.value
        assert decision.allowed is False

    def test_enforce_normal_path(self) -> None:
        ks = KillSwitch()
        gov = AutonomyGovernor()
        metrics = AutonomyMetrics(asr=0.0, pass_k=0.95, verification_rate=0.95, n_samples=40)
        decision = gov.enforce(metrics, AutonomyAction.DELEGATE, kill_switch=ks)
        assert not ks.is_fired
        assert decision.allowed is True
        assert decision.tier == AutonomyTier.T3_AUTONOMOUS

    def test_authorize_accepts_string(self) -> None:
        gov = AutonomyGovernor()
        decision = gov.authorize(AutonomyTier.T1_CONSTRAINED, "tool")
        assert decision.allowed is True

    def test_metrics_clamped(self) -> None:
        m = AutonomyMetrics(asr=-0.1, pass_k=1.5, verification_rate=-0.2, n_samples=-5)
        assert m.asr == 0.0
        assert m.pass_k == 1.0
        assert m.verification_rate == 0.0
        assert m.n_samples == 0

    def test_decision_to_dict(self) -> None:
        d = AutonomyDecision(
            tier=AutonomyTier.T2_CONDITIONAL,
            action="write",
            allowed=True,
            reason="ok",
        ).to_dict()
        assert d["tier"] == "T2_conditional"
        assert d["allowed"] is True
