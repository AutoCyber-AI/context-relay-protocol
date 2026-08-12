# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Map CRP runtime hooks to AG-UI + governance events (CRP-SPEC-056 §8.3.1)."""

from __future__ import annotations

import re
from typing import Any

from crp.agent_sdk.events import AgentEvent, AgentEventKind
from crp.tel import events as ev
from crp.tel.emitter import Emitter


class CRPEmitter:
    """Adapter: CRP governance hooks -> AG-UI-compatible event stream."""

    def __init__(self, emitter: Emitter) -> None:
        self.emit = emitter

    # -- standard lifecycle ---------------------------------------------------

    def run_started(self, goal: str = "") -> ev.Event:
        return self.emit(ev.run_started(goal=goal))

    def run_finished(self) -> ev.Event:
        return self.emit(ev.run_finished())

    def run_error(self, error: str) -> ev.Event:
        return self.emit(ev.run_error(error=error))

    def step_started(self, step: str) -> ev.Event:
        return self.emit(ev.step_started(step=step))

    def step_finished(self, step: str) -> ev.Event:
        return self.emit(ev.step_finished(step=step))

    # -- D2 governance vocabulary ---------------------------------------------

    def dpe_stage(self, stage: str, risk: str, ms: int, verdict: str) -> ev.Event:
        return self.emit(
            ev.custom("crp.safety_scan", {"stage": stage, "risk": risk, "ms": ms, "verdict": verdict})
        )

    def verification(self, ratio: float, invalid: int, repairs: int) -> ev.Event:
        return self.emit(
            ev.custom("crp.verification", {"ratio": ratio, "invalid": invalid, "repairs": repairs})
        )

    def quality(self, tier: str, confidence: float, entropy: float | None = None) -> ev.Event:
        payload: dict[str, Any] = {"tier": tier, "confidence": confidence}
        if entropy is not None:
            payload["semantic_entropy"] = entropy
        return self.emit(ev.custom("crp.quality", payload))

    def retrieval(self, sources: list[dict[str, Any]]) -> ev.Event:
        return self.emit(ev.custom("crp.retrieval", {"sources": sources}))

    def prediction(self, action: str, predicted: dict[str, Any], confidence: float) -> ev.Event:
        return self.emit(
            ev.custom("crp.prediction", {"action": action, "predicted": predicted, "confidence": confidence})
        )

    def provenance(self, prev_hash: str, this_hash: str, op: str) -> ev.Event:
        return self.emit(
            ev.custom("crp.provenance", {"op": op, "prev": prev_hash, "hash": this_hash})
        )

    def policy_envelope(self, envelope: dict[str, Any], verdict: str = "allow") -> ev.Event:
        return self.emit(ev.custom("crp.policy", {"envelope": envelope, "verdict": verdict}))

    def progress(self, percent: int, eta_seconds: int | None, confidence: str, current: str = "") -> ev.Event:
        return self.emit(
            ev.custom(
                "crp.progress",
                {"percent": percent, "eta_seconds": eta_seconds, "confidence": confidence, "current": current},
            )
        )


# ---------------------------------------------------------------------------
# AgentEvent -> TEL event mapping
# ---------------------------------------------------------------------------


def _capability_from_detail(detail: str) -> str:
    m = re.search(r"capability=([^\s,]+)", detail)
    return m.group(1) if m else detail


def _call_id_for(event: AgentEvent) -> str:
    return f"{event.operation or 'op'}_{event.operation_index}"


def map_agent_event(event: AgentEvent) -> list[ev.Event]:
    """Convert an internal :class:`AgentEvent` into AG-UI events.

    Returns a list because one internal transition may surface as multiple
    display events (e.g. tool selection + reasoning).
    """
    kind = event.kind
    op = event.operation or ""
    detail = event.detail
    data = event.data or {}

    out: list[ev.Event] = []

    if kind is AgentEventKind.INTENT_CLASSIFIED:
        out.append(
            ev.custom(
                "crp.intent",
                {"operation": op, "detail": detail, "plan": data.get("plan", [])},
            )
        )
        if detail:
            out.append(ev.reasoning_delta(messageId="reasoning", delta=detail))

    elif kind is AgentEventKind.OPERATION_POSITIONED:
        out.append(ev.step_started(step=op))
        out.append(ev.text_delta(messageId="narrative", delta=f"Positioning {op}... "))

    elif kind is AgentEventKind.TOOL_SELECTED:
        cap = _capability_from_detail(detail)
        call_id = _call_id_for(event)
        out.append(ev.tool_start(call_id=call_id, name=cap, reason=op))
        out.append(ev.reasoning_delta(messageId="reasoning", delta=f"Selected {cap}"))

    elif kind is AgentEventKind.TOOL_CALLED:
        cap = _capability_from_detail(detail)
        call_id = _call_id_for(event)
        out.append(ev.tool_args(call_id=call_id, delta=f'{{"capability":"{cap}"}}'))
        out.append(ev.tool_end(call_id=call_id))

    elif kind is AgentEventKind.OBSERVATION_RECEIVED:
        call_id = _call_id_for(event)
        content = data.get("content") if isinstance(data.get("content"), dict) else data
        out.append(ev.tool_result(call_id=call_id, content=content))

    elif kind is AgentEventKind.OPERATION_VERIFIED:
        out.append(ev.step_finished(step=op))
        out.append(
            ev.custom(
                "crp.quality",
                {"tier": data.get("tier", "A"), "confidence": data.get("confidence", 1.0)},
            )
        )

    elif kind is AgentEventKind.INTEGRATED:
        out.append(
            ev.state_delta(
                [{"op": "replace", "path": "/last_integrated", "value": op}]
            )
        )

    elif kind is AgentEventKind.HALT:
        out.append(ev.run_error(error=detail or "halted"))

    elif kind is AgentEventKind.FINAL:
        # The internal state machine is complete; the outer run may still
        # append governance events, so surface this as a CRP custom event and
        # leave RUN_FINISHED for the lifecycle owner to emit.
        out.append(ev.custom("crp.run_complete", {"operation": op, "detail": detail}))

    elif kind is AgentEventKind.CLARIFICATION_REQUESTED:
        out.append(ev.interrupt(reason=detail or "clarification_required", action=data.get("action", {})))

    return out
