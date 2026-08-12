# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Progressive SDK Level 0 + 1 (SPEC-032)."""

from __future__ import annotations

import pytest

from crp.sdk.client import CRPClient
from crp.sdk.proxies import _SafetyProxy
from crp.sdk.response import (
    CRPAskResponse,
    CRPCompletionResponse,
    CRPResponseMeta,
    SourceAttribution,
)


class TestCRPResponseMeta:
    def test_defaults(self) -> None:
        m = CRPResponseMeta()
        assert m.risk == "LOW"
        assert m.grounded is True
        assert m.fabrications == 0
        assert m.chain_valid is True


class TestCRPCompletionResponse:
    def test_str_returns_text(self) -> None:
        r = CRPCompletionResponse(text="hello")
        assert str(r) == "hello"

    def test_crp_meta_present(self) -> None:
        r = CRPCompletionResponse(text="hello")
        assert r.crp.risk == "LOW"


class TestCRPAskResponse:
    def test_quality_field(self) -> None:
        r = CRPAskResponse(text="answer", quality="A")
        assert r.quality == "A"
        assert str(r) == "answer"

    def test_sources_list(self) -> None:
        s = SourceAttribution(title="doc1", doc_id="d1", used_facts=3)
        r = CRPAskResponse(text="x", sources=[s])
        assert len(r.sources) == 1
        assert r.sources[0].title == "doc1"


class TestCRPClient:
    def test_init_defaults(self) -> None:
        client = CRPClient()
        assert client._orchestrator is None
        assert client._safety_profile == "balanced"
        assert isinstance(client.safety, _SafetyProxy)

    def test_tool_decorator(self) -> None:
        client = CRPClient()

        @client.tool
        def get_weather(city: str) -> dict:
            return {"temp": 20}

        assert "get_weather" in client._tools.tools

    def test_complete_without_provider_graceful(self) -> None:
        client = CRPClient()
        # Without a provider, _ensure_orchestrator falls back to the diagnostic
        # provider.  The client still returns a valid response object.
        r = client.complete("hello")
        assert r.text == ""
        assert r.finish_reason in {"stop", "error"}

    def test_ask_without_provider_graceful(self) -> None:
        client = CRPClient()
        r = client.ask("hello")
        assert r.text == ""
        assert r.finish_reason in {"stop", "error"}
