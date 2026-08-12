# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Operation State Machine — the agent always knows where it is (CRP-SPEC-050 §5).

An agentic task is an explicit lifecycle, tracked by the protocol rather than inferred
by the model:

    INTENT_CLASSIFIED → OPERATION_POSITIONED → TOOL_SELECTED → TOOL_EXECUTED
                      → OPERATION_VERIFIED → INTEGRATED → (next) … → COMPLETE
                      (any state → HALTED on preventive safety)

Every transition emits an :class:`OperationEvent`, which is both the audit record and
the live visibility stream the UI consumes ("not a blind machine"). The machine carries
the operation plan and the current position, so a 300-operation run is always
introspectable: which operation, which state, how much of the checklist remains.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crp.stl.classifier import STLOperation, operation_to_token

logger = logging.getLogger("crp.stl.operation_state")


class OperationState(str, Enum):
    """States of the agentic operation lifecycle (CRP-SPEC-050 §5.1)."""

    INTENT_CLASSIFIED = "INTENT_CLASSIFIED"
    OPERATION_POSITIONED = "OPERATION_POSITIONED"
    TOOL_SELECTED = "TOOL_SELECTED"
    TOOL_EXECUTED = "TOOL_EXECUTED"
    OPERATION_VERIFIED = "OPERATION_VERIFIED"
    INTEGRATED = "INTEGRATED"
    COMPLETE = "COMPLETE"
    HALTED = "HALTED"


# Allowed transitions (CRP-SPEC-050 §5.2). HALTED is reachable from any live state.
_ALLOWED: dict[OperationState, set[OperationState]] = {
    OperationState.INTENT_CLASSIFIED: {OperationState.OPERATION_POSITIONED, OperationState.HALTED},
    OperationState.OPERATION_POSITIONED: {
        OperationState.TOOL_SELECTED,
        OperationState.OPERATION_VERIFIED,  # direct generation, no tool needed
        OperationState.HALTED,
    },
    OperationState.TOOL_SELECTED: {OperationState.TOOL_EXECUTED, OperationState.HALTED},
    OperationState.TOOL_EXECUTED: {OperationState.OPERATION_VERIFIED, OperationState.HALTED},
    OperationState.OPERATION_VERIFIED: {OperationState.INTEGRATED, OperationState.HALTED},
    OperationState.INTEGRATED: {
        OperationState.OPERATION_POSITIONED,  # next operation
        OperationState.COMPLETE,
        OperationState.HALTED,
    },
    OperationState.COMPLETE: set(),
    OperationState.HALTED: set(),
}


class InvalidTransition(RuntimeError):
    """Raised when an illegal state transition is attempted."""


