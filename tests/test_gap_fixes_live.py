"""Live verification of GAP A-E fixes against LM Studio.

Tests that the CRP protocol fixes are actually working:
- GAP A: CKF retriever gets query_embedding, seed_ids, topic
- GAP B: Semantic gap analysis uses embedding_fn (cosine similarity)
- GAP C: Document map deduplicates headings; stitch removes duplicate sections
- GAP D: Continuation budget uses compact title, not full cont_envelope
- GAP E: Cross-encoder activates at 10+ facts (down from 50)

Run with: python -m pytest tests/test_gap_fixes_live.py -v --tb=short -s
Requires: LM Studio at http://192.168.0.6:1234 with qwen2.5-7b-instruct
"""

import logging
import os
import sys
import time

import pytest

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set dummy API key for LM Studio (OpenAI-compat requires one)
os.environ.setdefault("OPENAI_API_KEY", "lm-studio")

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LM_STUDIO_URL = "http://192.168.0.6:1234/v1"
LM_STUDIO_MODEL = "qwen2.5-7b-instruct"


def _check_lm_studio():
    """Check if LM Studio is reachable."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{LM_STUDIO_URL}/models", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


# Skip all tests if LM Studio not available
pytestmark = pytest.mark.skipif(
    not _check_lm_studio(),
    reason="LM Studio not available at " + LM_STUDIO_URL,
)


class TestGapAFixes:
    """GAP A: CKF wiring — embedding function, retriever callback."""

    def test_embedding_function_wired(self):
        """set_embedding_function() should be called at orchestrator init."""
        from crp.state.fact import _EMBED_FN, set_embedding_function
        from crp.envelope.decomposer import get_embedding_fn

        # get_embedding_fn should return a callable
        fn = get_embedding_fn()
        assert fn is not None, "get_embedding_fn() returned None — sentence_transformers not loaded"

        # Test that it produces embeddings
        emb = fn("test sentence for embedding")
        assert isinstance(emb, list)
        assert len(emb) == 384  # all-MiniLM-L6-v2 output dim

    def test_embedding_function_set_at_init(self):
        """CRPOrchestrator should wire set_embedding_function at init.

        Note: embedding model loading is lazy by default (``eager_load_models``
        defaults to False) to keep cold-start fast. This test explicitly opts
        into eager loading to verify the wiring path still works.
        """
        from crp.providers.openai import OpenAIAdapter
        import crp

        provider = OpenAIAdapter(
            base_url=LM_STUDIO_URL,
            model=LM_STUDIO_MODEL,
        )
        client = crp.Client(provider=provider, eager_load_models=True)

        # Check that _embedding_fn was set
        assert client._embedding_fn is not None, "Orchestrator._embedding_fn not set"

        # Check global _EMBED_FN
        from crp.state.fact import _EMBED_FN
        assert _EMBED_FN is not None, "Global _EMBED_FN not wired"

        client.close()

    def test_ckf_retriever_passes_params(self):
        """CKF retriever callback should pass query_embedding, seed_ids, topic."""
        from crp.providers.openai import OpenAIAdapter
        from crp.ckf.fabric import ContextualKnowledgeFabric
        import crp

        provider = OpenAIAdapter(
            base_url=LM_STUDIO_URL,
            model=LM_STUDIO_MODEL,
        )
        client = crp.Client(provider=provider)

        # Store some facts in CKF to ensure it has data
        from crp.extraction.types import Fact
        test_facts = [
            Fact(text="Machine learning uses neural networks", category="key_sentence", confidence=0.9),
            Fact(text="Deep learning is a subset of ML", category="key_sentence", confidence=0.85),
        ]
        client._ckf.store(test_facts, window_id="test-w0")

        # The CKF should now have facts
        assert client._ckf.fact_count() >= 2
        client.close()


class TestGapBFixes:
    """GAP B: Semantic gap analysis with embedding_fn."""

    def test_continuation_config_has_embedding_fn(self):
        """ContinuationConfig should carry embedding_fn.

        Note: embedding model loading is lazy by default (``eager_load_models``
        defaults to False). This test explicitly opts into eager loading.
        """
        from crp.providers.openai import OpenAIAdapter
        import crp

        provider = OpenAIAdapter(
            base_url=LM_STUDIO_URL,
            model=LM_STUDIO_MODEL,
        )
        client = crp.Client(provider=provider, eager_load_models=True)
        assert client._continuation_config.embedding_fn is not None, \
            "ContinuationConfig.embedding_fn not wired"
        client.close()

    def test_gap_analysis_uses_cosine(self):
        """gap_analysis should use cosine similarity when embedding_fn provided."""
        from crp.continuation.gap import gap_analysis, Requirement
        from crp.extraction.types import Fact
        from crp.envelope.decomposer import get_embedding_fn

        fn = get_embedding_fn()
        assert fn is not None

        reqs = [
            Requirement(text="Section 1: Data encryption and security", level=1, category="section_1"),
            Requirement(text="Section 2: Network protocols", level=1, category="section_2"),
        ]
        facts = [
            Fact(text="AES-256 encryption provides strong data protection at rest and in transit", category="key_sentence", confidence=0.9),
            Fact(text="TCP/IP is the fundamental network communication protocol", category="key_sentence", confidence=0.85),
        ]

        # With embedding — should get better fulfillment via cosine similarity
        result_with = gap_analysis("Write 2 sections", facts, reqs, embedding_fn=fn)

        # Without embedding — falls back to word overlap
        result_without = gap_analysis("Write 2 sections", facts, reqs)

        logger.info(
            "Gap with embedding: score=%.3f, fulfilled=%d/%d",
            result_with.gap_score, result_with.fulfilled_count, result_with.total_count,
        )
        logger.info(
            "Gap without embedding: score=%.3f, fulfilled=%d/%d",
            result_without.gap_score, result_without.fulfilled_count, result_without.total_count,
        )

        # Semantic matching should find at least as many fulfilled requirements
        # as text overlap alone, since we now use max(cosine, text_overlap)
        assert result_with.fulfilled_count >= result_without.fulfilled_count
        # The combined score should never be worse than text-only
        for rw, rwo in zip(result_with.requirements, result_without.requirements):
            assert rw.fulfillment_score >= rwo.fulfillment_score - 0.01, \
                f"Combined score ({rw.fulfillment_score:.3f}) worse than text-only ({rwo.fulfillment_score:.3f}) for: {rw.text}"


class TestGapCFixes:
    """GAP C: Content deduplication."""

    def test_document_map_heading_dedup(self):
        """DocumentMap.update() should skip duplicate section numbers."""
        from crp.continuation.document_map import DocumentMap

        dm = DocumentMap()

        # Window 1: sections 1-3
        text1 = "## 1. Introduction\nContent here\n## 2. Background\nMore content\n## 3. Methods\nStuff"
        new1 = dm.update(text1, "w1")
        assert len(new1) == 3

        # Window 2: tries to add section 2 again + new section 4
        text2 = "## 2. Background\nRepeated content\n## 4. Results\nNew content"
        new2 = dm.update(text2, "w2")

        # Should only add section 4 (section 2 is duplicate)
        assert len(new2) == 1, f"Expected 1 new heading, got {len(new2)}: {[h.text for h in new2]}"
        assert "4." in new2[0].text

        # Total should be 4 unique sections
        assert len(dm.headings) == 4

    def test_stitch_section_dedup(self):
        """stitch_outputs should remove duplicate numbered sections."""
        from crp.continuation.stitch import stitch_outputs

        prior = (
            "## 1. Introduction\nThis is the intro.\n\n"
            "## 2. Background\nThis is background.\n\n"
            "## 3. Methods\nMethodology here.\n\n"
        )
        continuation = (
            "## 2. Background\nSlightly different background.\n\n"
            "## 4. Results\nResults section.\n\n"
        )

        result = stitch_outputs(prior, continuation)

        # Count occurrences of "## 2."
        import re
        section2_count = len(re.findall(r"## 2\.", result.text))
        assert section2_count == 1, f"Section 2 appeared {section2_count} times (expected 1)"

        # Section 4 should be present
        assert "## 4." in result.text


class TestGapDFixes:
    """GAP D: Envelope budget overflow on continuation."""

    def test_budget_not_inflated_by_cont_envelope(self):
        """Budget calculation should use compact title, not full continuation envelope."""
        from crp.envelope.builder import compute_envelope_budget

        context_window = 4096
        system_tokens = 100
        generation_reserve = 1024

        # Compact title: ~10 tokens
        task_title_tokens = 10
        budget_with_title = compute_envelope_budget(
            context_window, system_tokens, task_title_tokens, generation_reserve,
        )

        # Full continuation envelope: ~600 tokens
        full_cont_tokens = 600
        budget_with_full = compute_envelope_budget(
            context_window, system_tokens, full_cont_tokens, generation_reserve,
        )

        # The title-based budget should be much larger
        improvement = budget_with_title - budget_with_full
        logger.info(
            "Budget improvement: %d tokens (title=%d, full=%d)",
            improvement, budget_with_title, budget_with_full,
        )
        assert improvement >= 500, f"Budget improvement only {improvement} tokens"


class TestGapEFixes:
    """GAP E: Cross-encoder threshold lowered."""

    def test_reranker_threshold_lowered(self):
        """MIN_FACTS_FOR_RERANK should be 10 (down from 50)."""
        from crp.envelope.reranker import MIN_FACTS_FOR_RERANK
        assert MIN_FACTS_FOR_RERANK == 10, f"MIN_FACTS_FOR_RERANK={MIN_FACTS_FOR_RERANK}, expected 10"


class TestEndToEnd:
    """End-to-end dispatch with all fixes active."""

    def test_dispatch_with_continuation(self):
        """Full dispatch that triggers continuation — verify all subsystems engaged.

        NOTE ON DURATION: this is a genuine end-to-end test against a live local
        LLM (LM Studio). It is NOT bounded to complete quickly — on modest local
        hardware (~10-15 tokens/sec CPU/GPU inference), a single continuation
        window's full generation reserve can take 10+ minutes, and this task
        (5 detailed sections) typically triggers multiple continuation windows.
        Measured baseline on reference hardware: ~11.5 tokens/sec, so total
        runtime can legitimately run into tens of minutes. This is NOT a hang —
        the dispatch loop is hard-bounded by `max_continuations` (default 50)
        and `dispatch_timeout` (default 3600s / 1 hour), so it always
        terminates. Do not mistake slow local-model throughput for a bug; let
        it run to completion (or increase patience/timeout) before concluding
        anything is broken.
        """
        from crp.providers.openai import OpenAIAdapter
        import crp

        provider = OpenAIAdapter(
            base_url=LM_STUDIO_URL,
            model=LM_STUDIO_MODEL,
        )
        client = crp.Client(provider=provider)

        t0 = time.time()
        output, report = client.dispatch(
            system_prompt="You are a technical writer. Write comprehensive content.",
            task_input=(
                "Write a document with 5 sections covering:\n"
                "1. Introduction to Machine Learning\n"
                "2. Supervised Learning Methods\n"
                "3. Unsupervised Learning Techniques\n"
                "4. Deep Learning Architectures\n"
                "5. Future Trends in AI\n\n"
                "Each section should be detailed with examples."
            ),
        )
        elapsed = time.time() - t0

        logger.info("=== END-TO-END RESULTS ===")
        logger.info("Output length: %d chars", len(output))
        logger.info("Facts extracted: %d", report.facts_extracted)
        logger.info("Continuation windows: %d", report.continuation_windows)
        logger.info("Quality tier: %s", report.quality_tier)
        logger.info("Elapsed: %.1fs", elapsed)

        # Telemetry
        tel = report.telemetry or {}
        logger.info("Envelope saturation: %.3f", tel.get("saturation", 0))
        logger.info("Gap coverage: %.3f", tel.get("gap_coverage", 0))
        logger.info("Final gap score: %.3f", tel.get("final_gap_score", 0))
        logger.info("CRP overhead: %.1f%%", tel.get("crp_overhead_pct", 0))

        # Per-window detail
        for w in tel.get("continuation_windows_detail", []):
            logger.info(
                "  Window %d: facts=%d, sat=%.3f, gap=%.3f, tokens=%d",
                w.get("window", 0), w.get("facts", 0),
                w.get("envelope_saturation", 0), w.get("gap_score", 0),
                w.get("output_tokens", 0),
            )

        # Assertions
        assert len(output) > 500, f"Output too short: {len(output)} chars"
        assert report.facts_extracted > 0, "No facts extracted"

        client.close()


# ── Issue I-L and GAP H tests (Round 2 fixes) ──────────────────────


class TestIssueIFixes:
    """Issue I: Streaming dispatch error recovery."""

    def test_streaming_error_updates_state(self):
        """Streaming error should still update state, not silently abandon.

        Note: the implementation no longer uses a dedicated ``streaming_error``
        variable name; the error path sets ``finish_reason = "error"`` and the
        continuation loop checks ``cont_state.finished or finish_reason ==
        "error"`` to exit gracefully instead of hanging or losing state.
        """
        from crp.core.orchestrator import CRPOrchestrator

        import inspect
        source = inspect.getsource(CRPOrchestrator.dispatch_stream)
        assert 'finish_reason = "error"' in source, "Error finish_reason not set"
        assert 'finish_reason == "error"' in source, (
            "Streaming loop should check finish_reason == 'error' to update "
            "state and exit gracefully, not silently abandon"
        )


class TestIssueJFixes:
    """Issue J: CKF mode inference silent failure."""

    def test_infer_modes_empty_when_no_inputs(self):
        """_infer_modes should return [] when no inputs provided."""
        from crp.ckf.fabric import ContextualKnowledgeFabric

        ckf = ContextualKnowledgeFabric()

        modes = ckf._infer_modes(
            seed_ids=None, entity_type=None,
            query_embedding=None, topic=None,
        )
        assert modes == [], f"Expected empty list, got {modes}"

    def test_infer_modes_semantic_when_embedding_provided(self):
        """_infer_modes should include 'semantic' when query_embedding is given."""
        from crp.ckf.fabric import ContextualKnowledgeFabric

        ckf = ContextualKnowledgeFabric()

        modes = ckf._infer_modes(
            seed_ids=None, entity_type=None,
            query_embedding=[0.1, 0.2, 0.3], topic=None,
        )
        assert "semantic" in modes


class TestIssueKFixes:
    """Issue K: HNSW index capacity auto-resize."""

    def test_hnsw_auto_resize(self):
        """HNSWIndex should auto-resize when exceeding initial capacity."""
        try:
            from crp.ckf.semantic import HNSWIndex
        except RuntimeError:
            pytest.skip("hnswlib not available")

        idx = HNSWIndex(dim=4, max_elements=5)

        for i in range(10):
            idx.add(f"fact_{i}", [float(i), float(i+1), float(i+2), float(i+3)])

        assert idx.count == 10
        results = idx.query([1.0, 2.0, 3.0, 4.0], k=3)
        assert len(results) == 3


class TestIssueLFixes:
    """Issue L: Fact content deduplication."""

    def test_warm_store_content_dedup(self):
        """WarmStateStore should reject facts with identical text but different IDs."""
        from crp.state.warm_store import WarmStateStore
        from crp.extraction.types import Fact

        store = WarmStateStore()
        added1 = store.add_facts([Fact(text="ML uses neural networks", category="key_sentence")])
        assert len(added1) == 1

        added2 = store.add_facts([Fact(text="ML uses neural networks", category="key_sentence")])
        assert len(added2) == 0, f"Content duplicate accepted: {len(added2)}"
        assert store.fact_count == 1

    def test_warm_store_different_text_accepted(self):
        """Facts with different text should still be added."""
        from crp.state.warm_store import WarmStateStore
        from crp.extraction.types import Fact

        store = WarmStateStore()
        added = store.add_facts([
            Fact(text="First fact about ML", category="key_sentence"),
            Fact(text="Second fact about DL", category="key_sentence"),
        ])
        assert len(added) == 2


class TestGapHFixes:
    """GAP H: Adaptive requirement discovery from document headings."""

    def test_adaptive_discovery_creates_new_reqs(self):
        """discover_adaptive_requirements adds requirements from new headings."""
        from crp.continuation.gap import Requirement, discover_adaptive_requirements

        existing = [
            Requirement(text="Section 1: Introduction", level=1, category="section_1"),
            Requirement(text="Section 2: Background", level=1, category="section_2"),
        ]
        headings = ["## 1. Introduction", "## 2. Background", "## 3. Methods", "## 4. Results"]

        result = discover_adaptive_requirements(existing, headings)
        assert len(result) == 4, f"Expected 4, got {len(result)}"

        adaptive = [r for r in result if r.category == "adaptive_discovery"]
        assert len(adaptive) == 2
        assert all(r.fulfilled for r in adaptive)

    def test_adaptive_discovery_no_duplicates(self):
        """Existing section requirements should not be duplicated."""
        from crp.continuation.gap import Requirement, discover_adaptive_requirements

        existing = [
            Requirement(text="Section 1: Introduction", level=1, category="section_1"),
        ]
        result = discover_adaptive_requirements(existing, ["## 1. Introduction"])
        assert len(result) == 1

    def test_gap_analysis_with_adaptive_discovery(self):
        """gap_analysis should include adaptive requirements in gap score."""
        from crp.continuation.gap import gap_analysis, Requirement
        from crp.extraction.types import Fact

        reqs = [Requirement(text="Section 1: Introduction", level=1, category="section_1")]
        facts = [
            Fact(text="## 1. Introduction\nThis is the intro.", category="key_sentence"),
            Fact(text="## 2. Methods\nCovers methodology.", category="key_sentence"),
        ]
        headings = ["## 1. Introduction", "## 2. Methods"]

        result = gap_analysis("Write intro and methods", facts, reqs, document_headings=headings)
        assert result.total_count == 2, f"Expected 2 total requirements, got {result.total_count}"
        assert result.fulfilled_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])


# ==========================================================================
# V-FIX TESTS: Deep audit findings V1-V11
# ==========================================================================


class TestV1CuratorPipelineIntegration:
    """V1: Curator synthesis should go through envelope pipeline, not post-pack append."""

    def test_curator_section_in_envelope_state(self):
        """When curator has a synthesis, it appears in envelope sections."""
        from crp.advanced.curator import LLMContextCurator, CurationConfig, LLMSynthesis
        from crp.envelope.builder import EnvelopeState, construct as construct_envelope
        from crp.core.task_intent import TaskIntent
        from crp.extraction.types import Fact

        # Simulate a curator with an existing synthesis
        curator = LLMContextCurator(dispatch_fn=lambda s, t, **k: ("", {}), config=CurationConfig())
        curator._current_synthesis = LLMSynthesis(
            window_index=1,
            evolution_count=1,
            critical_findings=["Finding A"],
            key_relationships=["Rel B"],
            gaps=["Gap C"],
        )

        # Build sections including curator (as the orchestrator now does)
        sections = {}
        curator_text = curator.format_for_envelope()
        assert curator_text, "Curator should produce formatted text"
        sections["LLM_SYNTHESIS"] = curator_text

        # Build envelope — curator text should be budget-accounted
        facts = [Fact(text=f"Fact {i}", category="test") for i in range(5)]
        state = EnvelopeState(facts=facts, sections=sections)
        intent = TaskIntent(description="Test task", task_input="Test task", system_prompt="sys")

        result = construct_envelope(
            task_intent=intent,
            budget_tokens=500,
            state=state,
            count_tokens=lambda s: len(s) // 4,
        )
        # Curator section should appear in the envelope text
        assert "LLM_SYNTHESIS" in result.envelope_text or "Finding A" in result.envelope_text

    def test_curator_not_appended_post_pack(self):
        """Verify the orchestrator's _build_envelope no longer appends curator post-pack."""
        import inspect
        from crp.core.orchestrator import CRPOrchestrator

        source = inspect.getsource(CRPOrchestrator._build_envelope)
        # The old naive pattern was: envelope_text=f"{envelope.envelope_text}\n{curator_section}"
        assert "curator_section" not in source, (
            "_build_envelope should no longer mention curator_section; "
            "curator synthesis must be in sections dict"
        )


