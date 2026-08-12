# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""InMemoryBackend — default development storage (SPEC-038 §3)."""

from __future__ import annotations

import time
from typing import Any

from crp.state.backends.base import StorageBackend


class InMemoryBackend(StorageBackend):
    """Simple in-memory key–value store with optional TTL.

    Thread-safe via RLock.
    """

    name = "memory"

    def __init__(self) -> None:
        import threading
        self._store: dict[str, Any] = {}
        self._expiry: dict[str, float] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Any:
        """Execute get and return the result.
        
            Args:
                key (str): The key value.
        
            Returns:
                ``Any``.
        """
        with self._lock:
            self._purge_expired()
            return self._store.get(key)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Execute set and return the result.
        
            Args:
                key (str): The key value.
                value (Any): The value value.
                ttl (int | None): The ttl value.
        
            Returns:
                ``None``.
        """
        with self._lock:
            self._store[key] = value
            if ttl is not None:
                self._expiry[key] = time.time() + ttl
            else:
                self._expiry.pop(key, None)

    def delete(self, key: str) -> None:
        """Execute delete and return the result.
        
            Args:
                key (str): The key value.
        
            Returns:
                ``None``.
        """
        with self._lock:
            self._store.pop(key, None)
            self._expiry.pop(key, None)

    def keys(self) -> list[str]:
        """Execute keys and return the result.
        
            Returns:
                ``list[str]``.
        """
        with self._lock:
            self._purge_expired()
            return list(self._store.keys())

    def size(self) -> int:
        """Return the current size count.
        
            Returns:
                ``int``.
        """
        with self._lock:
            self._purge_expired()
            return len(self._store)

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [k for k, exp in self._expiry.items() if exp <= now]
        for k in expired:
            self._store.pop(k, None)
            self._expiry.pop(k, None)
