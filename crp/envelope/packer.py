# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 4+5 — Graph-aware packing & bookend strategy (§3.2).

Greedy packing: sort by score, pack while token budget remains.
Graph neighbour pulling: 2-hop BFS, indented sub-lines.
Compressed fact fallback: if >50 tokens remain but no full fact fits.
Bookend strategy: duplicate top-3 scored facts at END of envelope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crp.extraction.types import FactGraph, RelationType

from .scoring import ScoredFact

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

# Default chars-per-token ratio for English BPE models.
# The spec PROHIBITS hardcoded //4 but ALLOWS a calibrated estimator.
# This default (3.3 chars/token) is conservative for most English BPE models.
_DEFAULT_CHARS_PER_TOKEN = 3.3


def estimate_tokens(text: str, chars_per_token: float = _DEFAULT_CHARS_PER_TOKEN) -> int:
    """Estimate token count from text length using calibrated ratio.

    This is used as a fallback when no model tokenizer is available.
    When an actual tokenizer is provided via ``count_tokens``, use that instead.
    """
    if not text:
        return 0
    return max(1, int(len(text) / chars_per_token + 0.5))


# ---------------------------------------------------------------------------
# Packing result
# ---------------------------------------------------------------------------


@dataclass
class PackedFact:
    """A fact selected for the envelope, with its formatted text."""

    fact_id: str = ""
    text: str = ""
    score: float = 0.0
    tokens: int = 0
    is_neighbour: bool = False
    is_compressed: bool = False
    is_bookend: bool = False


@dataclass
class PackingResult:
    """Output of the packing phase."""

    packed_facts: list[PackedFact] = field(default_factory=list)
    total_tokens: int = 0
    budget: int = 0
    facts_considered: int = 0
    facts_packed: int = 0
    compressed_count: int = 0
    bookend_count: int = 0


# ---------------------------------------------------------------------------
# Graph neighbour formatting
# ---------------------------------------------------------------------------

def _format_neighbours(
    fact_id: str,
    graph: FactGraph,
    max_hops: int = 2,
) -> list[str]:
    """BFS neighbours up to *max_hops*, formatted as indented sub-lines."""
    sub = graph.subgraph_for({fact_id}, max_hops=max_hops)
    lines: list[str] = []
    for edge in sub.edges:
        if edge.source_id == fact_id:
            target = sub.nodes.get(edge.target_id)
            if target:
                rel = edge.relation_type
                if isinstance(rel, RelationType):
                    rel = rel.value
                lines.append(f"  ↳ [{rel}] {target.text}")
    return lines


# ---------------------------------------------------------------------------
# Compressed fact (truncation)
# ---------------------------------------------------------------------------

def _compress_fact(text: str, max_tokens: int, chars_per_token: float) -> str:
    """Truncate *text* to fit within *max_tokens*."""
    max_chars = int(max_tokens * chars_per_token)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


# ---------------------------------------------------------------------------
# Main packing function
# ---------------------------------------------------------------------------

BOOKEND_COUNT = 3
MIN_REMAINING_FOR_COMPRESSED = 50


def pack_facts(
    scored_facts: list[ScoredFact],
    graph: FactGraph,
    budget_tokens: int,
    *,
    count_tokens: Any = None,
    chars_per_token: float = _DEFAULT_CHARS_PER_TOKEN,
) -> PackingResult:
    """Greedily pack *scored_facts* into the envelope token budget.

    Parameters
    ----------
    scored_facts : list[ScoredFact]
        Pre-sorted by composite score (descending).
    graph : FactGraph
        Fact graph for 2-hop neighbour pulling.
    budget_tokens : int
        Maximum tokens available for the facts section.
    count_tokens : callable | None
        Actual tokenizer function ``(str) → int``.  If None, uses estimate.
    chars_per_token : float
        Calibrated chars/token for the estimator fallback.
    """
    if not scored_facts or budget_tokens <= 0:
        return PackingResult(budget=budget_tokens, facts_considered=len(scored_facts))

    def _count(text: str) -> int:
        if count_tokens is not None:
            return count_tokens(text)
        return estimate_tokens(text, chars_per_token)

    result = PackingResult(budget=budget_tokens, facts_considered=len(scored_facts))
    used_tokens = 0
    packed_ids: set[str] = set()

    # Phase 4: Greedy packing with graph-neighbour pulling
    for sf in scored_facts:
        fact_line = f"- {sf.fact.text}"
        neighbour_lines = _format_neighbours(sf.fact.id, graph)
        full_text = fact_line
        if neighbour_lines:
            full_text = fact_line + "\n" + "\n".join(neighbour_lines)

        fact_tokens = _count(full_text)

        if used_tokens + fact_tokens <= budget_tokens:
            pf = PackedFact(
                fact_id=sf.fact.id,
                text=full_text,
                score=sf.composite_score,
                tokens=fact_tokens,
            )
            result.packed_facts.append(pf)
            packed_ids.add(sf.fact.id)
            used_tokens += fact_tokens
            continue

        # Compressed fallback: if >50 tokens remain, truncate this fact to fit
        remaining = budget_tokens - used_tokens
        if remaining >= MIN_REMAINING_FOR_COMPRESSED:
            compressed_text = _compress_fact(fact_line, remaining, chars_per_token)
            ct = _count(compressed_text)
            if ct <= remaining:
                pf = PackedFact(
                    fact_id=sf.fact.id,
                    text=compressed_text,
                    score=sf.composite_score,
                    tokens=ct,
                    is_compressed=True,
                )
                result.packed_facts.append(pf)
                packed_ids.add(sf.fact.id)
                used_tokens += ct
                result.compressed_count += 1
            break  # budget exhausted after compressed fit attempt
        else:
            break  # not enough room even for compression

    # Phase 5: Bookend strategy — duplicate top-3 facts at END
    bookend_candidates = [pf for pf in result.packed_facts if not pf.is_compressed][:BOOKEND_COUNT]
    for pf in bookend_candidates:
        bookend_tokens = _count(pf.text)
        if used_tokens + bookend_tokens <= budget_tokens:
            bpf = PackedFact(
                fact_id=pf.fact_id,
                text=pf.text,
                score=pf.score,
                tokens=bookend_tokens,
                is_bookend=True,
            )
            result.packed_facts.append(bpf)
            used_tokens += bookend_tokens
            result.bookend_count += 1

    result.total_tokens = used_tokens
    result.facts_packed = len(packed_ids)
    return result
