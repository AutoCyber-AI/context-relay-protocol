# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Intent compiler — turn Python callables / schemas into ToolSpecs (CRP-SPEC-059 §3.2).

The compiler is the bridge between the ergonomic SDK surface and the protocol's
TCF. It extracts the tool's intent from its signature, docstring, and type hints.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any, get_origin

from crp.agent_sdk.tool_manifest import CompiledTool, ToolSpec
from crp.stl.classifier import STLOperation, operation_from_token
from crp.tools.descriptor import CapabilityDescriptor, CapabilityKind, CostProfile

logger = logging.getLogger("crp.agent_sdk.intent_compiler")


_PY_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}

_NAME_TO_JSON: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
}


def _annotation_to_schema(annotation: Any) -> dict[str, Any]:
    """Convert a Python type hint to a lightweight JSON Schema fragment."""
    if annotation is inspect.Parameter.empty:
        return {"type": "string"}
    if isinstance(annotation, str):
        base = annotation.split("[", 1)[0].strip()
        return {"type": _NAME_TO_JSON.get(base, "string")}
    # Try Pydantic model schema if available
    pydantic_schema = _pydantic_schema(annotation)
    if pydantic_schema:
        return pydantic_schema
    origin = get_origin(annotation)
    if origin is not None:
        annotation = origin
    return {"type": _PY_TO_JSON.get(annotation, "string")}


def _pydantic_schema(annotation: Any) -> dict[str, Any] | None:
    """Return a JSON Schema for a Pydantic model, if the model supports it."""
    # Pydantic v2
    model_schema = getattr(annotation, "model_json_schema", None)
    if callable(model_schema):
        try:
            return model_schema()
        except Exception:  # noqa: BLE001
            pass
    # Pydantic v1
    schema_method = getattr(annotation, "schema", None)
    if callable(schema_method):
        try:
            return schema_method()
        except Exception:  # noqa: BLE001
            pass
    return None


def _callable_output_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """Infer a JSON Schema for the return annotation of ``fn``."""
    sig = inspect.signature(fn)
    annotation = sig.return_annotation
    if annotation is inspect.Signature.empty:
        return {"type": "object"}
    schema = _pydantic_schema(annotation)
    if schema:
        return schema
    if isinstance(annotation, str):
        return {"type": _NAME_TO_JSON.get(annotation.split("[", 1)[0].strip(), "string")}
    origin = get_origin(annotation)
    if origin is not None:
        annotation = origin
    return {"type": _PY_TO_JSON.get(annotation, "object")}


def _description_from_callable(fn: Callable[..., Any]) -> str:
    """First line of docstring, or the function name."""
    doc = (fn.__doc__ or "").strip()
    return doc.split("\n")[0] if doc else f"Call {getattr(fn, '__name__', 'tool')}"


def compile_tool(
    source: Callable[..., Any] | ToolSpec | dict[str, Any] | CapabilityDescriptor,
    operation_types: list[STLOperation] | None = None,
    kind: CapabilityKind = CapabilityKind.TOOL,
) -> CompiledTool:
    """Compile an arbitrary tool source into a ``CompiledTool``.

    Accepts:
      - Python callable (signature → schema)
      - :class:`ToolSpec`
      - dict with keys ``capability_id``, ``input_schema``, ``output_schema``
      - :class:`CapabilityDescriptor` (passed through)
    """
    if isinstance(source, CapabilityDescriptor):
        spec = ToolSpec(
            capability_id=source.capability_id,
            name=source.capability_id,
            description=source.description,
            input_schema=dict(source.input_schema),
            output_schema=dict(source.output_schema),
            operation_types=list(source.operation_types),
            cost_profile=source.cost_profile,
            kind=source.kind,
            metadata=dict(source.metadata),
        )
        return CompiledTool(spec=spec, descriptor=source, impl=None)

    if isinstance(source, ToolSpec):
        spec = source
    elif isinstance(source, dict):
        spec = _tool_spec_from_dict(source)
    elif callable(source):
        spec = _tool_spec_from_callable(source, operation_types, kind)
    else:
        raise TypeError(f"Cannot compile tool from {type(source).__name__}")

    descriptor = CapabilityDescriptor(
        capability_id=spec.capability_id,
        kind=spec.kind,
        operation_types=spec.operation_types or (operation_types or list(STLOperation)),
        input_schema=spec.input_schema,
        output_schema=spec.output_schema,
        cost_profile=spec.cost_profile,
        metadata={"description": spec.description, **spec.metadata},
    )
    impl = source if callable(source) else None
    return CompiledTool(spec=spec, descriptor=descriptor, impl=impl)


def _tool_spec_from_callable(
    fn: Callable[..., Any],
    operation_types: list[STLOperation] | None,
    kind: CapabilityKind,
) -> ToolSpec:
    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        properties[name] = _annotation_to_schema(param.annotation)
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return ToolSpec(
        capability_id=getattr(fn, "__name__", "tool"),
        name=getattr(fn, "__name__", "tool"),
        description=_description_from_callable(fn),
        input_schema={"type": "object", "properties": properties, "required": required},
        output_schema=_callable_output_schema(fn),
        operation_types=operation_types or list(STLOperation),
        kind=kind,
    )


def _tool_spec_from_dict(data: dict[str, Any]) -> ToolSpec:
    ops = data.get("operation_types")
    if ops is None:
        operations = list(STLOperation)
    else:
        operations = []
        for op in ops:
            if isinstance(op, STLOperation):
                operations.append(op)
            else:
                parsed = operation_from_token(str(op))
                if parsed is not None:
                    operations.append(parsed)
    return ToolSpec(
        capability_id=str(data["capability_id"]),
        name=str(data.get("name", data["capability_id"])),
        description=str(data.get("description", "")),
        input_schema=dict(data.get("input_schema", {"type": "object"})),
        output_schema=dict(data.get("output_schema", {"type": "object"})),
        operation_types=operations,
        parameters=dict(data.get("parameters", {})),
        cost_profile=CostProfile.from_dict(data.get("cost_profile", {})),
        kind=CapabilityKind(data.get("kind", "tool")),
        metadata=dict(data.get("metadata", {})),
    )


def compile_tools(
    tools: list[Any],
    operation_types: list[STLOperation] | None = None,
) -> list[CompiledTool]:
    """Compile a mixed list of tool sources."""
    return [compile_tool(t, operation_types=operation_types) for t in tools]
