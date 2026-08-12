# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Storage Access Router — selects the right primitive per access pattern (SPEC-035 §3).

The router is the unified entry point for all context storage and retrieval
in CRP v4.  It holds instances of all five primitives and dispatches each
access to the optimal one:

    SEMANTIC   → CKF graph (associative recall + CDGR multi-hop)
    RECENCY    → RollingContextLog (sequential, position-based)
    EXACT      → InvertedIndex (key/term exact match)
    CACHED     → HotCache (repeat query acceleration)
    LARGE      → EphemeralStore (pointer-addressed high-volume data)

The performance target from SPEC-035 §1.1:
    RECENCY / EXACT / CACHED: microseconds (no embedding, no search)
    SEMANTIC / CDGR:          sub-millisecond to ~2 ms
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from .ephemeral_store import EphemeralStore
from .hot_cache import HotCache
from .inverted_index import InvertedIndex
from .rolling_log import LogEntry, RollingContextLog


class AccessPattern(str, Enum):
    """The six access patterns CRP supports (SPEC-035 §1.1)."""

    SEMANTIC = "semantic"     # similarity search → CKF graph
    RECENCY = "recency"       # "what just happened" → rolling log
    EXACT = "exact"           # named key or term → inverted index
    CACHED = "cached"         # repeat query → hot cache
    LARGE = "large"           # pointer-addressed working data → ephemeral
    GRAPH = "graph"           # multi-hop reasoning → CDGR (routed to CKF)


