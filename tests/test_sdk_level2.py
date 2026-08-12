# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Progressive SDK Level 2 controls (SPEC-032 §4)."""

from __future__ import annotations

import pytest

from crp.sdk.client import CRPClient
from crp.sdk.response import CRPAskResponse


class TestSDKLevel2Depth:
    def test_ask_with_depth_param(self) -> None:
        client = CRPClient()
        # Without provider, the diagnostic provider returns an empty response.
        r = client.ask("hello", depth="thorough")
        assert r.text == ""
        assert r.finish_reason in {"stop", "error"}
        assert "thorough" in r.how_it_was_built

    def test_client_default_depth(self) -> None:
        client = CRPClient(depth="standard")
        assert client.depth == "standard"


class TestSDKLevel2Tools:
    def test_tool_decorator(self) -> None:
        client = CRPClient()

        @client.tool
        def get_weather(city: str) -> dict:
            return {"temp": 20}

        assert "get_weather" in client._tools.tools
        result = client.call_tool("get_weather", "London")
        assert result["temp"] == 20

    def test_call_unknown_tool_raises(self) -> None:
        client = CRPClient()
        with pytest.raises(ValueError, match="not registered"):
            client.call_tool("nonexistent")


class TestSDKLevel2InspectReasoning:
    def test_how_it_was_built_present(self) -> None:
        client = CRPClient()
        r = client.ask("test")
        assert isinstance(r, CRPAskResponse)
        assert r.how_it_was_built
        assert "Query" in r.how_it_was_built

    def test_open_questions_default_empty(self) -> None:
        client = CRPClient()
        r = client.ask("test")
        assert r.open_questions == []

    def test_decisions_default_empty(self) -> None:
        client = CRPClient()
        r = client.ask("test")
        assert r.decisions == []
