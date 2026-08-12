# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Multi-signal completion detection (§4.3).

Four signals, weighted by content type, with grace periods and self-calibrating baselines.
"""

from __future__ import annotations

import re
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import Enum


class CompletionSignal(str, Enum):
    """The four completion signals."""

    FACT_FLOW = "fact_flow"
    STRUCTURAL_FLOW = "structural_flow"
    VOCABULARY_NOVELTY = "vocabulary_novelty"
    STRUCTURAL_COMPLETION = "structural_completion"


@dataclass
class SignalState:
    """State of a single completion signal."""

    signal: CompletionSignal
    value: float  # 0.0–1.0 normalized
    alive: bool  # True if signal suggests more content coming
    weight: float  # content-type-dependent weight
    raw: float = 0.0  # pre-normalization value


@dataclass
class CompletionResult:
    """Aggregated completion assessment."""

    is_complete: bool
    composite_score: float  # 0=totally incomplete, 1=fully complete
    signals: list[SignalState]
    grace_tokens_remaining: int
    reason: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass
class CompletionConfig:
    """Configuration for completion detection."""

    # Content-type signal weights: {content_type: {signal: weight}}
    # Default weights below; override per content type
    default_weights: dict[str, float] = field(default_factory=lambda: {
        CompletionSignal.FACT_FLOW: 0.35,
        CompletionSignal.STRUCTURAL_FLOW: 0.25,
        CompletionSignal.VOCABULARY_NOVELTY: 0.20,
        CompletionSignal.STRUCTURAL_COMPLETION: 0.20,
    })

    entity_rich_weights: dict[str, float] = field(default_factory=lambda: {
        CompletionSignal.FACT_FLOW: 0.50,
        CompletionSignal.STRUCTURAL_FLOW: 0.15,
        CompletionSignal.VOCABULARY_NOVELTY: 0.15,
        CompletionSignal.STRUCTURAL_COMPLETION: 0.20,
    })

    reasoning_dense_weights: dict[str, float] = field(default_factory=lambda: {
        CompletionSignal.FACT_FLOW: 0.25,
        CompletionSignal.STRUCTURAL_FLOW: 0.35,
        CompletionSignal.VOCABULARY_NOVELTY: 0.20,
        CompletionSignal.STRUCTURAL_COMPLETION: 0.20,
    })

    narrative_weights: dict[str, float] = field(default_factory=lambda: {
        CompletionSignal.FACT_FLOW: 0.20,
        CompletionSignal.STRUCTURAL_FLOW: 0.25,
        CompletionSignal.VOCABULARY_NOVELTY: 0.35,
        CompletionSignal.STRUCTURAL_COMPLETION: 0.20,
    })

    completion_threshold: float = 0.75
    grace_tokens: int = 500  # extra tokens when secondary signal alive
    calibration_windows: int = 5  # N first windows for baseline


# ── Signal 1: Fact flow (§4.3) ───────────────────────────────────

_COMPLETION_HEADINGS = re.compile(
    r"^#+\s*(conclusion|summary|references|bibliography|appendix|closing|final\s+thoughts)",
    re.IGNORECASE | re.MULTILINE,
)

_LIST_CLOSE_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:\d+[.)]\s+|[-*]\s+).*(?:\n\s*$|\Z)",
    re.MULTILINE,
)


class CompletionDetector:
    """Multi-signal completion with self-calibrating baselines (§4.3)."""

    def __init__(self, content_type: str = "", config: CompletionConfig | None = None) -> None:
        self._config = config or CompletionConfig()
        self._content_type = content_type
        self._weights = self._select_weights(content_type)

        # Per-signal history for calibration (bounded to prevent memory leak)
        self._fact_rates: deque[float] = deque(maxlen=100)
        self._structural_scores: deque[float] = deque(maxlen=100)
        self._novelty_scores: deque[float] = deque(maxlen=100)
        self._completion_scores: deque[float] = deque(maxlen=100)

        # Baselines (calibrated from first N windows)
        self._fact_baseline: float | None = None
        self._structural_baseline: float | None = None
        self._novelty_baseline: float | None = None

        # N-gram pool for novelty
        self._prior_trigrams: Counter[tuple[str, ...]] = Counter()

        # Grace period tracking
        self._grace_budget = 0

    def evaluate(
        self,
        text: str,
        facts_produced: int,
        tokens_consumed: int,
        structural_state: dict[str, object] | None = None,
    ) -> CompletionResult:
        """Evaluate all 4 completion signals for a window output."""
        tokens = text.split()

        # Signal 1: Fact flow
        fact_rate = (facts_produced / max(1, tokens_consumed)) * 1000.0
        self._fact_rates.append(fact_rate)
        fact_signal = self._score_fact_flow(fact_rate)

        # Signal 2: Structural flow
        struct_score = self._score_structural_flow(text, structural_state)
        self._structural_scores.append(struct_score)

        # Signal 3: Vocabulary novelty (3-gram ratio)
        novelty = self._score_novelty(tokens)
        self._novelty_scores.append(novelty)
        self._update_trigrams(tokens)

        # Signal 4: Structural completion patterns
        completion_score = self._score_structural_completion(text)
        self._completion_scores.append(completion_score)

        # Calibrate baselines after N windows
        self._maybe_calibrate()

        # Build signal states
        signals = [
            SignalState(
                signal=CompletionSignal.FACT_FLOW,
                value=1.0 - fact_signal,  # invert: high=complete
                alive=fact_signal > 0.2,
                weight=self._weights.get(CompletionSignal.FACT_FLOW, 0.25),
                raw=fact_rate,
            ),
            SignalState(
                signal=CompletionSignal.STRUCTURAL_FLOW,
                value=1.0 - struct_score,
                alive=struct_score > 0.2,
                weight=self._weights.get(CompletionSignal.STRUCTURAL_FLOW, 0.25),
                raw=struct_score,
            ),
            SignalState(
                signal=CompletionSignal.VOCABULARY_NOVELTY,
                value=1.0 - novelty,
                alive=novelty > 0.3,
                weight=self._weights.get(CompletionSignal.VOCABULARY_NOVELTY, 0.25),
                raw=novelty,
            ),
            SignalState(
                signal=CompletionSignal.STRUCTURAL_COMPLETION,
                value=completion_score,
                alive=completion_score < 0.5,
                weight=self._weights.get(CompletionSignal.STRUCTURAL_COMPLETION, 0.25),
                raw=completion_score,
            ),
        ]

        # Composite score
        composite = sum(s.value * s.weight for s in signals)
        composite = max(0.0, min(1.0, composite))

        # Grace period: if any secondary signal alive, extend
        any_alive = any(s.alive for s in signals)
        if composite >= self._config.completion_threshold and any_alive:
            if self._grace_budget <= 0:
                self._grace_budget = self._config.grace_tokens
            self._grace_budget -= tokens_consumed
            if self._grace_budget > 0:
                return CompletionResult(
                    is_complete=False,
                    composite_score=composite,
                    signals=signals,
                    grace_tokens_remaining=self._grace_budget,
                    reason="grace_period",
                )

        is_complete = composite >= self._config.completion_threshold and not any_alive
        all_dead = not any(s.alive for s in signals)

        reason = "complete" if is_complete else ("all_signals_dead" if all_dead else "in_progress")

        return CompletionResult(
            is_complete=is_complete or all_dead,
            composite_score=composite,
            signals=signals,
            grace_tokens_remaining=max(0, self._grace_budget),
            reason=reason,
        )

    def reset(self) -> None:
        """Clear all state."""
        self._fact_rates.clear()
        self._structural_scores.clear()
        self._novelty_scores.clear()
        self._completion_scores.clear()
        self._prior_trigrams.clear()
        self._fact_baseline = None
        self._structural_baseline = None
        self._novelty_baseline = None
        self._grace_budget = 0

    # ── Signal scoring ────────────────────────────────────────

    def _score_fact_flow(self, rate: float) -> float:
        """Score fact flow relative to baseline. High = still flowing."""
        if self._fact_baseline is not None and self._fact_baseline > 0:
            return min(1.0, rate / self._fact_baseline)
        # Pre-calibration: raw rate normalized (10 facts/1000 tokens = 1.0)
        return min(1.0, rate / 10.0)

    def _score_structural_flow(self, text: str, structural_state: dict[str, object] | None) -> float:
        """Score structural continuation signals. High = structure still developing."""
        score = 0.0
        indicators = 0

        # Open code blocks
        if text.count("```") % 2 == 1:
            score += 1.0
            indicators += 1

        # Unfinished lists (last line is list item without blank line after)
        lines = text.rstrip().split("\n")
        if lines:
            last = lines[-1].strip()
            if re.match(r"^(\d+[.)]\s+|[-*]\s+)", last):
                score += 0.8
                indicators += 1

        # Mid-sentence ending (no terminal punctuation)
        stripped = text.rstrip()
        if stripped and stripped[-1] not in ".!?:;\"')]}":
            score += 0.6
            indicators += 1

        # Use structural_state if available
        if structural_state:
            if structural_state.get("code_block_open"):
                score += 1.0
                indicators += 1
            if structural_state.get("open_blocks"):
                score += 0.5 * len(structural_state["open_blocks"])  # type: ignore[arg-type]
                indicators += 1

        return min(1.0, score / max(1, indicators)) if indicators > 0 else 0.5

    def _score_novelty(self, tokens: list[str]) -> float:
        """3-gram novelty ratio. High = still producing new content."""
        n = 3
        if len(tokens) < n:
            return 1.0

        current = Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))
        if not self._prior_trigrams:
            return 1.0

        overlap = sum((current & self._prior_trigrams).values())
        total = sum(current.values())
        if total == 0:
            return 1.0
        return 1.0 - (overlap / total)

    def _score_structural_completion(self, text: str) -> float:
        """Score structural completion markers. High = content is concluding."""
        score = 0.0

        # Conclusion headings
        if _COMPLETION_HEADINGS.search(text):
            score += 0.6

        # Closing phrases
        closing = re.search(
            r"\b(in\s+conclusion|to\s+summarize|in\s+summary|overall|finally|"
            r"to\s+conclude|this\s+completes|that\s+covers)\b",
            text, re.IGNORECASE,
        )
        if closing:
            score += 0.3

        # All lists closed (no dangling list items at end)
        lines = text.rstrip().split("\n")
        if lines:
            last_lines = lines[-3:]
            has_list = any(re.match(r"\s*(\d+[.)]\s+|[-*]\s+)", line) for line in last_lines)
            ends_blank = lines[-1].strip() == ""
            if has_list and ends_blank:
                score += 0.1  # closed list

        return min(1.0, score)

    def _update_trigrams(self, tokens: list[str]) -> None:
        n = 3
        if len(tokens) < n:
            return
        for i in range(len(tokens) - n + 1):
            self._prior_trigrams[tuple(tokens[i:i + n])] += 1

    def _maybe_calibrate(self) -> None:
        """Self-calibrate baselines from first N windows (§4.3)."""
        from itertools import islice
        n = self._config.calibration_windows
        if self._fact_baseline is None and len(self._fact_rates) >= n:
            self._fact_baseline = sum(islice(self._fact_rates, n)) / n or 1.0
        if self._structural_baseline is None and len(self._structural_scores) >= n:
            self._structural_baseline = sum(islice(self._structural_scores, n)) / n or 0.5
        if self._novelty_baseline is None and len(self._novelty_scores) >= n:
            self._novelty_baseline = sum(islice(self._novelty_scores, n)) / n or 0.5

    def _select_weights(self, content_type: str) -> dict[str, float]:
        """Select signal weights by content type."""
        cfg = self._config
        ct = content_type.upper() if content_type else ""
        if ct == "ENTITY_RICH":
            return cfg.entity_rich_weights
        elif ct in ("REASONING_DENSE", "DOCUMENT"):
            return cfg.reasoning_dense_weights
        elif ct in ("NARRATIVE", "DISCURSIVE"):
            return cfg.narrative_weights
        return cfg.default_weights
