# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Verification Relay orchestrator (SPEC-049 §1.3.5).

Dispatches verifiers over a reasoning trace, runs a bounded LLM-Modulo
generate-critique-repair loop when a verifier returns INVALID, and produces a
report that caps the quality tier and raises the risk floor when unrepaired
INVALID steps remain.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from crp.vr.exec_verifier import ExecVerifier
from crp.vr.interface import Claim, Verdict, VerificationResult
from crp.vr.prm import ProcessRewardVerifier
from crp.vr.z3_verifier import Z3Verifier

logger = logging.getLogger(__name__)


# Default no-op repair function: returns the claim unchanged.
def _no_repair(claim: Claim, critique: str) -> Claim:
    return claim


class VerificationRelay:
    """Coordinate symbolic and probabilistic verifiers over a reasoning trace.

    Args:
        verifiers: Override the default verifier list.  Defaults to symbolic
            verifiers first, then the PRM.
        max_repairs: Maximum repair attempts per claim before giving up.
        min_depth_for_prm: Depths at which the probabilistic verifier is run.
            Symbolic verifiers run regardless of depth (SPEC-049 §1.5).
    """

    def __init__(
        self,
        verifiers: list[Any] | None = None,
        max_repairs: int = 2,
        min_depth_for_prm: set[str] | None = None,
    ):
        self.verifiers = verifiers or [Z3Verifier(), ExecVerifier(), ProcessRewardVerifier()]
        self.max_repairs = max_repairs
        self.min_depth_for_prm = min_depth_for_prm or {"thorough", "exhaustive"}

    def verify_trace(
        self,
        claims: list[Claim],
        context: dict[str, Any] | None = None,
        repair_fn: Callable[[Claim, str], Claim] | None = None,
        depth: str = "thorough",
    ) -> dict[str, Any]:
        """Verify every claim, repair INVALID ones, and return a report.

        Args:
            claims: Reasoning steps/assertions extracted from the trace.
            context: Optional shared context passed to each verifier.
            repair_fn: ``fn(claim, critique) -> revised_claim``.  Defaults to no-op.
            depth: Request depth; PRM is skipped unless depth is in
                ``min_depth_for_prm``.

        Returns:
            A report dict containing verification_ratio, tier_cap, risk_floor,
            step labels, and counts.
        """
        context = context or {}
        repair = repair_fn or _no_repair
        use_prm = depth in self.min_depth_for_prm

        results: list[tuple[Claim, VerificationResult]] = []
        repairs = 0

        for claim in claims:
            res = self._verify_claim(claim, context, use_prm)
            while res.verdict == Verdict.INVALID and repairs < self.max_repairs:
                claim = repair(claim, res.reason)
                res = self._verify_claim(claim, context, use_prm)
                repairs += 1
            results.append((claim, res))

        return self._score(results, repairs)

    def _verify_claim(
        self, claim: Claim, context: dict[str, Any], use_prm: bool
    ) -> VerificationResult:
        """Dispatch the first applicable verifier that returns a decisive verdict."""
        for verifier in self.verifiers:
            if not verifier.applies(claim):
                continue
            # Skip PRM outside of thorough/exhaustive depths (depth-gating).
            if isinstance(verifier, ProcessRewardVerifier) and not use_prm:
                continue
            res = verifier.verify(claim, context)
            if res.verdict != Verdict.UNKNOWN:
                return res
        return VerificationResult(
            Verdict.UNKNOWN, 0.0, "no verifier applies", "none", False
        )

    def _score(
        self, results: list[tuple[Claim, VerificationResult]], repairs: int
    ) -> dict[str, Any]:
        """Aggregate step results into a quality/risk report."""
        checked = [r for _, r in results if r.verdict != Verdict.UNKNOWN]
        invalid = [r for _, r in results if r.verdict == Verdict.INVALID]
        vr_ratio = 1.0 - (len(invalid) / max(1, len(checked)))

        return {
            "stage": "dpe_14_verification",
            "verification_ratio": round(vr_ratio, 3),
            "checked": len(checked),
            "invalid": len(invalid),
            "repairs": repairs,
            "tier_cap": "D" if invalid else None,
            "risk_floor": "HIGH" if invalid else "LOW",
            "labels": [
                (c.text, r.verdict.value, r.verifier, r.confidence)
                for c, r in results
            ],
        }
