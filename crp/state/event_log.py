# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Event sourcing — append-only immutable fact lifecycle log (§3.2).

Every fact mutation (create, supersede, compact, archive, restore) is recorded
as a FactEvent.  The log supports temporal queries: state_at_window,
facts_between, supersession_chain.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from crp.extraction.types import Fact, FactEdge

from .fact import StateFact

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

EVENT_CREATED = "created"
EVENT_SUPERSEDED = "superseded"
EVENT_COMPACTED = "compacted"
EVENT_ARCHIVED = "archived"
EVENT_RESTORED = "restored"
EVENT_EDGE_ADDED = "edge_added"

ALL_EVENT_TYPES = frozenset(
    {EVENT_CREATED, EVENT_SUPERSEDED, EVENT_COMPACTED, EVENT_ARCHIVED, EVENT_RESTORED, EVENT_EDGE_ADDED}
)

# ---------------------------------------------------------------------------
# FactEvent (from extraction/types.py, but we re-define here with monotonic ID)
# ---------------------------------------------------------------------------


@dataclass
class FactEvent:
    """Immutable audit-log entry for a fact lifecycle event."""

    event_id: int = 0  # monotonically increasing
    timestamp: float = field(default_factory=time.time)
    window_id: str = ""
    event_type: str = ""
    fact_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a dict."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "window_id": self.window_id,
            "event_type": self.event_type,
            "fact_id": self.fact_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FactEvent:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, Any]): The data value.
        
            Returns:
                ``FactEvent``.
        """
        return cls(
            event_id=data.get("event_id", 0),
            timestamp=data.get("timestamp", 0.0),
            window_id=data.get("window_id", ""),
            event_type=data.get("event_type", ""),
            fact_id=data.get("fact_id", ""),
            payload=data.get("payload", {}),
        )


# ---------------------------------------------------------------------------
# FactEventLog — append-only, thread-safe
# ---------------------------------------------------------------------------


class FactEventLog:
    """Append-only immutable event log for fact lifecycle (§3.2).

    Supports:
    - append(): add new event with monotonic ID
    - state_at_window(): replay events to reconstruct state at a point
    - facts_between(): range query
    - supersession_chain(): full lifecycle trail for a fact
    - Temporal queries: events_since, events_for_fact
    """

    def __init__(self) -> None:
        self._events: list[FactEvent] = []
        self._next_id: int = 1
        self._lock = threading.Lock()

        # Indexes for fast lookup
        self._by_fact: dict[str, list[int]] = {}  # fact_id → [event indices]
        self._by_window: dict[str, list[int]] = {}  # window_id → [event indices]

    @property
    def size(self) -> int:
        """Return the current size count."""
        return len(self._events)

    # --- Append ---------------------------------------------------------------

    def append(
        self,
        event_type: str,
        fact_id: str,
        window_id: str,
        payload: dict[str, Any] | None = None,
    ) -> FactEvent:
        """Record an immutable event.  Returns the created event."""
        with self._lock:
            event = FactEvent(
                event_id=self._next_id,
                timestamp=time.time(),
                window_id=window_id,
                event_type=event_type,
                fact_id=fact_id,
                payload=payload or {},
            )
            idx = len(self._events)
            self._events.append(event)
            self._next_id += 1

            # Update indexes
            self._by_fact.setdefault(fact_id, []).append(idx)
            self._by_window.setdefault(window_id, []).append(idx)

        return event

    def record_fact_created(self, fact: Fact | StateFact, window_id: str) -> FactEvent:
        """Convenience: record a fact creation event."""
        fid = fact.id if isinstance(fact, StateFact) else fact.id
        text = fact.text if isinstance(fact, StateFact) else fact.text
        return self.append(
            EVENT_CREATED,
            fid,
            window_id,
            {"text": text, "confidence": fact.confidence},
        )

    def record_supersession(
        self, old_fact_id: str, new_fact_id: str, window_id: str, confidence: float = 1.0
    ) -> FactEvent:
        """Record that *old_fact_id* was superseded by *new_fact_id*."""
        return self.append(
            EVENT_SUPERSEDED,
            old_fact_id,
            window_id,
            {"superseded_by": new_fact_id, "confidence": confidence},
        )

    def record_compaction(self, fact_id: str, window_id: str, summary_id: str = "") -> FactEvent:
        """Record that *fact_id* was compacted into *summary_id*."""
        return self.append(EVENT_COMPACTED, fact_id, window_id, {"summary_id": summary_id})

    def record_archived(self, fact_id: str, window_id: str) -> FactEvent:
        """Record that *fact_id* was archived."""
        return self.append(EVENT_ARCHIVED, fact_id, window_id)

    def record_restored(self, fact_id: str, window_id: str) -> FactEvent:
        """Record that *fact_id* was restored from archive."""
        return self.append(EVENT_RESTORED, fact_id, window_id)

    def record_edge_added(self, edge: FactEdge, window_id: str) -> FactEvent:
        """Record that a graph edge was added."""
        return self.append(
            EVENT_EDGE_ADDED,
            edge.source_id,
            window_id,
            {
                "edge_id": edge.id,
                "target_id": edge.target_id,
                "relation_type": edge.relation_type.value if hasattr(edge.relation_type, "value") else str(edge.relation_type),
                "confidence": edge.confidence,
            },
        )

    # --- Temporal queries (§3.2) ----------------------------------------------

    def state_at_window(self, window_id: str) -> set[str]:
        """Replay events up to *window_id* and return the set of active fact IDs.

        An active fact is one that was created and not yet superseded/compacted/archived.
        """
        active: set[str] = set()
        with self._lock:
            target_indices = self._by_window.get(window_id)
            if target_indices is None:
                return active
            max_idx = max(target_indices)

            for event in self._events[: max_idx + 1]:
                if event.event_type == EVENT_CREATED:
                    active.add(event.fact_id)
                elif event.event_type in (EVENT_SUPERSEDED, EVENT_COMPACTED, EVENT_ARCHIVED):
                    active.discard(event.fact_id)
                elif event.event_type == EVENT_RESTORED:
                    active.add(event.fact_id)
        return active

    def facts_between(self, start_window: str, end_window: str) -> list[FactEvent]:
        """Return events between two windows (inclusive)."""
        with self._lock:
            start_indices = self._by_window.get(start_window)
            end_indices = self._by_window.get(end_window)
            if start_indices is None or end_indices is None:
                return []
            min_idx = min(start_indices)
            max_idx = max(end_indices)
            return list(self._events[min_idx: max_idx + 1])

    def supersession_chain(self, fact_id: str) -> list[FactEvent]:
        """Return the full supersession lifecycle trail for *fact_id*."""
        chain: list[FactEvent] = []
        current_id = fact_id

        with self._lock:
            visited: set[str] = set()
            while current_id and current_id not in visited:
                visited.add(current_id)
                indices = self._by_fact.get(current_id, [])
                for idx in indices:
                    event = self._events[idx]
                    chain.append(event)
                    if event.event_type == EVENT_SUPERSEDED:
                        next_id = event.payload.get("superseded_by", "")
                        if next_id:
                            current_id = next_id
                            break
                else:
                    break  # no supersession event found
        return chain

    def events_since(self, timestamp: float) -> list[FactEvent]:
        """Return all events after *timestamp*."""
        with self._lock:
            return [e for e in self._events if e.timestamp >= timestamp]

    def events_for_fact(self, fact_id: str) -> list[FactEvent]:
        """Return all events for a specific fact."""
        with self._lock:
            indices = self._by_fact.get(fact_id, [])
            return [self._events[i] for i in indices]

    def events_by_type(self, event_type: str) -> list[FactEvent]:
        """Filter events by type."""
        with self._lock:
            return [e for e in self._events if e.event_type == event_type]

    def events_in_window(self, window_id: str) -> list[FactEvent]:
        """Return all events for a specific window."""
        with self._lock:
            indices = self._by_window.get(window_id, [])
            return [self._events[i] for i in indices]

    # --- Iteration / bulk access ----------------------------------------------

    def all_events(self) -> list[FactEvent]:
        """Return a copy of all events."""
        with self._lock:
            return list(self._events)

    def __iter__(self) -> Iterator[FactEvent]:
        return iter(self._events)

    def __len__(self) -> int:
        return len(self._events)

    # --- Serialization --------------------------------------------------------

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize all events for persistence."""
        with self._lock:
            return [e.to_dict() for e in self._events]

    def load_from_list(self, events: list[dict[str, Any]]) -> None:
        """Restore from serialized event list."""
        with self._lock:
            self._events.clear()
            self._by_fact.clear()
            self._by_window.clear()
            self._next_id = 1
            for edata in events:
                event = FactEvent.from_dict(edata)
                idx = len(self._events)
                self._events.append(event)
                self._by_fact.setdefault(event.fact_id, []).append(idx)
                self._by_window.setdefault(event.window_id, []).append(idx)
                if event.event_id >= self._next_id:
                    self._next_id = event.event_id + 1

    # --- Truncation (for snapshot support) ------------------------------------

    def truncate_before(self, event_id: int) -> list[FactEvent]:
        """Remove events before *event_id*.  Returns removed events for archival."""
        with self._lock:
            cut_idx = 0
            for i, e in enumerate(self._events):
                if e.event_id >= event_id:
                    cut_idx = i
                    break
            else:
                cut_idx = len(self._events)

            removed = self._events[:cut_idx]
            self._events = self._events[cut_idx:]

            # Rebuild indexes
            self._by_fact.clear()
            self._by_window.clear()
            for i, e in enumerate(self._events):
                self._by_fact.setdefault(e.fact_id, []).append(i)
                self._by_window.setdefault(e.window_id, []).append(i)

        return removed