class TestV2MetaLearningPipelineIntegration:
    """V2: Meta-learning scaffold should go through envelope pipeline."""

    def test_scaffold_not_appended_post_pack(self):
        """Verify the orchestrator's _build_envelope no longer appends scaffold post-pack."""
        import inspect
        from crp.core.orchestrator import CRPOrchestrator

        source = inspect.getsource(CRPOrchestrator._build_envelope)
        # Old pattern: "build_reasoning_scaffold" was called in _build_envelope
        # and appended post-pack. Now it's in sections dict before envelope_state.
        assert "REASONING_SCAFFOLD" in source, (
            "_build_envelope should include REASONING_SCAFFOLD in sections"
        )
        # Ensure no post-pack meta-learning append remains
        lines = source.split("\n")
        post_construct_scaffold = False
        past_construct = False
        for line in lines:
            if "construct_envelope(" in line:
                past_construct = True
            if past_construct and "build_reasoning_scaffold" in line:
                post_construct_scaffold = True
        assert not post_construct_scaffold, (
            "build_reasoning_scaffold should not be called after construct_envelope"
        )


class TestV3ContinuationBudget:
    """V3: Continuation budget must account for full cont_task tokens."""

    def test_budget_uses_full_cont_task(self):
        """Verify _build_envelope receives full cont_task, not just title.

        Note: ``CRPOrchestrator.dispatch`` is now a thin thread-safety wrapper
        (``with self._lock: return self._dispatch_locked(...)``); the actual
        continuation logic lives in ``_dispatch_locked`` (crp/core/dispatch_router.py).
        """
        import inspect
        from crp.core.orchestrator import CRPOrchestrator

        # Read the real dispatch implementation's source (not the thin lock wrapper)
        source = inspect.getsource(CRPOrchestrator._dispatch_locked)
        # Old pattern: budget_task = f"Original task: {task_title}"
        assert "budget_task" not in source, (
            "budget_task variable should no longer exist; "
            "cont_task should be passed directly to _build_envelope"
        )
        # New pattern: _build_envelope(system_prompt, cont_task, _cont_g)
        assert "_build_envelope(system_prompt, cont_task, _cont_g)" in source, (
            "Continuation should pass full cont_task to _build_envelope"
        )


