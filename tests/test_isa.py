# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Intent & Speech-Act Positioning (CRP-SPEC-052)."""

from __future__ import annotations

import os
from typing import Any

import pytest

import crp
from crp.isa import (
    CoreferenceResolver,
    IntentClassifier,
    LLMIntentClassifier,
    build_intent_section,
    confidence,
)
from crp.providers.custom import CustomProvider


def _make_provider(responses: list[str]) -> CustomProvider:
    """Build a provider that cycles through canned responses."""
    idx = 0

    def generate(messages: list[dict[str, str]]) -> tuple[str, str]:
        nonlocal idx
        idx += 1
        return responses[(idx - 1) % len(responses)] if responses else "Done.", "stop"

    return CustomProvider(
        generate_fn=generate,
        count_tokens_fn=lambda t: len(t.split()),
        context_size=4096,
        name="mock",
    )


class TestIntentClassifier:
    """Rule-based intent classification."""

    def test_classify_request(self) -> None:
        clf = IntentClassifier()
        tag = clf.classify("Check the contract for me.")
        assert tag.speech_act == "request"
        assert tag.directness == pytest.approx(0.9, abs=0.05)

    def test_classify_question(self) -> None:
        clf = IntentClassifier()
        tag = clf.classify("Can you check the contract?")
        assert tag.speech_act == "question"
        assert tag.directness == pytest.approx(0.4, abs=0.05)

    def test_classify_assertion(self) -> None:
        clf = IntentClassifier()
        tag = clf.classify("I think the contract covers this.")
        assert tag.speech_act == "assertion"

    def test_classify_expressive(self) -> None:
        clf = IntentClassifier()
        tag = clf.classify("I'm frustrated that this is still broken.")
        assert tag.speech_act == "expressive"
        assert tag.valence < 0

    def test_constraints(self) -> None:
        clf = IntentClassifier()
        tag = clf.classify("Check only the payment clause before the signature block.")
        assert "restrict-scope" in tag.implied_constraints
        assert "temporal-order" in tag.implied_constraints

    def test_valence_positive(self) -> None:
        clf = IntentClassifier()
        tag = clf.classify("Great, thanks!")
        assert tag.valence > 0

    def test_confidence_bounds(self) -> None:
        clf = IntentClassifier()
        tag = clf.classify("Please send the report.")
        assert 0.0 <= confidence(tag) <= 1.0


class TestCoreferenceResolver:
    """Cross-session pronoun + ordinal resolution."""

    def test_resolve_pronoun_with_recent_entity(self) -> None:
        resolver = CoreferenceResolver()
        entities = {"a": "the contract"}
        resolved = resolver.resolve("Can you check it?", entities)
        assert "contract" in resolved
        assert " it" not in resolved.lower()

    def test_no_change_without_entities(self) -> None:
        resolver = CoreferenceResolver()
        resolved = resolver.resolve("Can you check it?", {})
        assert resolved == "Can you check it?"

    def test_resolve_ordinal_second_option(self) -> None:
        resolver = CoreferenceResolver()
        entities = {"opt1": "monthly plan", "opt2": "annual plan"}
        resolved = resolver.resolve("Is the second option cheaper?", entities)
        assert "annual plan" in resolved

    def test_resolve_ordinal_last_option(self) -> None:
        resolver = CoreferenceResolver()
        entities = {"opt1": "plan A", "opt2": "plan B"}
        resolved = resolver.resolve("Go with the last option.", entities)
        assert "plan B" in resolved


class TestIntentSection:
    """Interpreted-intent envelope section builder."""

    def test_build_intent_section(self) -> None:
        clf = IntentClassifier()
        tag = clf.classify("Please check the contract.")
        section = build_intent_section("Please check the contract.", tag, "Please check the contract.")
        assert section["speech_act"] == "request"
        assert 0.0 <= section["intent_confidence"] <= 1.0
        assert section["tone_hint"] == "neutral"
        assert section["resolved"] == "Please check the contract."

    def test_negative_valence_sets_tone(self) -> None:
        clf = IntentClassifier()
        tag = clf.classify("It is still broken.")
        section = build_intent_section("It is still broken.", tag, "It is still broken.")
        assert section["tone_hint"] == "acknowledge_friction"


class TestAgentISAIntegration:
    """Agent.run performs intent classification and coreference resolution."""

    def test_agent_attaches_intent_section(self) -> None:
        agent = crp.Agent(provider=_make_provider(["Done."]), tools=[])
        result = agent.run("Can you check the contract?")
        assert result.intent["speech_act"] == "question"
        assert 0.0 <= result.intent["intent_confidence"] <= 1.0
        assert "resolved" in result.intent

    def test_agent_resolves_coreference_across_turns(self) -> None:
        agent = crp.Agent(provider=_make_provider(["Checked.", "Confirmed."]), tools=[])
        r1 = agent.run("Please review the contract.")
        assert "contract" in r1.intent["resolved"]
        r2 = agent.run("Can you check it again?")
        assert "contract" in r2.intent["resolved"]
        # The resolved turn, not the raw pronoun, should reach the model.
        assert "it" not in r2.intent["resolved"].lower()

    def test_agent_can_disable_coreference(self) -> None:
        agent = crp.Agent(provider=_make_provider(["Done."]), tools=[])
        result = agent.run("Can you check it?", resolve_coreferences=False)
        assert result.intent["resolved"] == "Can you check it?"


# ---------------------------------------------------------------------------
# Optional live LLM test against LM Studio
# ---------------------------------------------------------------------------


def _lm_studio_available() -> bool:
    base_url = os.getenv("CRP_LM_STUDIO_URL", "http://localhost:1234/v1")
    api_key = os.getenv("CRP_LM_STUDIO_KEY", "not-needed")
    try:
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=api_key, timeout=5)
        client.models.list()
        return True
    except Exception:
        return False


@pytest.mark.llm
@pytest.mark.skipif(not _lm_studio_available(), reason="LM Studio not reachable")
def test_llm_intent_classifier() -> None:
    """An optional end-to-end check that a local LLM can classify intent."""
    clf = LLMIntentClassifier()
    tag = clf.classify("Can you check the contract?")
    assert tag.speech_act in {"request", "question"}
    assert 0.0 <= tag.directness <= 1.0
