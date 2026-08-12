# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Operation State Machine (CRP-SPEC-050 §5)."""

from __future__ import annotations

import pytest

from crp.stl import (
    InvalidTransition,
    OperationState,
    OperationStateMachine,
    STLOperation,
)


def _machine() -> OperationStateMachine:
    return OperationStateMachine(plan=[STLOperation.RETRIEVE, STLOperation.SYNTHESISE])


class TestOperationStateMachine:
    def test_starts_intent_classified(self) -> None:
        sm = _machine()
        assert sm.state is OperationState.INTENT_CLASSIFIED
        assert sm.events[0].state is OperationState.INTENT_CLASSIFIED
        assert sm.current_operation is None

    def test_position_advances(self) -> None:
        sm = _machine()
        sm.position()
        assert sm.state is OperationState.OPERATION_POSITIONED
        assert sm.current_operation is STLOperation.RETRIEVE

    def test_full_tool_cycle(self) -> None:
        sm = _machine()
        sm.position()
        sm.select_tool("lookup")
        sm.execute_tool("lookup")
        sm.verify()
        sm.integrate()
        assert sm.state is OperationState.INTEGRATED
        # second operation
        sm.position()
        assert sm.current_operation is STLOperation.SYNTHESISE
        sm.verify()  # direct generation
        sm.integrate()
        sm.complete()
        assert sm.is_complete
        assert sm.completion == 1.0

    def test_direct_path(self) -> None:
        sm = _machine()
        sm.position()
        sm.verify(detail="direct")
        assert sm.state is OperationState.OPERATION_VERIFIED
        sm.integrate()
        assert sm.state is OperationState.INTEGRATED

    def test_invalid_transition_raises(self) -> None:
        sm = _machine()
        sm.position()
        # cannot integrate straight from positioned
        with pytest.raises(InvalidTransition):
            sm.integrate()

    def test_cannot_select_tool_without_positioning(self) -> None:
        sm = _machine()
        with pytest.raises(InvalidTransition):
            sm.select_tool("x")

    def test_halt_from_positioned(self) -> None:
        sm = _machine()
        sm.position()
        sm.halt("preventive_safety")
        assert sm.is_halted
        assert sm.halt_reason == "preventive_safety"

    def test_completion_fraction(self) -> None:
        sm = _machine()
        sm.position()
        sm.verify()
        sm.integrate()
        assert sm.completion == 0.5  # 1 of 2 integrated

    def test_headers(self) -> None:
        sm = _machine()
        sm.position()
        h = sm.to_headers()
        assert h["CRP-Agent-Operation-State"] == "OPERATION_POSITIONED"
        assert h["CRP-Agent-Operation-Type"] == "RETRIEVE"
        assert h["CRP-Agent-Operation-Plan"] == "RETRIEVE,SYNTHESISE"

    def test_event_stream_records_transitions(self) -> None:
        sm = _machine()
        sm.position()
        sm.verify()
        sm.integrate()
        states = [e["state"] for e in sm.event_stream()]
        assert states == [
            "INTENT_CLASSIFIED",
            "OPERATION_POSITIONED",
            "OPERATION_VERIFIED",
            "INTEGRATED",
        ]
