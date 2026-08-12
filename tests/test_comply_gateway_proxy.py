# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP Comply Gateway Proxy (SPEC-042 §3).

All external HTTP calls are mocked.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from crp.comply.gateway_proxy import ComplyGatewayProxy, GatewayProxyError
from crp.comply.header_mapping import (
    COMPLY_TO_CRP_REQUEST,
    CRP_TO_COMPLY_RESPONSE,
    map_request_headers,
    map_response_headers,
    strip_crp_headers_before_provider,
)

# ---------------------------------------------------------------------------
# Header mapping
# ---------------------------------------------------------------------------


class TestHeaderMapping:
    def test_map_request_headers_translates_comply_to_crp(self) -> None:
        incoming = {
            "X-CRP-Comply-Session": "token_123",
            "X-CRP-Comply-Coverage": "cov_abc",
            "X-CRP-Comply-Safety-Policy": "halt-on CRITICAL",
            "Content-Type": "application/json",
        }
        mapped = map_request_headers(incoming)
        assert mapped["CRP-Session-Token"] == "token_123"
        assert mapped["CRP-Coverage-Set"] == "cov_abc"
        assert mapped["CRP-Safety-Policy"] == "halt-on CRITICAL"
        assert mapped["Content-Type"] == "application/json"

    def test_map_request_headers_is_case_insensitive(self) -> None:
        incoming = {
            "x-crp-comply-session": "token_123",
        }
        mapped = map_request_headers(incoming)
        assert mapped["CRP-Session-Token"] == "token_123"

    def test_map_response_headers_translates_crp_to_comply(self) -> None:
        gateway = {
            "CRP-Safety-Hallucination-Risk": "LOW",
            "CRP-Compliance-Audit-Trail-URI": "https://audit/123",
        }
        mapped = map_response_headers(gateway)
        assert mapped["X-CRP-Comply-Hallucination-Risk"] == "LOW"
        assert mapped["X-CRP-Comply-Record-ID"] == "https://audit/123"
        assert mapped["X-CRP-Comply"] == "active"

    def test_strip_crp_headers_removes_all_crp_headers(self) -> None:
        headers = {
            "Authorization": "Bearer sk-123",
            "Content-Type": "application/json",
            "CRP-Session-Token": "tok",
            "CRP-Safety-Policy": "strict",
            "X-Custom": "value",
        }
        stripped = strip_crp_headers_before_provider(headers)
        assert "Authorization" in stripped
        assert "Content-Type" in stripped
        assert "CRP-Session-Token" not in stripped
        assert "CRP-Safety-Policy" not in stripped
        assert "X-Custom" not in stripped


# ---------------------------------------------------------------------------
# Gateway proxy
# ---------------------------------------------------------------------------


class TestComplyGatewayProxy:
    @patch("crp.comply.gateway_proxy.requests.post")
    @patch("crp.comply.gateway_proxy.QuotaGate")
    def test_forwards_to_gateway(self, mock_gate_cls: MagicMock, mock_post: MagicMock) -> None:
        mock_gate = MagicMock()
        mock_gate.check.return_value = {"status": "ok", "used": 0, "quota": 100}
        mock_gate_cls.return_value = mock_gate

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"CRP-Safety-Hallucination-Risk": "LOW"}
        mock_resp.content = b'{"id":"chatcmpl-1"}'
        mock_post.return_value = mock_resp

        proxy = ComplyGatewayProxy(gateway_url="http://gateway.test", gateway_key="gk")
        result = proxy.forward(
            body=b'{"model":"gpt-4"}',
            headers={"X-CRP-Comply-Session": "tok"},
            org_id="org_1",
        )

        assert result["status_code"] == 200
        assert result["headers"]["X-CRP-Comply-Hallucination-Risk"] == "LOW"
        assert result["headers"]["X-CRP-Comply"] == "active"

        # Verify the POST was made to the Gateway with mapped headers
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://gateway.test/v1/chat/completions"
        assert call_args[1]["headers"]["CRP-Session-Token"] == "tok"
        assert call_args[1]["headers"]["Authorization"] == "Bearer gk"

    @patch("crp.comply.gateway_proxy.requests.post")
    @patch("crp.comply.gateway_proxy.QuotaGate")
    def test_quota_exceeded_returns_429(self, mock_gate_cls: MagicMock, mock_post: MagicMock) -> None:
        mock_gate = MagicMock()
        mock_gate.check.return_value = {"status": "quota_exceeded", "used": 101, "quota": 100}
        mock_gate_cls.return_value = mock_gate

        proxy = ComplyGatewayProxy()
        result = proxy.forward(
            body=b'{}',
            headers={},
            org_id="org_over",
        )
        assert result["status_code"] == 429
        assert "quota_exceeded" in json.loads(result["body"])["error"]["code"]
        mock_post.assert_not_called()

    @patch("crp.comply.gateway_proxy.requests.post")
    @patch("crp.comply.gateway_proxy.QuotaGate")
    def test_gateway_unreachable_raises_503(self, mock_gate_cls: MagicMock, mock_post: MagicMock) -> None:
        mock_gate = MagicMock()
        mock_gate.check.return_value = {"status": "ok"}
        mock_gate_cls.return_value = mock_gate
        mock_post.side_effect = requests.RequestException("connection refused")

        proxy = ComplyGatewayProxy(gateway_url="http://bad-gateway")
        with pytest.raises(GatewayProxyError) as exc_info:
            proxy.forward(b'{}', {})
        assert exc_info.value.status_code == 503

    @patch("crp.comply.gateway_proxy.requests.get")
    def test_health_check_ok(self, mock_get: MagicMock) -> None:
        mock_get.return_value.status_code = 200
        proxy = ComplyGatewayProxy(gateway_url="http://gateway.test", gateway_key="gk")
        health = proxy.health()
        assert health["ok"] is True
        assert health["gateway_status"] == 200

    @patch("crp.comply.gateway_proxy.requests.get")
    def test_health_check_fail(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = requests.RequestException("timeout")
        proxy = ComplyGatewayProxy(gateway_url="http://gateway.test")
        health = proxy.health()
        assert health["ok"] is False
