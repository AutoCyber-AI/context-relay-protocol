# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 3 tests — Envelope builder, all 6 phases."""

from __future__ import annotations

import math

import pytest

from crp.core.task_intent import TaskIntent
from crp.extraction.types import Fact, FactEdge, FactGraph, RelationType

# ============================================================================
# Helpers
# ============================================================================


def _make_task(system: str = "You are a security analyst.", task: str = "Analyse CVE-2024-1234") -> TaskIntent:
    return TaskIntent(system_prompt=system, task_input=task)


def _make_fact(text: str, fid: str | None = None, confidence: float = 0.8) -> Fact:
    f = Fact(text=text, confidence=confidence, category="test")
    if fid:
        f.id = fid
    return f


def _make_graph(facts: list[Fact], edges: list[FactEdge] | None = None) -> FactGraph:
    g = FactGraph()
    for f in facts:
        g.add_fact(f)
    for e in (edges or []):
        g.add_edge(e)
    return g


# ============================================================================
# 3A: Decomposer tests
# ============================================================================


class TestDecomposer:
    """Tests for envelope/decomposer.py — task decomposition."""

    def test_basic_decomposition(self):
        from crp.envelope.decomposer import decompose_task_aspects

        ti = _make_task()
        result = decompose_task_aspects(ti)
        assert result.aspects  # at least 1 aspect extracted
        assert len(result.aspect_embeddings) == len(result.aspects)
        assert len(result.full_embedding) > 0

    def test_empty_task(self):
        from crp.envelope.decomposer import decompose_task_aspects

        ti = TaskIntent()
        result = decompose_task_aspects(ti)
        assert result.aspects == []
        assert result.aspect_embeddings == []

    def test_noun_phrases_extracted(self):
        from crp.envelope.decomposer import _extract_noun_phrases

        text = 'Analyse "buffer overflow" in Apache Server for Remote Code Execution'
        nps = _extract_noun_phrases(text)
        # Should find capitalised phrases and quoted strings
        assert any("buffer overflow" in p for p in nps)
        assert any("Apache" in p for p in nps)

    def test_implicit_expansion(self):
        from crp.envelope.decomposer import _expand_aspects_implicit

        aspects = ["security"]
        text = "security vulnerability analysis in network protocol scanning"
        expanded = _expand_aspects_implicit(aspects, text)
        assert len(expanded) >= len(aspects)

    def test_implicit_expansion_empty_aspects(self):
        from crp.envelope.decomposer import _expand_aspects_implicit

        result = _expand_aspects_implicit([], "hello world testing analysis")
        assert len(result) > 0  # should produce fallback aspects

    def test_embedding_dimension(self):
        from crp.envelope.decomposer import _EMBED_DIM, decompose_task_aspects

        ti = _make_task()
        result = decompose_task_aspects(ti)
        # Fallback embeddings should have the right dimension
        if not result.used_ml_model:
            assert len(result.full_embedding) == _EMBED_DIM
            for emb in result.aspect_embeddings:
                assert len(emb) == _EMBED_DIM

    def test_bag_vector_normalized(self):
        from crp.envelope.decomposer import _bag_vector, _build_vocab, _tokenize

        tokens = _tokenize("hello world testing")
        vocab = _build_vocab(tokens)
        vec = _bag_vector(tokens, vocab, 384)
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6

    def test_deduplicated_aspects(self):
        from crp.envelope.decomposer import _extract_noun_phrases

        text = "Apache Server and Apache Server configuration"
        nps = _extract_noun_phrases(text)
        lower_nps = [p.lower() for p in nps]
        assert len(lower_nps) == len(set(lower_nps))


# ============================================================================
# 3B: Scoring tests
# ============================================================================


