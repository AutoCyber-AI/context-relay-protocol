# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""SQLiteBackend — local persistent storage (SPEC-038 §3)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any

from crp.state.backends.base import StorageBackend


class SQLiteBackend(StorageBackend):
    """SQLite-backed persistent key–value store with TTL support."""

    name = "sqlite"

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._ensure_table()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    def _ensure_table(self) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                    CREATE TABLE IF NOT EXISTS crp_storage (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        expiry REAL
                    )
                    """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expiry ON crp_storage(expiry)"
            )

    def get(self, key: str) -> Any:
        """Execute get and return the result.
        
            Args:
                key (str): The key value.
        
            Returns:
                ``Any``.
        """
        with self._lock:
            self._purge_expired()
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT value FROM crp_storage WHERE key = ?", (key,)
                ).fetchone()
                if row is None:
                    return None
                return json.loads(row[0])

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
            expiry = time.time() + ttl if ttl is not None else None
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO crp_storage (key, value, expiry)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value=excluded.value,
                        expiry=excluded.expiry
                    """,
                    (key, json.dumps(value), expiry),
                )

    def delete(self, key: str) -> None:
        """Execute delete and return the result.
        
            Args:
                key (str): The key value.
        
            Returns:
                ``None``.
        """
        with self._lock, self._conn() as conn:
            conn.execute("DELETE FROM crp_storage WHERE key = ?", (key,))

    def keys(self) -> list[str]:
        """Execute keys and return the result.
        
            Returns:
                ``list[str]``.
        """
        with self._lock:
            self._purge_expired()
            with self._conn() as conn:
                return [row[0] for row in conn.execute("SELECT key FROM crp_storage")]

    def size(self) -> int:
        """Return the current size count.
        
            Returns:
                ``int``.
        """
        with self._lock:
            self._purge_expired()
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM crp_storage"
                ).fetchone()
                return row[0] if row else 0

    def _purge_expired(self) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM crp_storage WHERE expiry IS NOT NULL AND expiry <= ?",
                (time.time(),),
            )
