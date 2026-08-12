# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Agent SDK structured output / schema inference (SPEC-059 §3.2)."""

from __future__ import annotations

from typing import Any

from crp.agent_sdk.intent_compiler import compile_tool
from crp.stl.classifier import STLOperation


def test_output_schema_inferred_from_return_type() -> None:
    """The compiler infers a JSON Schema from the callable's return annotation."""

    def get_weather(city: str) -> dict[str, Any]:
        return {"city": city}

    compiled = compile_tool(get_weather, operation_types=[STLOperation.RETRIEVE])
    assert compiled.spec.output_schema.get("type") == "object"


def test_input_schema_marks_required_arguments() -> None:
    """Required parameters (no default) appear in input_schema.required."""

    def lookup(city: str, country: str = "AU") -> str:
        return f"{city}, {country}"

    compiled = compile_tool(lookup, operation_types=[STLOperation.RETRIEVE])
    assert "city" in compiled.spec.input_schema.get("required", [])
    assert "country" not in compiled.spec.input_schema.get("required", [])


def test_tool_spec_dict_parses_operation_tokens() -> None:
    """Operation-type tokens in a dict are normalised to STLOperation values."""
    spec: dict[str, Any] = {
        "capability_id": "lookup",
        "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        "output_schema": {"type": "object"},
        "operation_types": ["RETRIEVE", "ANALYSE"],
    }
    compiled = compile_tool(spec)
    assert STLOperation.RETRIEVE in compiled.descriptor.operation_types
    assert STLOperation.ANALYSE in compiled.descriptor.operation_types