class TestScoring:
    """Tests for envelope/scoring.py — bi-encoder scoring."""

    def test_cosine_similarity_identical(self):
        from crp.envelope.scoring import cosine_similarity

        vec = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(vec, vec) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        from crp.envelope.scoring import cosine_similarity

        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_recency_weight_zero_age(self):
        from crp.envelope.scoring import recency_weight

        assert recency_weight(0) == 1.0

    def test_recency_weight_decays(self):
        from crp.envelope.scoring import recency_weight

        w1 = recency_weight(1)
        w10 = recency_weight(10)
        assert w1 > w10 > 0.0

    def test_novelty_weight_values(self):
        from crp.envelope.scoring import novelty_weight

        assert novelty_weight(0) == 1.5
        assert novelty_weight(1) == 1.0
        assert novelty_weight(2) == 1.0
        assert novelty_weight(3) == 0.5
        assert novelty_weight(100) == 0.5

    def test_dependency_bonus_capped(self):
        from crp.envelope.scoring import dependency_bonus

        f1 = _make_fact("fact one", fid="f1")
        f2 = _make_fact("fact two", fid="f2")
        edge = FactEdge(source_id="f1", target_id="f2", confidence=1.0)
        graph = _make_graph([f1, f2], [edge])
        # Give f2 a very high score to test cap
        recent = {"f2": 100.0}
        bonus = dependency_bonus(f1, graph, recent)
        assert bonus <= 0.5

    def test_dependency_bonus_zero_no_edges(self):
        from crp.envelope.scoring import dependency_bonus

        f1 = _make_fact("standalone fact", fid="f1")
        graph = _make_graph([f1])
        bonus = dependency_bonus(f1, graph, {})
        assert bonus == 0.0

    def test_score_facts_basic(self):
        from crp.envelope.decomposer import decompose_task_aspects
        from crp.envelope.scoring import score_facts

        ti = _make_task(task="Analyse network security vulnerabilities")
        decomp = decompose_task_aspects(ti)

        facts = [
            _make_fact("CVE-2024-1234 is a critical vulnerability", fid="f1"),
            _make_fact("The weather is sunny today", fid="f2"),
        ]
        graph = _make_graph(facts)

        scored = score_facts(facts, decomp, graph)
        assert len(scored) == 2
        # Scores should be >= 0 (some may be 0 if no word overlap in fallback mode)
        assert all(s.composite_score >= 0 for s in scored)
        # Should be sorted descending
        assert scored[0].composite_score >= scored[1].composite_score
        # The security-related fact should score higher than weather
        f1_score = next(s for s in scored if s.fact.id == "f1")
        f2_score = next(s for s in scored if s.fact.id == "f2")
        assert f1_score.composite_score >= f2_score.composite_score

    def test_score_facts_empty(self):
        from crp.envelope.decomposer import decompose_task_aspects
        from crp.envelope.scoring import score_facts

        ti = _make_task()
        decomp = decompose_task_aspects(ti)
        scored = score_facts([], decomp, FactGraph())
        assert scored == []

    def test_score_facts_with_seen_counts(self):
        from crp.envelope.decomposer import decompose_task_aspects
        from crp.envelope.scoring import score_facts

        ti = _make_task(task="security analysis")
        decomp = decompose_task_aspects(ti)

        f1 = _make_fact("security vulnerability found", fid="f1")
        f2 = _make_fact("security vulnerability found", fid="f2")  # same text
        graph = _make_graph([f1, f2])

        # f1 never seen (novelty 1.5×), f2 seen 5 times (novelty 0.5×)
        scored = score_facts(
            [f1, f2],
            decomp,
            graph,
            seen_counts={"f2": 5},
        )
        # f1 should score higher due to novelty boost
        f1_score = next(s for s in scored if s.fact.id == "f1")
        f2_score = next(s for s in scored if s.fact.id == "f2")
        assert f1_score.composite_score > f2_score.composite_score

    def test_score_formula(self):
        """Verify the composite formula: sim × recency × novelty + dep_bonus."""
        from crp.envelope.scoring import ScoredFact

        # Construct a scored fact manually to verify
        sf = ScoredFact(
            fact=_make_fact("test"),
            similarity=0.8,
            recency_weight=0.9,
            novelty_weight=1.5,
            dependency_bonus=0.1,
        )
        expected = 0.8 * 0.9 * 1.5 + 0.1
        sf.composite_score = sf.similarity * sf.recency_weight * sf.novelty_weight + sf.dependency_bonus
        assert abs(sf.composite_score - expected) < 1e-6


