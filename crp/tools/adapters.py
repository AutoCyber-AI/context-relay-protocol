# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Adapters — build TCF capabilities from plain Python callables (CRP v5).

Lets the SDK's ``@client.tool`` functions (and any callables) participate in the
positioned-tool-loop without hand-writing capability descriptors. Each callable
becomes a :class:`CapabilityDescriptor` (input schema inferred from its signature)
and a registered executor implementation.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from crp.stl.classifier import STLOperation
from crp.tools.capability_fabric import ToolCapabilityFabric
from crp.tools.descriptor import CapabilityDescriptor, CostProfile
from crp.tools.executor import CapabilityExecutor

_PY_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}

# String form (PEP 563 / ``from __future__ import annotations`` makes hints strings).
_NAME_TO_JSON: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
}


def _annotation_to_schema(annotation: Any) -> dict[str, str]:
    if annotation is inspect.Parameter.empty:
        return {"type": "string"}
    if isinstance(annotation, str):
        # e.g. "int", "list[str]" — take the leading bare name.
        base = annotation.split("[", 1)[0].strip()
        return {"type": _NAME_TO_JSON.get(base, "string")}
    return {"type": _PY_TO_JSON.get(annotation, "string")}


def descriptor_from_callable(
    fn: Callable[..., Any],
    operation_types: list[STLOperation] | None = None,
) -> CapabilityDescriptor:
    """Build a capability descriptor from a callable's signature and docstring."""
    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        properties[name] = _annotation_to_schema(param.annotation)
        if param.default is inspect.Parameter.empty:
            required.append(name)
    description = (fn.__doc__ or f"Call {getattr(fn, '__name__', 'tool')}").strip().split("\n")[0]
    return CapabilityDescriptor(
        capability_id=getattr(fn, "__name__", "tool"),
        operation_types=operation_types or list(STLOperation),
        input_schema={"type": "object", "properties": properties, "required": required},
        output_schema={"type": "object"},
        produces_facts=True,
        cost_profile=CostProfile(),
        metadata={"description": description},
    )


def fabric_from_callables(
    callables: list[Callable[..., Any]],
    operation_types: list[STLOperation] | None = None,
) -> tuple[ToolCapabilityFabric, CapabilityExecutor]:
    """Build a Tool Capability Fabric + executor from plain callables.

    The executor invokes each callable with keyword arguments parsed from the
    model's tool call (``fn(**args)``).
    """
    fabric = ToolCapabilityFabric()
    executor = CapabilityExecutor()
    for fn in callables:
        descriptor = descriptor_from_callable(fn, operation_types)
        fabric.register(descriptor)
        executor.register_impl(descriptor.capability_id, lambda args, _fn=fn: _fn(**args))
    return fabric, executor
