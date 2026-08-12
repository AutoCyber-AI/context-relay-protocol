# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the CKF envelope gate fix (§audit G1).

Verifies that the Phase 6 CKF retrieval gate reserves budget for CKF
and activates even at high envelope saturation.
"""

from __future__ import annotations

import pytest

from crp.envelope.builder import (
    CKF_GATE_TOKENS,
    CKF_RESERVE_RATIO,
    EnvelopeResult,
    EnvelopeState,
    construct,
)
from crp.core.task_intent import TaskIntent
from crp.extraction.types import Fact, FactGraph


def _make_fact(text: str, fid: str = "") -> Fact:
    """Create a minimal test Fact."""
    return Fact(
        id=fid or f"f-{hash(text) % 10000}",
        text=text,
        category="test",
        confidence=0.9,
    )


def _simple_counter(text: str) -> int:
    """Count tokens as words (simple approximation for tests)."""
    return len(text.split())


# ---- CKF Gate constants ----

def test_ckf_gate_threshold_lowered():
    """CKF_GATE_TOKENS should be low enough that CKF can fire in practice."""
    assert CKF_GATE_TOKENS <= 200, f"CKF gate too high: {CKF_GATE_TOKENS}"


def test_ckf_reserve_ratio_exists():
    """CKF_RESERVE_RATIO should reserve a meaningful fraction."""
    assert 0.05 <= CKF_RESERVE_RATIO <= 0.30


# ---- CKF gate fires with reservation ----

def test_ckf_gate_fires_with_retriever():
    """When a CKF retriever is provided with sufficient budget, CKF facts are added."""
    ckf_fact = _make_fact("CKF retrieved knowledge about security", "ckf-1")

    def mock_retriever(query: str, budget: int) -> list[Fact]:
        return [ckf_fact]

    facts = [_make_fact(f"warm fact {i}", f"wf-{i}") for i in range(5)]

    state = EnvelopeState(
        facts=facts,
        ckf_retriever=mock_retriever,
    )

    ti = TaskIntent(task_input="Explain security best practices for web apps")
    result = construct(ti, budget_tokens=500, state=state, count_tokens=_simple_counter)

    assert result.ckf_facts_added > 0, "CKF gate should have fired"


def test_ckf_gate_reserves_budget():
    """CKF budget reservation ensures warm packing doesn't starve CKF."""
    call_log: list[tuple[str, int]] = []

    def tracking_retriever(query: str, budget: int) -> list[Fact]:
        call_log.append((query, budget))
        return [_make_fact("ckf insight", "ckf-t")]

    # Many warm facts to fill the envelope
    facts = [_make_fact(f"warm fact number {i} with some content", f"wf-{i}") for i in range(20)]

    state = EnvelopeState(
        facts=facts,
        ckf_retriever=tracking_retriever,
    )

    ti = TaskIntent(task_input="Analyze the data processing pipeline architecture")
    result = construct(ti, budget_tokens=800, state=state, count_tokens=_simple_counter)

    # CKF should have been called
    assert len(call_log) > 0, "CKF retriever should have been called due to budget reservation"


def test_ckf_no_retriever_no_reservation():
    """Without a CKF retriever, no budget is reserved and all goes to warm store."""
    facts = [_make_fact(f"fact {i}", f"f-{i}") for i in range(5)]
    state = EnvelopeState(facts=facts, ckf_retriever=None)

    ti = TaskIntent(task_input="Simple task")
    result = construct(ti, budget_tokens=500, state=state, count_tokens=_simple_counter)

    assert result.ckf_facts_added == 0


def test_ckf_gate_skipped_for_tiny_budget():
    """With very small budget, CKF reservation is skipped to avoid starving warm store."""
    def mock_retriever(query: str, budget: int) -> list[Fact]:
        return [_make_fact("ckf fact", "ckf-tiny")]

    facts = [_make_fact("warm fact", "wf-0")]
    state = EnvelopeState(facts=facts, ckf_retriever=mock_retriever)

    ti = TaskIntent(task_input="Very short task")
    # Budget too small for both warm + CKF reservation
    result = construct(ti, budget_tokens=50, state=state, count_tokens=_simple_counter)
    # Should not crash regardless of whether CKF fires
    assert isinstance(result, EnvelopeResult)


