# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Multi-Horizon Context Model (SPEC-028)."""

from __future__ import annotations

from crp.state.horizons import ContextTier, MultiHorizonContext, TurnEntry


class TestContextTier:
    def test_enum_values(self) -> None:
        assert ContextTier.PERSISTENT.value == "persistent"
        assert ContextTier.CONVERSATIONAL.value == "conversational"
        assert ContextTier.EPHEMERAL.value == "ephemeral"


class TestMultiHorizonContext:
    def test_classify_intent_reference(self) -> None:
        mhc = MultiHorizonContext()
        result = mhc.classify_intent("what did you mean about the second option")
        assert result["intent"] == "reference"
        assert result["confidence"] > 0.8

    def test_classify_intent_clarify(self) -> None:
        mhc = MultiHorizonContext()
        result = mhc.classify_intent("can you clarify that point")
        assert result["intent"] == "clarify"

    def test_classify_intent_explore_default(self) -> None:
        mhc = MultiHorizonContext()
        result = mhc.classify_intent("tell me about kubernetes networking")
        assert result["intent"] == "explore"

    def test_resolve_reference(self) -> None:
        mhc = MultiHorizonContext()
        history = ["We discussed Kubernetes pods", "Then we talked about services"]
        resolved = mhc.resolve_reference("what about pods", history)
        assert "pods" in resolved.lower()

    def test_blend_retrieve(self) -> None:
        mhc = MultiHorizonContext()
        weights = mhc.blend_for_operation("RETRIEVE")
        assert weights["persistent"] > weights["conversational"]
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_blend_clarify(self) -> None:
        mhc = MultiHorizonContext()
        weights = mhc.blend_for_operation("CLARIFY")
        assert weights["conversational"] > weights["persistent"]

    def test_add_turn(self) -> None:
        mhc = MultiHorizonContext(max_turn_log=3)
        mhc.add_turn("user", "hello")
        mhc.add_turn("assistant", "hi")
        assert len(mhc.turn_log) == 2
        assert mhc.turn_log[0].turn_id == 1

    def test_turn_log_eviction(self) -> None:
        mhc = MultiHorizonContext(max_turn_log=2)
        mhc.add_turn("user", "a")
        mhc.add_turn("user", "b")
        mhc.add_turn("user", "c")
        assert len(mhc.turn_log) == 2
        assert mhc.turn_log[0].content == "b"

    def test_get_recent_turns(self) -> None:
        mhc = MultiHorizonContext()
        mhc.add_turn("user", "a")
        mhc.add_turn("assistant", "b")
        recent = mhc.get_recent_turns(n=1)
        assert len(recent) == 1
        assert recent[0].content == "b"
