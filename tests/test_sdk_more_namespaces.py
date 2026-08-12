# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Smoke tests for the additional curated SDK namespace proxies (Phase 3)."""

from __future__ import annotations

import crp
from crp.sdk.proxies_more import (
    _AdvancedProxy,
    _CLIProxy,
    _ContinuationProxy,
    _CoreProxy,
    _EnvelopeProxy,
    _ErrorsProxy,
    _ResourcesProxy,
    _SecurityProxy,
    _StateProxy,
)

_client = crp.SDKClient()


def test_core_proxy_type() -> None:
    assert isinstance(_client.core, _CoreProxy)


def test_continuation_proxy_type() -> None:
    assert isinstance(_client.continuation, _ContinuationProxy)


def test_envelope_proxy_type() -> None:
    assert isinstance(_client.envelope, _EnvelopeProxy)


def test_state_proxy_type() -> None:
    assert isinstance(_client.state, _StateProxy)


def test_security_proxy_type() -> None:
    assert isinstance(_client.security, _SecurityProxy)


def test_resources_proxy_type() -> None:
    assert isinstance(_client.resources, _ResourcesProxy)


def test_advanced_proxy_type() -> None:
    assert isinstance(_client.advanced, _AdvancedProxy)


def test_cli_proxy_type() -> None:
    assert isinstance(_client.cli, _CLIProxy)


def test_errors_proxy_type() -> None:
    assert isinstance(_client.errors, _ErrorsProxy)


def test_core_orchestrator_returns_orchestrator() -> None:
    orch = _client.core.orchestrator()
    assert orch is not None


def test_core_session_returns_session() -> None:
    session = _client.core.session()
    assert session is not None


def test_continuation_manager_returns_manager() -> None:
    manager = _client.continuation.manager()
    assert manager is not None


def test_continuation_document_map_returns_document_map() -> None:
    doc_map = _client.continuation.document_map()
    assert doc_map is not None


def test_envelope_builder_returns_namespace() -> None:
    builder = _client.envelope.builder()
    assert builder is not None


def test_envelope_cdr_returns_callable() -> None:
    cdr = _client.envelope.cdr()
    assert cdr is not None


def test_state_warm_store_returns_store() -> None:
    store = _client.state.warm_store()
    assert store is not None


def test_state_router_returns_router() -> None:
    router = _client.state.router()
    assert router is not None


def test_security_manifest_returns_manifest() -> None:
    manifest = _client.security.manifest()
    assert manifest is not None


def test_security_checkpoint_returns_checkpoint() -> None:
    checkpoint = _client.security.checkpoint()
    assert checkpoint is not None


def test_security_pii_scan_returns_scanner() -> None:
    scanner = _client.security.pii_scan()
    assert scanner is not None


def test_resources_allocator_returns_allocator() -> None:
    allocator = _client.resources.allocator()
    assert allocator is not None


def test_resources_estimate_cost_returns_estimate() -> None:
    estimate = _client.resources.estimate_cost(input_tokens=1000, output_tokens=500)
    assert estimate is not None


def test_advanced_curator_returns_curator() -> None:
    curator = _client.advanced.curator()
    assert curator is not None


def test_advanced_cross_window_validator_returns_validator() -> None:
    validator = _client.advanced.cross_window_validator()
    assert validator is not None


def test_cli_sidecar_handler_returns_class() -> None:
    handler = _client.cli.sidecar_handler()
    assert handler is not None


def test_cli_startup_result_returns_result() -> None:
    result = _client.cli.startup_result()
    assert result is not None


def test_errors_exception_lookup() -> None:
    exc = _client.errors.exception("CRPError")
    assert exc is not None


def test_errors_all_exceptions_returns_dict() -> None:
    all_exc = _client.errors.all_exceptions()
    assert isinstance(all_exc, dict)
    assert "CRPError" in all_exc


def test_errors_common_properties() -> None:
    assert _client.errors.CRPError is not None
    assert _client.errors.ValidationError is not None
    assert _client.errors.SecurityInvariantError is not None
