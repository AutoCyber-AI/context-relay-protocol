# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Source grounding — store/retrieve verbatim source passages (§17).

Stores passages for facts with confidence ≥ 0.8. Integrates passages
into envelopes with tier-based budget allocation.

Relevant specifications:
  - CRP specification §17: Source grounding
  - CRP-SPEC-024: Coverage Differential Retrieval (CDR)
  - CRP-SPEC-025: Context Differential Graph Retrieval (CDGR)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants (§17)
# ---------------------------------------------------------------------------

HIGH_CONFIDENCE_THRESHOLD = 0.8

# Budget allocation by quality tier (fact_pct, source_pct)
BUDGET_BY_TIER: dict[str, tuple[float, float]] = {
    "S": (1.0, 0.0),    # No envelope needed
    "A": (0.90, 0.10),   # Low drift risk
    "B": (0.70, 0.30),   # Highest drift risk
    "C": (0.70, 0.30),   # Hierarchy adds abstraction
    "D": (0.75, 0.25),   # Space premium
}

HIGH_RELEVANCE_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SourcePassage:
    """Verbatim passage from the original input linked to facts.

    Attributes:
        passage_id: Unique identifier for the passage.
        text: Verbatim source text.
        source_window: Window number from which the passage was extracted.
        token_offset_start: Start token offset within the source window.
        token_offset_end: End token offset within the source window.
        linked_fact_ids: Identifiers of facts this passage grounds.
        token_count: Token count of ``text``.
        relevance_score: Relevance score for retrieval ranking.
    """

    passage_id: str = ""
    text: str = ""
    source_window: int = 0
    token_offset_start: int = 0
    token_offset_end: int = 0
    linked_fact_ids: list[str] = field(default_factory=list)
    token_count: int = 0
    relevance_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the passage to a dictionary.

        Returns:
            Dictionary with all passage fields.
        """
        return {
            "passage_id": self.passage_id,
            "text": self.text,
            "source_window": self.source_window,
            "token_offset_start": self.token_offset_start,
            "token_offset_end": self.token_offset_end,
            "linked_fact_ids": list(self.linked_fact_ids),
            "token_count": self.token_count,
            "relevance_score": self.relevance_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourcePassage:
        """Restore a passage from a serialized dictionary.

        Args:
            data: Serialized passage produced by :meth:`to_dict`.

        Returns:
            Reconstructed ``SourcePassage`` instance.
        """
        return cls(
            passage_id=data.get("passage_id", ""),
            text=data.get("text", ""),
            source_window=data.get("source_window", 0),
            token_offset_start=data.get("token_offset_start", 0),
            token_offset_end=data.get("token_offset_end", 0),
            linked_fact_ids=data.get("linked_fact_ids", []),
            token_count=data.get("token_count", 0),
            relevance_score=data.get("relevance_score", 0.0),
        )


# ---------------------------------------------------------------------------
# SourceGroundingEngine
# ---------------------------------------------------------------------------


class SourceGroundingEngine:
    """Store and retrieve verbatim source passages for high-confidence facts.

    Args:
        count_tokens: Callable that returns the token count for a piece of
            text.  Defaults to a rough character-based estimate when None.
    """

    def __init__(
        self,
        count_tokens: Callable[[str], int] | None = None,
    ) -> None:
        self._count_tokens = count_tokens or (lambda t: len(t) // 4)
        self._passages: dict[str, SourcePassage] = {}      # passage_id → passage
        self._fact_to_passages: dict[str, list[str]] = {}  # fact_id → [passage_ids]

    @property
    def passage_count(self) -> int:
        """Return the number of stored passages."""
        return len(self._passages)

    def store_passage(
        self,
        passage: SourcePassage,
        fact_confidence: float = 0.0,
    ) -> bool:
        """Store a passage if its linked fact has confidence ≥ threshold.

        Args:
            passage: Passage to store.
            fact_confidence: Confidence score of the fact linked to the passage.

        Returns:
            True if the passage was stored, False if it was below the threshold.
        """
        if fact_confidence < HIGH_CONFIDENCE_THRESHOLD:
            return False

        passage.token_count = self._count_tokens(passage.text)
        self._passages[passage.passage_id] = passage
        for fid in passage.linked_fact_ids:
            self._fact_to_passages.setdefault(fid, []).append(passage.passage_id)
        return True

    def get_passages_for_fact(self, fact_id: str) -> list[SourcePassage]:
        """Retrieve all source passages linked to a fact.

        Args:
            fact_id: Identifier of the fact.

        Returns:
            List of passages linked to the fact that remain in storage.
        """
        pids = self._fact_to_passages.get(fact_id, [])
        return [self._passages[pid] for pid in pids if pid in self._passages]

    def build_source_grounded_envelope(
        self,
        scored_facts: list[dict[str, Any]],
        budget_tokens: int,
        quality_tier: str = "B",
    ) -> tuple[list[dict[str, Any]], list[SourcePassage]]:
        """Build an envelope with source passages allocated by tier.

        Args:
            scored_facts: Sorted list of fact dictionaries such as
                ``{"id": ..., "text": ..., "score": ...}``.
            budget_tokens: Total envelope budget in tokens.
            quality_tier: Quality tier (S/A/B/C/D) controlling the fact/source
                budget split.

        Returns:
            A tuple of ``(packed_facts, included_passages)``.
        """
        fact_pct, source_pct = BUDGET_BY_TIER.get(quality_tier, (0.70, 0.30))
        fact_budget = int(budget_tokens * fact_pct)
        source_budget = int(budget_tokens * source_pct)

        # Phase 1: Pack facts within fact budget
        packed_facts: list[dict[str, Any]] = []
        tokens_used = 0
        for fact in scored_facts:
            t = self._count_tokens(fact.get("text", ""))
            if tokens_used + t > fact_budget:
                break
            packed_facts.append(fact)
            tokens_used += t

        # Phase 2: Allocate source passages for high-relevance packed facts
        included_passages: list[SourcePassage] = []
        source_tokens_used = 0

        for fact in packed_facts:
            fid = fact.get("id", "")
            score = fact.get("score", 0.0)
            if score < HIGH_RELEVANCE_THRESHOLD:
                continue

            for passage in self.get_passages_for_fact(fid):
                if source_tokens_used + passage.token_count > source_budget:
                    break
                included_passages.append(passage)
                source_tokens_used += passage.token_count

        return packed_facts, included_passages

    def format_envelope_section(
        self,
        fact: dict[str, Any],
        passages: list[SourcePassage],
    ) -> str:
        """Format a fact with its source passages for envelope inclusion.

        Format::

            - {fact text} — Window N
              ↳ [SOURCE: Window N, tokens X-Y]
                "{verbatim original text}"

        Args:
            fact: Fact dictionary containing at least ``text`` and ``window``.
            passages: Passages linked to the fact.

        Returns:
            Formatted envelope section string.
        """
        lines = [f"- {fact.get('text', '')} — Window {fact.get('window', '?')}"]
        for p in passages:
            lines.append(
                f"  ↳ [SOURCE: Window {p.source_window}, "
                f"tokens {p.token_offset_start}-{p.token_offset_end}]"
            )
            lines.append(f'    "{p.text}"')
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the engine for persistence.

        Returns:
            Dictionary with all passages and fact-to-passage mappings.
        """
        return {
            "passages": {pid: p.to_dict() for pid, p in self._passages.items()},
            "fact_to_passages": dict(self._fact_to_passages),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        count_tokens: Callable[[str], int] | None = None,
    ) -> SourceGroundingEngine:
        """Restore the engine from serialized state.

        Args:
            data: Serialized state produced by :meth:`to_dict`.
            count_tokens: Optional token-counting callable; defaults to the
                engine's fallback estimator if None.

        Returns:
            Reconstructed ``SourceGroundingEngine`` instance.
        """
        engine = cls(count_tokens=count_tokens)
        for pid, pdata in data.get("passages", {}).items():
            engine._passages[pid] = SourcePassage.from_dict(pdata)
        engine._fact_to_passages = data.get("fact_to_passages", {})
        return engine
