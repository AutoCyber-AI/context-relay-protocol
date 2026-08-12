# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Pluggable storage backends for CRP state (SPEC-038).

Backends:
    InMemoryBackend    — default for development
    SQLiteBackend      — local persistent storage
    RedisBackend       — production cache layer
    S3Backend          — cold storage for documents

Visibility API:
    client.storage.overview()  → {primitive: str, backend: str, size: int}[]
    client.knowledge.location  → "in-memory" | "sqlite" | "redis" | "s3"
"""

from __future__ import annotations

from crp.state.backends.base import StorageBackend, StorageBackendError
from crp.state.backends.memory import InMemoryBackend

__all__ = [
    "StorageBackend",
    "StorageBackendError",
    "InMemoryBackend",
]

# Deferred imports for optional backends — avoids hard dependencies
def _load_sqlite() -> type:
    from crp.state.backends.sqlite import SQLiteBackend
    return SQLiteBackend


def _load_redis() -> type:
    from crp.state.backends.redis import RedisBackend
    return RedisBackend


def _load_s3() -> type:
    from crp.state.backends.s3 import S3Backend
    return S3Backend
