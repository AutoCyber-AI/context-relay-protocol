# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP MCP checkpoint review-channel connectors."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from crp_mcp.connectors import get_configured_connectors
from crp_mcp.connectors.console import ConsoleConnector
from crp_mcp.connectors.fcm import FCMConnector
from crp_mcp.connectors.gmail import GmailConnector
from crp_mcp.connectors.webhook import WebhookConnector


# Test-only RSA key generated at import time. Never a real secret.
_TEST_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_PRIVATE_KEY = _TEST_RSA_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")


@pytest.fixture(autouse=True)
def _clear_connector_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "CRP_MCP_CHECKPOINT_CONNECTORS",
        "CRP_MCP_CHECKPOINT_WEBHOOK_URL",
        "SLACK_WEBHOOK_URL",
        "EMAIL_SMTP_HOST",
        "TWILIO_ACCOUNT_SID",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.asyncio
async def test_console_connector_logs_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    connector = ConsoleConnector()
    checkpoint = {
        "checkpoint_id": "ckpt-1",
        "trigger": "RISK_HIGH",
        "message": "approve me",
        "user_id": "u",
        "org_id": "o",
        "status_url": "https://crprotocol.io/checkpoints/ckpt-1",
    }
    result = await connector.notify(checkpoint)
    assert result["ok"] is True
    captured = capsys.readouterr()
    assert "ckpt-1" in captured.err
    assert "approve me" in captured.err


@pytest.mark.asyncio
async def test_webhook_connector_posts_json(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(
            {
                "url": str(request.url),
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(200, text="ok")

    monkeypatch.setenv("CRP_MCP_CHECKPOINT_WEBHOOK_URL", "https://example.com/hook")
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        timeout=5.0,
    )
    connector = WebhookConnector(client=client)

    checkpoint = {"checkpoint_id": "ckpt-2", "trigger": "HALT", "message": "halt"}
    result = await connector.notify(checkpoint)
    assert result["ok"] is True
    assert len(calls) == 1
    assert calls[0]["body"]["checkpoint_id"] == "ckpt-2"


@pytest.mark.asyncio
async def test_get_configured_connectors_default_includes_console() -> None:
    connectors = get_configured_connectors()
    assert [c.name for c in connectors] == ["console"]


@pytest.mark.asyncio
async def test_get_configured_connectors_includes_webhook_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRP_MCP_CHECKPOINT_WEBHOOK_URL", "https://example.com/hook")
    connectors = get_configured_connectors("webhook")
    names = [c.name for c in connectors]
    assert "console" in names
    assert "webhook" in names


@pytest.mark.asyncio
async def test_gmail_connector_uses_app_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GMAIL_USER", "alerts@crprotocol.io")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "fake_app_password")
    monkeypatch.setenv("GMAIL_TO", "ops@crprotocol.io")

    connector = GmailConnector()
    assert connector.is_configured() is True
    assert connector._fallback.host == "smtp.gmail.com"
    assert connector._fallback.port == 587


@pytest.mark.asyncio
async def test_fcm_connector_not_configured_without_service_account() -> None:
    connector = FCMConnector()
    assert connector.is_configured() is False
    result = await connector.notify({"checkpoint_id": "ckpt-3"})
    assert result["ok"] is False
    assert result["detail"] == "fcm_not_configured"


@pytest.mark.asyncio
async def test_fcm_connector_sends_push_notifications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_account = {
        "type": "service_account",
        "project_id": "crp-demo",
        "client_email": "fcm@crp-demo.iam.gserviceaccount.com",
        "private_key": _TEST_PRIVATE_KEY,
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON", json.dumps(service_account))
    monkeypatch.setenv("FCM_DEVICE_TOKENS", "device_token_1,device_token_2")

    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(200, json={"name": "projects/crp-demo/messages/123"})

    # Patch the synchronous OAuth flow to avoid real network/crypto.
    fake_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        timeout=5.0,
    )
    connector = FCMConnector(client=fake_client)
    connector.tokens = ["device_token_1", "device_token_2"]
    monkeypatch.setattr(connector, "_get_access_token", lambda: "fake_fcm_token")

    checkpoint = {
        "checkpoint_id": "ckpt-fcm",
        "trigger": "RISK_HIGH",
        "message": "approve me",
        "status_url": "https://crprotocol.io/checkpoints/ckpt-fcm",
    }
    result = await connector.notify(checkpoint)
    assert result["ok"] is True
    assert len(calls) == 2
    assert calls[0]["body"]["message"]["token"] == "device_token_1"
    assert calls[0]["body"]["message"]["notification"]["title"] == "CRP checkpoint ckpt-fcm"
    auth_header = calls[0]["headers"].get("authorization") or calls[0]["headers"].get("Authorization")
    assert "fake_fcm_token" in auth_header
