# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""AG-UI-compatible event model + CRP governance extensions (CRP-SPEC-056 §8.3.1)."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """AG-UI event vocabulary with CRP governance extensions carried in ``CUSTOM``."""

    # Lifecycle
    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"
    STEP_STARTED = "STEP_STARTED"
    STEP_FINISHED = "STEP_FINISHED"

    # Narrative substrate
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"

    # Reasoning substrate
    REASONING_START = "REASONING_START"
    REASONING_CONTENT = "REASONING_CONTENT"
    REASONING_END = "REASONING_END"

    # Tool-call substrate
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
    TOOL_CALL_END = "TOOL_CALL_END"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"

    # State synchronization
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_DELTA = "STATE_DELTA"
    MESSAGES_SNAPSHOT = "MESSAGES_SNAPSHOT"

    # Special
    INTERRUPT = "INTERRUPT"
    CUSTOM = "CUSTOM"
    RAW = "RAW"


@dataclass
class Event:
    """A single typed event on the transparency stream.

    Each event carries a monotonic ``seq`` (ordering + replay cursor), a stable
    ``id``, a wall-clock ``ts``, and a payload whose schema is determined by
    ``type``.
    """

    type: EventType
    seq: int = 0
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: float = field(default_factory=time.time)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Render as a JSON-serialisable dictionary."""
        return {
            "type": self.type.value,
            "seq": self.seq,
            "id": self.id,
            "ts": self.ts,
            **self.payload,
        }

    def to_sse(self) -> str:
        """Render to the Server-Sent Events wire format.

        The ``id:`` field enables ``Last-Event-ID`` replay; the ``event:`` field
        lets ``EventSource`` route by type.
        """
        body = self.to_dict()
        return (
            f"id: {self.seq}\n"
            f"event: {self.type.value}\n"
            f"data: {json.dumps(body, default=str)}\n\n"
        )


# ---------------------------------------------------------------------------
# Convenience constructors keep agent code readable.
# ---------------------------------------------------------------------------


def _constructor(t: EventType) -> Callable[..., Event]:
    def _fn(**payload: Any) -> Event:
        return Event(type=t, payload=payload)

    return _fn


run_started = _constructor(EventType.RUN_STARTED)
run_finished = _constructor(EventType.RUN_FINISHED)
run_error = _constructor(EventType.RUN_ERROR)
step_started = _constructor(EventType.STEP_STARTED)
step_finished = _constructor(EventType.STEP_FINISHED)

text_start = _constructor(EventType.TEXT_MESSAGE_START)
text_delta = _constructor(EventType.TEXT_MESSAGE_CONTENT)
text_end = _constructor(EventType.TEXT_MESSAGE_END)

reasoning_start = _constructor(EventType.REASONING_START)
reasoning_delta = _constructor(EventType.REASONING_CONTENT)
reasoning_end = _constructor(EventType.REASONING_END)


def tool_start(call_id: str, name: str, reason: str = "") -> Event:
    return Event(
        type=EventType.TOOL_CALL_START,
        payload={"toolCallId": call_id, "toolCallName": name, "reason": reason},
    )


def tool_args(call_id: str, delta: str) -> Event:
    return Event(
        type=EventType.TOOL_CALL_ARGS,
        payload={"toolCallId": call_id, "delta": delta},
    )


def tool_end(call_id: str) -> Event:
    return Event(
        type=EventType.TOOL_CALL_END,
        payload={"toolCallId": call_id},
    )


def tool_result(call_id: str, content: Any) -> Event:
    return Event(
        type=EventType.TOOL_CALL_RESULT,
        payload={"toolCallId": call_id, "content": content},
    )


def state_snapshot(snapshot: dict[str, Any]) -> Event:
    return Event(type=EventType.STATE_SNAPSHOT, payload={"snapshot": snapshot})


def state_delta(delta: list[dict[str, Any]]) -> Event:
    return Event(type=EventType.STATE_DELTA, payload={"delta": delta})


def interrupt(reason: str, action: dict[str, Any] | None = None) -> Event:
    return Event(
        type=EventType.INTERRUPT,
        payload={"reason": reason, "action": action or {}},
    )


def custom(name: str, value: dict[str, Any]) -> Event:
    """Namespaced governance event (e.g. ``crp.safety_scan``)."""
    return Event(type=EventType.CUSTOM, payload={"name": name, "value": value})
