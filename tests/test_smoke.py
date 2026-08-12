# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Smoke tests — verify package imports and version."""

from __future__ import annotations


def test_version() -> None:
    from crp import __version__

    assert __version__ == "6.0.0"


def test_imports() -> None:
    from crp import CRPError, TaskIntent

    assert CRPError is not None
    assert TaskIntent is not None


def test_crp_error() -> None:
    from crp import CRPError

    err = CRPError(1001, "test error")
    assert err.code == 1001
    assert "CRP-1001" in str(err)


def test_task_intent_defaults() -> None:
    from crp import TaskIntent

    ti = TaskIntent()
    assert ti.system_prompt is None
    assert ti.task_input is None
    assert ti.output_schema is None
    assert ti.metadata == {}


def test_schema_loader() -> None:
    from crp.schemas import load_schema

    schema = load_schema("task-intent")
    assert schema["type"] == "object"


def test_all_schemas_loadable() -> None:
    from crp.schemas import load_schema

    names = [
        "task-intent",
        "quality-report",
        "session-handle",
        "session-status",
        "crp-error",
        "stream-event",
        "cost-estimate",
        "envelope-preview",
        "persisted-state-header",
    ]
    for name in names:
        schema = load_schema(name)
        assert "type" in schema or "$schema" in schema, f"Schema {name} missing type/$schema"
