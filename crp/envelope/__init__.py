# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Envelope construction — 6-phase algorithm, scoring, packing, formatting."""

from .builder import EnvelopeResult, EnvelopeState, compute_envelope_budget, construct
from .cdr import CDR_MIN_RELEVANCE, CDRRankResult, CDRScoredFact, cdr_rank, cdr_score, update_coverage_after_window
from .decomposer import DecompositionResult, decompose_task_aspects
from .formatter import EnvelopeSection, format_envelope
from .packer import PackedFact, PackingResult, estimate_tokens, pack_facts
from .reranker import CrossEncoderCache, rerank
from .retrieval_integrity import apply_recency_decay, detect_contradication, resolve_fact_authority
from .scoring import ScoredFact, ScoringConfig, score_facts

__all__ = [
    "CDR_MIN_RELEVANCE",
    "CDRRankResult",
    "CDRScoredFact",
    "CrossEncoderCache",
    "DecompositionResult",
    "EnvelopeResult",
    "EnvelopeSection",
    "EnvelopeState",
    "PackedFact",
    "PackingResult",
    "ScoredFact",
    "ScoringConfig",
    "cdr_rank",
    "cdr_score",
    "compute_envelope_budget",
    "construct",
    "decompose_task_aspects",
    "estimate_tokens",
    "format_envelope",
    "pack_facts",
    "rerank",
    "score_facts",
    "update_coverage_after_window",
    # Retrieval integrity (SPEC-027)
    "apply_recency_decay",
    "detect_contradication",
    "resolve_fact_authority",
]

