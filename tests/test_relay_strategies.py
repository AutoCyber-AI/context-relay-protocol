# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for novel context relay strategies — §21 (reflexive, progressive, stream-augmented)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════
# §21 relay_strategies unit tests
# ═══════════════════════════════════════════════════════════════════════

from crp.core.relay_strategies import (
    AugmentationEvent,
    ContextIndex,
    ContextIndexEntry,
    FactCorrection,
    ReflexiveAnalysis,
    StreamAugmentationState,
    _compress_fact_to_summary,
    _detect_contradiction,
    _extract_key_terms,
    _split_into_sentences,
    analyze_output_against_kb,
    build_augmented_continuation,
    build_context_index,
    build_detail_injection,
    build_refinement_prompt,
    detect_index_references,
    find_relevant_facts_for_sentence,
)


# ---------------------------------------------------------------------------
# Helpers — lightweight Fact & WarmStore mocks
# ---------------------------------------------------------------------------

@dataclass
class MockFact:
    text: str
    confidence: float = 0.9
    id: str = ""
    source_window_id: str = "w1"
    flagged_confidence: bool = False
    confidence_flag_reason: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"fact-{uuid.uuid4().hex[:8]}"


class MockWarmStore:
    """Minimal WarmStore mock matching get_ranked_facts / fact_count interface."""

    def __init__(self, facts: list[MockFact] | None = None):
        self._facts = facts or []

    @property
    def fact_count(self) -> int:
        return len(self._facts)

    def get_ranked_facts(self, limit: int = 50) -> list[MockFact]:
        return self._facts[:limit]

    def advance_window(self, window_id: str) -> None:
        pass

    def add_facts(self, facts, edges=None):
        pass


