# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""StorageBackend ABC — base class for pluggable storage (SPEC-038 §2)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StorageBackendError(Exception):
    """Raised when a storage backend operation fails."""


class StorageBackend(ABC):
    """Base class for pluggable storage. Implement to use your own store.

    All methods are synchronous by default. Async variants may be added
    by subclasses for network-backed stores.
    """

    name: str = "abstract"

    @abstractmethod
    def get(self, key: str) -> Any:
        """Retrieve a value by key. Returns None if missing."""

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value. *ttl* is seconds until expiry (None = no expiry)."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove a key."""

    @abstractmethod
    def keys(self) -> list[str]:
        """Return all keys in the store."""

    @abstractmethod
    def size(self) -> int:
        """Return approximate number of entries."""

    def overview(self) -> dict[str, Any]:
        """Return visibility metadata for this backend."""
        return {
            "backend": self.name,
            "size": self.size(),
        }