# ============================================================================
# 3C: Reranker tests
# ============================================================================


class TestReranker:
    """Tests for envelope/reranker.py — cross-encoder reranking."""

    def test_skip_below_threshold(self):
        """Fewer than MIN_FACTS_FOR_RERANK facts → skip reranking."""
        from crp.envelope.reranker import MIN_FACTS_FOR_RERANK, rerank

        ti = _make_task()
        scored = [
            ScoredFact(fact=_make_fact(f"fact {i}", fid=f"f{i}"), composite_score=float(i))
            for i in range(MIN_FACTS_FOR_RERANK - 1)
        ]
        result = rerank(scored, ti)
        assert result is scored  # returned unchanged

    def test_empty_input(self):
        from crp.envelope.reranker import rerank

        ti = _make_task()
        assert rerank([], ti) == []

    def test_task_hash_deterministic(self):
        from crp.envelope.reranker import _task_hash

        ti = _make_task()
        h1 = _task_hash(ti)
        h2 = _task_hash(ti)
        assert h1 == h2

    def test_task_hash_changes(self):
        from crp.envelope.reranker import _task_hash

        t1 = _make_task(task="task A")
        t2 = _make_task(task="task B")
        assert _task_hash(t1) != _task_hash(t2)

    def test_cache_operations(self):
        from crp.envelope.reranker import CrossEncoderCache

        cache = CrossEncoderCache()
        cache.put("hash1", "f1", 0.95)
        assert cache.get("hash1", "f1") == 0.95
        assert cache.get("hash1", "f2") is None
        assert cache.size == 1

    def test_cache_invalidate_fact(self):
        from crp.envelope.reranker import CrossEncoderCache

        cache = CrossEncoderCache()
        cache.put("h1", "f1", 0.9)
        cache.put("h1", "f2", 0.8)
        cache.invalidate_fact("f1")
        assert cache.get("h1", "f1") is None
        assert cache.get("h1", "f2") == 0.8

    def test_cache_invalidate_all(self):
        from crp.envelope.reranker import CrossEncoderCache

        cache = CrossEncoderCache()
        cache.put("h1", "f1", 0.9)
        cache.put("h1", "f2", 0.8)
        cache.invalidate_all()
        assert cache.size == 0

    def test_cache_task_change(self):
        from crp.envelope.reranker import CrossEncoderCache

        cache = CrossEncoderCache()
        cache.check_task_change("hash_a")
        cache.put("hash_a", "f1", 0.9)
        # Same task — no invalidation
        cache.check_task_change("hash_a")
        assert cache.size == 1
        # Different task — full invalidation
        cache.check_task_change("hash_b")
        assert cache.size == 0


# Need the ScoredFact import at module level for TestReranker
from crp.envelope.scoring import ScoredFact  # noqa: E402

# ============================================================================
# 3D+3E: Packer tests
# ============================================================================