class StorageRouter:
    """Unified storage router — selects the right primitive per access pattern.

    The CKF graph (Primitive 1) is NOT owned by this router — it lives in
    ``ContextualKnowledgeFabric`` and is passed in via ``set_ckf()``.
    The router provides access to Primitives 2–5.

    Usage::

        router = StorageRouter()
        # Recency
        entries = router.get_recent_turns(n=5)
        # Exact
        facts = router.exact_lookup("pod_ip_fact")
        # Cache
        cached = router.get_cached(query_emb, ckf_hash)
        # Ephemeral
        ptr = router.store_ephemeral(tool_output, provenance="TOOL_GROUNDED")
        data = router.get_ephemeral(ptr)
    """

    def __init__(
        self,
        log_capacity: int = 200,
        cache_capacity: int = 128,
        cache_ttl: float = 60.0,
        ephemeral_capacity: int = 500,
    ) -> None:
        self.rolling_log = RollingContextLog(capacity=log_capacity)
        self.hot_cache = HotCache(capacity=cache_capacity, ttl_seconds=cache_ttl)
        self.inverted_index = InvertedIndex()
        self.ephemeral_store = EphemeralStore(max_entries=ephemeral_capacity)
        self._ckf: Any = None  # set via set_ckf()

    # ------------------------------------------------------------------
    # CKF registration (Primitive 1 — owned externally)
    # ------------------------------------------------------------------

    def set_ckf(self, ckf: Any) -> None:
        """Register the CKF instance for semantic / graph access."""
        self._ckf = ckf

    # ------------------------------------------------------------------
    # Recency access (Primitive 2)
    # ------------------------------------------------------------------

    def append_turn(
        self,
        content: str,
        window_number: int = 0,
        entry_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> LogEntry:
        """Append a turn to the rolling context log."""
        return self.rolling_log.append_turn(
            content=content,
            window_number=window_number,
            entry_id=entry_id,
            metadata=metadata,
        )

    def get_recent_turns(self, n: int = 10) -> list[LogEntry]:
        """Return the *n* most recent turns from the rolling log."""
        return self.rolling_log.get_recent(n)

    def get_recent_content(self, n: int = 10) -> list[str]:
        """Return content strings for the *n* most recent turns."""
        return self.rolling_log.get_recent_content(n)

    # ------------------------------------------------------------------
    # Hot cache access (Primitive 3)
    # ------------------------------------------------------------------

    def get_cached(
        self,
        query_embedding: list[float],
        ckf_state_hash: str,
    ) -> Any | None:
        """Return cached retrieval result, or None if not cached / stale."""
        self.hot_cache.set_ckf_state(ckf_state_hash)
        key = self.hot_cache.make_key(query_embedding, ckf_state_hash)
        return self.hot_cache.get(key)

    def put_cached(
        self,
        query_embedding: list[float],
        ckf_state_hash: str,
        value: Any,
    ) -> None:
        """Store a retrieval result in the hot cache."""
        self.hot_cache.set_ckf_state(ckf_state_hash)
        key = self.hot_cache.make_key(query_embedding, ckf_state_hash)
        self.hot_cache.put(key, value)

    def invalidate_cache(self, ckf_state_hash: str = "") -> None:
        """Invalidate the cache (called on CKF state change)."""
        if ckf_state_hash:
            self.hot_cache.set_ckf_state(ckf_state_hash)
        else:
            self.hot_cache.clear()

    # ------------------------------------------------------------------
    # Exact index access (Primitive 4)
    # ------------------------------------------------------------------

    def index_fact(
        self,
        fact_id: str,
        fact: Any,
        text: str = "",
        keys: list[str] | None = None,
    ) -> None:
        """Index a fact for exact-match lookup."""
        self.inverted_index.add(fact_id, fact, text=text, keys=keys)

    def exact_lookup(self, key: str) -> list[Any]:
        """Exact key lookup — returns facts matching the key."""
        return self.inverted_index.lookup_key(key)

    def term_lookup(self, term: str) -> list[Any]:
        """Single-term lookup."""
        return self.inverted_index.lookup_term(term)

    def remove_from_index(self, fact_id: str) -> None:
        """Remove a fact from the exact index (e.g. on GC/tombstone)."""
        self.inverted_index.remove(fact_id)

    # ------------------------------------------------------------------
    # Ephemeral store access (Primitive 5)
    # ------------------------------------------------------------------

    def store_ephemeral(
        self,
        data: Any,
        entry_id: str = "",
        ttl_seconds: float = 300.0,
        structure: str = "auto",
        provenance: str = "UNKNOWN",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store large working data; returns pointer (entry_id)."""
        return self.ephemeral_store.store(
            data,
            entry_id=entry_id,
            ttl_seconds=ttl_seconds,
            structure=structure,
            provenance=provenance,
            metadata=metadata,
        )

    def get_ephemeral(self, entry_id: str) -> Any | None:
        """Retrieve ephemeral data by pointer; None if expired."""
        return self.ephemeral_store.get(entry_id)

    def summarise_ephemeral(self, entry_id: str, max_tokens: int = 200) -> str:
        """Structure-aware summary for Operation Frame inclusion."""
        return self.ephemeral_store.summarise(entry_id, max_tokens)

    def get_ephemeral_provenance(self, entry_id: str) -> dict[str, Any]:
        """Provenance record for decisions based on ephemeral data."""
        return self.ephemeral_store.get_provenance(entry_id)

    # ------------------------------------------------------------------
    # Overview (SDK visibility API — SPEC-038)
    # ------------------------------------------------------------------

    def overview(self) -> list[dict[str, Any]]:
        """Return a summary of all active storage primitives."""
        return [
            {
                "primitive": "rolling_log",
                "description": "Sequential recency (turn log)",
                "entries": self.rolling_log.entry_count(),
                "capacity": self.rolling_log.capacity(),
            },
            {
                "primitive": "hot_cache",
                "description": "Repeat query acceleration",
                "entries": self.hot_cache.size(),
                "capacity": self.hot_cache.capacity(),
            },
            {
                "primitive": "inverted_index",
                "description": "Exact-match lookup",
                "facts": self.inverted_index.fact_count(),
                "terms": self.inverted_index.term_count(),
            },
            {
                "primitive": "ephemeral_store",
                "description": "Pointer-based large working data",
                "entries": self.ephemeral_store.entry_count(),
            },
            {
                "primitive": "ckf_graph",
                "description": "Semantic + multi-hop retrieval (CKF)",
                "available": self._ckf is not None,
            },
        ]
