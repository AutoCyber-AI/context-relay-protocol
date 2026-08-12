# Copyright © 2025-2026 Constantinos Vidiniotis / AutoCyber AI Pty Ltd.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Shared async PostgreSQL connection pool.

Used by BOTH CRP Gateway and CRP Comply.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_pool: Any | None = None


async def init_db() -> None:
    """Initialize the asyncpg connection pool.

    Call once at application startup (e.g. in FastAPI lifespan).
    """
    global _pool
    import asyncpg

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    _pool = await asyncpg.create_pool(
        dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    logger.info("PostgreSQL pool initialized: %s", dsn.split("@")[-1].split("/")[0])


def get_db() -> Any:
    """Acquire a connection from the pool.

    Usage::
        async with get_db() as conn:
            row = await conn.fetchrow("SELECT ...")

    This is a synchronous factory returning an async context manager so
    callers can write ``async with get_db() as conn:`` without awaiting
    the factory itself.
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool.acquire()


async def close_db() -> None:
    """Close the connection pool. Call on shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed")
