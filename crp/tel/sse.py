# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Server-Sent Events wire utilities and stream helpers (CRP-SPEC-056 §8.3)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

from crp.tel.emitter import _TIMEOUT, SessionBus
from crp.tel.events import Event

#: SSE comment heartbeat sent when no event arrives within the interval.
HEARTBEAT_FRAME = ": ping\n\n"


def to_sse(ev: Event) -> str:
    """Render an :class:`Event` to the SSE wire format."""
    return ev.to_sse()


def parse_sse(raw: str) -> list[dict[str, Any]]:
    """Parse a raw SSE payload into event dictionaries.

    This is a test helper and a reference parser; production clients typically
    use the browser's ``EventSource``.
    """
    events: list[dict[str, Any]] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        if line.startswith("id: "):
            current["id"] = line[4:]
        elif line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("data: "):
            current["data"] = current.get("data", "") + line[6:]
        elif line == "":
            if "data" in current:
                try:
                    events.append(json.loads(current["data"]))
                except json.JSONDecodeError:
                    events.append({"raw": current["data"]})
            current = {}
    if "data" in current:
        try:
            events.append(json.loads(current["data"]))
        except json.JSONDecodeError:
            events.append({"raw": current["data"]})
    return events


def stream_events_sync(
    bus: SessionBus,
    last_event_id: int | None = None,
    *,
    heartbeat_interval: float | None = None,
) -> Iterator[Event]:
    """Yield events from ``bus``, replaying missed events when ``last_event_id`` is given.

    This synchronous generator is useful for tests, CLIs, and adapters that run
    in a worker thread. It stops when the bus is closed.
    """
    resume_from = int(last_event_id) if last_event_id is not None else -1
    for ev in bus.replay_after(resume_from):
        yield ev

    # Block on live events until the bus closes.
    for ev in bus.subscribe():
        yield ev


async def stream_events(
    bus: SessionBus,
    last_event_id: int | None = None,
    *,
    heartbeat_interval: float | None = None,
) -> AsyncIterator[Event]:
    """Async variant of :func:`stream_events_sync`."""
    resume_from = int(last_event_id) if last_event_id is not None else -1
    for ev in bus.replay_after(resume_from):
        yield ev

    async for ev in bus.asubscribe():
        yield ev


def stream_frames_sync(
    bus: SessionBus,
    last_event_id: int | str | None = None,
    *,
    heartbeat_interval: float | None = 15.0,
) -> Iterator[str]:
    """Yield SSE wire frames (strings) with replay and heartbeats.

    Replays buffered events with ``seq > last_event_id`` first (the
    ``Last-Event-ID`` resume contract), then streams live events. When no
    event arrives within ``heartbeat_interval`` seconds a ``: ping`` comment
    frame is emitted so proxies and browsers keep the connection open.
    Stops when the bus is closed. Pass ``heartbeat_interval=None`` to disable
    heartbeats.
    """
    resume_from = int(last_event_id) if last_event_id is not None else -1
    for ev in bus.replay_after(resume_from):
        yield ev.to_sse()

    sub = bus.subscribe()
    if heartbeat_interval is None:
        for ev in sub:
            yield ev.to_sse()
        return

    while True:
        item = sub.poll(heartbeat_interval)
        if item is None:
            return
        if item is _TIMEOUT:
            yield HEARTBEAT_FRAME
            continue
        yield item.to_sse()


async def stream_frames(
    bus: SessionBus,
    last_event_id: int | str | None = None,
    *,
    heartbeat_interval: float | None = 15.0,
) -> AsyncIterator[str]:
    """Async variant of :func:`stream_frames_sync`."""
    resume_from = int(last_event_id) if last_event_id is not None else -1
    for ev in bus.replay_after(resume_from):
        yield ev.to_sse()

    sub = bus.asubscribe()
    if heartbeat_interval is None:
        async for ev in sub:
            yield ev.to_sse()
        return

    while True:
        item = await sub.poll(heartbeat_interval)
        if item is None:
            return
        if item is _TIMEOUT:
            yield HEARTBEAT_FRAME
            continue
        yield item.to_sse()
