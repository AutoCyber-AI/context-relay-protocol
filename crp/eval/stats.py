# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Statistical primitives for CRP benchmark evaluation (CRP-SPEC-026).

Stdlib-only core; numpy is used opportunistically (it is available in the dev
environment) but never required — the module imports and runs without it, in
keeping with the zero-dependency core.

All estimators are deterministic: :func:`bootstrap_ci` seeds its resampling
RNG, and :func:`pass_hat_k` / :func:`mcnemar_pvalue` are closed-form.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Sequence

try:  # numpy is optional in the zero-dependency core
    import numpy as np

    _DEFAULT_STATISTIC: Callable[[Sequence[float]], float] = np.mean
except ImportError:  # pragma: no cover — exercised only without numpy
    np = None  # type: ignore[assignment]
    _DEFAULT_STATISTIC = statistics.mean


def _comb(n: int, k: int) -> int:
    """Binomial coefficient C(n, k); returns 0 when k > n or k < 0."""
    if k < 0 or k > n:
        return 0
    return math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator (Chen et al., 2021 — Codex/HumanEval).

    Given ``n`` samples per task of which ``c`` are correct, the unbiased
    estimate of pass@k (probability that at least one of ``k`` sampled
    completions is correct) is::

        pass@k = 1 - C(n - c, k) / C(n, k)

    Args:
        n: Total number of samples (must be >= 1).
        c: Number of correct samples (0 <= c <= n).
        k: Number of samples drawn for the estimate (1 <= k <= n).

    Returns:
        The unbiased pass@k estimate in [0.0, 1.0]. ``c = 0`` yields 0.0
        (no correct sample can ever be drawn); ``c = n`` yields 1.0.

    Raises:
        ValueError: If the arguments are out of range.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if not 0 <= c <= n:
        raise ValueError(f"c must satisfy 0 <= c <= n (got c={c}, n={n})")
    if not 1 <= k <= n:
        raise ValueError(f"k must satisfy 1 <= k <= n (got k={k}, n={n})")
    return 1.0 - _comb(n - c, k) / _comb(n, k)


def _percentile(sorted_vals: Sequence[float], pct: float) -> float:
    """Linear-interpolation percentile (same method as ``numpy.percentile``)."""
    if not sorted_vals:
        raise ValueError("cannot take a percentile of an empty sequence")
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[lo] * (hi - k) + sorted_vals[hi] * (k - lo))


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[Sequence[float]], float] | None = None,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for a statistic.

    Resamples ``values`` with replacement ``n_boot`` times, applies
    ``statistic`` to each resample, and returns the ``(alpha/2, 1-alpha/2)``
    percentiles of the bootstrap distribution. Deterministic for a fixed
    ``seed``.

    Args:
        values: Observed sample (must be non-empty).
        statistic: Statistic to bootstrap; defaults to the mean
            (``numpy.mean`` when numpy is available, else ``statistics.mean``).
        n_boot: Number of bootstrap resamples.
        alpha: Significance level; the interval has coverage ``1 - alpha``.
        seed: Seed for the resampling RNG.

    Returns:
        ``(lower, upper)`` bounds of the confidence interval.

    Raises:
        ValueError: If ``values`` is empty or arguments are out of range.
    """
    vals = [float(v) for v in values]
    if not vals:
        raise ValueError("values must be non-empty")
    if n_boot < 1:
        raise ValueError("n_boot must be >= 1")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must satisfy 0 < alpha < 1")
    stat = statistic if statistic is not None else _DEFAULT_STATISTIC

    rng = random.Random(seed)
    n = len(vals)
    boot = []
    for _ in range(n_boot):
        resample = [vals[rng.randrange(n)] for _ in range(n)]
        boot.append(float(stat(resample)))
    boot.sort()
    return (
        _percentile(boot, 100.0 * alpha / 2.0),
        _percentile(boot, 100.0 * (1.0 - alpha / 2.0)),
    )


def mcnemar_pvalue(b: int, c: int) -> float:
    """Exact binomial McNemar p-value for a paired comparison.

    ``b`` counts discordant pairs where only A succeeded; ``c`` counts pairs
    where only B succeeded. Under the null hypothesis of no difference, the
    count of A-only wins is Binomial(n = b + c, p = 0.5); the exact two-sided
    p-value is::

        p = 2 * sum_{i=0}^{min(b, c)} C(n, i) * 0.5**n   (capped at 1.0)

    Args:
        b: Discordant pairs won only by A (must be >= 0).
        c: Discordant pairs won only by B (must be >= 0).

    Returns:
        Exact two-sided p-value in (0.0, 1.0]. ``b = c = 0`` yields 1.0.

    Raises:
        ValueError: If ``b`` or ``c`` is negative.
    """
    if b < 0 or c < 0:
        raise ValueError("b and c must be >= 0")
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(_comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    return min(1.0, 2.0 * tail)
