# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Structured decoding enforcement for tool outputs (CRP-SPEC-054 §4).

Validates model-produced tool outputs against a JSON Schema and, on mismatch,
attempts a single-turn repair prompt. The validator is intentionally a
zero-dependency subset (object/string/number/integer/boolean/array + required
and type checks) so it works on every profile.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("crp.gateway.structured_decoder")

ModelCall = Callable[[str, dict[str, Any] | None], str]


def _type_ok(value: Any, expected: str) -> bool:
    """Check whether ``value`` matches the expected JSON Schema type."""
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "null":
        return value is None
    return True


def _validate_value(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    """Recursively validate ``value`` against ``schema``."""
    errors: list[str] = []
    if not isinstance(schema, dict):
        return errors
    expected_type = schema.get("type")
    if expected_type:
        if isinstance(expected_type, list):
            if not any(_type_ok(value, t) for t in expected_type):
                errors.append(f"{path}: expected one of {expected_type}, got {type(value).__name__}")
        elif not _type_ok(value, expected_type):
            errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value not in enum {schema['enum']}")
    if expected_type == "object" and isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required field {key!r}")
        props = schema.get("properties", {})
        for key, sub_value in value.items():
            sub_schema = props.get(key)
            if sub_schema is not None:
                errors.extend(_validate_value(sub_value, sub_schema, f"{path}.{key}"))
    if expected_type == "array" and isinstance(value, list):
        items_schema = schema.get("items")
        if items_schema is not None:
            for i, item in enumerate(value):
                errors.extend(_validate_value(item, items_schema, f"{path}[{i}]"))
    return errors


def validate_output(payload: Any, output_schema: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (valid, errors) for ``payload`` against ``output_schema``."""
    errors = _validate_value(payload, output_schema, "$")
    return (not errors, errors)


def parse_json_output(raw_text: str) -> Any:
    """Best-effort parse of a JSON value from model text."""
    text = raw_text.strip()
    # Strip code fences.
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("\n```", 1)[0].strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        # Try to grab the first JSON object/array.
        for start_char, end_char in (("{", "}"), ("[", "]")):
            start = text.find(start_char)
            if start == -1:
                continue
            depth = 0
            for i in range(start, len(text)):
                if text[i] == start_char:
                    depth += 1
                elif text[i] == end_char:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except (ValueError, TypeError):
                            break
        raise ValueError("No JSON object or array found in output") from None


def repair_output(
    raw_text: str,
    output_schema: dict[str, Any],
    model_call: ModelCall,
    max_retries: int = 1,
) -> Any:
    """Ask the model to repair ``raw_text`` so it conforms to ``output_schema``."""
    current = raw_text
    for attempt in range(max_retries):
        prompt = (
            "The following output does not conform to the required JSON schema.\n\n"
            f"Schema: {json.dumps(output_schema)}\n\n"
            f"Output: {current}\n\n"
            "Return ONLY a corrected JSON object (or array) that matches the schema."
        )
        try:
            current = model_call(prompt, output_schema)
            return parse_json_output(current)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Repair attempt %d failed: %s", attempt + 1, exc)
    return None


def enforce_output(
    raw_text: str,
    output_schema: dict[str, Any],
    model_call: ModelCall,
    allow_repair: bool = True,
) -> dict[str, Any]:
    """Validate ``raw_text`` and optionally repair it.

    Returns a dict with keys:
      - ``ok``: bool
      - ``value``: parsed JSON value (or None)
      - ``errors``: list of validation/repair errors
      - ``repaired``: bool
    """
    try:
        value = parse_json_output(raw_text)
    except ValueError as exc:
        if allow_repair:
            value = repair_output(raw_text, output_schema, model_call)
            if value is not None:
                valid, errors = validate_output(value, output_schema)
                return {"ok": valid, "value": value, "errors": errors, "repaired": True}
        return {"ok": False, "value": None, "errors": [str(exc)], "repaired": False}

    valid, errors = validate_output(value, output_schema)
    if valid:
        return {"ok": True, "value": value, "errors": [], "repaired": False}

    if allow_repair:
        repaired = repair_output(raw_text, output_schema, model_call)
        if repaired is not None:
            valid2, errors2 = validate_output(repaired, output_schema)
            return {"ok": valid2, "value": repaired, "errors": errors2, "repaired": True}

    return {"ok": False, "value": value, "errors": errors, "repaired": False}
