# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""OpenAI tool schema ↔ CRP CapabilityDescriptor adapter (CRP-SPEC-054 §3).

Allows the Gateway to consume standard OpenAI-style ``tools`` definitions and
run them through the CRP positioned loop.
"""

from __future__ import annotations

from typing import Any

from crp.stl.classifier import STLOperation
from crp.tools.descriptor import CapabilityDescriptor, CapabilityKind, CostProfile

_OPENAI_TYPE_TO_JSON: dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}


def _normalise_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalise an OpenAI parameter schema to a lightweight JSON Schema."""
    if not isinstance(schema, dict):
        return {"type": "object"}
    out: dict[str, Any] = {"type": _OPENAI_TYPE_TO_JSON.get(schema.get("type"), "object")}
    if "properties" in schema and isinstance(schema["properties"], dict):
        out["properties"] = {
            k: _normalise_schema(v) for k, v in schema["properties"].items()
        }
    if "required" in schema and isinstance(schema["required"], list):
        out["required"] = list(schema["required"])
    if "enum" in schema:
        out["enum"] = list(schema["enum"])
    if "description" in schema:
        out["description"] = str(schema["description"])
    return out


def openai_tool_to_descriptor(tool: dict[str, Any]) -> CapabilityDescriptor:
    """Convert an OpenAI ``tools[]`` entry into a ``CapabilityDescriptor``."""
    if tool.get("type") != "function":
        raise ValueError(f"Unsupported tool type: {tool.get('type')}")
    func = tool.get("function", {})
    name = str(func.get("name", "tool"))
    description = str(func.get("description", f"Tool {name}"))
    params = _normalise_schema(func.get("parameters", {"type": "object"}))
    return CapabilityDescriptor(
        capability_id=name,
        kind=CapabilityKind.TOOL,
        operation_types=list(STLOperation),
        input_schema=params,
        output_schema={"type": "object"},
        produces_facts=True,
        cost_profile=CostProfile(),
        metadata={"description": description, "source": "openai-tool"},
    )


def descriptor_to_openai_tool(descriptor: CapabilityDescriptor) -> dict[str, Any]:
    """Convert a ``CapabilityDescriptor`` back into an OpenAI tool definition."""
    return {
        "type": "function",
        "function": {
            "name": descriptor.capability_id,
            "description": descriptor.description or f"Tool {descriptor.capability_id}",
            "parameters": descriptor.input_schema,
        },
    }


def tools_from_body(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract and validate the ``tools`` array from a chat-completion body."""
    tools = body.get("tools")
    if not tools:
        return []
    if not isinstance(tools, list):
        return []
    return tools
