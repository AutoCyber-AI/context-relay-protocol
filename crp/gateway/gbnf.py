# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""JSON Schema → GBNF grammar compiler for llama.cpp constrained decoding (CRP-SPEC-054 §4).

When the provider is a llama.cpp server (or ``llama-cpp-python``), tool-call
arguments can be made valid *by construction* by passing a GBNF grammar with
the request instead of validating and repairing after the fact.

Supported schema subset:
  - root object with ``properties`` (declaration order is preserved)
  - ``required`` (required keys first, optional keys wrapped in ``(...)?``)
  - typed properties: ``string``, ``integer``, ``number``, ``boolean``
  - ``enum`` (string/number/boolean literals)
  - nested objects
  - arrays of scalars (``items`` must be a scalar type or enum)

Anything outside this subset (``anyOf``, ``oneOf``, ``allOf``, ``$ref``,
``not``, arrays of objects, non-object roots) raises :class:`GBNFSchemaError`
with a path-qualified message so the caller can degrade to validate+repair.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("crp.gateway.gbnf")

_PRIMITIVE_RULES: dict[str, str] = {
    "string": 'string ::= "\\"" ([^"\\\\] | "\\\\" .)* "\\""',
    "integer": 'integer ::= "-"? [0-9]+',
    "number": 'number ::= "-"? [0-9]+ ("." [0-9]+)? ([eE] [-+]? [0-9]+)?',
    "boolean": 'boolean ::= "true" | "false"',
}

_WS_RULE = "ws ::= [ \\t\\n]*"

_UNSUPPORTED_KEYWORDS = ("anyOf", "oneOf", "allOf", "$ref", "not", "patternProperties")
_SCALAR_TYPES = ("string", "integer", "number", "boolean")


class GBNFSchemaError(ValueError):
    """Raised when a JSON Schema cannot be compiled to the supported GBNF subset."""