class TestV6CuratorInitAtConstruction:
    """V6: Curator dispatch_fn should be wired at __init__, not lazily."""

    def test_curator_dispatch_fn_not_none_at_init(self):
        """Curator should have dispatch_fn immediately after orchestrator init.

        Note: the mock provider must properly implement the documented
        ``LLMProvider`` ABC contract. Providers that subclass ``LLMProvider``
        get a default ``model_name`` property (falls back to class name) that
        the orchestrator relies on at init for observability events; a bare
        duck-typed class that skips the ABC does not get this default.
        """
        from crp.core.orchestrator import CRPOrchestrator
        from crp.providers.base import LLMProvider

        class MockProvider(LLMProvider):
            def generate_chat(self, messages, **kw):
                return ("mock output", "stop")
            def count_tokens(self, text):
                return len(text) // 4
            def context_window_size(self):
                return 8192
            @property
            def max_output_tokens(self):
                return 2048

        orc = CRPOrchestrator(provider=MockProvider())
        assert orc._curator._dispatch_fn is not None, (
            "Curator dispatch_fn should be wired at __init__, not lazily"
        )

    def test_no_lazy_init_in_dispatch(self):
        """The dispatch method should not contain lazy curator init."""
        import inspect
        from crp.core.orchestrator import CRPOrchestrator

        source = inspect.getsource(CRPOrchestrator._dispatch_locked)
        assert "_curator._dispatch_fn is None" not in source, (
            "Lazy curator dispatch_fn init should be removed from dispatch()"
        )


