# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""SSE wire tests for the Transparency Emission Layer (CRP-SPEC-056)."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator

import pytest

from crp.tel import Emitter, EventType, SessionBus, run_finished, run_started, text_delta
from crp.tel.sse import (
    HEARTBEAT_FRAME,
    parse_sse,
    stream_events,
    stream_events_sync,
    stream_frames_sync,
    to_sse,
)


class TestSSEWireFormat:
    def test_to_sse_contains_required_fields(self) -> None:
        ev = run_started(goal="demo")
        wire = to_sse(ev)
        assert wire.startswith(f"id: {ev.seq}\n")
        assert "event: RUN_STARTED\n" in wire
        assert "data: {" in wire
        assert wire.endswith("\n\n")

    def test_parse_sse_multiple_events(self) -> None:
        payload = ""
        for ev in [run_started(goal="g"), text_delta(messageId="m", delta="hi")]:
            payload += to_sse(ev)
        parsed = parse_sse(payload)
        assert len(parsed) == 2
        assert parsed[0]["type"] == "RUN_STARTED"
        assert parsed[1]["type"] == "TEXT_MESSAGE_CONTENT"


class TestStreamEventsSync:
    def test_replays_then_subscribes(self) -> None:
        bus = SessionBus("sse-1")
        emitter = Emitter("sse-1", bus)
        emitter(run_started())
        emitter(text_delta(messageId="m", delta="one"))

        received: list[str] = []

        def producer() -> None:
            emitter(text_delta(messageId="m", delta="two"))
            emitter(run_finished())
            bus.close()

        t = threading.Thread(target=producer)
        t.start()
        for ev in stream_events_sync(bus, last_event_id=0):
            received.append(ev.type.value)
        t.join()

        # We replayed the text_delta with seq>0, then received the live one.
        assert received.count("TEXT_MESSAGE_CONTENT") >= 1
        assert "RUN_STARTED" in received


class TestStreamEventsAsync:
    @pytest.mark.asyncio
    async def test_async_stream(self) -> None:
        bus = SessionBus("sse-2")
        emitter = Emitter("sse-2", bus)
        emitter(run_started())

        async def producer() -> None:
            await asyncio.sleep(0.01)
            emitter(run_finished())
            bus.close()

        task = asyncio.create_task(producer())
        received: list[str] = []
        async for ev in stream_events(bus):
            received.append(ev.type.value)
        await task

        assert "RUN_STARTED" in received
        assert "RUN_FINISHED" in received


class TestStreamFrames:
    def test_frames_have_monotonic_event_ids(self) -> None:
        bus = SessionBus("frames-1")
        emitter = Emitter("frames-1", bus)
        emitter(run_started())
        emitter(text_delta(messageId="m", delta="hi"))
        bus.close()

        frames = list(stream_frames_sync(bus, heartbeat_interval=None))
        assert frames[0].startswith("id: 1\n")
        assert frames[1].startswith("id: 2\n")
        assert all(f.endswith("\n\n") for f in frames)

    def test_replay_from_last_event_id(self) -> None:
        bus = SessionBus("frames-2")
        emitter = Emitter("frames-2", bus)
        emitter(run_started())
        emitter(text_delta(messageId="m", delta="one"))
        emitter(run_finished())
        bus.close()

        # Client reconnects with Last-Event-ID: 1 — only seq 2 and 3 replay.
        frames = list(stream_frames_sync(bus, last_event_id=1, heartbeat_interval=None))
        parsed = parse_sse("".join(frames))
        assert [p["seq"] for p in parsed] == [2, 3]
        assert parsed[0]["type"] == "TEXT_MESSAGE_CONTENT"

    def test_replay_accepts_string_last_event_id(self) -> None:
        bus = SessionBus("frames-3")
        emitter = Emitter("frames-3", bus)
        emitter(run_started())
        emitter(run_finished())
        bus.close()

        frames = list(stream_frames_sync(bus, last_event_id="1", heartbeat_interval=None))
        parsed = parse_sse("".join(frames))
        assert [p["seq"] for p in parsed] == [2]

    def test_heartbeat_emitted_when_idle(self) -> None:
        bus = SessionBus("frames-4")

        def closer() -> None:
            threading.Event().wait(0.25)
            bus.close()

        t = threading.Thread(target=closer)
        t.start()
        frames = list(stream_frames_sync(bus, heartbeat_interval=0.05))
        t.join()

        assert HEARTBEAT_FRAME in frames
        # No real events were emitted, so only heartbeats should be present.
        assert all(f == HEARTBEAT_FRAME for f in frames)

    def test_live_events_interleaved_with_heartbeats(self) -> None:
        bus = SessionBus("frames-5")
        emitter = Emitter("frames-5", bus)

        def producer() -> None:
            threading.Event().wait(0.12)
            emitter(run_started())
            bus.close()

        t = threading.Thread(target=producer)
        t.start()
        frames = list(stream_frames_sync(bus, heartbeat_interval=0.03))
        t.join()

        assert HEARTBEAT_FRAME in frames
        parsed = parse_sse("".join(f for f in frames if f != HEARTBEAT_FRAME))
        assert [p["type"] for p in parsed] == ["RUN_STARTED"]


class TestGatewayTelStreamEndpoint:
    def test_handle_returns_sse_headers_and_frames(self) -> None:
        from crp.gateway.tel_stream import SSE_HEADERS, handle_tel_stream
        from crp.tel.emitter import get_bus

        bus = get_bus("gw-stream-1")
        emitter = Emitter("gw-stream-1", bus)
        emitter(run_started(goal="demo"))
        bus.close()

        result = handle_tel_stream("gw-stream-1", heartbeat_interval=None)
        assert result["status_code"] == 200
        assert result["headers"] == SSE_HEADERS
        assert result["headers"]["Content-Type"] == "text/event-stream"

        frames = list(result["body"])
        parsed = parse_sse("".join(frames))
        assert parsed[0]["type"] == "RUN_STARTED"
        assert parsed[0]["goal"] == "demo"

    def test_handle_replays_after_last_event_id(self) -> None:
        from crp.gateway.tel_stream import handle_tel_stream
        from crp.tel.emitter import get_bus

        bus = get_bus("gw-stream-2")
        emitter = Emitter("gw-stream-2", bus)
        emitter(run_started())
        emitter(text_delta(messageId="m", delta="one"))
        emitter(run_finished())
        bus.close()

        result = handle_tel_stream("gw-stream-2", last_event_id="2", heartbeat_interval=None)
        parsed = parse_sse("".join(result["body"]))
        assert [p["seq"] for p in parsed] == [3]

    def test_missing_session_id_is_400(self) -> None:
        from crp.gateway.tel_stream import handle_tel_stream

        result = handle_tel_stream("", heartbeat_interval=None)
        assert result["status_code"] == 400