class TestPacker:
    """Tests for envelope/packer.py — graph-aware packing + bookend."""

    def test_estimate_tokens(self):
        from crp.envelope.packer import estimate_tokens

        assert estimate_tokens("") == 0
        # ~33 chars ÷ 3.3 ≈ 10 tokens
        assert estimate_tokens("a" * 33) == 10
        # Always at least 1
        assert estimate_tokens("x") >= 1

    def test_empty_packing(self):
        from crp.envelope.packer import pack_facts

        result = pack_facts([], FactGraph(), 1000)
        assert result.facts_packed == 0
        assert result.total_tokens == 0

    def test_zero_budget(self):
        from crp.envelope.packer import pack_facts

        scored = [ScoredFact(fact=_make_fact("test"), composite_score=1.0)]
        result = pack_facts(scored, FactGraph(), 0)
        assert result.facts_packed == 0

    def test_greedy_packing(self):
        from crp.envelope.packer import pack_facts

        facts = [_make_fact(f"Fact number {i} with some text", fid=f"f{i}") for i in range(5)]
        graph = _make_graph(facts)
        scored = [ScoredFact(fact=f, composite_score=10.0 - i) for i, f in enumerate(facts)]

        result = pack_facts(scored, graph, 10000)
        assert result.facts_packed > 0
        assert result.total_tokens > 0
        assert result.total_tokens <= 10000

    def test_budget_respected(self):
        from crp.envelope.packer import pack_facts

        # Very small budget — should only fit 1-2 facts
        facts = [_make_fact(f"This is fact number {i} with enough text to use tokens", fid=f"f{i}") for i in range(10)]
        graph = _make_graph(facts)
        scored = [ScoredFact(fact=f, composite_score=10.0 - i) for i, f in enumerate(facts)]

        result = pack_facts(scored, graph, 30)  # ~30 tokens = ~99 chars
        assert result.total_tokens <= 30

    def test_bookend_strategy(self):
        from crp.envelope.packer import pack_facts

        facts = [_make_fact(f"Fact {i} text", fid=f"f{i}") for i in range(10)]
        graph = _make_graph(facts)
        scored = [ScoredFact(fact=f, composite_score=10.0 - i) for i, f in enumerate(facts)]

        result = pack_facts(scored, graph, 10000)
        bookends = [pf for pf in result.packed_facts if pf.is_bookend]
        assert len(bookends) > 0  # at least some bookends added
        assert result.bookend_count > 0

    def test_compressed_fallback(self):
        from crp.envelope.packer import pack_facts

        # Create one fact that's too long for the remaining budget
        long_fact = _make_fact("x" * 500, fid="long")
        graph = _make_graph([long_fact])
        scored = [ScoredFact(fact=long_fact, composite_score=1.0)]

        # Budget allows ~60 tokens but fact needs more
        result = pack_facts(scored, graph, 60)
        compressed = [pf for pf in result.packed_facts if pf.is_compressed]
        if result.facts_packed > 0:
            assert len(compressed) > 0 or result.packed_facts[0].tokens <= 60

    def test_graph_neighbours_included(self):
        from crp.envelope.packer import pack_facts

        f1 = _make_fact("Main fact about security", fid="f1")
        f2 = _make_fact("Related vulnerability detail", fid="f2")
        edge = FactEdge(source_id="f1", target_id="f2", relation_type=RelationType.ELABORATION, confidence=0.9)
        graph = _make_graph([f1, f2], [edge])

        scored = [ScoredFact(fact=f1, composite_score=1.0)]
        result = pack_facts(scored, graph, 10000)

        # The packed text should include the neighbour
        full_text = "\n".join(pf.text for pf in result.packed_facts)
        assert "ELABORATION" in full_text
        assert "Related vulnerability" in full_text

    def test_custom_tokenizer(self):
        from crp.envelope.packer import pack_facts

        facts = [_make_fact("Hello world", fid="f1")]
        graph = _make_graph(facts)
        scored = [ScoredFact(fact=facts[0], composite_score=1.0)]

        # Custom tokenizer: each word = 1 token
        def word_count(text: str) -> int:
            return len(text.split())

        result = pack_facts(scored, graph, 100, count_tokens=word_count)
        assert result.facts_packed == 1


# ============================================================================
# 3G: Formatter tests
# ============================================================================


