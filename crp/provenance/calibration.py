# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Calibration harnesses for CRP scoring thresholds.

Provides ground-truth evaluation of attribution and hallucination risk scorers
so that hard-coded thresholds can be tuned against labelled data instead of
arbitrary constants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from crp.envelope.packer import PackedFact

from ._types import ClaimAttribution, FidelityReport
from .attribution_scorer import score_claim_against_facts
from .claim_detector import DetectedClaim
from .hallucination_scorer import score_hallucination_risk


@dataclass
class AttributionExample:
    """A labelled claim/fact pair for attribution calibration."""

    claim_text: str
    facts: list[PackedFact]
    label: Literal["grounded", "ungrounded"]


@dataclass
class HallucinationExample:
    """A labelled claim for hallucination-risk calibration."""

    claim: ClaimAttribution
    label: Literal["hallucinated", "faithful"]


@dataclass
class ThresholdMetrics:
    """Binary-classification metrics at a single threshold."""

    threshold: float
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def precision(self) -> float:
        """Return the precision."""
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        """Return the recall."""
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        """Return the f1."""
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def fpr(self) -> float:
        """Return the fpr."""
        denom = self.fp + self.tn
        return self.fp / denom if denom else 0.0

    @property
    def fnr(self) -> float:
        """Return the fnr."""
        denom = self.fn + self.tp
        return self.fn / denom if denom else 0.0


@dataclass
class CalibrationResult:
    """Outcome of evaluating a scorer over a labelled dataset."""

    metrics: list[ThresholdMetrics] = field(default_factory=list)
    auc: float = 0.0
    best_f1_threshold: float = 0.0


class AttributionCalibrationHarness:
    """Calibrate attribution thresholds against ground-truth labels.

    A claim is considered "grounded" if its top composite score is at or above
    the threshold.  Labels must be ``grounded`` (positive) or ``ungrounded``
    (negative).
    """

    def __init__(self) -> None:
        self.examples: list[AttributionExample] = []

    def add(
        self,
        claim_text: str,
        facts: list[PackedFact],
        label: Literal["grounded", "ungrounded"],
    ) -> None:
        """Add a labelled claim/fact pair to the calibration set.

        Args:
            claim_text: The claim to evaluate.
            facts: Candidate facts to attribute the claim against.
            label: Ground-truth label, either ``grounded`` or ``ungrounded``.
        """
        self.examples.append(AttributionExample(claim_text, facts, label))

    def score(self) -> list[tuple[str, float]]:
        """Return [(label, top_score), ...] for every example."""
        results: list[tuple[str, float]] = []
        for ex in self.examples:
            claim = DetectedClaim(text=ex.claim_text)
            attr = score_claim_against_facts(claim, ex.facts)
            results.append((ex.label, attr.top_score))
        return results

    def evaluate(
        self,
        thresholds: list[float] | None = None,
    ) -> CalibrationResult:
        """Compute precision/recall/FPR/FNR across thresholds and AUC."""
        scores = self.score()
        positives = [score for label, score in scores if label == "grounded"]
        negatives = [score for label, score in scores if label == "ungrounded"]

        if thresholds is None:
            thresholds = sorted({0.0, 0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0})

        metrics: list[ThresholdMetrics] = []
        best_f1 = -1.0
        best_threshold = 0.0
        for t in thresholds:
            tp = sum(1 for s in positives if s >= t)
            fn = len(positives) - tp
            fp = sum(1 for s in negatives if s >= t)
            tn = len(negatives) - fp
            m = ThresholdMetrics(threshold=t, tp=tp, fp=fp, tn=tn, fn=fn)
            metrics.append(m)
            if m.f1 > best_f1:
                best_f1 = m.f1
                best_threshold = t

        return CalibrationResult(
            metrics=metrics,
            auc=_compute_auc(positives, negatives),
            best_f1_threshold=best_threshold,
        )


class HallucinationCalibrationHarness:
    """Calibrate hallucination-risk thresholds against ground-truth labels.

    The risk score (higher = more likely hallucinated) is taken from the window
    mean risk score produced by :func:`score_hallucination_risk`.  Labels must
    be ``hallucinated`` (positive) or ``faithful`` (negative).
    """

    def __init__(self) -> None:
        self.examples: list[HallucinationExample] = []

    def add(self, claim: ClaimAttribution, label: Literal["hallucinated", "faithful"]) -> None:
        """Add a labelled claim for hallucination-risk calibration.

        Args:
            claim: Claim attribution result to evaluate.
            label: Ground-truth label, either ``hallucinated`` or ``faithful``.
        """
        self.examples.append(HallucinationExample(claim, label))

    def score(self) -> list[tuple[str, float]]:
        """Return [(label, mean_risk_score), ...] for every example."""
        results: list[tuple[str, float]] = []
        for ex in self.examples:
            report = score_hallucination_risk([ex.claim], fidelity=FidelityReport(), entailment_results=[])
            results.append((ex.label, report.mean_risk_score))
        return results

    def evaluate(
        self,
        thresholds: list[float] | None = None,
    ) -> CalibrationResult:
        """Compute precision/recall/FPR/FNR across thresholds and AUC.

        Args:
            thresholds: Thresholds to evaluate. Defaults to a standard set.

        Returns:
            Calibration result with per-threshold metrics and best F1 threshold.
        """
        scores = self.score()
        positives = [score for label, score in scores if label == "hallucinated"]
        negatives = [score for label, score in scores if label == "faithful"]

        if thresholds is None:
            thresholds = sorted({0.0, 0.25, 0.5, 0.75, 1.0})

        metrics: list[ThresholdMetrics] = []
        best_f1 = -1.0
        best_threshold = 0.0
        for t in thresholds:
            tp = sum(1 for s in positives if s >= t)
            fn = len(positives) - tp
            fp = sum(1 for s in negatives if s >= t)
            tn = len(negatives) - fp
            m = ThresholdMetrics(threshold=t, tp=tp, fp=fp, tn=tn, fn=fn)
            metrics.append(m)
            if m.f1 > best_f1:
                best_f1 = m.f1
                best_threshold = t

        return CalibrationResult(
            metrics=metrics,
            auc=_compute_auc(positives, negatives),
            best_f1_threshold=best_threshold,
        )


def _compute_auc(positives: list[float], negatives: list[float]) -> float:
    """Compute AUC from two lists of scores via the Mann-Whitney U statistic."""
    if not positives or not negatives:
        return 0.0
    n_pos = len(positives)
    n_neg = len(negatives)
    ranked = sorted([(s, 1) for s in positives] + [(s, 0) for s in negatives])
    rank_sum_pos = sum(rank + 1 for rank, (_, label) in enumerate(ranked) if label == 1)
    u = rank_sum_pos - (n_pos * (n_pos + 1)) / 2
    return u / (n_pos * n_neg)
