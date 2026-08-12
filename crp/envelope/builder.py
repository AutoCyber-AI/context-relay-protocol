# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Envelope builder — top-level 6-phase construction orchestrator (§3.2).

``construct(task_intent, budget, state)`` returns the final envelope text.

6-Phase algorithm:
  Phase 1: Multi-aspect task decomposition       → decomposer.py
  Phase 2: Bi-encoder scoring                    → scoring.py
  Phase 3: Cross-encoder reranking               → reranker.py
  Phase 4: Graph-aware packing                   → packer.py
  Phase 5: Bookend strategy                      → packer.py
  Phase 6: CKF retrieval gate                    → this module

Envelope budget formula (02_CORE §2.1):
  ``E_max = C − S − T − G``
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from crp.core.task_intent import TaskIntent
from crp.extraction.types import Fact, FactGraph

from .decomposer import DecompositionResult, decompose_task_aspects
from .formatter import format_envelope
from .packer import PackingResult, estimate_tokens, pack_facts
from .reranker import CrossEncoderCache, rerank
from .scoring import ScoringConfig, score_facts

logger = logging.getLogger("crp.envelope.builder")

# ---------------------------------------------------------------------------
# Envelope state — holds facts, graph, and per-session metadata
# ---------------------------------------------------------------------------

CKF_GATE_TOKENS = 120  # min remaining tokens before pulling from CKF
CKF_RESERVE_RATIO = 0.15  # fraction of fact_budget reserved for CKF when retriever is available


@dataclass
class EnvelopeState:
    """Session-scoped state passed to the envelope builder.

    Attributes:
        facts: Facts available in the warm tier.
        graph: Fact graph for relationship-aware packing.
        current_window_index: Index of the current window (for scoring).
        seen_counts: Per-fact occurrence counts (for redundancy discounting).
        fact_window_indices: Window index where each fact first appeared.
        sections: Pre-populated critical-state sections (e.g. "CONTEXT_SOURCES").
        ckf_retriever: Optional callback ``(query, budget_tokens) -> facts``.
        ce_cache: Shared cross-encoder cache across windows.
        scoring_config: Optional scoring configuration override.
    """

    # Fact store (warm tier)
    facts: list[Fact] = field(default_factory=list)
    graph: FactGraph = field(default_factory=FactGraph)

    # Metadata for scoring
    current_window_index: int = 0
    seen_counts: dict[str, int] = field(default_factory=dict)
    fact_window_indices: dict[str, int] = field(default_factory=dict)

    # Critical state sections (pre-populated by state management)
    sections: dict[str, str] = field(default_factory=dict)

    # CKF callback — if registered, called when budget allows
    ckf_retriever: Callable[[str, int], list[Fact]] | None = None

    # Cross-encoder cache (shared across windows)
    ce_cache: CrossEncoderCache = field(default_factory=CrossEncoderCache)

    # Scoring config override
    scoring_config: ScoringConfig | None = None


# ---------------------------------------------------------------------------
# Build result
# ---------------------------------------------------------------------------


@dataclass
class EnvelopeResult:
    """Output of ``construct()``.

    Attributes:
        envelope_text: Final formatted envelope string.
        envelope_tokens: Tokens in ``envelope_text``.
        budget_tokens: Maximum envelope budget supplied.
        saturation: ``envelope_tokens / budget_tokens``.
        facts_included: Number of facts packed into the envelope.
        facts_available: Number of facts available before packing.
        bookend_count: Facts placed in bookend positions.
        compressed_count: Facts that were compressed to fit budget.
        ckf_facts_added: Facts pulled from CKF during Phase 6.
        latency_ms: Wall-clock build time.
        decomposition: Task decomposition result.
        packing: Graph-aware packing result.
    """

    envelope_text: str = ""
    envelope_tokens: int = 0
    budget_tokens: int = 0
    saturation: float = 0.0  # envelope_tokens / budget_tokens
    facts_included: int = 0
    facts_available: int = 0
    bookend_count: int = 0
    compressed_count: int = 0
    ckf_facts_added: int = 0
    latency_ms: float = 0.0
    decomposition: DecompositionResult | None = None
    packing: PackingResult | None = None


# ---------------------------------------------------------------------------
# Envelope budget computation
# ---------------------------------------------------------------------------


