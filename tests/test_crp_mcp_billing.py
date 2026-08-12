# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP MCP Stripe/billing helpers."""

from __future__ import annotations

import os
from typing import Any

import pytest

from crp_mcp.auth import Identity
from crp_mcp.billing import create_checkout_session, get_entitlement


@pytest.fixture(autouse=True)
def _clear_stripe_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "STRIPE_SECRET_KEY",
        "STRIPE_GATEWAY_DEVELOPER_PRICE_ID",
        "STRIPE_GATEWAY_TEAM_PRICE_ID",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.asyncio
async def test_get_entitlement_without_stripe_is_free() -> None:
    identity = Identity(user_id="u", org_id="o")
    ent = await get_entitlement(identity, "gateway")
    assert ent["plan"] == "free"
    assert "view_plan" in ent["features"]
    assert ent["live"] is False


@pytest.mark.asyncio
async def test_create_checkout_session_without_stripe_fallback() -> None:
    identity = Identity(user_id="u", org_id="o")
    result = await create_checkout_session(identity, "gateway", "team")
    assert result["ok"] is True
    assert result["configured"] is False
    assert "crprotocol.io/upgrade/gateway/team" in result["url"]


@pytest.mark.asyncio
async def test_create_checkout_session_missing_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xxx")
    identity = Identity(user_id="u", org_id="o")
    result = await create_checkout_session(identity, "gateway", "enterprise")
    assert result["ok"] is False
    assert "No Stripe price configured" in result["error"]
