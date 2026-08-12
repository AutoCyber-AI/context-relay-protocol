# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Continuation trigger — wall detection and continuation conditions (§4.2)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TriggerConfig:
    """Configuration for continuation triggering."""

    max_continuations: int = 50
    token_ratio_threshold: float = 0.95
    min_gap_score: float = 0.0
    min_info_flow: float = 0.0
    # When the model stops naturally (no wall hit) but significant
    # unfulfilled requirements remain, override the stop and continue.
    # This handles small models that stop prematurely before completing
    # all requested sections.  Set to 0.0 to disable gap override.
    gap_override_threshold: float = 0.3
    # Minimum output tokens required before gap_override will fire.
    # If the model stopped with an output smaller than this, the stop is
    # treated as authoritative — continuing would just produce another
    # trivial stop.  Prevents runaway continuation loops against toy / test
    # providers that return very short fixed responses.
    gap_override_min_output_tokens: int = 16


@dataclass
class TriggerResult:
    """Result of continuation trigger evaluation."""

    should_continue: bool
    wall_hit: bool
    gap_remaining: float
    info_flow: float
    continuation_count: int
    reason: str
    details: dict[str, object] = field(default_factory=dict)


def detect_wall_hit(
    finish_reason: str | None,
    output_tokens: int | None = None,
    max_output_tokens: int | None = None,
) -> bool:
    """Detect physical context-window wall hit.

    Primary: finish_reason == "length" (universal across providers).
    Fallback: output_tokens / max_output_tokens >= 0.95 when finish_reason unavailable.
    """
    if finish_reason is not None:
        return finish_reason.lower() in ("length", "max_tokens")

    if output_tokens is not None and max_output_tokens is not None and max_output_tokens > 0:
        return output_tokens / max_output_tokens >= 0.95

    return False


def evaluate_continuation(
    *,
    finish_reason: str | None,
    output_tokens: int | None = None,
    max_output_tokens: int | None = None,
    gap_score: float = 1.0,
    info_flow: float = 1.0,
    continuation_count: int = 0,
    config: TriggerConfig | None = None,
) -> TriggerResult:
    """Evaluate whether continuation should proceed.

    Three conditions must ALL be met (§4.2):
    1. Wall hit detected (physical truncation)
    2. Gap score > min_gap_score (unfulfilled requirements remain)
    3. Info flow > min_info_flow (model still producing useful content)
    4. continuation_count < max_continuations (safety bound)
    """
    cfg = config or TriggerConfig()

    wall_hit = detect_wall_hit(finish_reason, output_tokens, max_output_tokens)

    if not wall_hit:
        # Gap override: if the model stopped naturally but significant
        # requirements remain unfulfilled, continue anyway.  This handles
        # small models that stop prematurely before completing all sections.
        # Still respect max_continuations safety bound.
        #
        # Trivial-output guard: if the model stopped with an output smaller
        # than ``gap_override_min_output_tokens``, treat the stop as
        # authoritative — extending a trivial output produces another
        # trivial stop and just burns budget.
        _tiny_output = (
            output_tokens is not None
            and output_tokens < cfg.gap_override_min_output_tokens
        )
        if (cfg.gap_override_threshold > 0.0
                and gap_score > cfg.gap_override_threshold
                and continuation_count < cfg.max_continuations
                and not _tiny_output):
            return TriggerResult(
                should_continue=True,
                wall_hit=False,
                gap_remaining=gap_score,
                info_flow=info_flow,
                continuation_count=continuation_count,
                reason="gap_override",
                details={"gap_threshold": cfg.gap_override_threshold},
            )
        return TriggerResult(
            should_continue=False,
            wall_hit=False,
            gap_remaining=gap_score,
            info_flow=info_flow,
            continuation_count=continuation_count,
            reason="no_wall_hit",
        )

    if gap_score <= cfg.min_gap_score:
        return TriggerResult(
            should_continue=False,
            wall_hit=True,
            gap_remaining=gap_score,
            info_flow=info_flow,
            continuation_count=continuation_count,
            reason="gap_fulfilled",
        )

    if info_flow <= cfg.min_info_flow:
        return TriggerResult(
            should_continue=False,
            wall_hit=True,
            gap_remaining=gap_score,
            info_flow=info_flow,
            continuation_count=continuation_count,
            reason="info_flow_dead",
        )

    if continuation_count >= cfg.max_continuations:
        return TriggerResult(
            should_continue=False,
            wall_hit=True,
            gap_remaining=gap_score,
            info_flow=info_flow,
            continuation_count=continuation_count,
            reason="max_continuations_reached",
        )

    return TriggerResult(
        should_continue=True,
        wall_hit=True,
        gap_remaining=gap_score,
        info_flow=info_flow,
        continuation_count=continuation_count,
        reason="continue",
    )
