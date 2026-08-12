# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tool Capability Fabric (TCF) — protocol-level tool selection (CRP-SPEC-050).

Positioning, not injection: the protocol selects the minimal 1–3 (up to 5–7 on
frontier) capabilities relevant to the current STL operation, so the model is never
flooded with the full tool catalogue.

Public API:
    CapabilityDescriptor, CostProfile, CapabilityKind, SafetyClass  — the declaration
    ToolCapabilityFabric, CapabilityProfile, PolicyContext          — the registry/selection
    CapabilitySelection, ScoredCapability, max_capabilities         — selection results
    CapabilityInvocation, GateDecision                              — invocation mediation
    CapabilityExecutor, ToolObservation, ToolExecutionResult        — execution
    ExecutionStatus, ToolResultExtractor, validate_arguments        — execution helpers
"""

from __future__ import annotations

from crp.tools.adapters import descriptor_from_callable, fabric_from_callables
from crp.tools.capability_fabric import (
    CapabilityInvocation,
    CapabilityProfile,
    CapabilitySelection,
    GateDecision,
    PolicyContext,
    ScoredCapability,
    ToolCapabilityFabric,
    max_capabilities,
)
from crp.tools.descriptor import (
    CapabilityDescriptor,
    CapabilityKind,
    CostProfile,
    SafetyClass,
)
from crp.tools.executor import (
    CapabilityExecutor,
    ExecutionStatus,
    ToolExecutionResult,
    ToolObservation,
    ToolResultExtractor,
    validate_arguments,
)

__all__ = [
    "CapabilityDescriptor",
    "CapabilityKind",
    "CostProfile",
    "SafetyClass",
    "ToolCapabilityFabric",
    "CapabilityProfile",
    "PolicyContext",
    "CapabilitySelection",
    "ScoredCapability",
    "CapabilityInvocation",
    "GateDecision",
    "max_capabilities",
    "CapabilityExecutor",
    "ToolObservation",
    "ToolExecutionResult",
    "ExecutionStatus",
    "ToolResultExtractor",
    "validate_arguments",
    "descriptor_from_callable",
    "fabric_from_callables",
]
