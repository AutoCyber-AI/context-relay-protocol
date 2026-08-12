# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the CRPv6 Agent SDK (SPEC-059)."""

from __future__ import annotations

import json
from typing import Any

import crp
from crp.agent_sdk.events import AgentEventKind
from crp.agent_sdk.intent_compiler import compile_tool
from crp.agent_sdk.policy import Policy
from crp.agent_sdk.tool_manifest import ToolSpec
from crp.providers.custom import CustomProvider
from crp.sdk.client import CRPClient
from crp.stl.classifier import STLOperation


def _make_provider(responses: list[str]) -> CustomProvider:
    """Build a provider that cycles through canned responses."""
    calls: list[list[dict[str, str]]] = []
    idx = 0

    def generate(messages: list[dict[str, str]]) -> tuple[str, str]:
        calls.append(messages)
        content = messages[0].get("content", "")
        # If a tool frame is present and we have a weather tool, return the tool call.
        if "get_weather" in content and "Available tools" in content:
            return (
                json.dumps({"capability_id": "get_weather", "arguments": {"city": "Sydney"}}),
                "stop",
            )
        # Fallback direct answer.
        response = responses[idx % len(responses)] if responses else "Done."
        return response, "stop"

    return CustomProvider(
        generate_fn=generate,
        count_tokens_fn=lambda t: len(t.split()),
        context_size=4096,
        name="mock",
    )


def test_agent_importable() -> None:
    """``crp.Agent`` must be available at the top-level namespace."""
    assert hasattr(crp, "Agent")
    assert crp.Agent is not None


def test_compile_callable() -> None:
    """The intent compiler turns a Python callable into a ToolSpec + descriptor."""

    def get_weather(city: str) -> dict[str, Any]:
        """Fetch current weather for a city."""
        return {"city": city, "temp": 22}

    compiled = compile_tool(get_weather, operation_types=[STLOperation.RETRIEVE])
    assert compiled.spec.capability_id == "get_weather"
    assert "city" in compiled.spec.input_schema["properties"]
    assert compiled.descriptor.serves_operation(STLOperation.RETRIEVE)


def test_agent_run_direct_answer() -> None:
    """An Agent can answer without tools when the request does not require them."""
    provider = _make_provider(["CRP is a context-relay protocol."])
    agent = crp.Agent(provider=provider, tools=[])
    result = agent.run("What is CRP?")
    assert "context-relay protocol" in result.answer
    assert not result.halted


def test_agent_run_with_tool() -> None:
    """An Agent selects and executes a registered tool."""

    def get_weather(city: str) -> dict[str, Any]:
        return {"city": city, "temp": 22, "condition": "sunny"}

    provider = _make_provider(["The weather is sunny and 22 °C."])
    agent = crp.Agent(
        provider=provider,
        tools=[get_weather],
        policy=Policy.balanced(),
    )
    result = agent.run("What is the weather in Sydney?")
    assert result.observation_count == 1
    assert any("sunny" in str(obs.get("payload", "")) for obs in result.cso.tool_observations)
    assert "22" in result.answer or "sunny" in result.answer


def test_agent_run_tool_spec_dict() -> None:
    """Tools can be supplied as ToolSpec dicts."""

    def get_weather(city: str) -> dict[str, Any]:
        return {"city": city, "temp": 18}

    spec: dict[str, Any] = {
        "capability_id": "get_weather",
        "description": "Fetch weather",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        "output_schema": {"type": "object"},
        "operation_types": ["RETRIEVE"],
    }
    provider = _make_provider(["It is 18 °C."])
    agent = crp.Agent(provider=provider, tools=[spec])
    # Register the implementation manually because a dict has no callable.
    compiled = compile_tool(get_weather, operation_types=[STLOperation.RETRIEVE])
    agent.register_tool(compiled.impl or get_weather)
    result = agent.run("Weather in Sydney?")
    assert result.observation_count >= 1


def test_agent_response_fields() -> None:
    """AgentResponse exposes inspectable reasoning fields."""

    def get_weather(city: str) -> dict[str, Any]:
        return {"city": city, "temp": 22}

    provider = _make_provider(["Sunny and 22 °C."])
    agent = crp.Agent(provider=provider, tools=[get_weather])
    result = agent.run("Weather in Sydney?")
    assert result.how_it_was_built
    assert isinstance(result.sources, list)
    assert result.complete or result.halted