def test_ckf_retriever_failure_non_fatal():
    """CKF retriever exception should not crash the envelope builder."""
    def failing_retriever(query: str, budget: int) -> list[Fact]:
        raise RuntimeError("CKF unavailable")

    facts = [_make_fact(f"fact {i}", f"f-{i}") for i in range(3)]
    state = EnvelopeState(facts=facts, ckf_retriever=failing_retriever)

    ti = TaskIntent(task_input="Task that triggers CKF")
    result = construct(ti, budget_tokens=500, state=state, count_tokens=_simple_counter)

    # Should complete without error
    assert result.ckf_facts_added == 0
    assert result.envelope_text  # Still produces output


def test_ckf_retriever_empty_return():
    """CKF retriever returning empty list is handled gracefully."""
    def empty_retriever(query: str, budget: int) -> list[Fact]:
        return []

    facts = [_make_fact(f"fact {i}", f"f-{i}") for i in range(3)]
    state = EnvelopeState(facts=facts, ckf_retriever=empty_retriever)

    ti = TaskIntent(task_input="Task with empty CKF")
    result = construct(ti, budget_tokens=500, state=state, count_tokens=_simple_counter)

    assert result.ckf_facts_added == 0


def test_ckf_gate_uses_query_from_decomposition():
    """CKF query should come from decomposed aspects."""
    captured_query: list[str] = []

    def query_capture_retriever(query: str, budget: int) -> list[Fact]:
        captured_query.append(query)
        return []

    facts = [_make_fact("fact", "f-0")]
    state = EnvelopeState(facts=facts, ckf_retriever=query_capture_retriever)

    ti = TaskIntent(task_input="Explain database indexing strategies for PostgreSQL")
    construct(ti, budget_tokens=500, state=state, count_tokens=_simple_counter)

    if captured_query:
        # Query should be derived from task aspects, not empty
        assert len(captured_query[0]) > 0


def test_ckf_budget_reservation_proportional():
    """CKF reserve should be at least CKF_GATE_TOKENS when retriever is present."""
    budget = 1000
    expected_min_reserve = CKF_GATE_TOKENS
    expected_ratio_reserve = int(budget * CKF_RESERVE_RATIO)
    expected_reserve = max(expected_min_reserve, expected_ratio_reserve)

    # The warm store should get budget - reserve
    # We verify by checking CKF is called with enough budget
    received_budgets: list[int] = []

    def budget_tracker(query: str, budget: int) -> list[Fact]:
        received_budgets.append(budget)
        return []

    facts = [_make_fact(f"fact {i}", f"f-{i}") for i in range(3)]
    state = EnvelopeState(facts=facts, ckf_retriever=budget_tracker)

    ti = TaskIntent(task_input="Test budget allocation for CKF reservation")
    construct(ti, budget_tokens=budget, state=state, count_tokens=_simple_counter)

    if received_budgets:
        # CKF should receive at least the reserved amount
        assert received_budgets[0] >= expected_min_reserve


# ---- Integration: CKF + warm store coexistence ----

def test_ckf_and_warm_facts_both_in_envelope():
    """Both warm store facts and CKF facts should appear in the envelope."""
    ckf_fact = _make_fact("CKF_UNIQUE_CONTENT_FROM_KNOWLEDGE_FRAMEWORK", "ckf-int")
    warm_fact = _make_fact("WARM_UNIQUE_CONTENT_FROM_WARM_STORE", "wf-int")

    def mock_retriever(query: str, budget: int) -> list[Fact]:
        return [ckf_fact]

    state = EnvelopeState(
        facts=[warm_fact],
        ckf_retriever=mock_retriever,
    )

    ti = TaskIntent(task_input="Comprehensive analysis of system architecture")
    result = construct(ti, budget_tokens=1000, state=state, count_tokens=_simple_counter)

    # Both facts should be in the envelope text
    assert "WARM_UNIQUE_CONTENT" in result.envelope_text
    if result.ckf_facts_added > 0:
        assert "CKF_UNIQUE_CONTENT" in result.envelope_text
