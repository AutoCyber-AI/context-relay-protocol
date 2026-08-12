# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRPClient.dispatch_positioned — the SDK-level positioned loop (CRP-SPEC-049/050)."""

from __future__ import annotations

from typing import Any

from crp.providers.custom import CustomProvider
from crp.sdk.client import CRPClient
from crp.tools import CapabilityProfile
from crp.tools.adapters import descriptor_from_callable, fabric_from_callables


def _provider(generate_fn: Any) -> CustomProvider:
    return CustomProvider(
        generate_fn=generate_fn,
        count_tokens_fn=lambda t: len(t.split()),
        context_size=4096,
        name="mock",
    )


class TestCallableAdapters:
    def test_descriptor_from_callable(self) -> None:
        def search(query: str, limit: int = 10) -> dict:
            """Search the index."""
            return {}
        desc = descriptor_from_callable(search)
        assert desc.capability_id == "search"
        assert desc.required_inputs() == ["query"]  # limit has a default
        assert desc.input_schema["properties"]["limit"]["type"] == "integer"
        assert "Search the index" in desc.description

    def test_fabric_from_callables_executes(self) -> None:
        from crp.stl import STLOperation
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b
        fabric, executor = fabric_from_callables([add])
        desc = fabric.get("add")
        assert desc is not None
        res = executor.execute(desc, {"a": 2, "b": 3}, STLOperation.GENERATE)
        assert res.ok and res.observation is not None and res.observation.payload == 5


class TestClientDispatchPositioned:
    def test_direct_generation(self) -> None:
        client = CRPClient(provider=_provider(lambda msgs: ("a friendly greeting", "stop")))
        res = client.dispatch_positioned("write a greeting")
        assert res.text == "a friendly greeting"
        assert res.state_machine is not None and res.state_machine.is_complete
        assert res.observation_count == 0

    def test_auto_tool_execution(self) -> None:
        def generate_fn(msgs: list[dict[str, str]]) -> tuple[str, str]:
            prompt = msgs[-1]["content"]
            if "capability_id" in prompt:  # a Tool Positioning Frame was shown
                return ('{"capability_id": "get_weather", "arguments": {"city": "Paris"}}', "stop")
            return ("done", "stop")

        client = CRPClient(provider=_provider(generate_fn))

        @client.tool
        def get_weather(city: str) -> dict:
            """Get the weather for a city."""
            return {"city": city, "temp": 20}

        res = client.dispatch_positioned("find the weather in Paris", profile=CapabilityProfile.SMALL_LOCAL)
        assert res.observation_count >= 1
        assert any("get_weather" in f.statement for f in res.cso.established_facts)

    def test_headers_present(self) -> None:
        client = CRPClient(provider=_provider(lambda msgs: ("ok", "stop")))
        res = client.dispatch_positioned("summarise the report")
        assert res.headers["CRP-Agent-Operation-State"] == "COMPLETE"
        assert "CRP-Tool-Observation-Count" in res.headers


class TestConversationHelper:
    def test_multi_turn_relays_state(self) -> None:
        def generate_fn(msgs: list[dict[str, str]]) -> tuple[str, str]:
            prompt = msgs[-1]["content"]
            if "capability_id" in prompt:
                return ('{"capability_id": "get_weather", "arguments": {"city": "Paris"}}', "stop")
            return ("done", "stop")

        client = CRPClient(provider=_provider(generate_fn))

        @client.tool
        def get_weather(city: str) -> dict:
            """Get the weather for a city."""
            return {"city": city, "temp": 20}

        convo = client.conversation(profile=CapabilityProfile.SMALL_LOCAL)
        r1 = convo.say("find the weather in Paris")
        assert r1.observation_count >= 1
        assert convo.turns == 1

        r2 = convo.say("is that warm?")
        # prior-turn fact carried forward into the second turn's CSO
        assert any("get_weather" in f.statement for f in r2.cso.established_facts)
        assert r2.cso.window_number == r1.cso.window_number + 1
        assert convo.turns == 2

        convo.reset()
        assert convo.turns == 0 and convo.cso is None

