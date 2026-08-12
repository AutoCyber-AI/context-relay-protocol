# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Verification Relay (SPEC-049)."""

from __future__ import annotations

import pytest

from crp.vr import (
    Claim,
    ExecVerifier,
    ProcessRewardVerifier,
    Verdict,
    VerificationRelay,
    VerificationResult,
    Z3Verifier,
)


class TestExecVerifier:
    def test_valid_arithmetic_claim(self):
        v = ExecVerifier()
        claim = Claim(
            text="254 * 3 = 762",
            kind="arithmetic",
            formal={"expr": "254 * 3", "expected": 762},
        )
        res = v.verify(claim, {})
        assert res.verdict == Verdict.VALID
        assert res.confidence == 1.0
        assert res.verifier == "sandboxed-exec"

    def test_invalid_arithmetic_claim(self):
        v = ExecVerifier()
        claim = Claim(
            text="254 * 3 = 700",
            kind="arithmetic",
            formal={"expr": "254 * 3", "expected": 700},
        )
        res = v.verify(claim, {})
        assert res.verdict == Verdict.INVALID
        assert res.verifier == "sandboxed-exec"

    def test_does_not_apply_without_expr(self):
        v = ExecVerifier()
        claim = Claim(text="no expr", kind="arithmetic", formal={})
        assert not v.applies(claim)


class TestZ3Verifier:
    def test_applies_to_constraint_claim(self):
        v = Z3Verifier()
        claim = Claim(
            text="x != 3",
            kind="constraint",
            formal={
                "vars": {"x": "Int"},
                "assert": ["x > 0", "x < 5"],
                "claim": "x != 3",
            },
        )
        assert v.applies(claim)

    def test_sound_entailment(self):
        v = Z3Verifier()
        claim = Claim(
            text="x > 2",
            kind="constraint",
            formal={
                "vars": {"x": "Int"},
                "assert": ["x > 5"],
                "claim": "x > 2",
            },
        )
        res = v.verify(claim, {})
        assert res.verdict == Verdict.VALID
        assert res.confidence == 1.0

    def test_counterexample(self):
        v = Z3Verifier()
        claim = Claim(
            text="x == 3",
            kind="constraint",
            formal={
                "vars": {"x": "Int"},
                "assert": ["x > 0", "x < 5"],
                "claim": "x == 3",
            },
        )
        res = v.verify(claim, {})
        assert res.verdict == Verdict.INVALID
        assert res.confidence == 1.0


class TestVerificationRelay:
    def _relay(self, **kwargs):
        # Use only symbolic verifiers so tests do not depend on transformers.
        return VerificationRelay(
            verifiers=[Z3Verifier(), ExecVerifier()],
            max_repairs=2,
            **kwargs,
        )

    def test_all_valid_trace(self):
        relay = self._relay()
        claims = [
            Claim(
                text="10 + 20 = 30",
                kind="arithmetic",
                formal={"expr": "10 + 20", "expected": 30},
            ),
            Claim(
                text="x > 2",
                kind="constraint",
                formal={"vars": {"x": "Int"}, "assert": ["x > 5"], "claim": "x > 2"},
            ),
        ]
        report = relay.verify_trace(claims, depth="thorough")
        assert report["verification_ratio"] == 1.0
        assert report["invalid"] == 0
        assert report["risk_floor"] == "LOW"
        assert report["tier_cap"] is None

    def test_invalid_trace_caps_tier_and_raises_risk(self):
        relay = self._relay()
        claims = [
            Claim(
                text="10 + 20 = 999",
                kind="arithmetic",
                formal={"expr": "10 + 20", "expected": 999},
            ),
        ]
        report = relay.verify_trace(claims, depth="thorough")
        assert report["invalid"] == 1
        assert report["tier_cap"] == "D"
        assert report["risk_floor"] == "HIGH"
        assert report["verification_ratio"] == 0.0

    def test_repair_loop(self):
        relay = self._relay()

        def fix(claim: Claim, critique: str) -> Claim:
            # Fix the obviously wrong expected value.
            formal = dict(claim.formal or {})
            formal["expected"] = 30
            return Claim(
                text=claim.text,
                kind=claim.kind,
                premises=claim.premises,
                formal=formal,
            )

        claims = [
            Claim(
                text="10 + 20 = 999",
                kind="arithmetic",
                formal={"expr": "10 + 20", "expected": 999},
            ),
        ]
        report = relay.verify_trace(claims, repair_fn=fix, depth="thorough")
        assert report["invalid"] == 0
        assert report["repairs"] == 1

    def test_prm_skipped_for_quick_depth(self):
        relay = VerificationRelay(
            verifiers=[ExecVerifier(), ProcessRewardVerifier()],
            max_repairs=0,
        )
        # No formal expr -> ExecVerifier does not apply; PRM should be skipped at quick.
        claims = [Claim(text="inference step", kind="inference")]
        report = relay.verify_trace(claims, depth="quick")
        assert all(label[1] == "unknown" for label in report["labels"])

    def test_labels_include_verifier_and_confidence(self):
        relay = self._relay()
        claims = [
            Claim(
                text="2 * 3 = 6",
                kind="arithmetic",
                formal={"expr": "2 * 3", "expected": 6},
            ),
        ]
        report = relay.verify_trace(claims, depth="thorough")
        labels = report["labels"]
        assert len(labels) == 1
        assert labels[0][1] == "valid"
        assert labels[0][2] in {"z3-smt", "sandboxed-exec"}
