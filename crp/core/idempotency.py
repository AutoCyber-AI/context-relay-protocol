# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Request deduplication and idempotency keys (§23).

Same key within TTL returns cached result — no re-dispatch.
Concurrency model: session-level write lock for dispatch/ingest/configure,
read lock for session_status/estimate/preview.
Lock timeout: 30 seconds → CRPError(code=1003).
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TTL = 300.0      # 5 minutes
LOCK_TIMEOUT = 30.0      # seconds


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class CachedResult:
    """Cached dispatch result for idempotency."""

    idempotency_key: str = ""
    output: str = ""
    report: Any = None
    created_at: float = field(default_factory=time.time)
    ttl: float = DEFAULT_TTL

    @property
    def is_expired(self) -> bool:
        """Return whether this object is expired."""
        return time.time() > (self.created_at + self.ttl)


@dataclass
class DeduplicationStats:
    """Statistics for request deduplication."""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    evictions: int = 0


# ---------------------------------------------------------------------------
# RequestDeduplicator
# ---------------------------------------------------------------------------


class RequestDeduplicator:
    """Idempotency key manager with TTL-based cache.

    Concurrency: session-level write lock for mutations,
    reads are lock-free.
    """

    def __init__(
        self,
        ttl: float = DEFAULT_TTL,
        max_cache_size: int = 1000,
    ) -> None:
        self._ttl = ttl
        self._max_cache_size = max_cache_size
        self._cache: dict[str, CachedResult] = {}
        self._stats = DeduplicationStats()
        self._write_lock = threading.Lock()

    @property
    def stats(self) -> DeduplicationStats:
        """Return the stats."""
        return self._stats

    @property
    def cache_size(self) -> int:
        """Return the current cache count."""
        return len(self._cache)

    def compute_key(
        self,
        system_prompt: str,
        task_input: str,
        **kwargs: Any,
    ) -> str:
        """Compute idempotency key from request parameters."""
        content = f"{system_prompt}|{task_input}|{sorted(kwargs.items())}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def check(self, key: str) -> CachedResult | None:
        """Check if a non-expired result exists for this key.

        Returns cached result or None.
        """
        self._stats.total_requests += 1
        cached = self._cache.get(key)
        if cached is None:
            self._stats.cache_misses += 1
            return None
        if cached.is_expired:
            del self._cache[key]
            self._stats.cache_misses += 1
            self._stats.evictions += 1
            return None
        self._stats.cache_hits += 1
        return cached

    def store(
        self,
        key: str,
        output: str,
        report: Any = None,
    ) -> None:
        """Store a dispatch result in the cache."""
        acquired = self._write_lock.acquire(timeout=LOCK_TIMEOUT)
        if not acquired:
            return  # Could not acquire lock, skip caching

        try:
            # Evict expired entries if at capacity
            if len(self._cache) >= self._max_cache_size:
                self._evict_expired()
            # If still at capacity, evict oldest
            if len(self._cache) >= self._max_cache_size:
                oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
                del self._cache[oldest_key]
                self._stats.evictions += 1

            self._cache[key] = CachedResult(
                idempotency_key=key,
                output=output,
                report=report,
                ttl=self._ttl,
            )
        finally:
            self._write_lock.release()

    def invalidate(self, key: str) -> bool:
        """Remove a cached entry. Returns True if found and removed."""
        acquired = self._write_lock.acquire(timeout=LOCK_TIMEOUT)
        if not acquired:
            return False
        try:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
        finally:
            self._write_lock.release()

    def clear(self) -> int:
        """Clear all cached entries. Returns count of entries cleared."""
        acquired = self._write_lock.acquire(timeout=LOCK_TIMEOUT)
        if not acquired:
            return 0
        try:
            count = len(self._cache)
            self._cache.clear()
            return count
        finally:
            self._write_lock.release()

    def _evict_expired(self) -> int:
        """Remove all expired entries. Returns count evicted."""
        expired = [k for k, v in self._cache.items() if v.is_expired]
        for k in expired:
            del self._cache[k]
        self._stats.evictions += len(expired)
        return len(expired)


# ---------------------------------------------------------------------------
# Session-level locking (§23)
# ---------------------------------------------------------------------------


class SessionLock:
    """Read-write lock with ordering for session operations.

    Lock ordering (deadlock prevention):
      1. Cold Storage Lock
      2. Model Registry Lock
      3. Session Write Lock

    Write lock for: dispatch, ingest, configure, reset, close
    Read lock (no-op) for: session_status, estimate, preview
    """

    def __init__(self, timeout: float = LOCK_TIMEOUT) -> None:
        self._lock = threading.RLock()
        self._timeout = timeout
        self._readers = 0
        self._readers_lock = threading.Lock()

    def acquire_write(self) -> bool:
        """Acquire write lock. Returns True if acquired within timeout."""
        return self._lock.acquire(timeout=self._timeout)

    def release_write(self) -> None:
        """Release the session write lock."""
        self._lock.release()

    def acquire_read(self) -> bool:
        """Acquire read lock (currently a no-op for reads)."""
        return True

    def release_read(self) -> None:
        """Release the read lock (no-op in the current implementation)."""
        pass
