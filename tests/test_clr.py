# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Clarification Protocol (CRP-SPEC-053)."""

from __future__ import annotations

import pytest

import crp
from crp.clr import (
    ClarificationPolicy,
    ClarificationRequired,
    ClarificationSession,
    build_clarification,
    header_value,
    should_clarify,
)
from crp.clr.response import Interpretation
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


class TestTrigger:
    """Clarification trigger logic."""

    def test_low_confidence_triggers(self) -> None:
        policy = ClarificationPolicy(threshold=0.2)
        assert should_clarify(
            intent_confidence=0.1,
            parse_divergence=0.5,
            risk="LOW",
            policy=policy,
        )

    def test_high_confidence_does_not_trigger(self) -> None:
        policy = ClarificationPolicy(threshold=0.4)
        assert not should_clarify(
            intent_confidence=0.95,
            parse_divergence=0.0,
            risk="HIGH",
            policy=policy,
        )

    def test_risk_weight_scales_threshold(self) -> None:
        # Same ambiguity; HIGH risk makes it more likely to clarify.
        policy = ClarificationPolicy(threshold=0.25)
        assert not should_clarify(
            intent_confidence=0.6,
            parse_divergence=0.2,
            risk="LOW",
            policy=policy,
        )
        assert should_clarify(
            intent_confidence=0.6,
            parse_divergence=0.2,
            risk="HIGH",
            policy=policy,
        )

    def test_policy_from_dict(self) -> None:
        policy = ClarificationPolicy.from_obj({"clarification_threshold": 0.1})
        assert policy.threshold == pytest.approx(0.1)


class TestResponse:
    """Clarification response builder."""

    def test_build_clarification_sorts_and_sets_default(self) -> None:
        candidates = [
            Interpretation("reading-b", ["RETRIEVE"], 0.35),
            Interpretation("reading-a", ["GENERATE"], 0.65),
        ]
        clarification = build_clarification(candidates, reason="ambiguous-target")
        assert clarification.interpretations[0].reading == "reading-a"
        assert clarification.default == 0

    def test_no_default_when_close(self) -> None:
        candidates = [
            Interpretation("reading-a", ["RETRIEVE"], 0.55),
            Interpretation("reading-b", ["GENERATE"], 0.45),
        ]
        clarification = build_clarification(candidates)
        assert clarification.default is None

    def test_header_value(self) -> None:
        clarification = ClarificationRequired(
            reason="ambiguous-target",
            interpretations=[
                Interpretation("a", ["RETRIEVE"], 0.6),
                Interpretation("b", ["GENERATE"], 0.4),
            ],
        )
        value = header_value(clarification)
        assert value.startswith('required; candidates=2; reason="ambiguous-target"')


class TestSession:
    """Clarification resolution lifecycle."""

    def test_resolve_by_index(self) -> None:
        session = ClarificationSession()
        clarification = build_clarification(
            [
                Interpretation("action", ["RETRIEVE"], 0.6),
                Interpretation("info", ["GENERATE"], 0.4),
            ]
        )
        session.set_pending(clarification, raw_turn="do it", resolved_turn="do the action")
        resolved = session.resolve(1)
        assert "clarified:" in resolved
        assert session.selections == [1]


class TestAgentClarification:
    """Agent integration with the clarification protocol."""

    def test_agent_emits_clarification_when_ambiguous(self) -> None:
        agent = crp.Agent(
            provider=_make_provider([]),
            tools=[],
            policy=crp.agent_sdk.Policy.balanced().clarify(0.0),
        )
        result = agent.run("That thing over there")
        assert result.halted
        assert "X-CRP-Clarification" in result.headers
        assert result.intent["intent_confidence"] >= 0.0

    def test_agent_skips_clarification_when_clear(self) -> None:
        agent = crp.Agent(
            provider=_make_provider(["Done."]),
            tools=[],
            policy=crp.agent_sdk.Policy.balanced().clarify(1.0),
        )
        result = agent.run("What is the weather in Sydney?")
        assert not result.halted
        assert result.answer == "Done."

    def test_clarification_response_has_candidates(self) -> None:
        agent = crp.Agent(
            provider=_make_provider([]),
            tools=[],
            policy=crp.agent_sdk.Policy.balanced().clarify(0.0),
        )
        result = agent.run("Do the needful")
        assert result.halted
        body = result.text
        assert "CRP-Clarification-Required" in body or "interpretations" in body
