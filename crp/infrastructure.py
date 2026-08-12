# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Infrastructure wiring from ``crp.config.yaml`` to real backends.

Users building with the CRP SDK can declaratively set where the audit trail
goes, which storage backend backs sessions/knowledge, and how ML models are
cached.  This module turns the ``infrastructure`` section of :class:`CRPConfig`
into configured runtime objects.
"""

from __future__ import annotations

import logging
from typing import Any

from crp.config import CRPConfig
from crp.ml import MANAGER

logger = logging.getLogger("crp.infrastructure")


def apply_config(config: CRPConfig | dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply infrastructure configuration and return the wired objects.

    Args:
        config: A :class:`CRPConfig` or plain dict. Defaults to ``CRPConfig()``.

    Returns:
        A dict of wired components: ``audit_sink``, ``storage_backend``,
        ``database_url``, and ``model_manager``.
    """
    if config is None:
        config = CRPConfig()
    if isinstance(config, CRPConfig):
        data = config.to_dict()
    else:
        data = dict(config)

    infra = data.get("infrastructure", {})

    # ML model manager knobs
    cache_dir = infra.get("model_cache_dir") or ""
    device = infra.get("model_device") or "auto"
    if cache_dir:
        MANAGER._default_cache_dir = cache_dir
    if device:
        MANAGER._default_device = device

    # Audit sink
    audit_sink = _build_audit_sink(infra)

    # Storage backend
    storage_backend = _build_storage_backend(infra)

    return {
        "audit_sink": audit_sink,
        "storage_backend": storage_backend,
        "database_url": infra.get("database_url", ""),
        "model_manager": MANAGER,
    }


def _build_audit_sink(infra: dict[str, Any]) -> Any:
    """Build an audit sink from infrastructure config."""
    sink_type = infra.get("audit_sink", "memory")
    if sink_type == "none":
        return None
    if sink_type == "file":
        path = infra.get("audit_path") or "crp_audit.jsonl"
        return _FileAuditSink(path)
    if sink_type == "http":
        endpoint = infra.get("audit_endpoint", "")
        if endpoint:
            return _HttpAuditSink(endpoint)
        logger.warning("audit_sink=http requires audit_endpoint")
        return None
    # memory fallback
    return _MemoryAuditSink()


class _MemoryAuditSink:
    """Simple in-memory audit sink."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self.events)


class _FileAuditSink:
    """Append-only JSONL audit sink."""

    def __init__(self, path: str) -> None:
        self.path = path

    def emit(self, event: dict[str, Any]) -> None:
        try:
            import json

            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, default=str) + "\n")
        except Exception as exc:  # noqa: BLE001
            logger.warning("File audit emit failed: %s", exc)

    def snapshot(self) -> list[dict[str, Any]]:
        try:
            import json

            with open(self.path, encoding="utf-8") as fh:
                return [json.loads(line) for line in fh if line.strip()]
        except Exception:  # noqa: BLE001
            return []


class _HttpAuditSink:
    """Fire-and-forget HTTP audit sink."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def emit(self, event: dict[str, Any]) -> None:
        try:
            import httpx

            httpx.post(self.endpoint, json=event, timeout=5)
        except Exception as exc:  # noqa: BLE001
            logger.debug("HTTP audit emit failed: %s", exc)

    def snapshot(self) -> list[dict[str, Any]]:
        return []


def _build_storage_backend(infra: dict[str, Any]) -> Any:
    """Build a storage backend from infrastructure config."""
    backend = infra.get("storage_backend", "memory")
    if backend == "memory":
        try:
            from crp.state.backends.memory import InMemoryBackend

            return InMemoryBackend()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("InMemoryBackend unavailable: %s", exc)
            return None
    if backend == "sqlite":
        path = infra.get("storage_path") or "crp_state.db"
        try:
            from crp.state.backends.sqlite import SQLiteBackend

            return SQLiteBackend(path=path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("SQLiteBackend unavailable: %s", exc)
            return None
    if backend == "redis":
        url = infra.get("redis_url", "")
        if url:
            try:
                from crp.state.backends.redis import RedisBackend

                return RedisBackend(url=url)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("RedisBackend unavailable: %s", exc)
                return None
        logger.warning("storage_backend=redis requires redis_url")
        return None
    if backend == "s3":
        bucket = infra.get("s3_bucket", "")
        prefix = infra.get("s3_prefix", "crp/")
        if bucket:
            try:
                from crp.state.backends.s3 import S3Backend

                return S3Backend(bucket=bucket, prefix=prefix)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("S3Backend unavailable: %s", exc)
                return None
        logger.warning("storage_backend=s3 requires s3_bucket")
        return None
    return None
