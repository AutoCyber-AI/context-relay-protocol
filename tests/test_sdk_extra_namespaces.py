# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Smoke tests for the additional curated SDK namespace proxies."""

from __future__ import annotations

import crp
from crp.gateway.api import GatewaySession
from crp.observability.metrics import MetricsExporter
from crp.sdk.proxies_extra import (
    ComplyGatewayClient,
    _ComplyProxy,
    _GatewayProxy,
    _HeadersProxy,
    _ObservabilityProxy,
    _PolicyProxy,
    _ScanProxy,
)

_client = crp.SDKClient()


def test_gateway_proxy_type() -> None:
    assert isinstance(_client.gateway, _GatewayProxy)


def test_headers_proxy_type() -> None:
    assert isinstance(_client.headers, _HeadersProxy)


def test_observability_proxy_type() -> None:
    assert isinstance(_client.observability, _ObservabilityProxy)


def test_policy_proxy_type() -> None:
    assert isinstance(_client.policy, _PolicyProxy)


def test_scan_proxy_type() -> None:
    assert isinstance(_client.scan, _ScanProxy)


def test_comply_proxy_type() -> None:
    assert isinstance(_client.comply, _ComplyProxy)


def test_gateway_session_returns_gateway_session() -> None:
    session = _client.gateway.session()
    assert isinstance(session, GatewaySession)


def test_headers_names_returns_list() -> None:
    names = _client.headers.names()
    assert isinstance(names, list)
    assert all(isinstance(n, str) for n in names)


def test_headers_should_halt_no_raise() -> None:
    # Empty headers should not raise and should not signal a halt.
    assert _client.headers.should_halt({}) is False


def test_observability_metrics_returns_exporter() -> None:
    metrics = _client.observability.metrics()
    assert isinstance(metrics, MetricsExporter)


def test_observability_structured_log_no_raise() -> None:
    line = _client.observability.structured_log({"msg": "test"})
    assert isinstance(line, str)
    assert "test" in line


def test_policy_profiles_returns_dict() -> None:
    profiles = _client.policy.profiles()
    assert isinstance(profiles, dict)


def test_policy_risk_level_no_raise() -> None:
    level = _client.policy.risk_level("HIGH")
    assert level.value == "HIGH"


def test_scan_ingest_code_returns_something() -> None:
    result = _client.scan.ingest_code("x")
    assert result is not None


def test_comply_gateway_client_returns_adapter() -> None:
    client = _client.comply.gateway_client()
    assert isinstance(client, ComplyGatewayClient)


def test_comply_quota_gate_no_raise() -> None:
    result = _client.comply.quota_gate("org_test")
    assert isinstance(result, dict)
