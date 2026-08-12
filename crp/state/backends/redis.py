# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""RedisBackend — production cache layer (SPEC-038 §3).

Optional dependency: ``redis`` package. Falls back to import-time error
with helpful message if unavailable.
"""

from __future__ import annotations

import json
from typing import Any

from crp.state.backends.base import StorageBackend, StorageBackendError


class RedisBackend(StorageBackend):
    """Redis-backed storage with native TTL support."""

    name = "redis"

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        try:
            import redis
        except ImportError as exc:
            raise StorageBackendError(
                "RedisBackend requires 'redis' package. Install: pip install redis"
            ) from exc
        self._client = redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> Any:
        """Execute get and return the result.
        
            Args:
                key (str): The key value.
        
            Returns:
                ``Any``.
        """
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Execute set and return the result.
        
            Args:
                key (str): The key value.
                value (Any): The value value.
                ttl (int | None): The ttl value.
        
            Returns:
                ``None``.
        """
        raw = json.dumps(value)
        if ttl is not None:
            self._client.setex(key, ttl, raw)
        else:
            self._client.set(key, raw)

    def delete(self, key: str) -> None:
        """Execute delete and return the result.
        
            Args:
                key (str): The key value.
        
            Returns:
                ``None``.
        """
        self._client.delete(key)

    def keys(self) -> list[str]:
        """Execute keys and return the result.
        
            Returns:
                ``list[str]``.
        """
        # SCAN is safer than KEYS for production
        return [k for k in self._client.scan_iter(match="*")]

    def size(self) -> int:
        """Return the current size count.
        
            Returns:
                ``int``.
        """
        return self._client.dbsize()
