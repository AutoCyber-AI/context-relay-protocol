# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Transparency Emission Layer (TEL) — stream CRP governance as AG-UI events (CRP-SPEC-056).

The ``crp.tel`` package maps CRP's internal governance evidence onto the AG-UI event
vocabulary so any standard frontend can render a CRP agent, while adding namespaced
governance events (``crp.safety_scan``, ``crp.quality``, ``crp.provenance``, ...) that
carry the protocol's differentiators.
"""

from __future__ import annotations

from crp.tel.adapter import CRPEmitter, map_agent_event
from crp.tel.emitter import Emitter, SessionBus
from crp.tel.events import (
    Event,
    EventType,
    custom,
    interrupt,
    reasoning_delta,
    reasoning_end,
    reasoning_start,
    run_error,
    run_finished,
    run_started,
    state_delta,
    state_snapshot,
    step_finished,
    step_started,
    text_delta,
    text_end,
    text_start,
    tool_args,
    tool_end,
    tool_result,
    tool_start,
)
from crp.tel.report import build_report
from crp.tel.sse import HEARTBEAT_FRAME, stream_events_sync, stream_frames_sync, to_sse

__all__ = [
    "Event",
    "EventType",
    "SessionBus",
    "Emitter",
    "CRPEmitter",
    "map_agent_event",
    "run_started",
    "run_finished",
    "run_error",
    "step_started",
    "step_finished",
    "text_start",
    "text_delta",
    "text_end",
    "reasoning_start",
    "reasoning_delta",
    "reasoning_end",
    "tool_start",
    "tool_args",
    "tool_end",
    "tool_result",
    "state_snapshot",
    "state_delta",
    "interrupt",
    "custom",
    "to_sse",
    "stream_events_sync",
    "stream_frames_sync",
    "HEARTBEAT_FRAME",
    "build_report",
]
