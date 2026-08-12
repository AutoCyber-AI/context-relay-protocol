# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Warm state store — in-memory Tier 2 with optional SQLite WAL persist (§3.0, §3.1).

The warm store holds all active facts, their graph, and provides the ranked
retrieval interface used by the envelope builder.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from crp.extraction.types import Fact, FactEdge, FactGraph

from .critical_state import CriticalState, StructuralState
from .fact import StateFact

logger = logging.getLogger("crp.state.warm_store")

# Schema version for session file format (§audit L6 / L7)
SCHEMA_VERSION = 2

# ---------------------------------------------------------------------------
# WarmStateStore
# ---------------------------------------------------------------------------


@dataclass
class WarmStoreConfig:
    """Configuration for the warm state store.

    Attributes:
        max_facts: Maximum number of facts to retain in memory.
        persist_enabled: Whether to write state to SQLite WAL on change.
        persist_path: Filesystem path for persistence (when enabled).
        compact_threshold: Fact count that triggers compaction consideration.
        compact_latency_ms: Target maximum compaction latency in milliseconds.
    """

    max_facts: int = 10_000
    persist_enabled: bool = False
    persist_path: str = ""
    compact_threshold: int = 5000
    compact_latency_ms: float = 500.0


class WarmStateStore:
    """In-memory warm state (Tier 2) with thread-safe access.

    Provides:
    - add_facts / get_facts / get_ranked_facts / mark_seen / supersede
    - Critical state & structural state management
    - Optional async SQLite WAL persistence (Phase 4E)
    """

    def __init__(self, config: WarmStoreConfig | None = None) -> None:
        """Initialise the warm state store.

        Args:
            config: Optional warm-store configuration.
        """
        self._config = config or WarmStoreConfig()
        self._lock = threading.Lock()

        # Fact storage
        self._facts: dict[str, StateFact] = {}
        self._fact_text_hashes: set[str] = set()
        self._graph = FactGraph()

        # Critical & structural state
        self._critical = CriticalState()
        self._structural = StructuralState()

        # Event callbacks
        self._on_fact_added: list[Callable[[StateFact], None]] = []
        self._on_fact_superseded: list[Callable[[StateFact, str], None]] = []

        # Window tracking
        self._current_window_id: str = ""
        self._window_count: int = 0

    # --- Properties -----------------------------------------------------------

    @property
    def fact_count(self) -> int:
        """Number of facts currently stored."""
        return len(self._facts)

    @property
    def graph(self) -> FactGraph:
        """Underlying fact graph."""
        return self._graph

    @property
    def critical_state(self) -> CriticalState:
        """Current critical state (goal, phase, blockers, constraints)."""
        return self._critical

    @property
    def structural_state(self) -> StructuralState:
        """Current structural state."""
        return self._structural

    @property
    def window_count(self) -> int:
        """Number of windows that have advanced through this store."""
        return self._window_count

    # --- Fact operations ------------------------------------------------------

    def add_facts(self, facts: list[Fact], edges: list[FactEdge] | None = None) -> list[StateFact]:
        """Add extraction facts to the warm store, wrapping them as StateFacts.

        Args:
            facts: Facts to add.
            edges: Optional graph edges linking the facts.

        Returns:
            List of newly added ``StateFact`` objects. Duplicate IDs or content
            hashes are skipped.
        """
        added: list[StateFact] = []
        with self._lock:
            for fact in facts:
                if len(self._facts) >= self._config.max_facts:  # §audit3 H3: enforce cap
                    logger.warning("Warm store fact cap reached (%d), dropping new facts", self._config.max_facts)
                    break
                if fact.id in self._facts:
                    continue  # deduplicate by ID
                text_hash = hashlib.sha256(fact.text.encode()).hexdigest()
                if text_hash in self._fact_text_hashes:
                    continue  # deduplicate by content
                sf = StateFact.from_fact(fact)
                self._facts[fact.id] = sf
                self._fact_text_hashes.add(text_hash)
                self._graph.add_fact(fact)
                added.append(sf)
            if edges:
                for edge in edges:
                    self._graph.add_edge(edge)
        # Fire callbacks outside lock
        for sf in added:
            for cb in self._on_fact_added:
                try:
                    cb(sf)
                except Exception:  # noqa: BLE001
                    logger.exception("Fact-added callback failed for fact %s", sf.id)
        return added

    def get_facts(self, *, include_superseded: bool = False) -> list[StateFact]:
        """Return all active facts (or all including superseded).

        Args:
            include_superseded: Whether to include superseded facts.

        Returns:
            List of matching ``StateFact`` objects.
        """
        with self._lock:
            if include_superseded:
                return list(self._facts.values())
            return [sf for sf in self._facts.values() if not sf.is_superseded]

    def get_fact(self, fact_id: str) -> StateFact | None:
        """Get a specific fact by ID.

        Args:
            fact_id: Fact identifier.

        Returns:
            The ``StateFact`` or ``None`` if not found.
        """
        return self._facts.get(fact_id)

    def get_active_facts_as_extraction(self) -> list[Fact]:
        """Return active facts as extraction Fact objects (for envelope builder).

        CRP 2.2: every returned fact is stamped with a
        :class:`~crp.core.context_source.ContextSource` of kind
        :data:`~crp.core.context_source.SourceKind.WARM_STORE` when its
        ``source`` is unset — making provenance explicit for envelope
        consumers and the attestation pipeline.

        Trust: ``TrustLevel.UNKNOWN``. Warm-store content may have
        originated from any upstream tier, including untrusted external
        retrieval; CRP cannot safely upgrade trust here. Integrators who
        can prove warm-store contents were vetted should override
        ``fact.source`` upstream before the fact enters the store.
        """
        from crp.core.context_source import (
            ContextSource,
            SourceKind,
            SourceOrigin,
            TrustLevel,
        )

        with self._lock:
            facts = [sf.fact for sf in self._facts.values() if not sf.is_superseded]

        stamped: list[Fact] = []
        for f in facts:
            if f.source is None:
                f.source = ContextSource(
                    kind=SourceKind.WARM_STORE,
                    source_id=f"warm_store://fact/{f.id}",
                    origin=SourceOrigin.OBSERVED,
                    trust_level=TrustLevel.UNKNOWN,
                )
            stamped.append(f)
        return stamped

    def get_ranked_facts(self, *, top_k: int | None = None, limit: int | None = None) -> list[StateFact]:
        """Return active facts sorted by relevance heuristic (confidence × recency).

        Args:
            top_k: Maximum number of facts to return (alias for ``limit``).
            limit: Maximum number of facts to return.

        Returns:
            Active facts ranked by ``confidence * (1 / (1 + age_in_windows))``.
        """
        k = top_k or limit
        with self._lock:
            active = [sf for sf in self._facts.values() if not sf.is_superseded]
        # Simple ranking: confidence × inverse age
        active.sort(
            key=lambda sf: sf.confidence * (1.0 / (1.0 + sf.age_in_windows)),
            reverse=True,
        )
        if k is not None:
            return active[:k]
        return active

    def mark_seen(self, fact_ids: list[str], window_id: str) -> None:
        """Record that facts were included in an envelope for *window_id*.

        Args:
            fact_ids: List of fact IDs that appeared in the envelope.
            window_id: Window that consumed the facts.
        """
        with self._lock:
            for fid in fact_ids:
                sf = self._facts.get(fid)
                if sf:
                    sf.mark_seen(window_id)

    def supersede(self, old_fact_id: str, new_fact_id: str, confidence: float = 1.0) -> None:
        """Mark *old_fact_id* as superseded by *new_fact_id*.

        Args:
            old_fact_id: Fact being replaced.
            new_fact_id: Fact that replaces it.
            confidence: Confidence in the supersession relationship.
        """
        with self._lock:
            old = self._facts.get(old_fact_id)
            if old:
                old.supersede(new_fact_id, confidence)
        # Fire callback outside lock
        if old:
            for cb in self._on_fact_superseded:
                try:
                    cb(old, new_fact_id)
                except Exception:  # noqa: BLE001
                    logger.exception("Fact-superseded callback failed for fact %s", old_fact_id)

    def remove_fact(self, fact_id: str) -> StateFact | None:
        """Remove a fact (for compaction/archival).

        Args:
            fact_id: Fact to remove.

        Returns:
            The removed ``StateFact`` or ``None`` if not found.
        """
        with self._lock:
            sf = self._facts.pop(fact_id, None)
            if sf is not None:
                # Clean content-dedup hash (§audit2 STATE-H1)
                text_hash = hashlib.sha256(sf.fact.text.encode()).hexdigest()
                self._fact_text_hashes.discard(text_hash)
                # Remove from graph (§audit2 STATE-H2)
                self._graph.remove_fact(fact_id)
            return sf

    def boost_confidence(self, fact_id: str, delta: float) -> None:
        """Increase a fact's confidence by *delta*, capped at 1.0 (§22 curation).

        Args:
            fact_id: Fact to boost.
            delta: Amount to add to the fact's confidence.
        """
        with self._lock:
            sf = self._facts.get(fact_id)
            if sf:
                sf.fact.confidence = min(1.0, sf.fact.confidence + delta)

    def reduce_confidence(self, fact_id: str, delta: float) -> None:
        """Decrease a fact's confidence by *delta*, floored at 0.0 (§22 curation).

        Args:
            fact_id: Fact to reduce.
            delta: Amount to subtract from the fact's confidence.
        """
        with self._lock:
            sf = self._facts.get(fact_id)
            if sf:
                sf.fact.confidence = max(0.0, sf.fact.confidence - delta)

    # --- Window lifecycle -----------------------------------------------------

    def advance_window(self, window_id: str) -> None:
        """Called when a new window begins — age all facts, update window tracking.

        Args:
            window_id: Identifier for the new window.
        """
        with self._lock:
            self._current_window_id = window_id
            self._window_count += 1
            for sf in self._facts.values():
                sf.increment_age()

    # --- Critical state -------------------------------------------------------

    def get_critical_state(self) -> CriticalState:
        """Return the current critical state."""
        return self._critical

    def update_critical_state(self, **kwargs: Any) -> None:
        """Update critical state fields (goal, phase, blockers, constraints).

        Args:
            **kwargs: Key-value pairs to set on the critical state.
        """
        with self._lock:
            self._critical.update(**kwargs)
            self._critical.window_id = self._current_window_id

    def update_phase(self, phase: str) -> None:
        """Update the current phase and window id.

        Args:
            phase: New phase string.
        """
        with self._lock:
            self._critical.phase = phase
            self._critical.window_id = self._current_window_id

    # --- Structural state -----------------------------------------------------

    def get_structural_state(self) -> StructuralState:
        """Return the current structural state."""
        return self._structural

    def update_structural_state(self, **kwargs: Any) -> None:
        """Update structural state fields.

        Args:
            **kwargs: Key-value pairs to set on the structural state.
        """
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._structural, key):
                    setattr(self._structural, key, value)

    # --- Scoring helpers (for envelope builder) -------------------------------

    def get_seen_counts(self) -> dict[str, int]:
        """Return {fact_id: seen_count} for all facts.

        Returns:
            Mapping of fact ID to number of times it has been seen in envelopes.
        """
        with self._lock:
            return {fid: sf.seen_count for fid, sf in self._facts.items()}

    def get_fact_window_indices(self) -> dict[str, int]:
        """Return {fact_id: creation_window_index} for scoring recency.

        Returns:
            Mapping of fact ID to the window index at which it was created.
        """
        with self._lock:
            return {
                fid: self._window_count - sf.age_in_windows
                for fid, sf in self._facts.items()
            }

    # --- Event subscriptions --------------------------------------------------

    def on_fact_added(self, callback: Callable[[StateFact], None]) -> None:
        """Subscribe a callback invoked when a fact is added.

        Args:
            callback: Function receiving the newly added ``StateFact``.
        """
        self._on_fact_added.append(callback)

    def on_fact_superseded(self, callback: Callable[[StateFact, str], None]) -> None:
        """Subscribe a callback invoked when a fact is superseded.

        Args:
            callback: Function receiving the superseded ``StateFact`` and the
                replacement fact ID.
        """
        self._on_fact_superseded.append(callback)

    # --- Compaction check -----------------------------------------------------

    def needs_compaction(self) -> bool:
        """Check if warm store exceeds compaction thresholds.

        Returns:
            True if ``fact_count`` exceeds ``compact_threshold``.
        """
        return self.fact_count > self._config.compact_threshold

    # --- Serialization --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize entire warm store state.

        Returns:
            Dict containing facts, edges, critical/structural state, and window info.
        """
        with self._lock:
            return {
                "schema_version": SCHEMA_VERSION,
                "facts": {fid: sf.to_dict() for fid, sf in self._facts.items()},
                "edges": [
                    {
                        "id": e.id,
                        "source_id": e.source_id,
                        "target_id": e.target_id,
                        "relation_type": e.relation_type.value if hasattr(e.relation_type, "value") else str(e.relation_type),
                        "confidence": e.confidence,
                        "source_stage": e.source_stage,
                    }
                    for e in self._graph.edges
                ],
                "critical_state": self._critical.to_dict(),
                "structural_state": self._structural.to_dict(),
                "window_count": self._window_count,
                "current_window_id": self._current_window_id,
            }

    def load_from_dict(self, data: dict[str, Any]) -> None:
        """Restore warm store from serialized dict.

        Args:
            data: Dict produced by ``to_dict``.

        Raises:
            ValueError: If the session file schema version is newer than supported.
        """
        file_version = data.get("schema_version", 1)
        if file_version > SCHEMA_VERSION:
            raise ValueError(
                f"Session file schema v{file_version} is newer than "
                f"supported v{SCHEMA_VERSION}. Upgrade CRP."
            )
        if file_version < SCHEMA_VERSION:
            data = self._migrate(data, file_version)
        with self._lock:
            self._facts.clear()
            self._graph = FactGraph()
            self._fact_text_hashes.clear()

            for _fid, fdata in data.get("facts", {}).items():
                sf = StateFact.from_dict(fdata)
                self._facts[sf.id] = sf
                self._graph.add_fact(sf.fact)
                # Rebuild content-dedup hashes (§audit2 STATE-C1)
                text_hash = hashlib.sha256(sf.fact.text.encode()).hexdigest()
                self._fact_text_hashes.add(text_hash)

            for edata in data.get("edges", []):
                edge = FactEdge(
                    id=edata.get("id", ""),
                    source_id=edata.get("source_id", ""),
                    target_id=edata.get("target_id", ""),
                    relation_type=edata.get("relation_type", "RELATED"),
                    confidence=edata.get("confidence", 0.0),
                    source_stage=edata.get("source_stage", 0),
                )
                self._graph.add_edge(edge)

            self._critical = CriticalState.from_dict(data.get("critical_state", {}))
            self._structural = StructuralState.from_dict(data.get("structural_state", {}))
            self._window_count = data.get("window_count", 0)
            self._current_window_id = data.get("current_window_id", "")

    @staticmethod
    def _migrate(data: dict[str, Any], from_version: int) -> dict[str, Any]:
        """Incrementally migrate session data from *from_version* to current (§audit L7).

        Args:
            data: Session data dict.
            from_version: Schema version of the data.

        Returns:
            Migrated session data dict.
        """
        d = dict(data)
        if from_version < 2:
            # v1 → v2: add schema_version, ensure edges have source_stage
            d.setdefault("schema_version", 2)
            for edata in d.get("edges", []):
                edata.setdefault("source_stage", 0)
            logger.info("Migrated session data v%d → v%d", from_version, SCHEMA_VERSION)
        return d