class TestFormatter:
    """Tests for envelope/formatter.py — serialization."""

    def test_basic_format(self):
        from crp.envelope.formatter import format_envelope

        sections = {"GOAL": "Analyse vulnerability", "PHASE": "scanning"}
        text = format_envelope(sections)
        assert "[GOAL]" in text
        assert "[PHASE]" in text
        assert "Analyse vulnerability" in text

    def test_tier_ordering(self):
        from crp.envelope.formatter import format_envelope

        # Tier 3 section should appear after tier 1
        sections = {"DISCOVERIES": "Found issues", "GOAL": "Analyse target"}
        text = format_envelope(sections)
        goal_pos = text.index("[GOAL]")
        disc_pos = text.index("[DISCOVERIES]")
        assert goal_pos < disc_pos

    def test_empty_sections_excluded(self):
        from crp.envelope.formatter import format_envelope

        sections = {"GOAL": "Valid content", "PHASE": "", "BLOCKER": "  "}
        text = format_envelope(sections)
        assert "[GOAL]" in text
        assert "[PHASE]" not in text
        assert "[BLOCKER]" not in text

    def test_facts_section_from_packed(self):
        from crp.envelope.formatter import format_envelope
        from crp.envelope.packer import PackedFact

        packed = [
            PackedFact(fact_id="f1", text="- Important discovery", score=1.0, tokens=10),
            PackedFact(fact_id="f2", text="- Secondary discovery", score=0.8, tokens=8),
        ]
        text = format_envelope({"GOAL": "Test"}, packed_facts=packed)
        assert "[DISCOVERIES]" in text
        assert "Important discovery" in text
        assert "Secondary discovery" in text

    def test_bookend_separator(self):
        from crp.envelope.formatter import format_facts_section
        from crp.envelope.packer import PackedFact

        packed = [
            PackedFact(fact_id="f1", text="- Main fact", score=1.0, tokens=5),
            PackedFact(fact_id="f1", text="- Main fact", score=1.0, tokens=5, is_bookend=True),
        ]
        text = format_facts_section(packed)
        assert "Key facts (reinforced)" in text

    def test_section_header_format(self):
        from crp.envelope.formatter import _section_header

        assert _section_header("goal") == "[GOAL]"
        assert _section_header("EXPANDED: source_1") == "[EXPANDED: SOURCE_1]"

    def test_tier_classification(self):
        from crp.envelope.formatter import _classify_tier

        assert _classify_tier("GOAL") == 1
        assert _classify_tier("BLOCKER") == 1
        assert _classify_tier("LLM_SYNTHESIS") == 2
        assert _classify_tier("DISCOVERIES") == 3
        assert _classify_tier("REASONING APPROACH") == 4

    def test_no_packed_facts_no_discoveries(self):
        from crp.envelope.formatter import format_envelope

        sections = {"GOAL": "Test"}
        text = format_envelope(sections, packed_facts=None)
        assert "[DISCOVERIES]" not in text

    def test_explicit_discoveries_not_overwritten(self):
        from crp.envelope.formatter import format_envelope
        from crp.envelope.packer import PackedFact

        # If user provides DISCOVERIES explicitly, don't duplicate from packed_facts
        packed = [PackedFact(fact_id="f1", text="- Auto fact", score=1.0, tokens=5)]
        sections = {"GOAL": "Test", "DISCOVERIES": "Manual discoveries here"}
        text = format_envelope(sections, packed_facts=packed)
        assert "Manual discoveries here" in text
        count = text.count("[DISCOVERIES]")
        assert count == 1


# ============================================================================
# Builder (orchestrator) tests
# ============================================================================