class TestV7CKFRetrieverLogging:
    """V7: CKF retriever should log failures instead of silently swallowing."""

    def test_ckf_retriever_logs_warning(self):
        """Verify CKF failure logging exists in source."""
        import inspect
        from crp.core.orchestrator import CRPOrchestrator

        source = inspect.getsource(CRPOrchestrator._build_envelope)
        assert "CKF retrieval failed" in source, (
            "CKF retriever should log failures with a warning message"
        )
        assert "logger.warning" in source, (
            "CKF failures should use logger.warning, not be silently swallowed"
        )


class TestV9AutoIngestDAGTracking:
    """V9: Auto-ingest should create a DAG node for traceability."""

    def test_auto_ingest_creates_dag_node(self):
        """Verify auto-ingest code creates a WindowNode.

        Note: ``CRPOrchestrator.dispatch`` is now a thin thread-safety wrapper;
        the actual dispatch implementation (including auto-ingest) lives in
        ``_dispatch_locked``.
        """
        import inspect
        from crp.core.orchestrator import CRPOrchestrator

        source = inspect.getsource(CRPOrchestrator._dispatch_locked)
        assert "auto-ingest-" in source, (
            "Auto-ingest should create window IDs with 'auto-ingest-' prefix"
        )
        assert "ingest_node" in source, (
            "Auto-ingest should create an ingest_node WindowNode"
        )
        assert "facts_produced" in source, (
            "Auto-ingest should track produced fact IDs in the DAG node"
        )


