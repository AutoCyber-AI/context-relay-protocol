# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""JSON Schema and validation for the Unified Configuration (SPEC-037 §4).

Provides a programmatic schema so that ``crp.config.yaml`` can be validated
before runtime, and so that IDEs can offer autocomplete. Validation is
lenient on additional properties to preserve forward compatibility.
"""

from __future__ import annotations

from typing import Any

# ── Schema fragments ───────────────────────────────────────────────────────


MODEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "default": {"type": "string"},
        "fallback": {"type": "string"},
        "providers": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "key_env": {"type": "string"},
                },
            },
        },
    },
}

SAFETY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "profile": {
            "type": "string",
            "enum": ["balanced", "strict", "medical", "financial", "public"],
        },
        "settings": {
            "type": "object",
            "properties": {
                "require_grounding": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "hallucination_halt": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                "hallucination_warn": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                "pii_handling": {"type": "string", "enum": ["flag", "redact", "block"]},
                "injection_shield": {"type": "boolean"},
                "block_fabrication": {"type": "boolean"},
                "block_distortion": {"type": "boolean"},
            },
        },
        "coverage": {
            "type": "object",
            "additionalProperties": {"type": "string", "enum": ["on", "off", "warn", "block"]},
        },
        "checkpoints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "when": {"type": "string"},
                    "reason": {"type": "string"},
                    "route_to": {"type": "string"},
                    "on_reject": {"type": "string", "enum": ["halt", "revise", "fallback"]},
                },
            },
        },
        "custom_rules": {"type": "array", "items": {"type": "string"}},
    },
}

CONTEXT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "mode": {"type": "string", "enum": ["auto", "document", "conversation", "hybrid", "zero-ckf"]},
        "depth": {"type": "string", "enum": ["auto", "quick", "standard", "thorough", "exhaustive"]},
        "windows": {
            "type": "object",
            "properties": {
                "max": {"type": "integer", "minimum": 1},
                "token_budget": {"type": "integer", "minimum": 1},
            },
        },
        "retrieval": {
            "type": "object",
            "properties": {
                "min_relevance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "graph_retrieval": {"type": "boolean"},
                "max_hops": {"type": "integer", "minimum": 1, "maximum": 5},
                "recency_weighting": {"type": "boolean"},
            },
        },
        "storage": {
            "type": "object",
            "properties": {
                "rolling_log_size": {"type": "integer", "minimum": 1},
                "hot_cache_size": {"type": "integer", "minimum": 1},
                "backend": {"type": "string", "enum": ["memory", "sqlite", "redis", "s3"]},
            },
        },
    },
}

KNOWLEDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sources": {"type": "array", "items": {"type": "string"}},
        "embedding_model": {"type": "string"},
        "auto_ingest": {"type": "boolean"},
    },
}

AUDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "retention_days": {"type": "integer", "minimum": 1},
        "forward_url": {"type": "string"},
    },
}

GATEWAY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "url": {"type": "string"},
        "api_key": {"type": "string"},
    },
}

INFRASTRUCTURE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "audit_sink": {"type": "string", "enum": ["memory", "file", "http", "none"]},
        "audit_endpoint": {"type": "string"},
        "audit_path": {"type": "string"},
        "database_url": {"type": "string"},
        "storage_backend": {"type": "string", "enum": ["memory", "sqlite", "redis", "s3"]},
        "storage_path": {"type": "string"},
        "redis_url": {"type": "string"},
        "s3_bucket": {"type": "string"},
        "s3_prefix": {"type": "string"},
        "model_cache_dir": {"type": "string"},
        "model_device": {"type": "string", "enum": ["auto", "cpu", "cuda", "mps"]},
        "telemetry_endpoint": {"type": "string"},
    },
}

FULL_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CRP Unified Configuration",
    "type": "object",
    "properties": {
        "version": {"type": "string", "enum": ["4", "4.0"]},
        "model": MODEL_SCHEMA,
        "safety": SAFETY_SCHEMA,
        "context": CONTEXT_SCHEMA,
        "knowledge": KNOWLEDGE_SCHEMA,
        "audit": AUDIT_SCHEMA,
        "gateway": GATEWAY_SCHEMA,
        "infrastructure": INFRASTRUCTURE_SCHEMA,
    },
}


# ── Validation ─────────────────────────────────────────────────────────────


def validate_config(data: dict[str, Any]) -> list[str]:
    """Validate a parsed config dict against the unified schema.

    Performs recursive type, enum, and range checks. Additional properties
    are allowed for forward compatibility.

    Args:
        data: Parsed config dict (e.g. from YAML/JSON).

    Returns:
        A list of human-readable error messages. An empty list means valid.
    """
    errors: list[str] = []

    def _check_type(path: str, value: Any, expected: str) -> None:
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        py_type = type_map.get(expected)
        if py_type is None:
            return
        if expected == "number" and isinstance(value, py_type):
            return
        if not isinstance(value, py_type):
            errors.append(f"{path}: expected {expected}, got {type(value).__name__}")

    def _validate(path: str, value: Any, schema: dict[str, Any]) -> None:
        stype = schema.get("type")
        if stype == "object" and isinstance(value, dict):
            props = schema.get("properties", {})
            for k, v in value.items():
                if k in props:
                    _validate(f"{path}.{k}", v, props[k])
            # No strict additionalProperties check — be lenient for forward-compat
        elif stype == "array" and isinstance(value, list):
            items = schema.get("items", {})
            for i, item in enumerate(value):
                _validate(f"{path}[{i}]", item, items)
        elif stype and value is not None:
            _check_type(path, value, stype)
            if stype in ("string", "integer", "number"):
                enum = schema.get("enum")
                if enum is not None and value not in enum:
                    errors.append(f"{path}: {value!r} not in {enum}")
                minimum = schema.get("minimum")
                if minimum is not None and value < minimum:
                    errors.append(f"{path}: {value} < minimum {minimum}")
                maximum = schema.get("maximum")
                if maximum is not None and value > maximum:
                    errors.append(f"{path}: {value} > maximum {maximum}")

    # Top-level validation
    for key, val in data.items():
        if key in FULL_SCHEMA.get("properties", {}):
            _validate(key, val, FULL_SCHEMA["properties"][key])

    return errors
