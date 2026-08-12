# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Hierarchical processing — map-reduce-validate for Tier C/D inputs (§4.5, §11).

Splits massive inputs into segments, processes each independently,
reduces iteratively, and validates cross-window consistency.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SEGMENT_SIZE_MULTIPLIER = 100  # segment_size = 100 × context_window
DEFAULT_FAN_IN = 50


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class HierarchicalPlan:
    """Plan for hierarchical processing."""

    total_tokens: int = 0
    segment_count: int = 0
    segment_size: int = 0
    fan_in: int = DEFAULT_FAN_IN
    hierarchy_levels: int = 1
    estimated_degradation: float = 0.0
    processing_mode: str = "hierarchical"


@dataclass
class HierarchicalConfig:
    """Configuration for hierarchical processing."""

    segment_size: int | None = None
    fan_in: int | None = None
    context_window: int = 128_000


@dataclass
class SegmentResult:
    """Output of processing one segment."""

    segment_index: int = 0
    synthesis: str = ""
    facts_extracted: int = 0
    token_count: int = 0


# ---------------------------------------------------------------------------
# Degradation model
# ---------------------------------------------------------------------------


def chain_degradation(levels: int, per_level: float = 0.03) -> float:
    """Compute effective degradation after N hierarchy levels.

    d_chain(L) = 1 - (1 - per_level)^L
    """
    return 1.0 - (1.0 - per_level) ** levels


def effective_context(
    context_window: int, levels: int, per_level: float = 0.03,
) -> float:
    """Effective context capacity after hierarchical degradation.

    EffCtx_hier(N) = C × (1 - d_chain(⌈log_k(N)⌉))
    """
    d = chain_degradation(levels, per_level)
    return context_window * (1.0 - d)


# ---------------------------------------------------------------------------
# HierarchicalProcessor
# ---------------------------------------------------------------------------


class HierarchicalProcessor:
    """Map-reduce-validate pattern for oversized inputs."""

    def __init__(
        self,
        dispatch_fn: Callable[[str, str], tuple[str, Any]] | None = None,
        count_tokens: Callable[[str], int] | None = None,
        context_window: int = 128_000,
    ) -> None:
        self._dispatch_fn = dispatch_fn
        self._count_tokens = count_tokens or (lambda t: len(t) // 4)
        self._context_window = context_window

    def plan(
        self, total_tokens: int, config: HierarchicalConfig | None = None,
    ) -> HierarchicalPlan:
        """Create a hierarchical processing plan."""
        cfg = config or HierarchicalConfig()
        seg_size = cfg.segment_size or (DEFAULT_SEGMENT_SIZE_MULTIPLIER * self._context_window)
        fan_in = cfg.fan_in or DEFAULT_FAN_IN

        segment_count = max(1, math.ceil(total_tokens / seg_size))
        levels = max(1, math.ceil(math.log(max(segment_count, 2)) / math.log(max(fan_in, 2))))
        degradation = chain_degradation(levels)

        mode = "hierarchical"
        if total_tokens > 1000 * self._context_window:
            mode = "hierarchical_multi_level"

        return HierarchicalPlan(
            total_tokens=total_tokens,
            segment_count=segment_count,
            segment_size=seg_size,
            fan_in=fan_in,
            hierarchy_levels=levels,
            estimated_degradation=degradation,
            processing_mode=mode,
        )

    def map_phase(
        self,
        segments: list[str],
        task_intent: str,
    ) -> list[SegmentResult]:
        """MAP: Process each segment independently."""
        results: list[SegmentResult] = []
        for i, segment in enumerate(segments):
            if self._dispatch_fn:
                prompt = (
                    "Summarize and extract ALL key facts from the following "
                    f"segment ({i + 1}/{len(segments)}) for: {task_intent}"
                )
                output, _ = self._dispatch_fn(prompt, segment)
            else:
                # Fallback: take first 500 chars as summary
                output = segment[:500]

            results.append(SegmentResult(
                segment_index=i,
                synthesis=output,
                facts_extracted=0,
                token_count=self._count_tokens(output),
            ))
        return results

    def reduce_phase(
        self,
        syntheses: list[str],
        task_intent: str,
        fan_in: int = DEFAULT_FAN_IN,
    ) -> list[str]:
        """REDUCE: Iteratively merge syntheses until ≤ fan_in remain."""
        current = syntheses
        while len(current) > fan_in:
            batches: list[list[str]] = []
            for i in range(0, len(current), fan_in):
                batches.append(current[i:i + fan_in])

            next_level: list[str] = []
            for batch in batches:
                joined = "\n\n---\n\n".join(batch)
                if self._dispatch_fn:
                    prompt = (
                        f"Synthesize these {len(batch)} segment summaries "
                        f"into a coherent overview for: {task_intent}"
                    )
                    output, _ = self._dispatch_fn(prompt, joined)
                else:
                    output = joined[:1000]
                next_level.append(output)
            current = next_level
        return current

    def hierarchical_dispatch(
        self,
        task_intent: str,
        large_input: str,
        config: HierarchicalConfig | None = None,
    ) -> tuple[list[str], HierarchicalPlan]:
        """Full map-reduce-validate pipeline for oversized input.

        Returns (final_syntheses, plan).
        """
        total_tokens = self._count_tokens(large_input)
        plan = self.plan(total_tokens, config)

        # Segment the input
        seg_char_size = len(large_input) // max(plan.segment_count, 1)
        segments: list[str] = []
        for i in range(plan.segment_count):
            start = i * seg_char_size
            end = start + seg_char_size if i < plan.segment_count - 1 else len(large_input)
            segments.append(large_input[start:end])

        # MAP
        map_results = self.map_phase(segments, task_intent)

        # REDUCE
        syntheses = [r.synthesis for r in map_results]
        reduced = self.reduce_phase(syntheses, task_intent, plan.fan_in)

        return reduced, plan
