# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""PubSub event bus for CKF internal notifications (§3.8).

Events: fact_created, fact_superseded, edge_added, community_updated, anomaly_detected.
Subscribers receive typed payloads asynchronously (fire-and-forget).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class CKFEventType(str, Enum):
    """Events emitted by the CKF subsystem."""

    FACT_CREATED = "fact_created"
    FACT_SUPERSEDED = "fact_superseded"
    EDGE_ADDED = "edge_added"
    COMMUNITY_UPDATED = "community_updated"
    ANOMALY_DETECTED = "anomaly_detected"


@dataclass
class CKFEvent:
    """Payload for a CKF event."""

    event_type: CKFEventType
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""


# ---------------------------------------------------------------------------
# Callback type
# ---------------------------------------------------------------------------

EventCallback = Callable[[CKFEvent], None]


# ---------------------------------------------------------------------------
# PubSubEventBus
# ---------------------------------------------------------------------------


class PubSubEventBus:
    """Thread-safe pub/sub for CKF lifecycle events.

    Usage::

        bus = PubSubEventBus()
        bus.subscribe(CKFEventType.FACT_CREATED, my_handler)
        bus.publish(CKFEvent(CKFEventType.FACT_CREATED, {"fact_id": "abc"}))
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[CKFEventType, list[EventCallback]] = {
            et: [] for et in CKFEventType
        }
        self._global: list[EventCallback] = []

    # --- Subscribe ---

    def subscribe(
        self,
        event_type: CKFEventType,
        callback: EventCallback,
    ) -> None:
        """Register *callback* for events of *event_type*."""
        with self._lock:
            self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: EventCallback) -> None:
        """Register *callback* for all event types."""
        with self._lock:
            self._global.append(callback)

    def unsubscribe(
        self,
        event_type: CKFEventType,
        callback: EventCallback,
    ) -> None:
        """Remove *callback* from *event_type* subscribers."""
        with self._lock:
            subs = self._subscribers.get(event_type, [])
            if callback in subs:
                subs.remove(callback)

    # --- Publish ---

    def publish(self, event: CKFEvent) -> None:
        """Dispatch *event* to all subscribers.  Fire-and-forget — errors logged."""
        with self._lock:
            callbacks = list(self._subscribers.get(event.event_type, []))
            callbacks += list(self._global)

        for cb in callbacks:
            try:
                cb(event)
            except Exception:  # noqa: BLE001
                logger.exception("CKF event handler error for %s", event.event_type)

    # --- Introspection ---

    def subscriber_count(self, event_type: CKFEventType | None = None) -> int:
        """Return number of subscribers, optionally filtered by event type."""
        with self._lock:
            if event_type is None:
                return sum(len(v) for v in self._subscribers.values()) + len(self._global)
            return len(self._subscribers.get(event_type, [])) + len(self._global)

    def clear(self) -> None:
        """Remove all subscribers."""
        with self._lock:
            for et in self._subscribers:
                self._subscribers[et] = []
            self._global = []
