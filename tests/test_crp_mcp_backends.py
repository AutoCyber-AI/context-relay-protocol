# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Integration tests for CRP backend clients (Gateway, Comply, Scan)."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import pytest

from crp_mcp.backend_client import (
    BackendNotConfigured,
    ComplyClient,
    GatewayClient,
    ScanClient,
)


@pytest.fixture(autouse=True)
def _clear_backend_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("CRP_GATEWAY_URL", "CRP_COMPLY_BASE_URL", "CRP_SCAN_BASE_URL", "CRP_HOSTED_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def _mock_transport(calls: list[dict[str, Any]], responses: list[dict[str, Any]]) -> httpx.MockTransport:
    index = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal index
        calls.append(
            {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": json.loads(request.content) if request.content else None,
            }
        )
        response = responses[index]
        index += 1
        return httpx.Response(
            status_code=response.get("status", 200),
            json=response.get("json", {}),
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_gateway_client_not_configured() -> None:
    client = GatewayClient()
    with pytest.raises(BackendNotConfigured):
        await client.create_api_key("test")


@pytest.mark.asyncio
async def test_gateway_client_create_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRP_GATEWAY_URL", "https://gateway.example.com/v1")
    monkeypatch.setenv("CRP_HOSTED_API_KEY", "hk_test_xxx")

    calls: list[dict[str, Any]] = []
    transport = _mock_transport(
        calls,
        [{"json": {"key": "crp_gw_live_123", "name": "test"}}],
    )
    client = GatewayClient()
    client._client = httpx.AsyncClient(
        base_url="https://gateway.example.com/v1",
        headers={"Authorization": "Bearer hk_test_xxx"},
        transport=transport,
        timeout=5.0,
    )

    result = await client.create_api_key("test")
    assert result["key"] == "crp_gw_live_123"
    auth_header = calls[0]["headers"].get("authorization") or calls[0]["headers"].get("Authorization")
    assert auth_header == "Bearer hk_test_xxx"
    assert calls[0]["body"]["name"] == "test"


@pytest.mark.asyncio
async def test_comply_client_create_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRP_COMPLY_BASE_URL", "https://comply.example.com")
    monkeypatch.setenv("CRP_HOSTED_API_KEY", "hk_test_xxx")

    calls: list[dict[str, Any]] = []
    transport = _mock_transport(
        calls,
        [{"json": {"analysis_id": "a-1", "status": "queued"}}],
    )
    client = ComplyClient()
    client._client = httpx.AsyncClient(
        base_url="https://comply.example.com",
        headers={"Authorization": "Bearer hk_test_xxx"},
        transport=transport,
        timeout=5.0,
    )

    result = await client.create_analysis("owner/repo", "EU AI Act")
    assert result["analysis_id"] == "a-1"
    assert calls[0]["url"] == "https://comply.example.com/analyses"


@pytest.mark.asyncio
async def test_scan_client_get_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRP_SCAN_BASE_URL", "https://scan.example.com")
    monkeypatch.setenv("CRP_HOSTED_API_KEY", "hk_test_xxx")

    calls: list[dict[str, Any]] = []
    transport = _mock_transport(
        calls,
        [{"json": {"scan_id": "s-1", "findings": []}}],
    )
    client = ScanClient()
    client._client = httpx.AsyncClient(
        base_url="https://scan.example.com",
        headers={"Authorization": "Bearer hk_test_xxx"},
        transport=transport,
        timeout=5.0,
    )

    result = await client.get_scan("s-1")
    assert result["scan_id"] == "s-1"
    assert calls[0]["url"] == "https://scan.example.com/scans/s-1"