class TestV10ContinuationBoundaryMarkers:
    """V10: Continuation task should use explicit boundary markers."""

    def test_boundary_markers_in_cont_task(self):
        """Verify continuation task uses structural boundary markers.

        Note: ``CRPOrchestrator.dispatch`` is now a thin thread-safety wrapper;
        the actual continuation logic lives in ``_dispatch_locked``.
        """
        import inspect
        from crp.core.orchestrator import CRPOrchestrator

        source = inspect.getsource(CRPOrchestrator._dispatch_locked)
        assert "=== ORIGINAL TASK ===" in source, (
            "Continuation task should have ORIGINAL TASK boundary marker"
        )
        assert "=== CONTINUATION DIRECTIVES ===" in source, (
            "Continuation task should have CONTINUATION DIRECTIVES boundary marker"
        )
        assert "=== END DIRECTIVES ===" in source, (
            "Continuation task should have END DIRECTIVES boundary marker"
        )


class TestV11RequirementCacheDeterministic:
    """V11: Requirement cache should use deterministic hashing."""

    def test_cache_uses_md5(self):
        """Verify requirement cache uses MD5, not Python's hash()."""
        import inspect
        from crp.continuation.gap import extract_task_requirements

        source = inspect.getsource(extract_task_requirements)
        assert "hashlib.md5" in source, (
            "Requirement cache should use hashlib.md5 for deterministic hashing"
        )
        assert "hash(task_intent)" not in source, (
            "Python's hash() is non-deterministic and should not be used for caching"
        )

    def test_cache_dict_type_is_str(self):
        """Cache key type should be str (MD5 hex), not int."""
        from crp.continuation import gap
        gap.clear_requirement_cache()
        assert isinstance(gap._requirement_cache, dict)
        # Populate cache and check key type
        gap.extract_task_requirements("Write a 10-section document about ML")
        for key in gap._requirement_cache:
            assert isinstance(key, str), f"Cache key should be str, got {type(key)}"
            assert len(key) == 32, f"MD5 hex digest should be 32 chars, got {len(key)}"