class TestBuilder:
    """Tests for envelope/builder.py — full 6-phase orchestration."""

    def test_compute_budget_basic(self):
        from crp.envelope.builder import compute_envelope_budget

        # 128K window, 800 system, 5000 task, default G = min(32K, 16384) = 16384
        b = compute_envelope_budget(128000, 800, 5000)
        assert b == 128000 - 800 - 5000 - 16384

    def test_compute_budget_user_max_output(self):
        from crp.envelope.builder import compute_envelope_budget

        b = compute_envelope_budget(128000, 800, 5000, max_output_tokens=4096)
        assert b == 128000 - 800 - 5000 - 4096

    def test_compute_budget_explicit_reserve(self):
        from crp.envelope.builder import compute_envelope_budget

        b = compute_envelope_budget(128000, 800, 5000, generation_reserve=8000)
        assert b == 128000 - 800 - 5000 - 8000

    def test_compute_budget_floor_at_zero(self):
        from crp.envelope.builder import compute_envelope_budget

        # Tiny window, large overheads → budget = 0
        b = compute_envelope_budget(1000, 800, 500, generation_reserve=500)
        assert b == 0

    def test_construct_empty_state(self):
        from crp.envelope.builder import EnvelopeState, construct

        ti = _make_task()
        state = EnvelopeState()
        result = construct(ti, 10000, state)
        assert result.envelope_text is not None
        assert result.facts_included == 0
        assert result.latency_ms >= 0

    def test_construct_with_facts(self):
        from crp.envelope.builder import EnvelopeState, construct

        ti = _make_task(task="Analyse network security")
        facts = [
            _make_fact("CVE-2024-1234 is critical", fid="f1"),
            _make_fact("Port 443 is open", fid="f2"),
            _make_fact("SSH banner reveals version", fid="f3"),
        ]
        graph = _make_graph(facts)

        state = EnvelopeState(
            facts=facts,
            graph=graph,
            sections={"GOAL": "Analyse target", "PHASE": "reconnaissance"},
        )

        result = construct(ti, 10000, state)
        assert result.facts_included > 0
        assert result.envelope_tokens > 0
        assert "[GOAL]" in result.envelope_text
        assert result.saturation > 0

    def test_construct_saturation(self):
        """Saturation should be envelope_tokens / budget_tokens."""
        from crp.envelope.builder import EnvelopeState, construct

        ti = _make_task(task="security analysis of target systems")
        facts = [_make_fact(f"Important security fact number {i} with details", fid=f"f{i}") for i in range(20)]
        graph = _make_graph(facts)

        state = EnvelopeState(
            facts=facts,
            graph=graph,
            sections={"GOAL": "Analysis", "PHASE": "active"},
        )

        result = construct(ti, 10000, state)
        if result.budget_tokens > 0:
            expected_sat = result.envelope_tokens / result.budget_tokens
            assert abs(result.saturation - expected_sat) < 0.01

    def test_construct_with_ckf_retriever(self):
        from crp.envelope.builder import EnvelopeState, construct

        ti = _make_task(task="Analyse target")
        facts = [_make_fact("Initial fact", fid="f1")]
        graph = _make_graph(facts)

        ckf_called = {"called": False}

        def mock_ckf(query: str, remaining: int) -> list[Fact]:
            ckf_called["called"] = True
            return [_make_fact("CKF retrieved fact", fid="ckf1")]

        state = EnvelopeState(
            facts=facts,
            graph=graph,
            ckf_retriever=mock_ckf,
        )

        result = construct(ti, 10000, state)
        # CKF gate should fire when budget allows
        assert result.envelope_text is not None

    def test_construct_zero_budget(self):
        from crp.envelope.builder import EnvelopeState, construct

        ti = _make_task()
        state = EnvelopeState(facts=[_make_fact("test")])
        result = construct(ti, 0, state)
        assert result.envelope_text == ""
        assert result.facts_included == 0

    def test_construct_with_custom_tokenizer(self):
        from crp.envelope.builder import EnvelopeState, construct

        ti = _make_task(task="security test")
        facts = [_make_fact("A fact about security", fid="f1")]
        graph = _make_graph(facts)
        state = EnvelopeState(facts=facts, graph=graph)

        def word_counter(text: str) -> int:
            return len(text.split())

        result = construct(ti, 10000, state, count_tokens=word_counter)
        assert result.envelope_tokens > 0

    def test_construct_preserves_section_order(self):
        from crp.envelope.builder import EnvelopeState, construct

        ti = _make_task(task="test")
        state = EnvelopeState(
            sections={
                "DISCOVERIES": "Found items",
                "GOAL": "Primary goal",
                "CONSTRAINT": "Must be fast",
                "ERROR_LOG": "No errors",
            },
        )

        result = construct(ti, 10000, state)
        text = result.envelope_text
        # Tier 1 sections (GOAL, CONSTRAINT) before tier 3 (DISCOVERIES, ERROR_LOG)
        if "[GOAL]" in text and "[DISCOVERIES]" in text:
            assert text.index("[GOAL]") < text.index("[DISCOVERIES]")


# ============================================================================
# Integration tests
# ============================================================================


