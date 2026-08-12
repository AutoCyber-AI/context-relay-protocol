# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Constrained-decoding dispatch tests (CRP-SPEC-054 §4) — mocked providers, no network."""

from __future__ import annotations

from typing import Any

from crp.gateway.api import ChatMessage, ChatRequest, GatewaySession, ProviderResponse
from crp.gateway.capability_router import CapabilityRouter
from crp.gateway.router import ProviderConfig, ProviderRouter

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "days": {"type": "integer"},
    },
    "required": ["city"],
}


class _MockRouter:
    """Provider router stand-in: returns a fixed ProviderConfig, records requests."""

    def __init__(self, constrained_decoding: str | None) -> None:
        self.config = ProviderConfig(
            provider_slug="mock",
            base_url="http://mock",
            api_key="mock",
            model="mock-model",
            constrained_decoding=constrained_decoding,
        )
        self.dispatched: list[ChatRequest] = []

    def resolve_provider(self, model: str, tenant_id: str) -> ProviderConfig:
        return self.config

    def dispatch(
        self,
        request: ChatRequest,
        messages: list[ChatMessage],
        session: GatewaySession,
    ) -> ProviderResponse:
        self.dispatched.append(request)
        return ProviderResponse(content='{"city": "Sydney"}', model=request.model)


def _model_call_for(router: _MockRouter) -> Any:
    capability_router = CapabilityRouter(tools=[])
    request = ChatRequest(
        model="mock-model",
        messages=[ChatMessage(role="user", content="weather?")],
    )
    session = GatewaySession(session_id="s-1", tenant_id="t-1")
    return capability_router._build_model_call(request, session, router)


class TestConstrainedDispatch:
    def test_json_schema_provider_receives_response_format(self) -> None:
        router = _MockRouter("json_schema")
        model_call = _model_call_for(router)
        out = model_call("Return the weather as JSON.", _SCHEMA)

        assert out == '{"city": "Sydney"}'
        sent = router.dispatched[-1]
        assert sent.response_format == {
            "type": "json_schema",
            "json_schema": {
                "name": "crp_structured_output",
                "schema": _SCHEMA,
                "strict": True,
            },
        }
        assert sent.grammar is None

    def test_llamacpp_provider_receives_grammar(self) -> None:
        router = _MockRouter("gbnf")
        model_call = _model_call_for(router)
        model_call("Return the weather as JSON.", _SCHEMA)

        sent = router.dispatched[-1]
        assert sent.response_format is None
        assert sent.grammar is not None
        assert sent.grammar.startswith("ws ::= ")
        assert "root ::= " in sent.grammar
        assert '"\\"city\\"" ws ":" ws string' in sent.grammar

    def test_unsupported_provider_falls_back(self) -> None:
        router = _MockRouter(None)
        model_call = _model_call_for(router)
        out = model_call("Return the weather as JSON.", _SCHEMA)

        # Identical external behaviour: content returned, no constraint fields.
        assert out == '{"city": "Sydney"}'
        sent = router.dispatched[-1]
        assert sent.response_format is None
        assert sent.grammar is None

    def test_no_schema_no_constraints(self) -> None:
        router = _MockRouter("json_schema")
        model_call = _model_call_for(router)
        model_call("Free-form prompt.", None)

        sent = router.dispatched[-1]
        assert sent.response_format is None
        assert sent.grammar is None

    def test_gbnf_compile_failure_degrades_to_repair(self) -> None:
        router = _MockRouter("gbnf")
        model_call = _model_call_for(router)
        bad_schema = {"type": "object", "properties": {"x": {"anyOf": [{"type": "string"}]}}}
        out = model_call("prompt", bad_schema)

        assert out == '{"city": "Sydney"}'
        sent = router.dispatched[-1]
        assert sent.grammar is None  # degraded; validate+repair handles it

    def test_resolve_provider_failure_degrades(self) -> None:
        class _ExplodingRouter(_MockRouter):
            def resolve_provider(self, model: str, tenant_id: str) -> ProviderConfig:
                raise RuntimeError("no config store")

        router = _ExplodingRouter("json_schema")
        model_call = _model_call_for(router)
        out = model_call("prompt", _SCHEMA)

        assert out == '{"city": "Sydney"}'
        sent = router.dispatched[-1]
        assert sent.response_format is None


class TestProviderRouterIntegration:
    def test_openai_config_enables_json_schema(self) -> None:
        router = ProviderRouter()
        config = router.resolve_provider("gpt-4o", "tenant")
        assert config.constrained_decoding == "json_schema"

    def test_local_config_default_unconstrained(self) -> None:
        router = ProviderRouter()
        config = router.resolve_provider("llama-3.1-8b", "tenant")
        assert config.constrained_decoding is None

    def test_local_llamacpp_config_enables_gbnf(self) -> None:
        router = ProviderRouter(local_constrained="gbnf")
        config = router.resolve_provider("llama-3.1-8b", "tenant")
        assert config.constrained_decoding == "gbnf"

    def test_request_body_carries_response_format(self) -> None:
        router = ProviderRouter()
        config = router.resolve_provider("gpt-4o", "tenant")
        request = ChatRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hi")],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "x", "schema": _SCHEMA, "strict": True},
            },
        )
        body = router._build_request_body(request, request.messages, config)
        assert body["response_format"]["json_schema"]["strict"] is True
        assert "grammar" not in body

    def test_request_body_carries_grammar(self) -> None:
        router = ProviderRouter(local_constrained="gbnf")
        config = router.resolve_provider("llama-3.1-8b", "tenant")
        request = ChatRequest(
            model="llama-3.1-8b",
            messages=[ChatMessage(role="user", content="hi")],
            grammar='ws ::= [ \\t\\n]*\nroot ::= "{" ws "}" ws\n',
        )
        body = router._build_request_body(request, request.messages, config)
        assert body["grammar"].startswith("ws ::= ")
        assert "response_format" not in body
