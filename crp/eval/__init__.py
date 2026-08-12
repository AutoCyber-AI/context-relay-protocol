# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Evaluation statistics toolkit for CRP benchmarks (CRP-SPEC-026).

Small, dependency-light statistical primitives shared by CRP benchmark
harnesses (SQB, governed-vs-bare):

    pass_hat_k       — unbiased pass@k / pass^k estimator (Chen et al., 2021)
    bootstrap_ci     — deterministic percentile bootstrap confidence interval
    mcnemar_pvalue   — exact binomial McNemar p-value for paired comparisons
"""

from __future__ import annotations

from crp.eval.stats import bootstrap_ci, mcnemar_pvalue, pass_hat_k

__all__ = [
    "pass_hat_k",
    "bootstrap_ci",
    "mcnemar_pvalue",
]
