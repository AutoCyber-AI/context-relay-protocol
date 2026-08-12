# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Gateway structured decoder (CRP-SPEC-054 §4)."""

from __future__ import annotations

from typing import Any

from crp.gateway.structured_decoder import (
    enforce_output,
    parse_json_output,
    validate_output,
)


def _schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "temp": {"type": "integer"},
        },
        "required": ["city", "temp"],
    }


def test_validate_valid_output() -> None:
    """A conforming object passes validation."""
    ok, errors = validate_output({"city": "Sydney", "temp": 22}, _schema())
    assert ok
    assert not errors


def test_validate_missing_required() -> None:
    """Missing required fields are reported."""
    ok, errors = validate_output({"city": "Sydney"}, _schema())
    assert not ok
    assert any("temp" in e for e in errors)


def test_validate_wrong_type() -> None:
    """Type mismatches are reported."""
    ok, errors = validate_output({"city": "Sydney", "temp": "twenty"}, _schema())
    assert not ok
    assert any("temp" in e for e in errors)


def test_parse_json_output_strips_fences() -> None:
    """The parser handles markdown-fenced JSON."""
    raw = '```json\n{"city": "Sydney", "temp": 22}\n```'
    value = parse_json_output(raw)
    assert value == {"city": "Sydney", "temp": 22}


def test_enforce_output_valid() -> None:
    """enforce_output returns the value directly when valid."""
    result = enforce_output('{"city": "Sydney", "temp": 22}', _schema(), lambda p, s: "")
    assert result["ok"]
    assert not result["repaired"]
    assert result["value"]["temp"] == 22


def test_enforce_output_repairs_invalid() -> None:
    """enforce_output calls the model to repair invalid JSON."""
    calls: list[str] = []

    def repair_model(prompt: str, schema: dict[str, Any] | None) -> str:
        calls.append(prompt)
        return '{"city": "Sydney", "temp": 22}'

    result = enforce_output('{"city": "Sydney", "temp": "twenty"}', _schema(), repair_model)
    assert result["ok"]
    assert result["repaired"]
    assert result["value"]["temp"] == 22
    assert calls


def test_enforce_output_no_repair_when_disabled() -> None:
    """When repair is disabled, invalid output stays invalid."""
    result = enforce_output(
        '{"city": "Sydney", "temp": "twenty"}',
        _schema(),
        lambda p, s: '{"city": "Sydney", "temp": 22}',
        allow_repair=False,
    )
    assert not result["ok"]
