# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Config / policy generation and validation helpers for the MCP server."""

from __future__ import annotations

import json
from typing import Any

import yaml  # type: ignore[import-untyped]


def _translate_intent(intent: dict[str, Any]) -> dict[str, Any]:
    """Map user-friendly intent keys to the no-code translator vocabulary."""
    mapping: dict[str, Any] = {
        "grounding_threshold": "grounding_threshold",
        "require_grounding": "require_grounding",
        "prevent_hallucinations": "prevent_hallucinations",
        "block_fabrications": "block_fabrications",
        "detect_distortions": "detect_distortions",
        "halt_on_critical": "halt_on_critical",
        "human_oversight": "human_oversight",
        "checkpoint_review": "checkpoint_review",
        "detect_contradictions": "detect_contradictions",
        "detect_repetition": "detect_repetition",
        "pii_detection": "pii_detection",
        "prompt_injection_shield": "prompt_injection_shield",
        "tamper_evident_audit": "tamper_evident_audit",
        "jailbreak_detection": "jailbreak_detection",
        "toxicity_filter": "toxicity_filter",
        "secrets_detection": "secrets_detection",
        "copyright_detection": "copyright_detection",
        "agency_boundary": "agency_boundary",
        "semantic_drift": "semantic_drift",
        "profile": "profile",
        "safety_budget": "safety_budget",
    }
    out: dict[str, Any] = {}
    for key, value in intent.items():
        out[mapping.get(key, key)] = value
    return out


def generate_config(intent: dict[str, Any]) -> dict[str, Any]:
    """Generate a ``crp.config.yaml`` fragment from plain-language intent."""
    try:
        from crp.comply.no_code import generate_config as _gen

        translated = _translate_intent(intent)
        yaml_text = _gen(translated)
        return {"valid": True, "config_yaml": yaml_text, "notes": []}
    except Exception as exc:
        return {
            "valid": False,
            "config_yaml": "",
            "notes": [f"Could not generate config: {exc}"],
        }


def generate_safety_policy(intent: dict[str, Any]) -> dict[str, Any]:
    """Generate a CRP-Safety-Policy directive string from plain-language intent."""
    directives: list[str] = ["default-src 'self'"]
    notes: list[str] = []

    grounding = intent.get("grounding_threshold") or intent.get("require_grounding")
    if grounding is not None:
        try:
            g = float(grounding)
            if 0.0 <= g <= 1.0:
                directives.append(f"require-grounding {g:.2f}")
            else:
                notes.append("require-grounding must be between 0.0 and 1.0")
        except (TypeError, ValueError):
            notes.append(f"Ignoring non-numeric grounding value: {grounding}")

    halt_on = intent.get("hallucination_halt") or intent.get("halt_on")
    if halt_on in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        directives.append(f"halt-on {halt_on}")
    elif halt_on:
        notes.append(f"Ignoring unknown halt level: {halt_on}")

    warn_on = intent.get("hallucination_warn") or intent.get("warn_on")
    if warn_on in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        directives.append(f"warn-on {warn_on}")
    elif warn_on:
        notes.append(f"Ignoring unknown warn level: {warn_on}")

    pii = intent.get("pii_handling") or intent.get("pii")
    if pii in {"flag", "redact", "block"}:
        directives.append(f"block-pii {pii}")
    elif pii:
        notes.append(f"Ignoring unknown pii handling: {pii}")

    if intent.get("block_fabrications") or intent.get("block_fabrication"):
        directives.append("block-fabrication")
    if intent.get("block_distortions") or intent.get("block_distortion"):
        directives.append("block-distortion")
    if intent.get("prompt_injection_shield") or intent.get("injection_shield"):
        directives.append("upgrade-on-risk HIGH")
    if intent.get("human_oversight") or intent.get("checkpoint_review"):
        directives.append("oversight manual")

    policy = "; ".join(directives)
    return {"policy": policy, "notes": notes}


def validate_config_yaml(yaml_text: str) -> dict[str, Any]:
    """Validate a ``crp.config.yaml`` document against the CRP v4 schema."""
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return {"valid": False, "errors": [f"YAML parse error: {exc}"]}
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["Top-level config must be a mapping."]}

    try:
        from crp.config_schema import validate_config as _validate

        errors = _validate(data)
    except Exception as exc:
        return {"valid": False, "errors": [f"Validation failed: {exc}"]}

    return {"valid": not errors, "errors": errors}


def validate_config_json(json_text: str) -> dict[str, Any]:
    """Validate a JSON config document against the CRP v4 schema."""
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return {"valid": False, "errors": [f"JSON parse error: {exc}"]}
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["Top-level config must be a mapping."]}

    try:
        from crp.config_schema import validate_config as _validate

        errors = _validate(data)
    except Exception as exc:
        return {"valid": False, "errors": [f"Validation failed: {exc}"]}

    return {"valid": not errors, "errors": errors}
