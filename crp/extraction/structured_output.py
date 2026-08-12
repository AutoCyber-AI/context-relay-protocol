# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Structured output handling — schema/grammar enforcement (§06 §6.9, 2J).

Supports: Outlines FSM, GBNF grammar, logit masking, fallback JSON repair.
All integrations are optional — graceful fallback if libraries unavailable.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON repair (always available — no external deps)
# ---------------------------------------------------------------------------

def repair_json(raw: str) -> str | None:
    """Best-effort repair of malformed JSON.

    Handles: trailing commas, unquoted keys, single quotes, truncated output.
    Returns the repaired JSON string, or None if unrecoverable.
    """
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    # Try direct parse first
    try:
        json.loads(cleaned)
        return cleaned
    except (json.JSONDecodeError, ValueError):
        pass

    # Fix single quotes → double quotes (naive — handles simple cases)
    attempt = cleaned.replace("'", '"')
    try:
        json.loads(attempt)
        return attempt
    except (json.JSONDecodeError, ValueError):
        pass

    # Remove trailing commas before } or ]
    attempt = re.sub(r",\s*([}\]])", r"\1", attempt)
    try:
        json.loads(attempt)
        return attempt
    except (json.JSONDecodeError, ValueError):
        pass

    # Try closing truncated output
    open_braces = attempt.count("{") - attempt.count("}")
    open_brackets = attempt.count("[") - attempt.count("]")
    if open_braces > 0 or open_brackets > 0:
        attempt += "}" * max(open_braces, 0)
        attempt += "]" * max(open_brackets, 0)
        try:
            json.loads(attempt)
            return attempt
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def validate_json_schema(data: Any, schema: dict[str, Any]) -> list[str]:
    """Validate *data* against JSON Schema. Returns list of error messages."""
    try:
        import jsonschema  # type: ignore[import-untyped]

        validator = jsonschema.Draft7Validator(schema)
        return [e.message for e in validator.iter_errors(data)]
    except ImportError:
        # jsonschema not installed — skip validation
        return []


# ---------------------------------------------------------------------------
# Outlines FSM integration (optional)
# ---------------------------------------------------------------------------

class OutlinesFSMHandler:
    """Outlines-based constrained generation via finite state machine."""

    def __init__(self) -> None:
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        """Return whether this object is available."""
        if self._available is None:
            try:
                import outlines  # type: ignore[import-untyped]  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def build_guide(self, schema: dict[str, Any]) -> Any:
        """Build an Outlines JSON guide from a JSON Schema."""
        if not self.is_available:
            return None
        try:
            from outlines.generate import json as outlines_json  # type: ignore[import-untyped]

            return outlines_json(schema)
        except Exception:
            logger.warning("Failed to build Outlines guide")
            return None


# ---------------------------------------------------------------------------
# GBNF grammar support (for llama.cpp providers)
# ---------------------------------------------------------------------------

def json_schema_to_gbnf(schema: dict[str, Any]) -> str | None:
    """Convert a simple JSON Schema to GBNF grammar string.

    Handles flat object schemas with string/number/boolean/array properties.
    Complex nested schemas require the full llama.cpp grammar converter.
    """
    props = schema.get("properties", {})
    if not props:
        return None

    rules: list[str] = ['root ::= "{" ws']
    prop_rules: list[str] = []

    for i, (name, prop_schema) in enumerate(props.items()):
        ptype = prop_schema.get("type", "string")
        sep = ', "' if i > 0 else '"'
        type_rule = _type_to_gbnf(ptype, name)
        prop_rules.append(f'{sep}{name}": ' + type_rule)

    rules.append(" ".join(prop_rules))
    rules.append('ws "}"')
    rules.append('ws ::= [ \\t\\n]*')
    rules.append('string ::= "\\"" [^"\\\\]* "\\""')
    rules.append('number ::= "-"? [0-9]+ ("." [0-9]+)?')
    rules.append('boolean ::= "true" | "false"')

    return "\n".join(rules)


def _type_to_gbnf(json_type: str, _name: str) -> str:
    mapping = {
        "string": "ws string",
        "number": "ws number",
        "integer": "ws number",
        "boolean": "ws boolean",
    }
    return mapping.get(json_type, "ws string")


# ---------------------------------------------------------------------------
# Composite handler
# ---------------------------------------------------------------------------

class StructuredOutputHandler:
    """Orchestrates structured-output enforcement.

    Priority order:
    1. Outlines FSM (if available and provider supports it)
    2. GBNF grammar (if provider is llama.cpp compatible)
    3. Logit masking (if provider supports token-level constraints)
    4. Fallback: post-hoc JSON repair + validation
    """

    def __init__(self) -> None:
        self._outlines = OutlinesFSMHandler()

    @property
    def outlines_available(self) -> bool:
        """Return the outlines available."""
        return self._outlines.is_available

    def enforce(
        self,
        raw_output: str,
        schema: dict[str, Any] | None = None,
    ) -> tuple[Any | None, list[str]]:
        """Attempt to parse and validate *raw_output* against *schema*.

        Returns ``(parsed_data, errors)`` where *errors* is empty on success.
        """
        if schema is None:
            # No schema — just try to parse as JSON
            try:
                return json.loads(raw_output), []
            except (json.JSONDecodeError, ValueError):
                repaired = repair_json(raw_output)
                if repaired is not None:
                    return json.loads(repaired), ["json_repaired"]
                return None, ["json_parse_failed"]

        # Try direct parse
        try:
            data = json.loads(raw_output)
        except (json.JSONDecodeError, ValueError):
            repaired = repair_json(raw_output)
            if repaired is None:
                return None, ["json_parse_failed"]
            data = json.loads(repaired)

        # Validate against schema
        errors = validate_json_schema(data, schema)
        return data, errors

    def build_gbnf(self, schema: dict[str, Any]) -> str | None:
        """Build a GBNF grammar string for llama.cpp providers."""
        return json_schema_to_gbnf(schema)

    def build_outlines_guide(self, schema: dict[str, Any]) -> Any:
        """Build an Outlines FSM guide (returns None if unavailable)."""
        return self._outlines.build_guide(schema)
