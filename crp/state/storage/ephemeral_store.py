# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Ephemeral Store — pointer-based large working data primitive (SPEC-035 §2.5).

High-volume tool output, intermediate results, and scratch data are stored
here as pointer-addressed entries.  The data lives in memory (or optionally
on disk); only the pointer (a short ID) lives in the session context.

Structure-aware: knows if content is tabular, JSON, code, or text.
Freshness-gated: each entry has a TTL.  Expired entries are excluded from
Operation Frames and return None.

This is the correct primitive for "these 5,000 tool-output rows" — never
force large working data through the vector index.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


class DataStructure:
    """Detected structure types for ephemeral entries."""
    TEXT = "text"
    JSON = "json"
    TABULAR = "tabular"
    CODE = "code"
    BINARY = "binary"


@dataclass
class EphemeralEntry:
    """A pointer-addressed ephemeral data entry."""

    entry_id: str
    data: Any
    structure: str = DataStructure.TEXT
    provenance: str = "UNKNOWN"   # "TOOL_GROUNDED" | "LLM" | "USER" | etc.
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0    # 5 min default; set to 0 for no expiry
    size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_fresh(self) -> bool:
        """True if the entry has not expired."""
        if self.ttl_seconds <= 0:
            return True
        return (time.time() - self.created_at) < self.ttl_seconds

    def age_seconds(self) -> float:
        """Return the elapsed seconds since the entry was created."""
        return time.time() - self.created_at


def _detect_structure(data: Any) -> str:
    """Heuristically detect data structure."""
    if isinstance(data, (dict, list)):
        return DataStructure.JSON
    if isinstance(data, str):
        stripped = data.strip()
        if stripped.startswith(("{", "[")):
            return DataStructure.JSON
        # Rough code detection
        code_markers = ("def ", "class ", "import ", "function ", "const ", "var ")
        if any(stripped.startswith(m) for m in code_markers):
            return DataStructure.CODE
        # Tabular: lines with consistent delimiter counts
        lines = stripped.split("\n")[:5]
        if len(lines) >= 2 and all("," in l or "\t" in l for l in lines):
            return DataStructure.TABULAR
    return DataStructure.TEXT


def _estimate_size(data: Any) -> int:
    """Rough byte size estimate."""
    try:
        if isinstance(data, (str, bytes)):
            return len(data)
        import json
        return len(json.dumps(data, default=str))
    except Exception:
        return 0


class EphemeralStore:
    """Pointer-based ephemeral store for high-volume working data.

    Store data with ``store()`` → get back a pointer (entry_id).
    Retrieve with ``get()`` — returns None if expired.
    Summarise with ``summarise()`` for inclusion in Operation Frames.
    """

    def __init__(self, max_entries: int = 500) -> None:
        self._store: dict[str, EphemeralEntry] = {}
        self._max_entries = max_entries

    def store(
        self,
        data: Any,
        entry_id: str = "",
        ttl_seconds: float = 300.0,
        structure: str = "auto",
        provenance: str = "UNKNOWN",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store data and return its pointer (entry_id).

        If ``entry_id`` is empty, a UUID is generated.
        ``structure="auto"`` detects structure heuristically.
        """
        import uuid
        if not entry_id:
            entry_id = str(uuid.uuid4())

        if structure == "auto":
            structure = _detect_structure(data)

        # Evict expired entries if near capacity
        if len(self._store) >= self._max_entries:
            self._evict_expired()
        if len(self._store) >= self._max_entries:
            # Evict oldest
            oldest = min(self._store.values(), key=lambda e: e.created_at)
            del self._store[oldest.entry_id]

        self._store[entry_id] = EphemeralEntry(
            entry_id=entry_id,
            data=data,
            structure=structure,
            provenance=provenance,
            ttl_seconds=ttl_seconds,
            size_bytes=_estimate_size(data),
            metadata=metadata or {},
        )
        return entry_id

    def get(self, entry_id: str) -> Any | None:
        """Return data for *entry_id* if fresh, None if expired or missing."""
        entry = self._store.get(entry_id)
        if entry is None:
            return None
        if not entry.is_fresh():
            del self._store[entry_id]
            return None
        return entry.data

    def get_entry(self, entry_id: str) -> EphemeralEntry | None:
        """Return the full EphemeralEntry (with metadata)."""
        entry = self._store.get(entry_id)
        if entry and not entry.is_fresh():
            del self._store[entry_id]
            return None
        return entry

    def get_provenance(self, entry_id: str) -> dict[str, Any]:
        """Return provenance record for decisions based on this data."""
        entry = self.get_entry(entry_id)
        if entry is None:
            return {"entry_id": entry_id, "status": "expired_or_missing"}
        return {
            "entry_id": entry_id,
            "provenance": entry.provenance,
            "structure": entry.structure,
            "created_at": entry.created_at,
            "age_seconds": entry.age_seconds(),
            "size_bytes": entry.size_bytes,
            "metadata": entry.metadata,
        }

    def summarise(self, entry_id: str, max_tokens: int = 200) -> str:
        """Structure-aware summary for inclusion in Operation Frames."""
        entry = self.get_entry(entry_id)
        if entry is None:
            return f"[ephemeral:{entry_id} — expired or not found]"

        data = entry.data
        structure = entry.structure

        if structure == DataStructure.JSON:
            try:
                import json
                text = json.dumps(data, default=str)
            except Exception:
                text = str(data)
        else:
            text = str(data)

        # Truncate to approximate token budget (4 chars/token)
        max_chars = max_tokens * 4
        if len(text) > max_chars:
            text = text[: max_chars - 20] + f"... [{len(text)} chars total]"

        return f"[{structure}:{entry_id}] {text}"

    def _evict_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        expired = [eid for eid, e in self._store.items() if not e.is_fresh()]
        for eid in expired:
            del self._store[eid]
        return len(expired)

    def entry_count(self) -> int:
        """Return the number of entries currently stored."""
        return len(self._store)

    def clear(self) -> None:
        """Remove all entries from the store."""
        self._store.clear()
