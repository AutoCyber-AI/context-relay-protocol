# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Known-answer tests for the eval statistics toolkit (``crp.eval``)."""

from __future__ import annotations

import math
import random

import pytest

from crp.eval import bootstrap_ci, mcnemar_pvalue, pass_hat_k


class TestPassHatK:
    def test_no_correct_samples_is_zero(self) -> None:
        # pass@k = 1 - C(n-c,k)/C(n,k); c = 0 ⇒ no correct sample can be drawn
        assert pass_hat_k(n=10, c=0, k=1) == 0.0
        assert pass_hat_k(n=10, c=0, k=5) == 0.0

    def test_all_correct_samples_is_one(self) -> None:
        assert pass_hat_k(n=10, c=10, k=1) == 1.0
        assert pass_hat_k(n=10, c=10, k=10) == 1.0

    def test_k_equals_n(self) -> None:
        # drawing all n samples finds a correct one iff c > 0
        assert pass_hat_k(n=10, c=1, k=10) == 1.0
        assert pass_hat_k(n=10, c=0, k=10) == 0.0

    def test_k_one_reduces_to_empirical_rate(self) -> None:
        assert pass_hat_k(n=10, c=3, k=1) == pytest.approx(0.3)

    def test_known_value(self) -> None:
        # n=10, c=5, k=2: 1 - C(5,2)/C(10,2) = 1 - 10/45 = 7/9
        assert pass_hat_k(n=10, c=5, k=2) == pytest.approx(7.0 / 9.0)

    def test_matches_bruteforce_probability(self) -> None:
        # probability that at least one of k draws (without replacement) is correct
        n, c, k = 20, 7, 4
        expected = 1.0 - math.comb(n - c, k) / math.comb(n, k)
        assert pass_hat_k(n, c, k) == pytest.approx(expected)

    def test_invalid_arguments_raise(self) -> None:
        with pytest.raises(ValueError):
            pass_hat_k(n=0, c=0, k=1)
        with pytest.raises(ValueError):
            pass_hat_k(n=10, c=11, k=1)
        with pytest.raises(ValueError):
            pass_hat_k(n=10, c=5, k=0)
        with pytest.raises(ValueError):
            pass_hat_k(n=10, c=5, k=11)


class TestBootstrapCI:
    def test_ci_contains_true_mean_seeded_normal(self) -> None:
        rng = random.Random(1234)
        sample = [rng.gauss(100.0, 15.0) for _ in range(400)]
        lo, hi = bootstrap_ci(sample, seed=42)
        assert lo < 100.0 < hi

    def test_deterministic_for_fixed_seed(self) -> None:
        rng = random.Random(7)
        sample = [rng.gauss(0.0, 1.0) for _ in range(100)]
        first = bootstrap_ci(sample, seed=42)
        second = bootstrap_ci(sample, seed=42)
        assert first == second

    def test_different_seeds_still_bracket_sample_mean(self) -> None:
        rng = random.Random(99)
        sample = [rng.gauss(5.0, 2.0) for _ in range(200)]
        mean = sum(sample) / len(sample)
        for seed in (1, 2, 3):
            lo, hi = bootstrap_ci(sample, seed=seed)
            assert lo <= mean <= hi or abs(hi - mean) < 0.2 or abs(mean - lo) < 0.2

    def test_constant_sample_gives_degenerate_ci(self) -> None:
        lo, hi = bootstrap_ci([3.0] * 50, seed=42)
        assert lo == hi == 3.0

    def test_invalid_arguments_raise(self) -> None:
        with pytest.raises(ValueError):
            bootstrap_ci([], seed=42)
        with pytest.raises(ValueError):
            bootstrap_ci([1.0], n_boot=0)
        with pytest.raises(ValueError):
            bootstrap_ci([1.0], alpha=1.5)


class TestMcNemar:
    def test_hand_computed_exact_value(self) -> None:
        # b=2, c=8: n=10, p = 2 * (C(10,0)+C(10,1)+C(10,2)) / 2**10
        #         = 2 * 56 / 1024 = 0.109375
        assert mcnemar_pvalue(2, 8) == pytest.approx(0.109375)

    def test_hand_computed_zero_b(self) -> None:
        # b=0, c=5: n=5, p = 2 * 1 / 2**5 = 0.0625
        assert mcnemar_pvalue(0, 5) == pytest.approx(0.0625)

    def test_symmetric_discordance_is_nonsignificant(self) -> None:
        # b=c=3: p = 2 * 42 / 64 = 1.3125 → capped at 1.0
        assert mcnemar_pvalue(3, 3) == 1.0

    def test_no_discordant_pairs(self) -> None:
        assert mcnemar_pvalue(0, 0) == 1.0

    def test_symmetry(self) -> None:
        assert mcnemar_pvalue(2, 8) == pytest.approx(mcnemar_pvalue(8, 2))

    def test_strong_difference_is_significant(self) -> None:
        assert mcnemar_pvalue(1, 20) < 0.001

    def test_negative_counts_raise(self) -> None:
        with pytest.raises(ValueError):
            mcnemar_pvalue(-1, 3)
