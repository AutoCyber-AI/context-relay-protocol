# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Mechanism-level tests for the governed-vs-bare benchmark harness.

These tests exercise ``examples/crp_demos/governed_vs_bare.py`` with the
modeled ``ModelSim`` (no live model, no network). They establish the core
claims of the harness:

  * governed ASR is exactly 0.0 at every susceptibility multiplier,
  * bare ASR is positive at the 1x baseline,
  * the real CRP gate (``PolicyContext.evaluate_invocation``) adds < 1 ms of
    overhead per mediated action,
  * decisions are deterministic for a fixed seed.
"""

from __future__ import annotations

import pytest

from examples.crp_demos import governed_vs_bare as H


@pytest.fixture(scope="module")
def suite() -> list[H.Scenario]:
    return H.build_suite(n_per_type=25)


class TestGateDecisions:
    def test_every_attack_class_blocked(self, suite: list[H.Scenario]) -> None:
        gate = H.CRPGateAdapter()
        for sc in suite:
            decision = gate.mediate(sc.injected_action, sc)
            assert decision is not H.GateDecision.ALLOW, (
                f"injected action in {sc.name} was allowed"
            )

    def test_benign_actions_allowed(self, suite: list[H.Scenario]) -> None:
        gate = H.CRPGateAdapter()
        for sc in suite:
            assert gate.mediate(sc.benign_action, sc) is H.GateDecision.ALLOW

    def test_decisions_recorded_in_audit_trail(self, suite: list[H.Scenario]) -> None:
        gate = H.CRPGateAdapter()
        gate.mediate(suite[0].injected_action, suite[0])
        gate.mediate(suite[0].benign_action, suite[0])
        assert gate.audit_trail.entry_count == 2
        valid, broken_at = gate.audit_trail.verify_chain()
        assert valid and broken_at == -1


class TestArms:
    def test_bare_asr_positive_at_baseline(self, suite: list[H.Scenario]) -> None:
        asrs = [H.run_arm(suite, False, 1000 + t)["attack_success_rate"] for t in range(10)]
        assert sum(asrs) / len(asrs) > 0.0

    def test_governed_asr_zero(self, suite: list[H.Scenario]) -> None:
        for t in range(10):
            result = H.run_arm(suite, True, 1000 + t)
            assert result["attack_success_rate"] == 0.0

    def test_governance_preserves_utility(self, suite: list[H.Scenario]) -> None:
        bare = H.run_arm(suite, False, 1000)
        governed = H.run_arm(suite, True, 1000)
        assert governed["task_utility"] == bare["task_utility"] == 1.0

    def test_gate_overhead_under_one_ms(self, suite: list[H.Scenario]) -> None:
        result = H.run_arm(suite, True, 1000)
        assert result["gate_calls"] > 0
        assert result["avg_gate_overhead_us"] < 1000.0  # < 1 ms per action

    def test_governed_arm_records_audit_entries(self, suite: list[H.Scenario]) -> None:
        result = H.run_arm(suite, True, 1000)
        assert result["audit_entries"] == result["gate_calls"]


class TestDeterminism:
    def test_same_seed_same_decisions(self, suite: list[H.Scenario]) -> None:
        first = H.run_arm(suite, True, 42)
        second = H.run_arm(suite, True, 42)
        for key in ("attack_success_rate", "task_utility", "gate_calls", "audit_entries"):
            assert first[key] == second[key]

    def test_benchmark_reproducible(self) -> None:
        r1 = H.run_benchmark(n_per_type=25, trials=5)
        r2 = H.run_benchmark(n_per_type=25, trials=5)
        assert r1["bare"]["asr_mean"] == r2["bare"]["asr_mean"]
        assert r1["governed"]["asr_mean"] == r2["governed"]["asr_mean"]
        assert r1["bare"]["asr_ci95"] == r2["bare"]["asr_ci95"]


class TestSweep:
    def test_governed_asr_zero_at_every_multiplier(self) -> None:
        rows = H.run_sweep(
            multipliers=[0.5, 1.0, 2.0, 3.0, 5.0], n_per_type=25, trials=10
        )
        assert [r["multiplier"] for r in rows] == [0.5, 1.0, 2.0, 3.0, 5.0]
        for row in rows:
            assert row["governed_asr"] == 0.0, (
                f"governed ASR {row['governed_asr']} at {row['multiplier']}x"
            )
        # bare ASR is positive at baseline and non-decreasing with susceptibility
        bare = [r["bare_asr"] for r in rows]
        assert bare[1] > 0.0
        assert all(b2 >= b1 for b1, b2 in zip(bare, bare[1:], strict=False))

    def test_sweep_restores_susceptibility(self) -> None:
        base = dict(H.SUSCEPTIBILITY)
        H.run_sweep(multipliers=[5.0], n_per_type=5, trials=2)
        assert base == H.SUSCEPTIBILITY