def _escape_literal(value: str) -> str:
    """Escape a string for use as a double-quoted GBNF literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _rule_name(path: str) -> str:
    """Derive a GBNF-safe rule name from a schema path."""
    name = re.sub(r"[^a-zA-Z0-9-]", "-", path).strip("-").lower()
    return name or "root"


class _Compiler:
    def __init__(self) -> None:
        self._rules: list[tuple[str, str]] = []  # (name, body) in creation order
        self._primitives: list[str] = []  # primitive names used, fixed order

    def _use_primitive(self, name: str) -> str:
        if name not in self._primitives:
            self._primitives.append(name)
        return name

    def _add_rule(self, name: str, body: str) -> str:
        if any(existing == name for existing, _ in self._rules):
            raise GBNFSchemaError(f"duplicate rule name {name!r} (schema has colliding keys)")
        self._rules.append((name, body))
        return name

    def value_expr(self, schema: dict[str, Any], path: str) -> str:
        """Return a GBNF expression for ``schema`` (may register named rules)."""
        if not isinstance(schema, dict):
            raise GBNFSchemaError(f"{path}: schema must be an object, got {type(schema).__name__}")
        for kw in _UNSUPPORTED_KEYWORDS:
            if kw in schema:
                raise GBNFSchemaError(f"{path}: unsupported keyword {kw!r}")

        if "enum" in schema:
            return self._enum_expr(schema["enum"], path)

        typ = schema.get("type")
        if typ in _SCALAR_TYPES:
            return self._use_primitive(typ)
        if typ == "object":
            return self._object_rule(schema, path)
        if typ == "array":
            return self._array_rule(schema, path)
        raise GBNFSchemaError(
            f"{path}: unsupported or missing type {typ!r} "
            f"(supported: {', '.join(_SCALAR_TYPES)}, object, array, enum)"
        )

    def _enum_expr(self, values: Any, path: str) -> str:
        if not isinstance(values, list) or not values:
            raise GBNFSchemaError(f"{path}: enum must be a non-empty array")
        parts: list[str] = []
        for v in values:
            if isinstance(v, str):
                parts.append(f'"\\"{_escape_literal(v)}\\""')
            elif isinstance(v, bool):
                parts.append(f'"{"true" if v else "false"}"')
            elif isinstance(v, (int, float)):
                parts.append(f'"{v}"')
            else:
                raise GBNFSchemaError(
                    f"{path}: enum values must be strings, numbers, or booleans, "
                    f"got {type(v).__name__}"
                )
        if len(parts) == 1:
            return parts[0]
        # Parenthesise: bare alternation would bind across the enclosing sequence.
        return "(" + " | ".join(parts) + ")"

    def _object_rule(self, schema: dict[str, Any], path: str) -> str:
        props = schema.get("properties")
        if not isinstance(props, dict) or not props:
            raise GBNFSchemaError(f"{path}: object schemas need a non-empty 'properties' map")
        required = schema.get("required", [])
        if not isinstance(required, list):
            raise GBNFSchemaError(f"{path}: 'required' must be an array")
        unknown = [k for k in required if k not in props]
        if unknown:
            raise GBNFSchemaError(f"{path}: required keys not in properties: {unknown}")

        kv_parts: dict[str, str] = {}
        for key, subschema in props.items():
            if not isinstance(key, str):
                raise GBNFSchemaError(f"{path}: property names must be strings")
            expr = self.value_expr(subschema, f"{path}-{key}" if path else key)
            kv_parts[key] = f'"\\"{_escape_literal(key)}\\"" ws ":" ws {expr}'

        required_seq = ' "," ws '.join(kv_parts[k] for k in props if k in required)
        optional_seq = "".join(
            f' ("," ws {kv_parts[k]})?' for k in props if k not in required
        )
        if required_seq:
            body = f'"{{" ws {required_seq}{optional_seq} "}}" ws'
        else:
            # All properties optional: nested-optional chain.
            keys = list(props)
            chain = kv_parts[keys[-1]]
            for key in reversed(keys[:-1]):
                chain = f'{kv_parts[key]} ("," ws {chain})?'
            body = f'"{{" ws ({chain})? "}}" ws'
        return self._add_rule(_rule_name(path), body)

    def _array_rule(self, schema: dict[str, Any], path: str) -> str:
        items = schema.get("items")
        if not isinstance(items, dict):
            raise GBNFSchemaError(f"{path}: array schemas need an 'items' schema")
        for kw in _UNSUPPORTED_KEYWORDS:
            if kw in items:
                raise GBNFSchemaError(f"{path}: unsupported keyword {kw!r} in array items")
        if "enum" in items:
            item_expr = self._enum_expr(items["enum"], f"{path}-items")
        else:
            item_type = items.get("type")
            if item_type not in _SCALAR_TYPES:
                raise GBNFSchemaError(
                    f"{path}: only arrays of scalars are supported, "
                    f"got item type {item_type!r}"
                )
            item_expr = self._use_primitive(item_type)
        return self._add_rule(
            _rule_name(path),
            f'"[" ws ({item_expr} ("," ws {item_expr})*)? "]" ws',
        )


def compile_gbnf(schema: dict[str, Any], *, root_name: str = "root") -> str:
    """Compile a JSON Schema (supported subset) to a GBNF grammar string.

    Args:
        schema: JSON Schema dict. The root must be an object with properties.
        root_name: Name of the root rule (llama.cpp expects ``root``).

    Returns:
        A GBNF grammar suitable for the llama.cpp ``grammar`` request field
        or ``llama_cpp.LlamaGrammar.from_string``.

    Raises:
        GBNFSchemaError: when the schema uses constructs outside the subset.
    """
    if not isinstance(schema, dict):
        raise GBNFSchemaError(f"schema must be an object, got {type(schema).__name__}")
    if schema.get("type") != "object":
        raise GBNFSchemaError(
            f"root: expected type 'object', got {schema.get('type')!r} — "
            "GBNF constrained decoding requires an object root"
        )

    compiler = _Compiler()
    compiler._object_rule(schema, root_name)

    lines: list[str] = [_WS_RULE]
    for prim in _PRIMITIVE_RULES:
        if prim in compiler._primitives:
            lines.append(_PRIMITIVE_RULES[prim])
    lines.extend(f"{name} ::= {body}" for name, body in compiler._rules)
    return "\n".join(lines) + "\n"


def build_llama_grammar(schema: dict[str, Any]) -> Any:
    """Build a ``llama_cpp.LlamaGrammar`` from ``schema`` (lazy import).

    ``llama-cpp-python`` is an optional dependency; raises ImportError with an
    actionable message when it is not installed.
    """
    try:
        from llama_cpp import LlamaGrammar  # type: ignore[import-untyped]
    except ImportError:
        raise ImportError(
            "llama-cpp-python is required for in-process GBNF grammars; "
            "install it or pass the compile_gbnf() string to a llama.cpp server"
        ) from None
    return LlamaGrammar.from_string(compile_gbnf(schema))
