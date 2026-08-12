# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""NLI-backed faithful narration + real-chain provenance tests (CRP-SPEC-056 §8.3.2)."""

from __future__ import annotations

import re
import sys
from types import ModuleType
from typing import Any

import pytest

from crp.tel import EventType
from crp.tel.events import tool_result, tool_start
from crp.tel.faithful import entailment_check, filter_faithful, reset_nli_cache


class _FakeCrossEncoder:
    """Stand-in for sentence_transformers.CrossEncoder with a scripted verdict."""

    # Scores follow the verifier's label order: [contradiction, entailment, neutral].
    verdicts: dict[str, list[float]] = {}
    fail: bool = False
    loaded_with: str = ""

    def __init__(self, model_name: str) -> None:
        _FakeCrossEncoder.loaded_with = model_name

    def predict(self, pairs: list[tuple[str, str]]) -> list[list[float]]:
        if _FakeCrossEncoder.fail:
            raise RuntimeError("simulated NLI inference failure")
        out: list[list[float]] = []
        for _premise, claim in pairs:
            out.append(_FakeCrossEncoder.verdicts.get(claim, [-5.0, -5.0, 5.0]))
        return out


def _fake_sentence_transformers() -> ModuleType:
    mod = ModuleType("sentence_transformers")
    mod.CrossEncoder = _FakeCrossEncoder  # type: ignore[attr-defined]
    return mod


@pytest.fixture(autouse=True)
def _reset_caches(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Give every test a clean NLI cache and a fake sentence_transformers."""
    from crp.provenance import entailment_verifier

    _FakeCrossEncoder.verdicts = {}
    _FakeCrossEncoder.fail = False
    monkeypatch.setitem(sys.modules, "sentence_transformers", _fake_sentence_transformers())
    reset_nli_cache()
    entailment_verifier.reset_model_cache()
    yield
    reset_nli_cache()
    entailment_verifier.reset_model_cache()


_TRACE = [
    tool_start("t1", "port_scan", "fingerprint"),
    tool_result("t1", {"open_ports": [22, 80]}),
]


class TestNLIFaithfulNarration:
    def test_entailed_claim_accepted(self) -> None:
        _FakeCrossEncoder.verdicts["The scan found open ports 22 and 80."] = [-5.0, 5.0, -5.0]
        assert entailment_check("The scan found open ports 22 and 80.", _TRACE) is True

    def test_fabricated_claim_rejected(self) -> None:
        _FakeCrossEncoder.verdicts["The scan found port 443 open."] = [5.0, -5.0, -5.0]
        assert entailment_check("The scan found port 443 open.", _TRACE) is False

    def test_neutral_claim_rejected(self) -> None:
        _FakeCrossEncoder.verdicts["The weather is sunny."] = [-5.0, -5.0, 5.0]
        assert entailment_check("The weather is sunny.", _TRACE) is False

    def test_nli_accepts_paraphrase_heuristic_would_miss(self) -> None:
        # "exposed services" shares no content words with the trace, so the
        # word-subset heuristic rejects it; NLI entailment accepts it.
        claim = "The host exposes two services."
        _FakeCrossEncoder.verdicts[claim] = [-5.0, 5.0, -5.0]
        assert entailment_check(claim, _TRACE) is True

    def test_filter_faithful_gates_claims_with_nli(self) -> None:
        _FakeCrossEncoder.verdicts["ports 22 and 80 are open"] = [-5.0, 5.0, -5.0]
        _FakeCrossEncoder.verdicts["port 443 is open"] = [5.0, -5.0, -5.0]
        claims = ["ports 22 and 80 are open", "port 443 is open"]
        assert filter_faithful(claims, _TRACE) == ["ports 22 and 80 are open"]

    def test_model_loaded_with_configured_name(self) -> None:
        entailment_check("anything", _TRACE)
        assert "nli" in _FakeCrossEncoder.loaded_with.lower()


class TestHeuristicFallback:
    def test_fallback_when_nli_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # import fails
        trace = [tool_result("t1", {"open_ports": [22]})]
        assert entailment_check("open port 22", trace) is True
        assert entailment_check("open port 443", trace) is False

    def test_fallback_when_inference_fails(self) -> None:
        _FakeCrossEncoder.fail = True
        trace = [tool_result("t1", {"open_ports": [22]})]
        assert entailment_check("open port 22", trace) is True
        assert entailment_check("open port 443", trace) is False

    def test_filter_faithful_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        trace = [tool_result("t1", {"open_ports": [22]})]
        assert filter_faithful(["open port 22", "open port 443"], trace) == ["open port 22"]


class TestRealChainProvenance:
    def _make_agent(self) -> Any:
        from crp.agent_sdk.agent import Agent
        from crp.providers.custom import CustomProvider

        provider = CustomProvider(
            generate_fn=lambda _msgs: ("The weather in Sydney is sunny.", "stop"),
            count_tokens_fn=lambda t: len(t.split()),
            context_size=4096,
            name="mock",
        )
        return Agent(provider=provider, tools=[])

    def _provenance_events(self, agent: Any, session_id: str) -> list[dict[str, Any]]:
        events = list(agent.run_tel("What's the weather?", session_id=session_id))
        return [
            e.payload["value"]
            for e in events
            if e.type == EventType.CUSTOM and e.payload.get("name") == "crp.provenance"
        ]

    def test_provenance_carries_real_chain_hash(self) -> None:
        agent = self._make_agent()
        prov = self._provenance_events(agent, "chain-test-1")
        assert len(prov) == 1
        entry = prov[0]
        # Real HMAC window-chain entry, not the old "0"*64 / bare-sha256 stub.
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", entry["hash"])
        assert entry["prev"] == "genesis"

    def test_chain_links_consecutive_runs(self) -> None:
        agent = self._make_agent()
        first = self._provenance_events(agent, "chain-test-2")[0]
        second = self._provenance_events(agent, "chain-test-2")[0]
        assert second["prev"] == first["hash"]
        assert second["hash"] != first["hash"]

    def test_chain_entry_is_verifiable(self) -> None:
        # Recompute the window HMAC independently and compare.
        import hashlib

        from crp.provenance.window_chain import build_window_hmac

        agent = self._make_agent()
        prov = self._provenance_events(agent, "chain-test-3")[0]
        key = hashlib.sha256(b"chain-test-3").digest()
        recomputed = build_window_hmac(agent._tel_chain_input, key)  # type: ignore[attr-defined]
        # The event hash must be reproducible from the recorded window inputs.
        assert prov["hash"] == recomputed
