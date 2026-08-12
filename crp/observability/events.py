# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Event emitter for CRP observability — structured event bus (§09 §9.5).

EventEmitter is a lightweight publish/subscribe bus that lets CLI,
diagnostics, and future metrics sinks observe protocol activity
without coupling to internals.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("crp.events")


# ---------------------------------------------------------------------------
# Canonical event type constants (§8.9) — 30+ named event types.
#
# Naming convention: ``<domain>.<action>``  (e.g. "session.created").
# All lowercase, dots as separators, past-tense verbs.
# ---------------------------------------------------------------------------

# Session lifecycle
SESSION_CREATED = "session.created"
SESSION_CLOSED = "session.closed"
SESSION_EXPIRED = "session.expired"
SESSION_RESTORED = "session.restored"

# Dispatch / window lifecycle
DISPATCH_STARTED = "dispatch.started"
DISPATCH_COMPLETED = "dispatch.completed"
DISPATCH_FAILED = "dispatch.failed"
WINDOW_OPENED = "window.opened"
WINDOW_COMPLETED = "window.completed"
WINDOW_CONTINUED = "window.continued"
WINDOW_CANCELLED = "window.cancelled"

# Extraction
FACT_CREATED = "fact.created"
FACT_SUPERSEDED = "fact.superseded"
FACT_COMPACTED = "fact.compacted"
FACT_ARCHIVED = "fact.archived"
FACT_RESTORED = "fact.restored"
EXTRACTION_COMPLETED = "extraction.completed"

# Ingestion
INGEST_STARTED = "ingest.started"
INGEST_COMPLETED = "ingest.completed"

# Envelope / context
ENVELOPE_BUILT = "envelope.built"
ENVELOPE_SATURATED = "envelope.saturated"  # saturation > 0.95
CONTEXT_OVERFLOW = "context.overflow"
CONTEXT_TRUNCATED = "context.truncated"

# Budget / cost
BUDGET_WARNING = "budget.warning"
BUDGET_EXHAUSTED = "budget.exhausted"
OVERHEAD_SHED = "overhead.shed"
COST_RECORDED = "cost.recorded"

# Provider / LLM
PROVIDER_CONNECTED = "provider.connected"
PROVIDER_DISCONNECTED = "provider.disconnected"
PROVIDER_ERROR = "provider.error"
PROVIDER_RETRY = "provider.retry"

# Quality
QUALITY_ASSESSED = "quality.assessed"
QUALITY_DEGRADED = "quality.degraded"

# Security
AUTH_SUCCESS = "auth.success"
AUTH_FAILURE = "auth.failure"

# Health
HEALTH_CHECK_PASSED = "health.check.passed"
HEALTH_CHECK_FAILED = "health.check.failed"

# Startup
STARTUP_COMPLETED = "startup.completed"
STARTUP_FAILED = "startup.failed"

# Collect all event types for programmatic access (useful for audit/metrics).
ALL_EVENT_TYPES: frozenset[str] = frozenset([
    SESSION_CREATED, SESSION_CLOSED, SESSION_EXPIRED, SESSION_RESTORED,
    DISPATCH_STARTED, DISPATCH_COMPLETED, DISPATCH_FAILED,
    WINDOW_OPENED, WINDOW_COMPLETED, WINDOW_CONTINUED, WINDOW_CANCELLED,
    FACT_CREATED, FACT_SUPERSEDED, FACT_COMPACTED, FACT_ARCHIVED,
    FACT_RESTORED, EXTRACTION_COMPLETED,
    INGEST_STARTED, INGEST_COMPLETED,
    ENVELOPE_BUILT, ENVELOPE_SATURATED, CONTEXT_OVERFLOW, CONTEXT_TRUNCATED,
    BUDGET_WARNING, BUDGET_EXHAUSTED, OVERHEAD_SHED, COST_RECORDED,
    PROVIDER_CONNECTED, PROVIDER_DISCONNECTED, PROVIDER_ERROR, PROVIDER_RETRY,
    QUALITY_ASSESSED, QUALITY_DEGRADED,
    AUTH_SUCCESS, AUTH_FAILURE,
    HEALTH_CHECK_PASSED, HEALTH_CHECK_FAILED,
    STARTUP_COMPLETED, STARTUP_FAILED,
])

# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------


@dataclass
class CRPEvent:
    """Single protocol event."""

    event_type: str  # e.g. "session.created", "dispatch.started", "window.completed"
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the event as a plain dict.

        Returns:
            Dict with ``event_type``, ``timestamp``, and ``data`` fields.
        """
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "data": self.data,
        }


# Listener type: callable that receives one CRPEvent.
Listener = Callable[[CRPEvent], None]


# ---------------------------------------------------------------------------
# EventEmitter
# ---------------------------------------------------------------------------


class EventEmitter:
    """Simple synchronous event bus.

    Usage::

        emitter = EventEmitter()
        emitter.on("dispatch.started", my_callback)
        emitter.emit("dispatch.started", {"task": "..."})
    """

    def __init__(self, *, max_listeners_per_event: int = 100) -> None:
        self._listeners: dict[str, list[Listener]] = {}
        self._global_listeners: list[Listener] = []
        self._started = False
        self._max_listeners = max_listeners_per_event

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        """Mark the emitter as active (startup step 6)."""
        self._started = True
        logger.debug("EventEmitter started")

    def stop(self) -> None:
        """Stop accepting and delivering events."""
        self._started = False

    @property
    def is_running(self) -> bool:
        """Return whether this object is running."""
        return self._started

    # -- subscription -----------------------------------------------------

    def on(self, event_type: str, listener: Listener) -> None:
        """Subscribe *listener* to *event_type*.

        Deduplicates listeners and enforces a per-event cap (§audit4 REL-M2).
        """
        listeners = self._listeners.setdefault(event_type, [])
        if listener in listeners:
            return
        if len(listeners) >= self._max_listeners:
            logger.warning(
                "Max listeners (%d) reached for event '%s' — ignoring",
                self._max_listeners, event_type,
            )
            return
        listeners.append(listener)

    def on_all(self, listener: Listener) -> None:
        """Subscribe *listener* to every event type."""
        if listener in self._global_listeners:
            return
        if len(self._global_listeners) >= self._max_listeners:
            logger.warning(
                "Max global listeners (%d) reached — ignoring",
                self._max_listeners,
            )
            return
        self._global_listeners.append(listener)

    def off(self, event_type: str, listener: Listener) -> bool:
        """Remove a specific listener. Returns True if removed."""
        listeners = self._listeners.get(event_type, [])
        try:
            listeners.remove(listener)
            return True
        except ValueError:
            return False

    # -- emission ---------------------------------------------------------

    def emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event to all matching listeners.

        If the emitter has not been started, events are silently dropped.
        Listener exceptions are logged but never propagate.
        """
        if not self._started:
            return
        event = CRPEvent(event_type=event_type, data=data or {})

        for listener in self._listeners.get(event_type, []):
            try:
                listener(event)
            except Exception:
                logger.exception("Listener error for %s", event_type)

        for listener in self._global_listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("Global listener error for %s", event_type)

    @property
    def listener_count(self) -> int:
        """Return the current listener count."""
        total = sum(len(v) for v in self._listeners.values())
        return total + len(self._global_listeners)
