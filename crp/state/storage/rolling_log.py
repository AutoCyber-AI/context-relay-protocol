# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Rolling Context Log — sequential recency primitive (SPEC-035 §2.2).

Append-only ring buffer: new entries append at the head; old entries roll
off the tail when capacity is exceeded.  Reading "the last N" is O(N) via
list slice — no search, no embedding required.

This is the Turn Log and recent-operations store.  It is NOT the vector
index — it is the "what just happened" store, accessed by position.

Access cost target: microseconds (list slice).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LogEntry:
    """A single entry in the rolling context log."""

    entry_id: str
    content: str
    entry_type: str = "turn"   # "turn" | "operation" | "fact" | "event"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    window_number: int = 0


class RollingContextLog:
    """Fixed-capacity append-only ring buffer for sequential recency access.

    When capacity is exceeded, oldest entries are discarded from the tail.
    Reading recent entries is a deque-slice — no search or embedding needed.
    """

    def __init__(self, capacity: int = 200) -> None:
        self._buf: deque[LogEntry] = deque(maxlen=capacity)
        self._capacity = capacity

    def append(self, entry: LogEntry) -> None:
        """Append an entry; oldest auto-discarded when capacity exceeded."""
        self._buf.append(entry)

    def append_turn(
        self,
        content: str,
        window_number: int = 0,
        entry_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> LogEntry:
        """Convenience: append a conversation turn."""
        import uuid
        e = LogEntry(
            entry_id=entry_id or str(uuid.uuid4()),
            content=content,
            entry_type="turn",
            metadata=metadata or {},
            window_number=window_number,
        )
        self.append(e)
        return e

    def get_recent(self, n: int = 10) -> list[LogEntry]:
        """Return the *n* most recent entries (newest last)."""
        entries = list(self._buf)
        return entries[-n:] if n < len(entries) else entries

    def get_recent_content(self, n: int = 10) -> list[str]:
        """Return content strings for the *n* most recent entries."""
        return [e.content for e in self.get_recent(n)]

    def get_window(self, window_number: int) -> list[LogEntry]:
        """Return all entries from a specific window."""
        return [e for e in self._buf if e.window_number == window_number]

    def entry_count(self) -> int:
        """Return the number of entries currently in the log."""
        return len(self._buf)

    def capacity(self) -> int:
        """Return the maximum number of entries the log can hold."""
        return self._capacity

    def clear(self) -> None:
        """Remove all entries from the log."""
        self._buf.clear()