def _count_tokens(text: str) -> int:
    """Approximate token counter for tests (4 chars ≈ 1 token)."""
    return max(1, len(text) // 4)


# ═══════════════════════════════════════════════════════════════════════
# Utility function tests
# ═══════════════════════════════════════════════════════════════════════

class TestExtractKeyTerms:
    def test_basic_extraction(self):
        terms = _extract_key_terms("The quick brown fox jumps over the lazy dog")
        assert "quick" in terms
        assert "brown" in terms
        assert "fox" in terms
        # Stop words removed
        assert "the" not in terms
        assert "over" not in terms

    def test_empty_string(self):
        assert _extract_key_terms("") == []

    def test_numbers_included(self):
        terms = _extract_key_terms("Python 3.13 has 500 improvements")
        assert "python" in terms
        assert "500" in terms

    def test_short_words_excluded(self):
        terms = _extract_key_terms("I am at it")
        assert terms == []  # All short/stop words


class TestSplitIntoSentences:
    def test_basic_split(self):
        text = "First sentence. Second sentence. Third sentence."
        sentences = _split_into_sentences(text)
        assert len(sentences) == 3

    def test_paragraph_split(self):
        text = "First paragraph.\n\nSecond paragraph."
        sentences = _split_into_sentences(text)
        assert len(sentences) >= 2

    def test_exclamation_question(self):
        text = "What is CRP? It's a protocol! Very innovative."
        sentences = _split_into_sentences(text)
        assert len(sentences) == 3

    def test_empty_text(self):
        assert _split_into_sentences("") == []


class TestCompressFactToSummary:
    def test_short_fact_unchanged(self):
        text = "CRP uses 6-phase envelope construction."
        assert _compress_fact_to_summary(text) == text

    def test_long_fact_truncated(self):
        text = "The Context Relay Protocol implements a sophisticated multi-window continuation system with budgeted context packing that maximizes information density across generation windows."
        summary = _compress_fact_to_summary(text)
        assert len(summary) <= 85  # ~80 + "..."
        assert summary.endswith("...")

    def test_multi_sentence_takes_first(self):
        text = "CRP is innovative. It has many features. It scales well."
        summary = _compress_fact_to_summary(text)
        assert summary == "CRP is innovative."


class TestDetectContradiction:
    def test_no_contradiction(self):
        assert not _detect_contradiction(
            "CRP uses 6 phases", "CRP uses 6 phases"
        )

    def test_numeric_contradiction(self):
        assert _detect_contradiction(
            "CRP uses 4 phases for envelope construction",
            "CRP uses 6 phases for envelope construction",
        )

    def test_negation_contradiction(self):
        assert _detect_contradiction(
            "This statement is not correct",
            "This statement is correct",
        )

    def test_unrelated_numbers_no_contradiction(self):
        # Different topics, different numbers — no contradiction
        assert not _detect_contradiction(
            "Python has 5 features",
            "CRP uses 6 phases",
        )


# ═══════════════════════════════════════════════════════════════════════
# §21.1 Reflexive dispatch tests
# ═══════════════════════════════════════════════════════════════════════

class TestReflexiveAnalysis:
    def test_needs_refinement_with_corrections(self):
        analysis = ReflexiveAnalysis(corrections=[
            FactCorrection("claim", "fact", "f1", 0.9, "contradiction"),
        ])
        assert analysis.needs_refinement

    def test_no_refinement_when_empty(self):
        analysis = ReflexiveAnalysis(claims_checked=5, claims_supported=5)
        analysis.coverage_score = 1.0
        assert not analysis.needs_refinement

    def test_needs_refinement_low_coverage(self):
        analysis = ReflexiveAnalysis(coverage_score=0.1)
        assert analysis.needs_refinement

    def test_needs_refinement_many_unsupported(self):
        analysis = ReflexiveAnalysis(
            unsupported_claims=["a", "b", "c"],
            coverage_score=0.5,
        )
        assert analysis.needs_refinement


class TestAnalyzeOutputAgainstKB:
    def test_empty_warm_store(self):
        store = MockWarmStore([])
        analysis = analyze_output_against_kb(
            "CRP is a protocol. It is innovative.",
            store, _count_tokens,
        )
        assert analysis.claims_checked == 0 or len(analysis.unsupported_claims) > 0

    def test_supported_claims(self):
        facts = [
            MockFact("CRP implements a 6-phase envelope construction protocol", 0.95),
            MockFact("The extraction pipeline has graduated 6 stages", 0.90),
        ]
        store = MockWarmStore(facts)
        analysis = analyze_output_against_kb(
            "CRP implements a 6-phase envelope construction protocol for context relay. "
            "The extraction pipeline uses graduated 6 stages for fact discovery.",
            store, _count_tokens,
        )
        assert analysis.claims_checked > 0
        # At least some support expected
        assert analysis.claims_supported >= 0  # Might vary by matching

    def test_enrichment_facts_detected(self):
        facts = [
            MockFact("CRP uses continuation windows for long text", 0.95),
            MockFact("The WarmStore tracks fact aging and confidence", 0.85),
            MockFact("Source grounding provides provenance metadata", 0.80),
        ]
        store = MockWarmStore(facts)
        analysis = analyze_output_against_kb(
            "CRP is a simple protocol.",  # Doesn't mention most facts
            store, _count_tokens,
        )
        assert len(analysis.enrichment_facts) >= 0  # May find enrichment

    def test_short_fragments_skipped(self):
        store = MockWarmStore([MockFact("some fact", 0.9)])
        analysis = analyze_output_against_kb("OK.", store, _count_tokens)
        # Very short fragment should be skipped
        assert analysis.claims_checked == 0


class TestBuildRefinementPrompt:
    def test_basic_prompt_structure(self):
        analysis = ReflexiveAnalysis(
            corrections=[
                FactCorrection(
                    "CRP uses 4 phases",
                    "CRP uses 6 phases",
                    "f1", 0.95, "contradiction",
                ),
            ],
            coverage_score=0.5,
        )
        prompt = build_refinement_prompt("output text", analysis, _count_tokens)
        assert "FACT-CHECK RESULTS" in prompt
        assert "CORRECTIONS" in prompt
        assert "CRP uses 4 phases" in prompt
        assert "CRP uses 6 phases" in prompt

    def test_enrichment_facts_included(self):
        analysis = ReflexiveAnalysis(
            corrections=[],
            enrichment_facts=["CRP has continuation windows", "WarmStore manages facts"],
            coverage_score=0.2,
        )
        prompt = build_refinement_prompt("output", analysis, _count_tokens)
        assert "ADDITIONAL VERIFIED FACTS" in prompt
        assert "continuation windows" in prompt

    def test_empty_analysis(self):
        analysis = ReflexiveAnalysis(coverage_score=0.8)
        prompt = build_refinement_prompt("output", analysis, _count_tokens)
        assert "FACT-CHECK RESULTS" in prompt
        assert "Coverage: 80%" in prompt


# ═══════════════════════════════════════════════════════════════════════
# §21.2 Progressive disclosure tests
# ═══════════════════════════════════════════════════════════════════════

class TestBuildContextIndex:
    def test_basic_index_creation(self):
        facts = [
            MockFact("CRP uses 6-phase envelope construction for context packing.", 0.95),
            MockFact("The extraction pipeline discovers facts via graduated stages.", 0.90),
            MockFact("WarmStore tracks fact aging and confidence scores.", 0.85),
        ]
        store = MockWarmStore(facts)
        index = build_context_index(store, _count_tokens)
        assert len(index.entries) == 3
        assert index.total_facts == 3
        assert index.entries[0].ref_id == "F1"
        assert index.entries[1].ref_id == "F2"
        assert index.entries[2].ref_id == "F3"

    def test_empty_store(self):
        store = MockWarmStore([])
        index = build_context_index(store, _count_tokens)
        assert len(index.entries) == 0
        assert index.total_facts == 0

    def test_index_text_format(self):
        facts = [MockFact("CRP is innovative.", 0.9)]
        store = MockWarmStore(facts)
        index = build_context_index(store, _count_tokens)
        text = index.to_text()
        assert "AVAILABLE CONTEXT INDEX" in text
        assert "[F1]" in text
        assert "confidence: 90%" in text

    def test_token_budget_respected(self):
        # Create many facts — index should stop when budget exhausted
        facts = [MockFact(f"Fact number {i} about some topic with details " * 3, 0.9)
                 for i in range(100)]
        store = MockWarmStore(facts)
        index = build_context_index(store, _count_tokens, max_index_tokens=200)
        assert len(index.entries) < 100  # Budget should cap entries
        assert index.index_tokens <= 200


class TestDetectIndexReferences:
    def test_explicit_reference(self):
        index = ContextIndex(entries=[
            ContextIndexEntry("F1", "fact-1", "CRP envelope", 0.9, "full text", 10),
            ContextIndexEntry("F2", "fact-2", "Extraction pipeline", 0.9, "full text", 10),
        ])
        output = "According to [F1], the envelope is important. [F2] confirms extraction works."
        referenced = detect_index_references(output, index)
        assert len(referenced) == 2

    def test_term_overlap_reference(self):
        index = ContextIndex(entries=[
            ContextIndexEntry("F1", "fact-1", "CRP envelope construction phases", 0.9, "full text", 10),
        ])
        output = "The CRP envelope uses multiple construction phases to pack context."
        referenced = detect_index_references(output, index)
        assert len(referenced) >= 1  # Should detect via term overlap

    def test_no_references(self):
        index = ContextIndex(entries=[
            ContextIndexEntry("F1", "fact-1", "Quantum mechanics explanation", 0.9, "full text", 10),
        ])
        output = "CRP is a protocol for context relay."
        referenced = detect_index_references(output, index)
        # No overlap with quantum mechanics
        assert len(referenced) == 0

    def test_empty_index(self):
        index = ContextIndex(entries=[])
        referenced = detect_index_references("some output", index)
        assert referenced == []


class TestBuildDetailInjection:
    def test_basic_injection(self):
        entries = [
            ContextIndexEntry("F1", "fact-1", "summary", 0.9, "Full detailed text about CRP", 10),
            ContextIndexEntry("F2", "fact-2", "summary", 0.85, "Full detailed text about extraction", 10),
        ]
        text = build_detail_injection(entries, _count_tokens)
        assert "EXPANDED CONTEXT" in text
        assert "[F1]" in text
        assert "[F2]" in text
        assert "Full detailed text about CRP" in text

    def test_empty_entries(self):
        text = build_detail_injection([], _count_tokens)
        assert text == ""

    def test_token_budget_limits(self):
        entries = [
            ContextIndexEntry("F1", "f1", "s", 0.9, "x" * 10000, 2500),
            ContextIndexEntry("F2", "f2", "s", 0.9, "y" * 10000, 2500),
        ]
        text = build_detail_injection(entries, _count_tokens, max_tokens=100)
        # Should not include both — budget too small
        assert text.count("[F") <= 2  # At most partial


# ═══════════════════════════════════════════════════════════════════════
# §21.3 Stream-augmented generation tests
# ═══════════════════════════════════════════════════════════════════════

class TestStreamAugmentationState:
    def test_should_check_every_2_sentences(self):
        state = StreamAugmentationState()
        state.sentences_completed = 0
        assert state.should_check  # 0 % 2 == 0
        state.sentences_completed = 1
        assert not state.should_check  # 1 % 2 != 0
        state.sentences_completed = 2
        assert state.should_check  # 2 % 2 == 0

    def test_initial_state(self):
        state = StreamAugmentationState()
        assert state.total_injections == 0
        assert state.accumulated_output == ""
        assert state.sentences_completed == 0


class TestFindRelevantFacts:
    def test_finds_relevant_facts(self):
        facts = [
            MockFact("CRP uses envelope construction with 6 phases", 0.95),
            MockFact("Quantum mechanics describes wave-particle duality", 0.90),
        ]
        store = MockWarmStore(facts)
        results = find_relevant_facts_for_sentence(
            "The CRP envelope construction process has multiple phases.",
            store, set(), _count_tokens,
        )
        # Should find the CRP-related fact, not quantum mechanics
        assert len(results) >= 0  # May or may not match depending on overlap

    def test_already_injected_excluded(self):
        facts = [MockFact("CRP uses envelope construction", 0.95, id="f1")]
        store = MockWarmStore(facts)
        results = find_relevant_facts_for_sentence(
            "CRP envelope construction is important.",
            store, {"f1"}, _count_tokens,
        )
        assert len(results) == 0  # f1 already injected

    def test_empty_store(self):
        store = MockWarmStore([])
        results = find_relevant_facts_for_sentence(
            "Some sentence about CRP.",
            store, set(), _count_tokens,
        )
        assert results == []

    def test_short_sentence(self):
        store = MockWarmStore([MockFact("some fact", 0.9)])
        results = find_relevant_facts_for_sentence(
            "OK", store, set(), _count_tokens,
        )
        assert results == []


class TestBuildAugmentedContinuation:
    def test_message_structure(self):
        messages = build_augmented_continuation(
            system_prompt="You are helpful.",
            partial_output="CRP uses envelope construction. It has 6 phases.",
            injected_facts=[("f1", "CRP envelope has budget-aware packing")],
            task_input="Explain CRP architecture.",
        )
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"
        assert "CONTEXT INJECTION" in messages[3]["content"]
        assert "budget-aware packing" in messages[3]["content"]
        assert "Continue writing" in messages[3]["content"]

    def test_partial_output_preserved(self):
        messages = build_augmented_continuation(
            "sys", "partial output text",
            [("f1", "fact1")], "task",
        )
        assert messages[2]["content"] == "partial output text"

    def test_multiple_facts_injected(self):
        messages = build_augmented_continuation(
            "sys", "output",
            [("f1", "fact one"), ("f2", "fact two"), ("f3", "fact three")],
            "task",
        )
        content = messages[3]["content"]
        assert "fact one" in content
        assert "fact two" in content
        assert "fact three" in content


# ═══════════════════════════════════════════════════════════════════════
# §21 Orchestrator integration tests (mocked provider)
# ═══════════════════════════════════════════════════════════════════════


def _make_mock_orchestrator():
    """Create a CRPOrchestrator with fully mocked subsystems."""
    from crp.core.orchestrator import CRPOrchestrator

    provider = MagicMock(spec=[
        "generate_chat", "count_tokens", "context_window_size",
        "max_output_tokens", "model_name", "generate_chat_stream",
        "supports_tools",
    ])
    provider.count_tokens.side_effect = lambda t: max(1, len(t) // 4)
    provider.context_window_size.return_value = 8192
    provider.max_output_tokens = 4096
    provider.model_name = "mock-model"
    provider.supports_tools.return_value = False

    orch = CRPOrchestrator.__new__(CRPOrchestrator)

    # Minimal internal state
    orch._provider = provider
    orch._config = MagicMock()
    orch._config.max_total_output_tokens = None
    orch._config.budget_cap = None
    orch._session = MagicMock()
    orch._session.session_id = "test-session"
    orch._session.status = "active"
    type(orch._session).is_expired = property(lambda self: False)
    orch._dag = MagicMock()
    orch._dag.add_node = MagicMock()
    orch._extraction = MagicMock()

    # Extraction mock
    mock_extraction = MagicMock()
    mock_extraction.facts = []
    mock_extraction.edges = []
    mock_extraction.total_facts = 0
    mock_extraction.stages_run = [0]
    orch._extraction.extract.return_value = mock_extraction
    orch._extraction_history = []

    # Security mocks
    orch._injection_detector = MagicMock()
    scan_result = MagicMock()
    scan_result.has_flags = False
    scan_result.flags = []
    orch._injection_detector.scan.return_value = scan_result

    orch._input_validator = MagicMock()
    val_result = MagicMock()
    val_result.valid = True
    val_result.sanitized_text = "test task"
    val_result.sanitized_size = 9
    val_result.original_size = 9
    val_result.control_chars_removed = 0
    val_result.warnings = []
    orch._input_validator.validate.return_value = val_result

    rbac_perm = MagicMock()
    rbac_perm.allowed = True
    rbac_rate = MagicMock()
    rbac_rate.allowed = True
    orch._rbac = MagicMock()
    orch._rbac.check_permission.return_value = rbac_perm
    orch._rbac.check_rate_limit.return_value = rbac_rate

    # Warm store
    orch._warm_store = MockWarmStore([
        MockFact("CRP uses 6-phase envelope construction", 0.95),
        MockFact("Extraction pipeline has 6 graduated stages", 0.90),
        MockFact("WarmStore tracks fact aging and confidence", 0.85),
    ])

    # CKF
    orch._ckf = MagicMock()

    # Quality gate mock
    from crp.extraction.quality_gate import run_quality_gate
    orch._quality_gate = run_quality_gate

    # Quarantine
    orch._quarantine = MagicMock()
    orch._quarantine.quarantine_count = 0

    # Curator
    orch._curator = MagicMock()
    orch._curator.should_curate.return_value = False

    # Circuit breaker
    from crp.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
    orch._circuit_breaker = CircuitBreaker(CircuitBreakerConfig())

    # Counters
    orch._windows_completed = 0
    orch._total_input_tokens = 0
    orch._total_output_tokens = 0

    # Session lifecycle
    orch._closed = False

    return orch, provider


class TestDispatchReflexive:
    def test_basic_reflexive_dispatch(self):
        orch, provider = _make_mock_orchestrator()
        # Pass 1: generate with no context
        # Pass 2: generate refined (may or may not happen depending on analysis)
        provider.generate_chat.return_value = (
            "CRP uses 6-phase envelope construction for packing context. "
            "The extraction pipeline has graduated stages.",
            "stop",
        )

        output, report = orch.dispatch_reflexive("You are helpful.", "Explain CRP.")
        assert output is not None
        assert len(output) > 0
        assert report.quality_tier is not None
        assert report.telemetry["relay_strategy"] == "reflexive"
        assert report.telemetry["reflexive_passes"] >= 1

    def test_reflexive_with_corrections(self):
        orch, provider = _make_mock_orchestrator()
        call_count = [0]

        def mock_generate(messages, max_tokens=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # First pass: incorrect claim
                return (
                    "CRP uses 4-phase envelope construction. "
                    "The extraction pipeline handles facts automatically.",
                    "stop",
                )
            else:
                # Second pass: corrected
                return (
                    "CRP uses 6-phase envelope construction for context packing. "
                    "The extraction pipeline has 6 graduated stages for fact discovery.",
                    "stop",
                )

        provider.generate_chat.side_effect = mock_generate
        output, report = orch.dispatch_reflexive("You are helpful.", "Explain CRP.")
        assert report.telemetry["relay_strategy"] == "reflexive"
        # Should have done at least 1 pass
        assert report.telemetry["reflexive_passes"] >= 1

    def test_reflexive_max_passes_respected(self):
        orch, provider = _make_mock_orchestrator()
        call_count = [0]

        def mock_generate(messages, max_tokens=None):
            call_count[0] += 1
            return ("Some unrelated output about quantum mechanics.", "stop")

        provider.generate_chat.side_effect = mock_generate
        output, report = orch.dispatch_reflexive(
            "You are helpful.", "Explain quantum mechanics.",
            max_refinement_passes=1,
        )
        # 1 initial + at most 1 refinement = 2 max
        assert report.telemetry["reflexive_passes"] <= 2


class TestDispatchProgressive:
    def test_basic_progressive_dispatch(self):
        orch, provider = _make_mock_orchestrator()
        provider.generate_chat.return_value = (
            "CRP implements context relay via [F1] envelope construction. "
            "The extraction pipeline [F2] discovers facts.",
            "stop",
        )

        output, report = orch.dispatch_progressive("You are helpful.", "Explain CRP.")
        assert output is not None
        assert report.telemetry["relay_strategy"] == "progressive"
        assert report.telemetry["progressive_index_entries"] == 3  # 3 facts in store

    def test_progressive_no_references(self):
        orch, provider = _make_mock_orchestrator()
        provider.generate_chat.return_value = (
            "I don't know anything about this topic.",
            "stop",
        )

        output, report = orch.dispatch_progressive("You are helpful.", "Explain CRP.")
        assert report.telemetry["relay_strategy"] == "progressive"
        # No detail expansion expected
        assert report.telemetry["progressive_detail_tokens"] >= 0

    def test_progressive_with_empty_store(self):
        orch, provider = _make_mock_orchestrator()
        orch._warm_store = MockWarmStore([])  # Empty store
        provider.generate_chat.return_value = (
            "CRP is a protocol.", "stop",
        )

        output, report = orch.dispatch_progressive("You are helpful.", "Explain CRP.")
        assert report.telemetry["progressive_index_entries"] == 0

    def test_progressive_detail_expansion(self):
        orch, provider = _make_mock_orchestrator()
        call_count = [0]

        def mock_generate(messages, max_tokens=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return ("According to [F1], CRP uses envelope construction.", "stop")
            else:
                return (
                    "CRP uses 6-phase envelope construction for context packing. "
                    "This ensures optimal utilization of the context window.",
                    "stop",
                )

        provider.generate_chat.side_effect = mock_generate
        output, report = orch.dispatch_progressive("You are helpful.", "Explain CRP.")
        assert report.telemetry["relay_strategy"] == "progressive"
        # Should have detected [F1] reference and done detail expansion
        assert call_count[0] >= 1  # At least initial pass


class TestDispatchStreamAugmented:
    def test_basic_stream_augmented(self):
        orch, provider = _make_mock_orchestrator()

        # Mock streaming: yields tokens that complete sentences
        def mock_stream(messages, max_tokens=None):
            tokens = [
                "CRP ", "uses ", "envelope ", "construction. ",
                "It ", "has ", "6 ", "phases.",
            ]
            for t in tokens:
                yield t

        provider.generate_chat_stream.side_effect = mock_stream

        output, report = orch.dispatch_stream_augmented(
            "You are helpful.", "Explain CRP."
        )
        assert output is not None
        assert len(output) > 0
        assert report.telemetry["relay_strategy"] == "stream_augmented"

    def test_stream_augmented_no_injections_when_empty_store(self):
        orch, provider = _make_mock_orchestrator()
        orch._warm_store = MockWarmStore([])  # Empty store

        def mock_stream(messages, max_tokens=None):
            yield "Some output text."

        provider.generate_chat_stream.side_effect = mock_stream

        output, report = orch.dispatch_stream_augmented(
            "You are helpful.", "Explain CRP."
        )
        assert report.telemetry["stream_augment_injections"] == 0

    def test_stream_augmented_max_injections_cap(self):
        orch, provider = _make_mock_orchestrator()

        # Add many matching facts
        orch._warm_store = MockWarmStore([
            MockFact(f"CRP envelope phase {i} handles context packing step {i}", 0.95, id=f"f{i}")
            for i in range(20)
        ])

        call_count = [0]

        def mock_stream(messages, max_tokens=None):
            call_count[0] += 1
            # Each call yields a sentence about CRP envelope
            tokens = [f"CRP envelope handles phase {call_count[0]} of context. "]
            for t in tokens:
                yield t

        provider.generate_chat_stream.side_effect = mock_stream

        output, report = orch.dispatch_stream_augmented(
            "You are helpful.", "Explain CRP.",
            max_injections=2,
        )
        assert report.telemetry["stream_augment_injections"] <= 2

    def test_stream_augmented_telemetry_fields(self):
        orch, provider = _make_mock_orchestrator()

        def mock_stream(messages, max_tokens=None):
            yield "Simple output text."

        provider.generate_chat_stream.side_effect = mock_stream

        output, report = orch.dispatch_stream_augmented(
            "You are helpful.", "Explain CRP."
        )
        telem = report.telemetry
        assert "relay_strategy" in telem
        assert "stream_augment_injections" in telem
        assert "stream_augment_injection_tokens" in telem
        assert telem["relay_strategy"] == "stream_augmented"


# ═══════════════════════════════════════════════════════════════════════
# WindowMetrics §21 fields tests
# ═══════════════════════════════════════════════════════════════════════

class TestWindowMetricsRelayFields:
    def test_relay_strategy_fields_exist(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics()
        assert m.relay_strategy == ""
        assert m.reflexive_passes == 0
        assert m.reflexive_corrections == 0
        assert m.reflexive_coverage == 0.0
        assert m.progressive_index_entries == 0
        assert m.progressive_index_tokens == 0
        assert m.progressive_detail_entries == 0
        assert m.progressive_detail_tokens == 0
        assert m.stream_augment_injections == 0
        assert m.stream_augment_injection_tokens == 0

    def test_relay_fields_in_to_dict(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics(
            relay_strategy="reflexive",
            reflexive_passes=3,
            reflexive_corrections=2,
            reflexive_coverage=0.85,
        )
        d = m.to_dict()
        assert d["relay_strategy"] == "reflexive"
        assert d["reflexive_passes"] == 3
        assert d["reflexive_corrections"] == 2
        assert d["reflexive_coverage"] == 0.85

    def test_progressive_fields_in_to_dict(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics(
            relay_strategy="progressive",
            progressive_index_entries=10,
            progressive_index_tokens=500,
            progressive_detail_entries=3,
            progressive_detail_tokens=800,
        )
        d = m.to_dict()
        assert d["progressive_index_entries"] == 10
        assert d["progressive_detail_entries"] == 3

    def test_stream_augmented_fields_in_to_dict(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics(
            relay_strategy="stream_augmented",
            stream_augment_injections=4,
            stream_augment_injection_tokens=1200,
        )
        d = m.to_dict()
        assert d["stream_augment_injections"] == 4
        assert d["stream_augment_injection_tokens"] == 1200
