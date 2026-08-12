# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Typed tool manifest, intent compiler, and result envelope (CRP-SPEC-059 §3).

A :class:`ToolSpec` is the developer-facing declaration of a capability. It is
agnostic of the underlying runtime — the same spec can drive a local Python
callable, an MCP tool, or a remote service. The :class:`IntentCompiler` turns a
``ToolSpec`` into a TCF :class:`CapabilityDescriptor` so the protocol can select
it without injecting the full catalogue into the model prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crp.stl.classifier import STLOperation
from crp.tools.descriptor import CapabilityDescriptor, CapabilityKind, CostProfile


@dataclass
class ToolSpec:
    """Developer-facing declaration of one tool the agent may use (SPEC-059 §3.1)."""

    capability_id: str
    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    operation_types: list[STLOperation] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    cost_profile: CostProfile = field(default_factory=CostProfile)
    kind: CapabilityKind = CapabilityKind.TOOL
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.capability_id


@dataclass
class ToolIntent:
    """A resolved intent to call a single tool with validated arguments (SPEC-059 §3.3)."""

    capability_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    operation: STLOperation | None = None


@dataclass
class CompiledTool:
    """A ``ToolSpec`` bound to a runtime implementation and TCF descriptor."""

    spec: ToolSpec
    descriptor: CapabilityDescriptor
    impl: Any = None


@dataclass
class ResultEnvelope:
    """Structured result of executing one tool (SPEC-059 §3.4)."""

    capability_id: str
    payload: Any
    status: str = "ok"
    errors: list[str] = field(default_factory=list)
    invocation_id: str = ""
    operation: STLOperation | None = None