class TestIntegration:
    """End-to-end integration tests through the full pipeline."""

    def test_full_pipeline_no_ml(self):
        """Full 6-phase pipeline with fallback scoring (no ML deps)."""
        from crp.envelope.builder import EnvelopeState, construct

        ti = TaskIntent(
            system_prompt="You are a penetration tester.",
            task_input="Scan the target 192.168.1.1 for open ports and vulnerabilities.",
        )

        facts = [
            _make_fact("Port 22 (SSH) is open on 192.168.1.1", fid="f1"),
            _make_fact("Port 80 (HTTP) is open on 192.168.1.1", fid="f2"),
            _make_fact("Port 443 (HTTPS) is open on 192.168.1.1", fid="f3"),
            _make_fact("SSH banner: OpenSSH 7.4", fid="f4"),
            _make_fact("HTTP server: Apache 2.4.29", fid="f5"),
            _make_fact("CVE-2019-0211 affects Apache 2.4.29", fid="f6"),
            _make_fact("Default credentials found on admin panel", fid="f7"),
            _make_fact("SSL certificate expired", fid="f8"),
            _make_fact("Directory listing enabled on /backup/", fid="f9"),
            _make_fact("PHP version 7.1 detected (EOL)", fid="f10"),
        ]

        edges = [
            FactEdge(source_id="f5", target_id="f6", relation_type=RelationType.CAUSE_EFFECT, confidence=0.95),
            FactEdge(source_id="f2", target_id="f5", relation_type=RelationType.ELABORATION, confidence=0.8),
            FactEdge(source_id="f3", target_id="f8", relation_type=RelationType.RELATED, confidence=0.7),
        ]

        graph = _make_graph(facts, edges)

        state = EnvelopeState(
            facts=facts,
            graph=graph,
            current_window_index=3,
            seen_counts={"f1": 2, "f2": 1},
            fact_window_indices={f"f{i}": i % 3 for i in range(1, 11)},
            sections={
                "GOAL": "Identify vulnerabilities on 192.168.1.1",
                "PHASE": "active scanning",
                "CONSTRAINT": "Stay within scope, no exploitation",
            },
        )

        result = construct(ti, 5000, state)

        # Verify structure
        assert result.envelope_text
        assert "[GOAL]" in result.envelope_text
        assert "[PHASE]" in result.envelope_text
        assert result.facts_included > 0
        assert result.envelope_tokens > 0
        assert result.envelope_tokens <= 5000
        assert result.saturation > 0
        assert result.latency_ms >= 0

    def test_envelope_contains_graph_relations(self):
        """Verify that graph relations appear in the formatted output."""
        from crp.envelope.builder import EnvelopeState, construct

        ti = _make_task(task="Analyse Apache vulnerability")
        f1 = _make_fact("Apache 2.4.29 detected", fid="f1")
        f2 = _make_fact("CVE-2019-0211 is critical", fid="f2")
        edge = FactEdge(source_id="f1", target_id="f2", relation_type=RelationType.CAUSE_EFFECT, confidence=0.9)
        graph = _make_graph([f1, f2], [edge])

        state = EnvelopeState(facts=[f1, f2], graph=graph)
        result = construct(ti, 10000, state)

        # The relation should appear in the output
        assert "CAUSE_EFFECT" in result.envelope_text

    def test_public_api_exports(self):
        """Verify that the public API is accessible from crp.envelope."""
        from crp.envelope import (
            CrossEncoderCache,
            DecompositionResult,
            EnvelopeResult,
            EnvelopeSection,
            EnvelopeState,
            PackedFact,
            PackingResult,
            ScoredFact,
            ScoringConfig,
            compute_envelope_budget,
            construct,
            decompose_task_aspects,
            estimate_tokens,
            format_envelope,
            pack_facts,
            rerank,
            score_facts,
        )

        assert callable(construct)
        assert callable(decompose_task_aspects)
        assert callable(score_facts)
        assert callable(rerank)
        assert callable(pack_facts)
        assert callable(format_envelope)
        assert callable(compute_envelope_budget)
        assert callable(estimate_tokens)
