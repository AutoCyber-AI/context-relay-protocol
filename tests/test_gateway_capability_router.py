# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Gateway Capability Router (CRP-SPEC-054)."""

from __future__ import annotations

import json
from typing import Any

from crp.gateway.api import (
    ChatMessage,
    ChatRequest,
    GatewayRequestLifecycle,
    GatewaySession,
    ProviderResponse,
)
from crp.gateway.capability_router import CapabilityRouter
from crp.gateway.router import ProviderConfig
from crp.gateway.tool_adapter import (
    descriptor_to_openai_tool,
    openai_tool_to_descriptor,
)


def _weather_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Fetch current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }


class _MockRouter:
    """Provider-router double that returns canned model responses."""

    def __init__(self) -> None:
        self.last_request: ChatRequest | None = None
        self.last_messages: list[ChatMessage] | None = None

    def dispatch(self, request: ChatRequest, messages: list[ChatMessage], session: GatewaySession) -> ProviderResponse:
        self.last_request = request
        self.last_messages = messages
        content = messages[-1].content if messages else ""
        if "Available tools" in content and "get_weather" in content:
            return ProviderResponse(
                content=json.dumps({"capability_id": "get_weather", "arguments": {"city": "Sydney"}}),
                model=request.model,
                finish_reason="stop",
            )
        return ProviderResponse(
            content="It is sunny and 22 °C in Sydney.",
            model=request.model,
            finish_reason="stop",
        )

    def resolve_provider(self, model: str, tenant_id: str) -> ProviderConfig:
        return ProviderConfig(provider_slug="local", base_url="http://localhost:1234", api_key="test", model=model)


def test_chat_request_parses_tools() -> None:
    """Gateway parses OpenAI ``tools`` and ``tool_choice`` from the body."""
    body = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Weather in Sydney?"}],
        "tools": [_weather_tool()],
        "tool_choice": "auto",
    }
    req = ChatRequest.from_body(body, {})
    assert len(req.tools) == 1
    assert req.tools[0]["function"]["name"] == "get_weather"
    assert req.tool_choice == "auto"


def test_openai_tool_to_descriptor() -> None:
    """An OpenAI tool definition converts to a valid CapabilityDescriptor."""
    descriptor = openai_tool_to_descriptor(_weather_tool())
    assert descriptor.capability_id == "get_weather"
    assert "city" in descriptor.input_schema["properties"]
    assert "city" in descriptor.required_inputs()


def test_descriptor_to_openai_tool_round_trip() -> None:
    """Descriptor → OpenAI tool preserves the essentials."""
    descriptor = openai_tool_to_descriptor(_weather_tool())
    tool = descriptor_to_openai_tool(descriptor)
    assert tool["function"]["name"] == "get_weather"
    assert "city" in tool["function"]["parameters"]["properties"]


def test_capability_router_executes_registered_tool() -> None:
    """A registered capability implementation is executed by the router."""

    def get_weather(args: dict[str, Any]) -> dict[str, Any]:
        return {"city": args["city"], "temp": 22, "condition": "sunny"}

    router = _MockRouter()
    cap_router = CapabilityRouter(tools=[_weather_tool()]).register_impl("get_weather", get_weather)
    request = ChatRequest.from_body(
        {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "What is the weather in Sydney?"}],
            "tools": [_weather_tool()],
        },
        {},
    )
    session = GatewaySession(session_id="s1", tenant_id="t1")
    response = cap_router.execute(request, session, router)
    assert response.content
    assert "22" in response.content or "sunny" in response.content


def test_capability_router_selection_only_without_impl() -> None:
    """Without a registered implementation, the router returns the selected call."""
    router = _MockRouter()
    cap_router = CapabilityRouter(tools=[_weather_tool()])
    request = ChatRequest.from_body(
        {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "What is the weather in Sydney?"}],
            "tools": [_weather_tool()],
        },
        {},
    )
    session = GatewaySession(session_id="s1", tenant_id="t1")
    response = cap_router.execute(request, session, router)
    assert "get_weather" in response.content


def test_gateway_lifecycle_uses_capability_router() -> None:
    """A request with ``tools`` is routed through the CapabilityRouter end-to-end."""

    def get_weather(args: dict[str, Any]) -> dict[str, Any]:
        return {"city": args["city"], "temp": 22}

    router = _MockRouter()
    lifecycle = GatewayRequestLifecycle(
        router=router,
        tool_implementations={"get_weather": get_weather},
    )
    body = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Weather in Sydney?"}],
        "tools": [_weather_tool()],
    }
    result = lifecycle.process(body, {"Authorization": "Bearer sk-test"})
    assert result["status_code"] == 200
    rb = result["body"]
    assert rb["choices"][0]["message"]["role"] == "assistant"
    assert "22" in rb["choices"][0]["message"]["content"]


def test_capability_router_uses_plain_dispatch_for_no_tools() -> None:
    """A request without tools falls through to plain provider dispatch."""
    router = _MockRouter()
    lifecycle = GatewayRequestLifecycle(router=router)
    body = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    result = lifecycle.process(body)
    assert result["status_code"] == 200
    assert router.last_request is not None
    assert not router.last_request.tools


def test_axiom4_no_crp_headers_in_tool_provider_call() -> None:
    """CRP headers are not forwarded to the provider during tool execution."""
    router = _MockRouter()
    cap_router = CapabilityRouter(tools=[_weather_tool()])
    request = ChatRequest.from_body(
        {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Weather in Sydney?"}],
            "tools": [_weather_tool()],
        },
        {"CRP-Safety-Profile": "strict"},
    )
    session = GatewaySession(session_id="s1", tenant_id="t1")
    cap_router.execute(request, session, router)
    assert router.last_request is not None
    # The temporary provider request must not carry CRP-* headers.
    assert getattr(router.last_request, "crp_safety_profile", None) is None or not router.last_request.crp_safety_profile
