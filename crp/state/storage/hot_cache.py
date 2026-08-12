# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Hot Cache — repeat-access acceleration primitive (SPEC-035 §2.3).

LRU cache keyed by (query_hash, ckf_state_hash).  When the same query is
issued against an unchanged CKF, the prior assembled result is returned
directly without re-running CDR/CDGR.

This turns repeat retrieval (retries, parallel branches, follow-ups) into
a hash lookup — microseconds instead of milliseconds.

Invalidated when the CKF state changes (tracked via state_hash).
Short TTL (default 60 s) as a secondary safety net.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    """A cached retrieval result."""

    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    hits: int = 0


class HotCache:
    """LRU cache for repeat retrieval acceleration.

    Keys are ``(query_embedding_hash, ckf_state_hash)`` tuples.
    Entries are invalidated when ``ckf_state_hash`` changes or TTL expires.
    """

    def __init__(self, capacity: int = 128, ttl_seconds: float = 60.0) -> None:
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._capacity = capacity
        self._ttl = ttl_seconds
        self._current_ckf_hash: str = ""

    # ------------------------------------------------------------------
    # CKF state tracking
    # ------------------------------------------------------------------

    def set_ckf_state(self, state_hash: str) -> None:
        """Update the current CKF state hash.  Clears cache on change."""
        if state_hash != self._current_ckf_hash:
            self._cache.clear()
            self._current_ckf_hash = state_hash

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(query_embedding: list[float], ckf_state_hash: str) -> str:
        """Build a cache key from query embedding + CKF state hash."""
        # Bucket the embedding to tolerate tiny float variations
        bucketed = ",".join(f"{v:.3f}" for v in query_embedding[:32])
        raw = f"{bucketed}:{ckf_state_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(self, key: str) -> Any | None:
        """Return cached value or None if not found / expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        # TTL check
        if time.time() - entry.created_at > self._ttl:
            del self._cache[key]
            return None
        # LRU: move to end
        self._cache.move_to_end(key)
        entry.hits += 1
        return entry.value

    def put(self, key: str, value: Any) -> None:
        """Store a value; evict LRU entry if over capacity."""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key].value = value
            return
        if len(self._cache) >= self._capacity:
            self._cache.popitem(last=False)  # evict LRU
        self._cache[key] = CacheEntry(key=key, value=value)

    def invalidate(self, key: str) -> None:
        """Remove a single entry from the cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Remove all entries from the cache."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def size(self) -> int:
        """Return the number of cached entries."""
        return len(self._cache)

    def capacity(self) -> int:
        """Return the maximum number of entries the cache can hold."""
        return self._capacity
