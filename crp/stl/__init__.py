# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Semantic Task Layer (STL) — positioning, not injection (SPEC-031 / SPEC-049 / SPEC-050).

Modules:
    classifier        — classify_operations() 10-op taxonomy + operation token normalisers
    depth_model       — D1–D5 depth negotiation
    frame_builder     — build_operation_frame() minimal frame assembly
    goal_compass      — anchored goal-compass ensures coherence
    operation_state   — Operation State Machine (the agent knows where it is)
    tool_positioner   — Operation Frame → Tool Positioning Frame + tool-call parsing
    orchestrator      — stl_execute() the (legacy) simulated STL cycle
    positioned        — run_positioned() the live positioned-tool-loop
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from crp.stl.classifier import (
    STLOperation,
    classify_operations,
    operation_from_token,
    operation_to_token,
)
from crp.stl.depth_model import DepthLevel, negotiate_depth, renegotiate_depth
from crp.stl.frame_builder import OperationFrame, build_operation_frame
from crp.stl.goal_compass import GoalCompass, build_goal_compass
from crp.stl.operation_state import (
    InvalidTransition,
    OperationEvent,
    OperationState,
    OperationStateMachine,
)
from crp.stl.orchestrator import STLResult, stl_execute

if TYPE_CHECKING:
    from crp.stl.positioned import (
        ModelCall,
        PositionedResult,
        guard_prompt_budget,
        provider_model_call,
        run_positioned,
    )
    from crp.stl.tool_positioner import (
        CapabilitySlot,
        ParsedToolCall,
        ToolPositioningFrame,
        build_tool_positioning_frame,
        parse_tool_call,
    )

# Lazily-loaded symbols (PEP 562). ``positioned`` and ``tool_positioner`` import
# ``crp.tools``, which imports back into ``crp.stl`` — so we defer them to avoid an
# import cycle when ``crp.tools`` (or ``crp.resources``) is imported first.
_LAZY: dict[str, str] = {
    "run_positioned": "crp.stl.positioned",
    "PositionedResult": "crp.stl.positioned",
    "ModelCall": "crp.stl.positioned",
    "provider_model_call": "crp.stl.positioned",
    "guard_prompt_budget": "crp.stl.positioned",
    "ToolPositioningFrame": "crp.stl.tool_positioner",
    "CapabilitySlot": "crp.stl.tool_positioner",
    "build_tool_positioning_frame": "crp.stl.tool_positioner",
    "parse_tool_call": "crp.stl.tool_positioner",
    "ParsedToolCall": "crp.stl.tool_positioner",
}


def __getattr__(name: str) -> object:  # PEP 562
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module_path), name)

__all__ = [
    # taxonomy
    "STLOperation",
    "classify_operations",
    "operation_from_token",
    "operation_to_token",
    # depth
    "DepthLevel",
    "negotiate_depth",
    "renegotiate_depth",
    # frames
    "OperationFrame",
    "build_operation_frame",
    "GoalCompass",
    "build_goal_compass",
    # operation state machine
    "OperationState",
    "OperationStateMachine",
    "OperationEvent",
    "InvalidTransition",
    # tool positioning
    "ToolPositioningFrame",
    "CapabilitySlot",
    "build_tool_positioning_frame",
    "parse_tool_call",
    "ParsedToolCall",
    # execution
    "STLResult",
    "stl_execute",
    "run_positioned",
    "PositionedResult",
    "ModelCall",
    "provider_model_call",
    "guard_prompt_budget",
]
