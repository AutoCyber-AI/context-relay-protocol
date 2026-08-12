# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Per-session event bus: sequence, replay buffer, and fan-out (CRP-SPEC-056 §8.3.5)."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import uuid
from collections import deque
from collections.abc import AsyncIterator, Iterator
from typing import Any

from crp.tel.events import Event

logger = logging.getLogger("crp.tel.emitter")

# Sentinel used to unblock synchronous subscribers on close.
_CLOSE: Any = object()

# Sentinel returned by ``poll`` when the timeout elapses with no event.
_TIMEOUT: Any = object()


class _SyncSubscriber(Iterator[Event]):
    """Iterator that registers its queue immediately so producers do not race it."""

    def __init__(self, bus: SessionBus) -> None:
        self._bus = bus
        self._q: queue.Queue[Any] = queue.Queue(maxsize=256)
        self._closed = False
        with bus._lock:
            if bus._closed:
                self._closed = True
            else:
                bus._sync_subs.append(self._q)

    def __iter__(self) -> Iterator[Event]:
        return self

    def __next__(self) -> Event:
        if self._closed:
            raise StopIteration
        item = self._q.get()
        if item is _CLOSE:
            raise StopIteration
        return item

    def poll(self, timeout: float) -> Event | Any | None:
        """Return the next event, ``_TIMEOUT`` on timeout, or ``None`` on close.

        Unlike :meth:`__next__` this never blocks longer than ``timeout``
        seconds, which lets callers interleave heartbeats with live events.
        """
        if self._closed:
            return None
        try:
            item = self._q.get(timeout=timeout)
        except queue.Empty:
            return _TIMEOUT
        if item is _CLOSE:
            self._closed = True
            return None
        return item


class _AsyncSubscriber(AsyncIterator[Event]):
    """Async iterator that registers its queue immediately."""

    def __init__(self, bus: SessionBus) -> None:
        self._bus = bus
        self._q: asyncio.Queue[Any] = asyncio.Queue(maxsize=256)
        self._closed = False
        with bus._lock:
            if bus._closed:
                self._closed = True
            else:
                bus._async_subs.append(self._q)

    def __aiter__(self) -> AsyncIterator[Event]:
        return self

    async def __anext__(self) -> Event:
        if self._closed:
            raise StopAsyncIteration
        item = await self._q.get()
        if item is _CLOSE:
            raise StopAsyncIteration
        return item

    async def poll(self, timeout: float) -> Event | Any | None:
        """Async variant of :meth:`_SyncSubscriber.poll`."""
        if self._closed:
            return None
        try:
            item = await asyncio.wait_for(self._q.get(), timeout)
        except TimeoutError:
            return _TIMEOUT
        if item is _CLOSE:
            self._closed = True
            return None
        return item


class SessionBus:
    """Isolated event bus for one session.

    Buffers the most recent ``buffer_size`` events so ``Last-Event-ID`` replay is
    possible, and fans out live events to both synchronous and asynchronous
    subscribers.
    """

    def __init__(self, session_id: str, buffer_size: int = 2000) -> None:
        self.session_id = session_id
        self._seq = 0
        self._buffer: deque[Event] = deque(maxlen=buffer_size)
        self._closed = False
        self._lock = threading.RLock()
        self._sync_subs: list[queue.Queue[Any]] = []
        self._async_subs: list[asyncio.Queue[Any]] = []

    @property
    def next_seq(self) -> int:
        with self._lock:
            return self._seq + 1

    def emit(self, ev: Event) -> Event:
        """Assign a sequence number, buffer, and fan out ``ev``."""
        with self._lock:
            if self._closed:
                logger.debug("Session %s is closed; dropping event", self.session_id)
                return ev
            self._seq += 1
            ev.seq = self._seq
            if not ev.id:
                ev.id = uuid.uuid4().hex[:12]
            self._buffer.append(ev)
            sync_subs = list(self._sync_subs)
            async_subs = list(self._async_subs)

        for q in sync_subs:
            try:
                q.put_nowait(ev)
            except queue.Full:
                logger.debug("Sync subscriber queue full for %s", self.session_id)

        if async_subs:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            for aq in async_subs:
                if loop is not None:
                    loop.call_soon_threadsafe(aq.put_nowait, ev)
                else:
                    # No running loop: drop the async subscriber for this emit.
                    logger.debug("No running event loop; async subscriber skipped")
        return ev

    def replay_after(self, seq: int) -> list[Event]:
        """Return all buffered events with ``seq`` greater than ``seq``."""
        with self._lock:
            return [e for e in self._buffer if e.seq > seq]

    def subscribe(self) -> _SyncSubscriber:
        """Block and yield live events until :meth:`close` is called.

        The returned iterator registers its queue immediately, so a producer
        thread started right after this call will not race the registration.
        It also exposes :meth:`_SyncSubscriber.poll` for timeout-bounded reads
        (used for SSE heartbeats).
        """
        return _SyncSubscriber(self)

    def asubscribe(self) -> _AsyncSubscriber:
        """Return an async iterator yielding live events until the bus is closed."""
        return _AsyncSubscriber(self)

    def close(self) -> None:
        """Close the bus and unblock all subscribers."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            subs = list(self._sync_subs)
            async_subs = list(self._async_subs)
        for q in subs:
            try:
                q.put_nowait(_CLOSE)
            except queue.Full:
                pass
        if async_subs:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            for aq in async_subs:
                if loop is not None:
                    loop.call_soon_threadsafe(aq.put_nowait, _CLOSE)


_buses: dict[str, SessionBus] = {}
_buses_lock = threading.Lock()


def get_bus(session_id: str, buffer_size: int = 2000) -> SessionBus:
    """Return the existing bus for ``session_id`` or create one."""
    with _buses_lock:
        bus = _buses.get(session_id)
        if bus is None:
            bus = SessionBus(session_id, buffer_size=buffer_size)
            _buses[session_id] = bus
        return bus


class Emitter:
    """Ergonomic facade agents call. Knows nothing about transport."""

    def __init__(self, session_id: str, bus: SessionBus | None = None) -> None:
        self.session_id = session_id
        self.bus = bus if bus is not None else get_bus(session_id)

    def __call__(self, ev: Event) -> Event:
        return self.bus.emit(ev)

    def close(self) -> None:
        self.bus.close()
