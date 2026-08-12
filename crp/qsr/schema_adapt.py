# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Schema adaptation for small-model tool inputs (SPEC-050 §2.3.5).

When a tool's JSON schema is deeper than a target model's
``schema_complexity_ceiling``, flatten nested objects into plain-language string
fields before the schema enters the tool-selection window.
"""

from __future__ import annotations

from typing import Any


def _natural_name(key: str, prefix: str) -> str:
    """Build a human-readable flattened name."""
    name = f"{prefix}{key}".strip(".")
    return name.replace("_", " ")


def _flatten(
    obj: dict[str, Any], prefix: str = "", depth: int = 0, ceiling: int = 2
) -> dict[str, Any]:
    """Recursively flatten *obj* beyond *ceiling* levels."""
    out: dict[str, Any] = {}
    properties = obj.get("properties", {})
    for key, value in properties.items():
        name = _natural_name(key, prefix)
        if value.get("type") == "object" and depth >= ceiling:
            out[name] = {
                "type": "string",
                "description": f"describe {name} in plain words",
            }
        elif value.get("type") == "object":
            out.update(_flatten(value, prefix=f"{prefix}{key}.", depth=depth + 1, ceiling=ceiling))
        else:
            out[name] = value
    return out


def adapt_schema(schema: dict[str, Any], ceiling: int) -> dict[str, Any]:
    """Flatten nested objects beyond *ceiling* levels into plain-language fields.

    Args:
        schema: JSON schema dict (must be object type at root).
        ceiling: Maximum nesting depth the target model can handle reliably.

    Returns:
        A simplified schema dict.
    """
    if schema.get("type") != "object":
        return schema
    return {"type": "object", "properties": _flatten(schema, ceiling=ceiling)}
