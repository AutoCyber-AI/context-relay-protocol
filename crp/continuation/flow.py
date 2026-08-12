# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Information flow monitor — Δfacts/Δtokens rolling measurement (§4.3).

v4 amendment (SPEC-004): adds ``ResidualTaskAnchor`` — a forward-looking
continuation context that replaces the v3 backward-looking text summary.

Instead of carrying a growing summary of what has been done, the anchor
carries only what still needs to be done — a fixed-size list of remaining
sub-topics.  This eliminates the "backward-looking bloat" problem where
continuation context grew with each window and eventually dominated the
token budget.

Also adds ``should_terminate()`` — formal loop exit rules (SPEC-024 §5.2
and SPEC-004 amendment).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowSample:
    """Single measurement point in the flow monitor."""

    window_id: str
    facts_produced: int
    tokens_consumed: int
    timestamp: float = 0.0


@dataclass
class FlowMetrics:
    """Current information flow metrics."""

    current_rate: float  # facts per 1000 tokens
    rolling_average: float  # rolling average over last N windows
    trend: float  # positive = increasing, negative = decreasing
    sample_count: int
    is_alive: bool  # True if flow > 0


class InformationFlowMonitor:
    """Measures Δfacts/Δtokens rolling rate across windows (§4.3).

    Tracks how much new information the LLM is producing per token.
    When flow drops to zero, the model has stopped producing new facts.
    """

    def __init__(self, rolling_window: int = 5) -> None:
        self._samples: list[FlowSample] = []
        self._rolling_window = max(1, rolling_window)

    def record(self, window_id: str, facts_produced: int, tokens_consumed: int, timestamp: float = 0.0) -> None:
        """Record a new flow sample after a window completes."""
        self._samples.append(FlowSample(
            window_id=window_id,
            facts_produced=facts_produced,
            tokens_consumed=max(1, tokens_consumed),
            timestamp=timestamp,
        ))

    def current_rate(self) -> float:
        """Facts per 1000 tokens for the most recent window."""
        if not self._samples:
            return 0.0
        s = self._samples[-1]
        return (s.facts_produced / s.tokens_consumed) * 1000.0

    def rolling_average(self) -> float:
        """Rolling average rate over the last N windows."""
        if not self._samples:
            return 0.0
        recent = self._samples[-self._rolling_window:]
        total_facts = sum(s.facts_produced for s in recent)
        total_tokens = sum(s.tokens_consumed for s in recent)
        if total_tokens == 0:
            return 0.0
        return (total_facts / total_tokens) * 1000.0

    def trend(self) -> float:
        """Rate of change: positive = flow increasing, negative = decreasing.

        Computed as linear slope over rolling window.
        """
        recent = self._samples[-self._rolling_window:]
        if len(recent) < 2:
            return 0.0

        rates = [(s.facts_produced / max(1, s.tokens_consumed)) * 1000.0 for s in recent]
        n = len(rates)
        x_mean = (n - 1) / 2.0
        y_mean = sum(rates) / n

        num = sum((i - x_mean) * (r - y_mean) for i, r in enumerate(rates))
        den = sum((i - x_mean) ** 2 for i in range(n))
        if den == 0.0:
            return 0.0
        return num / den

    def is_alive(self) -> bool:
        """True if information flow is still positive."""
        return self.current_rate() > 0.0

    def metrics(self) -> FlowMetrics:
        """Get current flow metrics snapshot."""
        return FlowMetrics(
            current_rate=self.current_rate(),
            rolling_average=self.rolling_average(),
            trend=self.trend(),
            sample_count=len(self._samples),
            is_alive=self.is_alive(),
        )

    @property
    def sample_count(self) -> int:
        """Return the current sample count."""
        return len(self._samples)

    def reset(self) -> None:
        """Clear all samples."""
        self._samples.clear()


# ---------------------------------------------------------------------------
# Residual Task Anchor — SPEC-004 amendment (v4)
# ---------------------------------------------------------------------------


