# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Chain degradation tracking and regrounding (§04 §3.5.3).

d_chain(n) = 1 - ∏(1 - d_i) where d_i is per-window degradation.
Regrounding: re-extract from raw outputs every N=5 windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crp.extraction.types import Fact


@dataclass
class DegradationMetrics:
    """Per-window degradation measurement."""

    window_id: str
    d_i: float  # per-window degradation (0=perfect, 1=total loss)
    d_chain: float  # cumulative chain degradation
    fact_drift: float  # how much facts changed on regrounding
    window_index: int


@dataclass
class RegroundingResult:
    """Result of regrounding: re-extracting from raw outputs."""

    new_facts: list[Fact]
    reconciled: int  # facts confirmed
    drifted: int  # facts that changed
    lost: int  # facts no longer extractable
    drift_score: float  # 0=no drift, 1=total drift


class ChainDegradation:
    """Track cumulative degradation across continuation windows (§04 §3.5.3).

    Formula: d_chain(n) = 1 - ∏(1 - d_i)
    where d_i is per-window degradation based on extraction quality drop.

    Triggers regrounding every N=5 windows to reconcile drifted facts.
    """

    def __init__(self, reground_interval: int = 5) -> None:
        self._reground_interval = max(1, reground_interval)
        self._per_window: list[DegradationMetrics] = []
        self._product: float = 1.0  # running ∏(1 - d_i)

    def record(
        self,
        window_id: str,
        facts_expected: int,
        facts_produced: int,
        quality_score: float = 1.0,
    ) -> DegradationMetrics:
        """Record per-window degradation.

        d_i estimated from:
        - fact count drop: (expected - produced) / expected
        - quality score inversion: 1 - quality_score
        Combined with equal weight.
        """
        if facts_expected > 0:
            count_deg = max(0.0, (facts_expected - facts_produced) / facts_expected)
        else:
            count_deg = 0.0

        quality_deg = max(0.0, 1.0 - quality_score)

        d_i = 0.5 * count_deg + 0.5 * quality_deg
        d_i = max(0.0, min(1.0, d_i))

        self._product *= (1.0 - d_i)
        d_chain = 1.0 - self._product

        metrics = DegradationMetrics(
            window_id=window_id,
            d_i=d_i,
            d_chain=d_chain,
            fact_drift=0.0,
            window_index=len(self._per_window),
        )
        self._per_window.append(metrics)
        return metrics

    @property
    def chain_degradation(self) -> float:
        """Current cumulative chain degradation d_chain(n)."""
        return 1.0 - self._product

    @property
    def window_count(self) -> int:
        """Return the current window count."""
        return len(self._per_window)

    def should_reground(self) -> bool:
        """Whether regrounding is due (every N windows)."""
        return len(self._per_window) > 0 and len(self._per_window) % self._reground_interval == 0

    def reground(
        self,
        current_facts: list[Fact],
        regrounded_facts: list[Fact],
    ) -> RegroundingResult:
        """Reconcile current facts against re-extracted facts.

        Compare by text similarity (word overlap). Facts with overlap < 0.5
        are considered drifted.
        """
        current_texts = {f.id: set(f.text.lower().split()) for f in current_facts}
        reground_texts = {f.id: set(f.text.lower().split()) for f in regrounded_facts}

        reconciled = 0
        drifted = 0
        lost = 0

        for _cid, cwords in current_texts.items():
            best_overlap = 0.0
            for _, rwords in reground_texts.items():
                if cwords and rwords:
                    overlap = len(cwords & rwords) / max(len(cwords), len(rwords))
                    best_overlap = max(best_overlap, overlap)

            if best_overlap >= 0.7:
                reconciled += 1
            elif best_overlap >= 0.3:
                drifted += 1
            else:
                lost += 1

        total = max(1, reconciled + drifted + lost)
        drift_score = (drifted + lost) / total

        # Update last window's fact_drift
        if self._per_window:
            self._per_window[-1].fact_drift = drift_score

        return RegroundingResult(
            new_facts=regrounded_facts,
            reconciled=reconciled,
            drifted=drifted,
            lost=lost,
            drift_score=drift_score,
        )

    @property
    def history(self) -> list[DegradationMetrics]:
        """Return the history."""
        return list(self._per_window)

    def reset(self) -> None:
        """Clear all state."""
        self._per_window.clear()
        self._product = 1.0
