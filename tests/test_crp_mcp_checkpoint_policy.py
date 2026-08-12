# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP checkpoint policy compiler (Phase 8)."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from crp_mcp.checkpoint_policy import (
    CheckpointPolicyError,
    compile_condition,
    evaluate_condition,
    resolve_route,
)


def test_compile_condition_matches_risk_shorthand() -> None:
    evaluator = compile_condition('risk >= HIGH')
    assert evaluator({"risk": "HIGH"}) is True
    assert evaluator({"risk": "MEDIUM"}) is False


def test_compile_condition_matches_amount_and_tool() -> None:
    evaluator = compile_condition(
        "tool_call == 'approve_loan' and amount > 1000000"
    )
    assert evaluator({"tool_call": "approve_loan", "amount": 1500000}) is True
    assert evaluator({"tool_call": "approve_loan", "amount": 500000}) is False
    assert evaluator({"tool_call": "send_email", "amount": 1500000}) is False


def test_compile_condition_supports_not() -> None:
    evaluator = compile_condition("not internal_user")
    assert evaluator({"internal_user": False}) is True
    assert evaluator({"internal_user": True}) is False


def test_compile_condition_rejects_disallowed_nodes() -> None:
    with pytest.raises(CheckpointPolicyError):
        compile_condition("__import__('os').system('rm -rf /')")


def test_evaluate_condition_returns_structure() -> None:
    result = evaluate_condition(
        'risk >= HIGH',
        '{"risk": "HIGH", "amount": 123}',
    )
    assert result["matched"] is True
    assert result["condition"] == "risk >= HIGH"
    assert "risk" in result["context_keys"]


def test_resolve_route_uses_env_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    rules = [
        {"condition": "risk >= HIGH", "connector": "slack", "route_to": "#safety"},
        {"condition": "tool_call == 'deploy_endpoint'", "connector": "pagerduty"},
    ]
    monkeypatch.setenv("CRP_MCP_CHECKPOINT_ROUTES", json.dumps(rules))
    connector, route_to = resolve_route(
        trigger="RISK_HIGH",
        condition="risk >= HIGH",
        context={"risk": "HIGH"},
    )
    assert connector == "slack"
    assert route_to == "#safety"


def test_resolve_route_falls_back_to_default() -> None:
    connector, route_to = resolve_route(
        trigger="RISK_HIGH",
        condition="risk >= HIGH",
        context={"risk": "LOW"},
        default_connector="console",
    )
    assert connector == "console"
    assert route_to == ""