def test_agent_multiturn_relay() -> None:
    """Reusing an Agent relays the CSO across turns."""
    provider = _make_provider(["First answer.", "Second answer."])
    agent = crp.Agent(provider=provider, tools=[])
    r1 = agent.run("Question one?")
    r2 = agent.run("Question two?")
    assert r2.cso.window_number > r1.cso.window_number
    assert "First answer" in r1.answer


def test_agent_run_stream() -> None:
    """run_stream yields AgentEvents for the transparency layer."""

    def get_weather(city: str) -> dict[str, Any]:
        return {"city": city, "temp": 22}

    provider = _make_provider(["Sunny and 22 °C."])
    agent = crp.Agent(provider=provider, tools=[get_weather])
    events = list(agent.run_stream("Weather in Sydney?"))
    kinds = {e.kind for e in events}
    assert AgentEventKind.INTENT_CLASSIFIED in kinds
    assert AgentEventKind.TOOL_SELECTED in kinds or AgentEventKind.FINAL in kinds
    assert any(e.kind is AgentEventKind.FINAL for e in events)


def test_policy_builder() -> None:
    """Policy compiles into a TCF PolicyContext and safety overrides."""
    policy = Policy.strict().block("dangerous_tool").domain("eu_ai_act")
    ctx = policy.to_policy_context()
    assert "dangerous_tool" in ctx.blocklist
    assert "eu_ai_act" in ctx.policy_domains
    overrides = policy.to_safety_overrides()
    assert overrides["safety.profile"] == "strict"


def test_agent_register_tool_chain() -> None:
    """register_tool returns self and clears cached fabric."""
    agent = crp.Agent(provider=_make_provider([]), tools=[])
    assert agent.register_tool(lambda x: x) is agent


def test_crp_client_make_agent_bridge() -> None:
    """CRPClient.make_agent() returns an Agent bound to the client's provider."""

    def get_weather(city: str) -> dict[str, Any]:
        return {"city": city, "temp": 22}

    provider = _make_provider(["Sunny and 22 °C."])
    client = CRPClient(provider=provider, depth="standard")
    agent = client.make_agent(tools=[get_weather])
    assert isinstance(agent, crp.Agent)
    result = agent.run("Weather in Sydney?")
    assert result.observation_count >= 1
    assert "22" in result.answer or "Sunny" in result.answer


# ---------------------------------------------------------------------------
# SPEC-049 — Verification Relay integration
# ---------------------------------------------------------------------------


def test_agent_verification_relay_catches_invalid_claim() -> None:
    """At thorough depth the Agent verifies arithmetic claims in its answer."""
    provider = _make_provider(["The total is 10 + 20 = 999."])
    agent = crp.Agent(provider=provider, tools=[], depth="thorough")
    result = agent.run("What is 10 + 20?")
    assert result.verification is not None
    assert result.verification["invalid"] == 1
    assert result.verification["verification_ratio"] == 0.0
    assert result.crp.risk == "HIGH"


def test_agent_verification_relay_valid_claim() -> None:
    """A correct arithmetic claim is marked valid."""
    provider = _make_provider(["The total is 10 + 20 = 30."])
    agent = crp.Agent(provider=provider, tools=[], depth="thorough")
    result = agent.run("What is 10 + 20?")
    assert result.verification is not None
    assert result.verification["invalid"] == 0
    assert result.verification["verification_ratio"] == 1.0


def test_agent_verification_relay_skipped_for_quick() -> None:
    """At quick depth verification is skipped by default."""
    provider = _make_provider(["The total is 10 + 20 = 999."])
    agent = crp.Agent(provider=provider, tools=[], depth="quick")
    result = agent.run("What is 10 + 20?")
    assert result.verification is None
    assert result.crp.risk == "LOW"


def test_agent_verification_relay_overridden_by_kwarg() -> None:
    """verify=True can force verification even at standard depth."""
    provider = _make_provider(["The total is 2 * 3 = 7."])
    agent = crp.Agent(provider=provider, tools=[], depth="standard")
    result = agent.run("What is 2 * 3?", verify=True)
    assert result.verification is not None
    assert result.verification["invalid"] == 1