@dataclass
class OperationEvent:
    """A single transition — both audit record and live visibility event."""

    state: OperationState
    operation: STLOperation | None = None
    operation_index: int = 0
    detail: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, object]:
        """Render the event for streaming / audit."""
        return {
            "state": self.state.value,
            "operation": operation_to_token(self.operation) if self.operation else None,
            "operation_index": self.operation_index,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


@dataclass
class OperationStateMachine:
    """Tracks the lifecycle of an agentic task across its operation plan."""

    plan: list[STLOperation] = field(default_factory=list)
    state: OperationState = OperationState.INTENT_CLASSIFIED
    current_index: int = -1  # -1 until the first operation is positioned
    events: list[OperationEvent] = field(default_factory=list)
    halt_reason: str = ""
    event_callback: Callable[[dict[str, Any]], None] | None = None

    def __post_init__(self) -> None:
        # Record the initial INTENT_CLASSIFIED state as the first event.
        event = OperationEvent(
            state=OperationState.INTENT_CLASSIFIED,
            detail=f"plan={[op.name for op in self.plan]}",
        )
        self.events.append(event)
        if self.event_callback is not None:
            try:
                self.event_callback(event.to_dict())
            except Exception:  # noqa: BLE001
                logger.debug("event_callback failed", exc_info=True)

    # -- introspection -------------------------------------------------------

    @property
    def current_operation(self) -> STLOperation | None:
        """The operation currently being executed, or None."""
        if 0 <= self.current_index < len(self.plan):
            return self.plan[self.current_index]
        return None

    @property
    def is_complete(self) -> bool:
        """Whether the plan has finished."""
        return self.state is OperationState.COMPLETE

    @property
    def is_halted(self) -> bool:
        """Whether the machine halted (preventive safety or failure)."""
        return self.state is OperationState.HALTED

    @property
    def completion(self) -> float:
        """Fraction of the plan integrated so far (0.0–1.0)."""
        if not self.plan:
            return 1.0
        done = sum(1 for e in self.events if e.state is OperationState.INTEGRATED)
        return min(done / len(self.plan), 1.0)

    @property
    def remaining(self) -> list[str]:
        """Names of operations not yet started."""
        start = self.current_index + 1 if self.current_index >= 0 else 0
        if self.state is OperationState.INTEGRATED:
            start = self.current_index + 1
        return [op.name for op in self.plan[start:]]

    # -- transitions ---------------------------------------------------------

    def can_transition(self, to_state: OperationState) -> bool:
        """Return whether a transition to ``to_state`` is legal from the current state."""
        return to_state in _ALLOWED.get(self.state, set())

    def _transition(
        self, to_state: OperationState, *, operation: STLOperation | None = None, detail: str = ""
    ) -> OperationEvent:
        if not self.can_transition(to_state):
            raise InvalidTransition(f"{self.state.value} → {to_state.value} is not allowed")
        self.state = to_state
        event = OperationEvent(
            state=to_state,
            operation=operation or self.current_operation,
            operation_index=max(self.current_index, 0),
            detail=detail,
        )
        self.events.append(event)
        if self.event_callback is not None:
            try:
                self.event_callback(event.to_dict())
            except Exception:  # noqa: BLE001
                logger.debug("event_callback failed", exc_info=True)
        logger.debug("Operation state → %s (%s)", to_state.value, detail)
        return event

    # -- convenience drivers (one per lifecycle edge) ------------------------

    def position(self, *, detail: str = "") -> OperationEvent:
        """Advance to the next operation and mark it positioned."""
        self.current_index += 1
        op = self.current_operation
        return self._transition(OperationState.OPERATION_POSITIONED, operation=op, detail=detail)

    def select_tool(self, capability_id: str) -> OperationEvent:
        """Mark that the model emitted a valid tool selection."""
        return self._transition(OperationState.TOOL_SELECTED, detail=f"capability={capability_id}")

    def execute_tool(self, capability_id: str) -> OperationEvent:
        """Mark that the selected capability executed."""
        return self._transition(OperationState.TOOL_EXECUTED, detail=f"capability={capability_id}")

    def verify(self, *, detail: str = "") -> OperationEvent:
        """Mark the operation output verified (DPE / safety check)."""
        return self._transition(OperationState.OPERATION_VERIFIED, detail=detail)

    def integrate(self, *, detail: str = "") -> OperationEvent:
        """Mark the operation result integrated into the CSO."""
        return self._transition(OperationState.INTEGRATED, detail=detail)

    def complete(self, *, detail: str = "") -> OperationEvent:
        """Mark the whole plan complete."""
        return self._transition(OperationState.COMPLETE, detail=detail)

    def halt(self, reason: str) -> OperationEvent:
        """Halt the machine (preventive safety or unrecoverable failure)."""
        self.halt_reason = reason
        return self._transition(OperationState.HALTED, detail=reason)

    def note(self, detail: str, *, operation: STLOperation | None = None) -> OperationEvent:
        """Record an informational event (e.g. a continuation window) WITHOUT a
        state transition. Visible in the event stream/audit; does not affect the
        FSM state or the completion count."""
        event = OperationEvent(
            state=self.state,
            operation=operation or self.current_operation,
            operation_index=max(self.current_index, 0),
            detail=detail,
        )
        self.events.append(event)
        if self.event_callback is not None:
            try:
                self.event_callback(event.to_dict())
            except Exception:  # noqa: BLE001
                logger.debug("event_callback failed", exc_info=True)
        return event

    # -- visibility / headers ------------------------------------------------

    def to_headers(self) -> dict[str, str]:
        """Emit the CRP-SPEC-049/050 operation headers for the current state."""
        op = self.current_operation
        headers = {
            "CRP-Agent-Operation-State": self.state.value,
            "CRP-Agent-Operation-Plan": ",".join(operation_to_token(o) for o in self.plan),
        }
        if op is not None:
            headers["CRP-Agent-Operation-Type"] = operation_to_token(op)
        return headers

    def event_stream(self) -> list[dict[str, object]]:
        """Return the full event log (for the visibility UI / audit)."""
        return [e.to_dict() for e in self.events]
