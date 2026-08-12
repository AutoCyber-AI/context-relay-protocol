# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Audit log — reconstruct sessions from recorded events (§8.9).

AuditLog stores every emitted CRPEvent and provides query helpers to:
  * Replay the full timeline for a session or time range.
  * Filter by event type.
  * Reconstruct how many facts were created / superseded / archived.

Design goals:
  * In-memory by default (no external DB).
  * Thread-safe append + query.
  * Easy to hook into EventEmitter via ``emitter.on_all(audit.record)``.
"""

from __future__ import annotations

import threading
from typing import Any

from crp.observability.events import CRPEvent


class AuditLog:
    """Immutable append-only event log with query support.

    Usage::

        audit = AuditLog()
        emitter.on_all(audit.record)   # auto-capture every event
        ...
        timeline = audit.query(session_id="abc")
        fact_events = audit.query(event_type="fact.created")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[CRPEvent] = []

    # -- recording --------------------------------------------------------

    def record(self, event: CRPEvent) -> None:
        """Append an event (thread-safe, never raises)."""
        with self._lock:
            self._events.append(event)

    # -- querying ---------------------------------------------------------

    def query(
        self,
        *,
        event_type: str | None = None,
        session_id: str | None = None,
        since: float | None = None,
        until: float | None = None,
    ) -> list[CRPEvent]:
        """Return events matching all supplied filters.

        Args:
            event_type: Exact event type string (e.g. "dispatch.completed").
            session_id: Match events whose ``data["session_id"]`` equals this.
            since: Only events with ``timestamp >= since``.
            until: Only events with ``timestamp <= until``.
        """
        with self._lock:
            results: list[CRPEvent] = []
            for ev in self._events:
                if event_type is not None and ev.event_type != event_type:
                    continue
                if session_id is not None and ev.data.get("session_id") != session_id:
                    continue
                if since is not None and ev.timestamp < since:
                    continue
                if until is not None and ev.timestamp > until:
                    continue
                results.append(ev)
            return results

    def reconstruct_session(self, session_id: str) -> dict[str, Any]:
        """Build a summary dict for *session_id* from the event stream.

        Returns a dict with keys:
          * ``session_id``
          * ``events`` — full ordered list of events (as dicts).
          * ``dispatch_count`` — number of dispatch.completed events.
          * ``facts_created`` — count of fact.created events.
          * ``facts_superseded`` — count of fact.superseded events.
          * ``duration_s`` — seconds between first and last event.
        """
        events = self.query(session_id=session_id)
        dispatch_count = sum(1 for e in events if e.event_type == "dispatch.completed")
        facts_created = sum(1 for e in events if e.event_type == "fact.created")
        facts_superseded = sum(1 for e in events if e.event_type == "fact.superseded")

        if events:
            duration = events[-1].timestamp - events[0].timestamp
        else:
            duration = 0.0

        return {
            "session_id": session_id,
            "events": [e.to_dict() for e in events],
            "dispatch_count": dispatch_count,
            "facts_created": facts_created,
            "facts_superseded": facts_superseded,
            "duration_s": round(duration, 3),
        }

    @property
    def count(self) -> int:
        """Total number of recorded events."""
        with self._lock:
            return len(self._events)

    def clear(self) -> None:
        """Remove all stored events (useful in testing)."""
        with self._lock:
            self._events.clear()
