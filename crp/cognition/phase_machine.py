# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Hard-enforced reasoning-phase state machine (CRP-SPEC-046 §2.3).

A CognitivePreset's ``reasoning.phases[]`` is not merely a prompt hint.  When a
preset is loaded, :class:`PhasePlan` compiles the phases into an explicit
operation plan that the positioned loop follows step-by-step.  Each phase
restricts which STL operation may run and which tools may be selected, so the
agent's reasoning process becomes a protocol-level state machine rather than a
best-effort instruction.

Tool semantics per phase:
  * ``tools`` omitted or ``null`` → no tool restriction.
  * ``tools: []`` → no tools are allowed in this phase.
  * ``tools: ["id1", "id2"]`` → only those tools may be selected.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from crp.stl.classifier import STLOperation, operation_from_token

logger = logging.getLogger("crp.cognition.phase_machine")


@dataclass
class Phase:
    """One hard-enforced phase of a reasoning scaffold."""

    name: str
    prompt: str = ""
    operations: list[STLOperation] = field(default_factory=list)
    tools: list[str] | None = None
    depth: str = ""

    @property
    def operation(self) -> STLOperation:
        """The single STL operation this phase executes."""
        if self.operations:
            return self.operations[0]
        return STLOperation.GENERATE

    def allows_tool(self, capability_id: str) -> bool:
        """Return True when the phase does not restrict tools or includes this one.

        ``None`` means no restriction. An explicit empty list means no tools are
        allowed in this phase.
        """
        if self.tools is None:
            return True
        return capability_id in self.tools

    def allows_operation(self, operation: STLOperation) -> bool:
        """Return True when the phase does not restrict operations or includes this one."""
        if not self.operations:
            return True
        return operation in self.operations

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "prompt": self.prompt,
            "operation": self.operation.name,
            "allowed_operations": [op.name for op in self.operations],
            "tools": self.tools,
            "depth": self.depth,
        }


@dataclass
class PhasePlan:
    """Compiled, ordered plan of reasoning phases."""

    phases: list[Phase] = field(default_factory=list)
    loop_until: str = "complete"
    current_index: int = 0

    @property
    def current_phase(self) -> Phase | None:
        if 0 <= self.current_index < len(self.phases):
            return self.phases[self.current_index]
        return None

    def to_operations(self) -> list[STLOperation]:
        """Return the STL operation sequence the positioned loop should execute."""
        return [phase.operation for phase in self.phases]

    def copy(self) -> PhasePlan:
        """Return an independent copy so each run advances its own cursor."""
        return PhasePlan(
            phases=list(self.phases),
            loop_until=self.loop_until,
            current_index=0,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a serialisable representation of the phase plan."""
        return {
            "phases": [phase.to_dict() for phase in self.phases],
            "loop_until": self.loop_until,
            "current_index": self.current_index,
        }

    def advance(self) -> Phase | None:
        """Move to the next phase and return it, or None if finished."""
        self.current_index += 1
        return self.current_phase

    def violation_frame(
        self,
        *,
        operation: STLOperation | None = None,
        capability_id: str = "",
    ) -> dict[str, Any]:
        """Build a preventive-safety halt frame for a phase-plan violation."""
        phase = self.current_phase
        return {
            "crp_halt_reason": "PHASE_PLAN_VIOLATION",
            "halt_point": "TOOL_SELECTED" if capability_id else "OPERATION_POSITIONED",
            "problematic_frame": {
                "phase_index": self.current_index,
                "phase_name": phase.name if phase else "",
                "phase": phase.to_dict() if phase else {},
                "operation": operation.name if operation else "",
                "capability_id": capability_id,
            },
        }

    @classmethod
    def from_reasoning_scaffold(
        cls,
        phases: list[dict[str, Any]],
        loop_until: str = "complete",
    ) -> PhasePlan:
        """Build a PhasePlan from raw preset phase dicts."""
        parsed: list[Phase] = []
        for raw in phases:
            ops: list[STLOperation] = []
            for token in raw.get("operations", []):
                op = operation_from_token(str(token))
                if op is None:
                    logger.warning(
                        "Ignoring unknown operation token %r in phase %r",
                        token,
                        raw.get("name"),
                    )
                    continue
                if op not in ops:
                    ops.append(op)
            tools = raw.get("tools")
            parsed.append(
                Phase(
                    name=raw.get("name", ""),
                    prompt=raw.get("prompt", ""),
                    operations=ops,
                    tools=list(tools) if tools is not None else None,
                    depth=raw.get("depth", ""),
                )
            )
        return cls(phases=parsed, loop_until=loop_until)
