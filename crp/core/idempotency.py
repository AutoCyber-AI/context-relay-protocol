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
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TTL = 300.0      # 5 minutes
LOCK_TIMEOUT = 30.0      # seconds


def _canonicalize(value: Any) -> Any:
    """Deterministic, type-tagged JSON-safe form of an arbitrary value (U-L8).

    dicts sort by stringified key; non-JSON scalars are tagged with their
    type so ``1`` and ``"1"`` never canonicalise to the same thing.
    """
    if isinstance(value, dict):
        return {
            str(k): _canonicalize(value[k])
            for k in sorted(value, key=lambda k: str(k))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return {"__type__": type(value).__qualname__, "__repr__": repr(value)}


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
    """Idempotency key manager with TTL-based cache and single-flight.

    Concurrency: a single write lock guards all cache mutations (including
    reads that may evict), so ``check()``/``store()``/``_evict_expired()``
    can never iterate the dict concurrently with a deletion. Single-flight
    (:meth:`acquire_inflight`) coalesces concurrent identical requests —
    followers wait on the owner's completion event and then serve the
    cached result, so a retried dispatch never reaches the provider twice.
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
        self._inflight: dict[str, threading.Event] = {}

    @property
    def stats(self) -> DeduplicationStats:
        """Return the stats."""
        return self._stats

    @property
    def cache_size(self) -> int:
        """Return the current cache count."""
        with self._write_lock:
            return len(self._cache)

    def compute_key(
        self,
        system_prompt: str,
        task_input: str,
        **kwargs: Any,
    ) -> str:
        """Compute idempotency key from request parameters.

        Canonicalised via deterministic JSON (sorted keys, type-tagged
        values — audit U-L8): the pre-6.2.2 ``sorted(kwargs.items())`` +
        ``repr`` construction crashed on unorderable mixed-type values and
        was insertion-order-sensitive for nested dicts, so the same logical
        request could produce different keys.
        """
        payload = {
            "system_prompt": system_prompt,
            "task_input": task_input,
            "kwargs": _canonicalize(kwargs),
        }
        content = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def check(self, key: str) -> CachedResult | None:
        """Check if a non-expired result exists for this key.

        Returns cached result or None. Takes the write lock for the whole
        lookup (the critical section is microseconds) so an expired-entry
        eviction can never race with ``store()``/``_evict_expired()``
        iterating the dict.
        """
        acquired = self._write_lock.acquire(timeout=LOCK_TIMEOUT)
        if not acquired:
            return None  # conservative: treat as a miss
        try:
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
        finally:
            self._write_lock.release()

    def acquire_inflight(self, key: str) -> tuple[bool, threading.Event]:
        """Claim single-flight ownership of *key*.

        Returns ``(True, event)`` when the caller becomes the owner (it must
        later call :meth:`release_inflight`, which stores nothing by itself),
        or ``(False, event)`` when another thread is already dispatching this
        key — the follower then waits on the event and re-:meth:`check`s.
        """
        with self._write_lock:
            existing = self._inflight.get(key)
            if existing is not None:
                return False, existing
            event = threading.Event()
            self._inflight[key] = event
            return True, event

    def release_inflight(self, key: str, event: threading.Event) -> None:
        """Drop the single-flight claim and wake every follower of *key*."""
        with self._write_lock:
            if self._inflight.get(key) is event:
                del self._inflight[key]
        event.set()

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
    """Read-write lock with writer exclusion and timeout (§23).

    Lock ordering (deadlock prevention):
      1. Cold Storage Lock
      2. Model Registry Lock
      3. Session Write Lock

    Write lock for: dispatch, ingest, configure, reset, close
    Read lock for: session_status, estimate, preview

    Previously ``acquire_read`` was a no-op (documented as such) — reads ran
    unguarded against writers. It is now a genuine shared lock: readers
    proceed concurrently, a writer excludes everyone, and a writer waiting
    behind active readers blocks new readers from barging (writer fairness
    via the ``_writer_waiting`` flag). All acquires honour the timeout and
    return False rather than blocking forever.
    """

    def __init__(self, timeout: float = LOCK_TIMEOUT) -> None:
        self._timeout = timeout
        self._cond = threading.Condition()
        self._readers = 0
        self._writer = False
        self._writer_waiting = 0

    def acquire_write(self) -> bool:
        """Acquire the write lock. Returns True if acquired within timeout."""
        deadline = time.monotonic() + self._timeout
        with self._cond:
            self._writer_waiting += 1
            try:
                while self._writer or self._readers > 0:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
                self._writer = True
                return True
            finally:
                self._writer_waiting -= 1

    def release_write(self) -> None:
        """Release the session write lock."""
        with self._cond:
            self._writer = False
            self._cond.notify_all()

    def acquire_read(self) -> bool:
        """Acquire the read lock. Returns True if acquired within timeout."""
        deadline = time.monotonic() + self._timeout
        with self._cond:
            while self._writer or self._writer_waiting > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(remaining)
            self._readers += 1
            return True

    def release_read(self) -> None:
        """Release the read lock; wakes a waiting writer when the last
        reader leaves."""
        with self._cond:
            if self._readers > 0:
                self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()