class ResidualTaskAnchor:
    """Forward-looking continuation context (SPEC-004 v4 amendment).

    Replaces the v3 backward-looking text summary approach.

    v3 approach (problem):
        continuation_context = f"Previously covered: {summary_of_done_work}"
        → context grew with each window, dominated token budget by W5

    v4 approach (fix):
        continuation_context = f"Still to cover: {', '.join(remaining[:5])}"
        → fixed size regardless of how many windows have run
        → model focuses forward, not backward

    Usage::

        anchor = ResidualTaskAnchor(task_sections=["intro", "arch", "deploy"])
        anchor.mark_complete("intro")
        anchor.to_prompt_prefix()  # → "Still to cover: arch, deploy"

    Maximum ``max_remaining`` items rendered (default 5) keeps the anchor
    a fixed token cost throughout all windows.
    """

    def __init__(
        self,
        task_sections: list[str] | None = None,
        max_remaining: int = 5,
    ) -> None:
        self._all_sections: list[str] = list(task_sections or [])
        self._completed: set[str] = set()
        self.max_remaining = max_remaining

    def set_sections(self, sections: list[str]) -> None:
        """Set (or replace) the full task section list."""
        self._all_sections = list(sections)
        self._completed = self._completed & set(sections)

    def mark_complete(self, section: str) -> None:
        """Mark a section as completed."""
        self._completed.add(section)

    def mark_complete_batch(self, sections: list[str]) -> None:
        """Mark multiple sections as completed."""
        for s in sections:
            self._completed.add(s)

    def remaining(self) -> list[str]:
        """Return the list of not-yet-completed sections."""
        return [s for s in self._all_sections if s not in self._completed]

    def to_prompt_prefix(self, label: str = "Still to cover") -> str:
        """Render as a fixed-size prompt prefix for the next window.

        Returns an empty string when all sections are complete.
        """
        rem = self.remaining()
        if not rem:
            return ""
        subset = rem[: self.max_remaining]
        items = ", ".join(subset)
        more = f" (+{len(rem) - self.max_remaining} more)" if len(rem) > self.max_remaining else ""
        return f"{label}: {items}{more}"

    def completion_fraction(self) -> float:
        """Fraction of sections completed (0.0–1.0)."""
        if not self._all_sections:
            return 1.0
        return len(self._completed) / len(self._all_sections)

    def is_complete(self) -> bool:
        """Return True when all task sections have been marked complete."""
        return len(self.remaining()) == 0

    def __repr__(self) -> str:
        return (
            f"ResidualTaskAnchor(total={len(self._all_sections)}, "
            f"done={len(self._completed)}, "
            f"remaining={len(self.remaining())})"
        )


# ---------------------------------------------------------------------------
# Formal loop exit rules — SPEC-024 §5.2 + SPEC-004 amendment
# ---------------------------------------------------------------------------


def should_terminate(
    window_number: int,
    max_windows: int,
    *,
    completeness_score: float = 0.0,
    completeness_threshold: float = 0.92,
    ckf_mean_novelty: float = 1.0,
    ckf_exhaustion_threshold: float = 0.15,
    safety_budget: float = 1.0,
    safety_budget_min: float = 0.10,
    finish_reason: str = "",
) -> tuple[bool, str]:
    """Formal loop exit rules (SPEC-024 §5.2, SPEC-004 amendment).

    Returns ``(should_stop: bool, reason: str)``.

    Exit conditions (any one sufficient):
    1. ``completeness_score >= threshold``    — task complete per DPE
    2. ``window_number >= max_windows``       — hard window cap
    3. ``ckf_mean_novelty < threshold``       — CKF exhausted (CDR signal)
    4. ``safety_budget <= min``               — safety budget depleted
    5. ``finish_reason == "stop"``            — model explicitly stopped
    """
    if completeness_score >= completeness_threshold:
        return True, "completeness_reached"
    if window_number >= max_windows:
        return True, "max_windows_reached"
    if ckf_mean_novelty < ckf_exhaustion_threshold:
        return True, "ckf_exhausted"
    if safety_budget <= safety_budget_min:
        return True, "safety_budget_depleted"
    if finish_reason == "stop":
        return True, "model_stop_signal"
    return False, ""