def compute_envelope_budget(
    context_window: int,
    system_tokens: int,
    task_tokens: int,
    generation_reserve: int | None = None,
    max_output_tokens: int | None = None,
) -> int:
    """Compute ``E_max = C − S − T − G``.

    Generation reserve precedence:
      1. User-specified ``max_output_tokens``
      2. Explicit ``generation_reserve``
      3. Default: ``min(C // 4, 16384)``

    Args:
        context_window: Model context window size ``C``.
        system_tokens: System prompt tokens ``S``.
        task_tokens: Task input tokens ``T``.
        generation_reserve: Explicit generation reserve ``G``.
        max_output_tokens: User output limit (highest precedence for ``G``).

    Returns:
        Non-negative envelope budget ``E_max``.
    """
    if max_output_tokens is not None:
        g = max_output_tokens
    elif generation_reserve is not None:
        g = generation_reserve
    else:
        g = min(context_window // 4, 16384)
    return max(0, context_window - system_tokens - task_tokens - g)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def construct(
    task_intent: TaskIntent,
    budget_tokens: int,
    state: EnvelopeState,
    *,
    count_tokens: Callable[[str], int] | None = None,
    chars_per_token: float = 3.3,
) -> EnvelopeResult:
    """Build an envelope for *task_intent* within *budget_tokens*.

    This is the top-level orchestrator implementing the 6-phase algorithm.

    Args:
        task_intent: The task to assemble context for.
        budget_tokens: Maximum envelope tokens (``E_max`` from budget formula).
        state: Session-scoped state containing facts, graph, sections, etc.
        count_tokens: Model tokenizer function ``(str) -> int``. Falls back to
            the character-based estimator if None.
        chars_per_token: Calibrated chars/token ratio for fallback estimation.

    Returns:
        An ``EnvelopeResult`` with the built envelope and metadata.
    """
    t0 = time.perf_counter()

    def _count(text: str) -> int:
        if count_tokens is not None:
            return count_tokens(text)
        return estimate_tokens(text, chars_per_token)

    result = EnvelopeResult(
        budget_tokens=budget_tokens,
        facts_available=len(state.facts),
    )

    if budget_tokens <= 0:
        result.latency_ms = (time.perf_counter() - t0) * 1000
        return result

    # -----------------------------------------------------------------------
    # Phase 1: Multi-aspect task decomposition
    # -----------------------------------------------------------------------
    decomposition = decompose_task_aspects(task_intent)
    result.decomposition = decomposition

    # -----------------------------------------------------------------------
    # Phase 2: Bi-encoder scoring
    # -----------------------------------------------------------------------
    scored = score_facts(
        state.facts,
        decomposition,
        state.graph,
        current_window_index=state.current_window_index,
        seen_counts=state.seen_counts,
        fact_window_indices=state.fact_window_indices,
        config=state.scoring_config,
    )

    # -----------------------------------------------------------------------
    # Phase 3: Cross-encoder reranking
    # -----------------------------------------------------------------------
    scored = rerank(
        scored,
        task_intent,
        cache=state.ce_cache,
        current_window=state.current_window_index,
    )

    # -----------------------------------------------------------------------
    # Compute section overhead (tier 1-2 sections that always appear)
    # -----------------------------------------------------------------------
    section_text_parts: dict[str, str] = {}
    section_overhead = 0
    for name, content in state.sections.items():
        if content and content.strip():
            header = f"[{name.upper()}]\n{content.strip()}"
            section_overhead += _count(header) + 2  # +2 for "\n\n"
            section_text_parts[name] = content.strip()

    # Budget remaining for facts
    fact_budget = max(0, budget_tokens - section_overhead)

    # Reserve budget for CKF when retriever is available (§audit fix G1)
    ckf_reserve = 0
    if state.ckf_retriever is not None and fact_budget > CKF_GATE_TOKENS * 2:
        ckf_reserve = max(CKF_GATE_TOKENS, int(fact_budget * CKF_RESERVE_RATIO))
    warm_budget = fact_budget - ckf_reserve

    # -----------------------------------------------------------------------
    # Phase 4+5: Graph-aware packing + bookend strategy
    # -----------------------------------------------------------------------
    packing = pack_facts(
        scored,
        state.graph,
        warm_budget,
        count_tokens=count_tokens,
        chars_per_token=chars_per_token,
    )
    result.packing = packing
    result.facts_included = packing.facts_packed
    result.bookend_count = packing.bookend_count
    result.compressed_count = packing.compressed_count

    # -----------------------------------------------------------------------
    # Phase 6: CKF retrieval gate
    # -----------------------------------------------------------------------
    # CKF gets reserved budget + any unused warm store budget
    remaining_for_ckf = ckf_reserve + (warm_budget - packing.total_tokens)
    if (
        remaining_for_ckf > CKF_GATE_TOKENS
        and state.ckf_retriever is not None
        and decomposition.aspects
    ):
        query = " ".join(decomposition.aspects[:3])
        try:
            ckf_facts = state.ckf_retriever(query, remaining_for_ckf)
            if ckf_facts:
                # Score and pack CKF facts into remaining budget
                ckf_scored = score_facts(
                    ckf_facts,
                    decomposition,
                    state.graph,
                    current_window_index=state.current_window_index,
                    config=state.scoring_config,
                )
                ckf_packed = pack_facts(
                    ckf_scored,
                    state.graph,
                    remaining_for_ckf,
                    count_tokens=count_tokens,
                    chars_per_token=chars_per_token,
                )
                # Merge CKF results
                packing.packed_facts.extend(ckf_packed.packed_facts)
                packing.total_tokens += ckf_packed.total_tokens
                result.ckf_facts_added = ckf_packed.facts_packed
        except Exception:  # noqa: BLE001
            logger.warning("CKF lookup failed during envelope build", exc_info=True)

    # -----------------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------------
    envelope_text = format_envelope(section_text_parts, packing.packed_facts)

    result.envelope_text = envelope_text
    result.envelope_tokens = _count(envelope_text)

    # Clamp envelope to budget if it overflows (§audit M9)
    if budget_tokens > 0 and result.envelope_tokens > budget_tokens:
        # Truncate envelope text to fit within budget
        target_chars = int(budget_tokens * chars_per_token)
        if len(envelope_text) > target_chars:
            result.envelope_text = envelope_text[:target_chars]
            result.envelope_tokens = _count(result.envelope_text)

    if budget_tokens > 0:
        result.saturation = min(1.0, result.envelope_tokens / budget_tokens)
    result.latency_ms = (time.perf_counter() - t0) * 1000

    return result
