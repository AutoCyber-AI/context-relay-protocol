# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP MCP checkpoint service and safety checkpoint tool."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest

from crp_mcp.auth import Identity
from crp_mcp.checkpoint_service import create_checkpoint, get_checkpoint
from crp_mcp.safety_tools import crp_safety_checkpoint


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "CLERK_ISSUER",
        "CLERK_AUTHORIZED_PARTIES",
        "CLERK_SECRET_KEY",
        "CRP_MCP_CHECKPOINT_CONNECTORS",
        "CRP_MCP_CHECKPOINT_LOG",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.asyncio
async def test_create_checkpoint_notifies_console() -> None:
    identity = Identity(user_id="u", org_id="o", org_role="user")
    checkpoint = await create_checkpoint(
        trigger="RISK_HIGH",
        message="approve this",
        identity=identity,
        channels=["console"],
    )
    assert checkpoint["checkpoint_id"] != "preview-only"
    assert checkpoint["status"] == "waiting_for_human"
    assert checkpoint["user_id"] == "u"
    assert checkpoint["org_id"] == "o"
    assert any(c["channel"] == "console" and c["ok"] for c in checkpoint["notified_channels"])

    assert get_checkpoint(checkpoint["checkpoint_id"]) is not None


@pytest.mark.asyncio
async def test_safety_checkpoint_returns_confirmation_prompt() -> None:
    result = await crp_safety_checkpoint(trigger="HALT", message="stop")
    data = json.loads(result)
    assert data["ok"] is True
    assert data["requires_confirmation"] is True


@pytest.mark.asyncio
async def test_safety_checkpoint_preview_without_auth() -> None:
    result = await crp_safety_checkpoint(
        trigger="HALT",
        message="stop",
        confirm=True,
    )
    data = json.loads(result)
    assert data["ok"] is True
    assert data["checkpoint_id"] == "preview-only"


@pytest.mark.asyncio
async def test_checkpoint_signature_and_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRP_MCP_AUDIT_HMAC_SECRET", "test-secret")
    from crp_mcp import checkpoint_service

    checkpoint_service._checkpoints.clear()
    checkpoint = await create_checkpoint(
        trigger="RISK_HIGH",
        message="sign me",
        channels=["console"],
    )
    cp_id = checkpoint["checkpoint_id"]
    assert checkpoint["signature"] is not None
    assert checkpoint_service.verify_checkpoint_signature(cp_id) is True

    # Tamper with the in-memory record.
    record = checkpoint_service._checkpoints[cp_id]
    record.message = "tampered"
    assert checkpoint_service.verify_checkpoint_signature(cp_id) is False


@pytest.mark.asyncio
async def test_multi_approver_checkpoint_requires_multiple_approvals() -> None:
    from crp_mcp import checkpoint_service

    checkpoint_service._checkpoints.clear()
    checkpoint = await create_checkpoint(
        trigger="RISK_HIGH",
        message="needs two approvers",
        channels=["console"],
        required_approvers=2,
    )
    cp_id = checkpoint["checkpoint_id"]

    first = checkpoint_service.approve_checkpoint(cp_id, "alice")
    assert first["ok"] is True
    assert first["status"] == "waiting_for_human"

    second = checkpoint_service.approve_checkpoint(cp_id, "bob")
    assert second["ok"] is True
    assert second["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_checkpoint_immediately_rejects() -> None:
    from crp_mcp import checkpoint_service

    checkpoint_service._checkpoints.clear()
    checkpoint = await create_checkpoint(
        trigger="RISK_HIGH",
        message="reject me",
        channels=["console"],
        required_approvers=2,
    )
    cp_id = checkpoint["checkpoint_id"]

    result = checkpoint_service.reject_checkpoint(cp_id, "alice", "no go")
    assert result["ok"] is True
    assert result["status"] == "rejected"


@pytest.mark.asyncio
async def test_escalation_auto_rejects_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from crp_mcp import checkpoint_service

    checkpoint_service._checkpoints.clear()
    checkpoint = await create_checkpoint(
        trigger="RISK_HIGH",
        message="timeout test",
        channels=["console"],
        escalation=[{"after_seconds": 0, "on_timeout": "reject"}],
    )
    cp_id = checkpoint["checkpoint_id"]

    # Give the asyncio task a moment to fire.
    await asyncio.sleep(0.1)

    record = checkpoint_service.get_checkpoint(cp_id)
    assert record is not None
    assert record["status"] == "rejected"
