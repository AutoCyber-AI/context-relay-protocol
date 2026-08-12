# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""State-layer Fact model — extends extraction Fact with lazy embedding,
age tracking, and seen_count for the 4-tier memory hierarchy (§3.1).

StateFact wraps extraction.types.Fact with additional state-management fields
that the warm store, envelope builder, and compaction engine need.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from crp.extraction.types import Fact

logger = logging.getLogger("crp.state.fact")

# ---------------------------------------------------------------------------
# Lazy embedding support
# ---------------------------------------------------------------------------

_EMBED_FN: Any = None  # set by scoring / warm store init


def set_embedding_function(fn: Any) -> None:
    """Register the global embedding function for lazy compute."""
    global _EMBED_FN  # noqa: PLW0603
    _EMBED_FN = fn


# ---------------------------------------------------------------------------
# StateFact
# ---------------------------------------------------------------------------


@dataclass
class StateFact:
    """Fact extended with state-management metadata (§3.1).

    Wraps an extraction ``Fact`` and adds:
    - Lazy embedding (computed on first access, cached)
    - ``age_in_windows`` — updated each window by the warm store
    - ``seen_count`` — how many envelopes this fact appeared in
    - ``consumed_by_windows`` — which windows used this fact
    - ``graph_edges`` — IDs of connected FactEdges
    """

    fact: Fact
    _embedding: list[float] | None = field(default=None, repr=False)
    age_in_windows: int = 0
    seen_count: int = 0
    consumed_by_windows: list[str] = field(default_factory=list)
    graph_edges: list[str] = field(default_factory=list)
    tier: int = 2  # 0=critical, 1=hot, 2=warm, 3=cold

    # --- Delegated properties from inner Fact ---------------------------------

    @property
    def id(self) -> str:
        """Return the id."""
        return self.fact.id

    @property
    def text(self) -> str:
        """Return the text."""
        return self.fact.text

    @property
    def category(self) -> str:
        """Return the category."""
        return self.fact.category

    @property
    def confidence(self) -> float:
        """Return the confidence."""
        return self.fact.confidence

    @property
    def source_window_id(self) -> str:
        """Return the source window identifier."""
        return self.fact.source_window_id

    @property
    def created_at(self) -> float:
        """Return the created at."""
        return self.fact.created_at

    @property
    def extraction_stage(self) -> int:
        """Return the extraction stage."""
        return self.fact.extraction_stage

    @property
    def superseded_by(self) -> str | None:
        """Return the superseded by."""
        return self.fact.superseded_by

    @superseded_by.setter
    def superseded_by(self, value: str | None) -> None:
        self.fact.superseded_by = value

    # --- Lazy embedding -------------------------------------------------------

    @property
    def embedding(self) -> list[float] | None:
        """Lazy-compute embedding on first access."""
        if self._embedding is None and _EMBED_FN is not None:
            try:
                self._embedding = _EMBED_FN(self.text)
            except Exception:  # noqa: BLE001
                logger.warning("Embedding computation failed for fact %s", self.id)
        return self._embedding

    @embedding.setter
    def embedding(self, value: list[float] | None) -> None:
        self._embedding = value

    def has_embedding(self) -> bool:
        """Return True if an embedding has been computed or assigned."""
        return self._embedding is not None

    # --- State mutations ------------------------------------------------------

    def mark_seen(self, window_id: str) -> None:
        """Record that this fact was included in an envelope for *window_id*."""
        self.seen_count += 1
        if window_id not in self.consumed_by_windows:
            self.consumed_by_windows.append(window_id)

    def increment_age(self) -> None:
        """Advance age by one window."""
        self.age_in_windows += 1

    def supersede(self, by_fact_id: str, confidence: float = 1.0) -> None:
        """Mark this fact as superseded."""
        self.fact.superseded_by = by_fact_id
        self.fact.supersession_confidence = confidence

    @property
    def is_superseded(self) -> bool:
        """Return whether this object is superseded."""
        return self.fact.superseded_by is not None

    # --- Serialization --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence (including embeddings §4D.1)."""
        d: dict[str, Any] = {
            "fact_id": self.id,
            "text": self.text,
            "category": self.category,
            "confidence": self.confidence,
            "source_window_id": self.source_window_id,
            "created_at": self.created_at,
            "extraction_stage": self.fact.extraction_stage,
            "age_in_windows": self.age_in_windows,
            "seen_count": self.seen_count,
            "consumed_by_windows": self.consumed_by_windows,
            "graph_edges": self.graph_edges,
            "superseded_by": self.superseded_by,
            "supersession_confidence": self.fact.supersession_confidence,
            "tier": self.tier,
            "has_embedding": self.has_embedding(),
        }
        # Persist actual embedding vectors when available (§4D.1)
        if self._embedding is not None:
            d["embedding"] = self._embedding
        return d

    @classmethod
    def from_fact(cls, fact: Fact) -> StateFact:
        """Wrap an extraction Fact into a StateFact."""
        return cls(fact=fact)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateFact:
        """Deserialize from dict."""
        fact = Fact(
            id=data["fact_id"],
            text=data["text"],
            category=data.get("category", ""),
            confidence=data.get("confidence", 0.0),
            source_window_id=data.get("source_window_id", ""),
            created_at=data.get("created_at", time.time()),
            extraction_stage=data.get("extraction_stage", 0),
            superseded_by=data.get("superseded_by"),
            supersession_confidence=data.get("supersession_confidence", 0.0),
        )
        sf = cls(
            fact=fact,
            age_in_windows=data.get("age_in_windows", 0),
            seen_count=data.get("seen_count", 0),
            consumed_by_windows=data.get("consumed_by_windows", []),
            graph_edges=data.get("graph_edges", []),
            tier=data.get("tier", 2),
        )
        # Restore embedding vectors if persisted (§4D.1)
        if "embedding" in data and data["embedding"] is not None:
            sf._embedding = data["embedding"]
        return sf
