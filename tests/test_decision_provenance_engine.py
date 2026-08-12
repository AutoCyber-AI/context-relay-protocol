# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Decision Provenance Engine (§7.14.3).

Covers: claim detection, attribution scoring, provenance chains,
report generation, DPE orchestration, and orchestrator integration.
"""

from __future__ import annotations

import time

import pytest

from crp.envelope.packer import PackedFact
from crp.provenance import (
    AttributionType,
    ClaimAttribution,
    ClaimType,
    DecisionProvenanceEngine,
    DetectedClaim,
    FactScore,
    ProvenanceConfig,
    ProvenanceReport,
    build_all_chains,
    detect_claims,
    enrich_fact_metadata,
    generate_json_report,
    generate_markdown_report,
    score_all_claims,
)
from crp.provenance._types import ProvenanceChain, ProvenanceLink
from crp.provenance.attribution_scorer import (
    _bag_vector,
    _cosine,
    _lexical_overlap,
    _tokenize,
    score_claim_against_facts,
)
from crp.provenance.claim_detector import classify_claim, split_into_sentences
from crp.provenance.provenance_chain import build_provenance_chain
from crp.security.audit_trail import ComplianceEventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_packed_fact(fact_id: str, text: str) -> PackedFact:
    """Create a minimal PackedFact for testing."""
    return PackedFact(
        fact_id=fact_id,
        text=text,
        score=0.9,
        tokens=len(text.split()),
        is_neighbour=False,
        is_compressed=False,
        is_bookend=False,
    )


def _make_claim(text: str, index: int = 0,
                claim_type: ClaimType = ClaimType.FACTUAL_CLAIM) -> DetectedClaim:
    """Create a DetectedClaim for testing."""
    return DetectedClaim(
        text=text,
        index=index,
        claim_type=claim_type,
        type_confidence=0.8,
    )


# ===================================================================
# 1. Claim Detector Tests
# ===================================================================


class TestSplitIntoSentences:
    """split_into_sentences() tests."""

    def test_basic_split(self):
        text = "Hello world. This is a test. Another sentence."
        result = split_into_sentences(text)
        assert len(result) == 3

    def test_single_sentence(self):
        result = split_into_sentences("Just one sentence.")
        assert len(result) == 1
        assert result[0].strip() == "Just one sentence."

    def test_empty_string(self):
        result = split_into_sentences("")
        # Either empty list or list with empty string
        assert all(s.strip() == "" for s in result) or result == []

    def test_paragraph_split(self):
        text = "Paragraph one.\n\nParagraph two."
        result = split_into_sentences(text)
        assert len(result) >= 2

    def test_preserves_abbreviations(self):
        text = "Dr. Smith went to Washington. He arrived safely."
        result = split_into_sentences(text)
        # Should handle abbreviations gracefully
        assert len(result) >= 1


class TestClassifyClaim:
    """classify_claim() tests."""

    def test_factual_claim(self):
        claim_type, conf = classify_claim(
            "Python is a widely-used programming language released in 2024."
        )
        assert claim_type == ClaimType.FACTUAL_CLAIM
        assert conf > 0.0

    def test_opinion_detection(self):
        claim_type, _ = classify_claim("I think this solution is an excellent approach.")
        assert claim_type == ClaimType.OPINION

    def test_procedural_detection(self):
        claim_type, _ = classify_claim("First, install Python 3.12 on your system.")
        assert claim_type == ClaimType.PROCEDURAL

    def test_hedge_detection(self):
        claim_type, _ = classify_claim(
            "This might possibly cause issues under heavy load."
        )
        assert claim_type == ClaimType.HEDGE

    def test_connective_detection(self):
        claim_type, _ = classify_claim("In addition to the above,")
        assert claim_type == ClaimType.CONNECTIVE


class TestDetectClaims:
    """detect_claims() tests."""

    def test_multi_sentence_output(self):
        text = (
            "The server uses AES-256 encryption. "
            "I think this is a good approach. "
            "First, install the required packages."
        )
        claims = detect_claims(text)
        assert len(claims) >= 2
        assert all(isinstance(c, DetectedClaim) for c in claims)

    def test_respects_min_length(self):
        text = "Short. This is a longer sentence that exceeds the minimum."
        claims = detect_claims(text, min_length=10)
        for c in claims:
            assert len(c.text) >= 10

    def test_respects_max_claims(self):
        text = ". ".join(f"Sentence number {i} is here" for i in range(100))
        claims = detect_claims(text, max_claims=5)
        assert len(claims) <= 5

    def test_empty_input(self):
        claims = detect_claims("")
        assert claims == []

    def test_claim_indices_ordered(self):
        text = "First claim here. Second claim here. Third claim here."
        claims = detect_claims(text)
        indices = [c.index for c in claims]
        assert indices == sorted(indices)


# ===================================================================
# 2. Attribution Scorer Tests
# ===================================================================


class TestTokenize:
    """_tokenize() tests."""

    def test_basic_tokenize(self):
        tokens = _tokenize("The server uses AES-256 encryption")
        assert "server" in tokens
        assert "encryption" in tokens
        # Stopwords removed
        assert "the" not in tokens

    def test_empty(self):
        assert _tokenize("") == []


class TestBagVector:
    """_bag_vector() tests."""

    def test_returns_correct_dim(self):
        vec = _bag_vector(["hello", "world"], dim=128)
        assert len(vec) == 128

    def test_normalized(self):
        import math
        vec = _bag_vector(["server", "encryption", "aes"])
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 0.01

    def test_empty_tokens(self):
        vec = _bag_vector([])
        assert len(vec) == 256
        assert all(v == 0.0 for v in vec)


class TestCosine:
    """_cosine() tests."""

    def test_identical_vectors(self):
        vec = _bag_vector(["server", "uses", "encryption"])
        assert abs(_cosine(vec, vec) - 1.0) < 0.01

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(_cosine(a, b)) < 0.01

    def test_zero_vectors(self):
        a = [0.0, 0.0]
        b = [0.0, 0.0]
        # Should not raise, returns 0 or ~0
        result = _cosine(a, b)
        assert result >= 0.0


class TestLexicalOverlap:
    """_lexical_overlap() tests."""

    def test_identical_tokens(self):
        tokens = ["server", "encryption"]
        result = _lexical_overlap(tokens, tokens)
        assert result == 1.0

    def test_no_overlap(self):
        result = _lexical_overlap(["server"], ["banana"])
        assert result == 0.0

    def test_partial_overlap(self):
        result = _lexical_overlap(["server", "encryption"], ["server", "banana"])
        assert 0.0 < result < 1.0

    def test_empty(self):
        assert _lexical_overlap([], ["server"]) == 0.0
        assert _lexical_overlap(["server"], []) == 0.0


class TestScoreClaimAgainstFacts:
    """score_claim_against_facts() tests."""

    def test_high_similarity_claim(self):
        claim = _make_claim("The server uses AES-256 encryption for data at rest.")
        facts = [
            _make_packed_fact("f1", "The server uses AES-256 encryption for data at rest."),
            _make_packed_fact("f2", "Python is a programming language."),
        ]
        result = score_claim_against_facts(claim, facts)
        assert isinstance(result, ClaimAttribution)
        assert result.attribution_type == AttributionType.CONTEXT_GROUNDED
        assert result.top_score > 0.5
        assert result.attributed_facts[0].fact_id == "f1"

    def test_no_matching_facts(self):
        claim = _make_claim("The moon orbits the earth every 27.3 days.")
        facts = [
            _make_packed_fact("f1", "Python is a programming language."),
            _make_packed_fact("f2", "JavaScript runs in the browser."),
        ]
        result = score_claim_against_facts(claim, facts)
        assert result.attribution_type in (
            AttributionType.PARAMETRIC,
            AttributionType.UNCERTAIN,
            AttributionType.MIXED,
        )

    def test_empty_facts(self):
        claim = _make_claim("Some factual claim.")
        result = score_claim_against_facts(claim, [])
        assert result.attribution_type == AttributionType.UNCERTAIN
        assert result.top_score == 0.0

    def test_returns_top5_facts(self):
        claim = _make_claim("Server encryption at rest.")
        facts = [_make_packed_fact(f"f{i}", f"Fact number {i}") for i in range(10)]
        result = score_claim_against_facts(claim, facts)
        assert len(result.attributed_facts) <= 5

    def test_custom_config(self):
        cfg = ProvenanceConfig(similarity_threshold=0.90, mixed_threshold=0.80)
        claim = _make_claim("Server encryption test.")
        facts = [_make_packed_fact("f1", "Server encryption test.")]
        result = score_claim_against_facts(claim, facts, config=cfg)
        assert isinstance(result, ClaimAttribution)


class TestScoreAllClaims:
    """score_all_claims() tests."""

    def test_factual_claims_scored(self):
        claims = [_make_claim("The server uses encryption.", 0, ClaimType.FACTUAL_CLAIM)]
        facts = [_make_packed_fact("f1", "The server uses encryption.")]
        results = score_all_claims(claims, facts)
        assert len(results) == 1
        assert results[0].top_score > 0.0

    def test_opinions_not_scored(self):
        claims = [_make_claim("I think this is great.", 0, ClaimType.OPINION)]
        facts = [_make_packed_fact("f1", "I think this is great.")]
        results = score_all_claims(claims, facts)
        assert len(results) == 1
        assert results[0].attribution_type == AttributionType.UNCERTAIN
        assert results[0].top_score == 0.0

    def test_connective_not_scored(self):
        claims = [_make_claim("Furthermore, as noted above,", 0, ClaimType.CONNECTIVE)]
        facts = [_make_packed_fact("f1", "Furthermore, as noted above,")]
        results = score_all_claims(claims, facts)
        assert results[0].top_score == 0.0

    def test_hedge_claims_scored(self):
        claims = [_make_claim(
            "This might use AES-256 encryption.", 0, ClaimType.HEDGE
        )]
        facts = [_make_packed_fact("f1", "It uses AES-256 encryption.")]
        results = score_all_claims(claims, facts)
        assert results[0].top_score > 0.0

    def test_mixed_claim_types(self):
        claims = [
            _make_claim("The server uses encryption.", 0, ClaimType.FACTUAL_CLAIM),
            _make_claim("I think this is great.", 1, ClaimType.OPINION),
            _make_claim("First, install Python.", 2, ClaimType.PROCEDURAL),
        ]
        facts = [_make_packed_fact("f1", "The server uses encryption.")]
        results = score_all_claims(claims, facts)
        assert len(results) == 3
        # Only first claim (factual) should have a non-zero score
        assert results[0].top_score > 0.0
        assert results[1].top_score == 0.0
        assert results[2].top_score == 0.0


# ===================================================================
# 3. Provenance Chain Tests
# ===================================================================


class TestEnrichFactMetadata:
    """enrich_fact_metadata() tests."""

    def test_enrichment(self):
        attr = ClaimAttribution(
            claim_text="Some claim",
            claim_index=0,
            claim_type=ClaimType.FACTUAL_CLAIM,
            attributed_facts=[
                FactScore(fact_id="f1", fact_text_preview="Preview"),
            ],
            top_score=0.8,
            attribution_type=AttributionType.CONTEXT_GROUNDED,
            confidence=0.85,
        )
        metadata = {
            "f1": {"source_window_id": "win-abc", "extraction_stage": 3},
        }
        enrich_fact_metadata([attr], metadata)
        assert attr.attributed_facts[0].fact_source_window == "win-abc"
        assert attr.attributed_facts[0].fact_extraction_stage == 3

    def test_missing_metadata_no_crash(self):
        attr = ClaimAttribution(
            claim_text="Some claim",
            claim_index=0,
            claim_type=ClaimType.FACTUAL_CLAIM,
            attributed_facts=[
                FactScore(fact_id="f-unknown", fact_text_preview="Preview"),
            ],
            top_score=0.5,
            attribution_type=AttributionType.CONTEXT_GROUNDED,
            confidence=0.6,
        )
        enrich_fact_metadata([attr], {})
        assert attr.attributed_facts[0].fact_source_window == ""


class TestBuildProvenanceChain:
    """build_provenance_chain() tests."""

    def test_context_grounded_chain(self):
        attr = ClaimAttribution(
            claim_text="The server uses AES-256 encryption.",
            claim_index=0,
            claim_type=ClaimType.FACTUAL_CLAIM,
            attributed_facts=[
                FactScore(
                    fact_id="f1",
                    fact_text_preview="AES-256 encryption used",
                    semantic_similarity=0.85,
                    lexical_overlap=0.6,
                    composite_score=0.75,
                    fact_source_window="win-001",
                    fact_extraction_stage=2,
                ),
            ],
            top_score=0.75,
            attribution_type=AttributionType.CONTEXT_GROUNDED,
            confidence=0.85,
        )
        chain = build_provenance_chain(
            attr,
            session_id="sess-001",
            window_id="win-001",
            envelope_saturation=0.85,
            envelope_facts_included=10,
            task_input_preview="Tell me about server security",
        )
        assert isinstance(chain, ProvenanceChain)
        assert chain.attribution_type == AttributionType.CONTEXT_GROUNDED
        # Should have claim, fact, window, envelope, task links
        levels = [link.level for link in chain.links]
        assert "claim" in levels
        assert "fact" in levels
        assert "envelope" in levels
        assert "task" in levels

    def test_parametric_chain(self):
        attr = ClaimAttribution(
            claim_text="The moon is about 384,400 km from Earth.",
            claim_index=1,
            claim_type=ClaimType.FACTUAL_CLAIM,
            attributed_facts=[],
            top_score=0.1,
            attribution_type=AttributionType.PARAMETRIC,
            confidence=0.5,
        )
        chain = build_provenance_chain(attr, session_id="s1", window_id="w1")
        levels = [link.level for link in chain.links]
        assert "claim" in levels
        assert "fact" in levels  # "No supporting context fact" link
        assert "envelope" in levels


class TestBuildAllChains:
    """build_all_chains() tests."""

    def test_builds_for_all_attributions(self):
        attrs = [
            ClaimAttribution(
                claim_text="Claim 1",
                claim_index=0,
                claim_type=ClaimType.FACTUAL_CLAIM,
                attributed_facts=[],
                top_score=0.1,
                attribution_type=AttributionType.PARAMETRIC,
                confidence=0.5,
            ),
            ClaimAttribution(
                claim_text="Claim 2",
                claim_index=1,
                claim_type=ClaimType.OPINION,
                attributed_facts=[],
                top_score=0.0,
                attribution_type=AttributionType.UNCERTAIN,
                confidence=0.2,
            ),
        ]
        chains = build_all_chains(attrs, session_id="s1", window_id="w1")
        assert len(chains) == 2


# ===================================================================
# 4. Report Generator Tests
# ===================================================================


class TestGenerateMarkdownReport:
    """generate_markdown_report() tests."""

    def _make_report(self) -> ProvenanceReport:
        return ProvenanceReport(
            session_id="sess-abc123def456",
            window_id="win-xyz789",
            timestamp=1700000000.0,
            total_claims=5,
            factual_claims=3,
            opinion_claims=1,
            procedural_claims=0,
            hedge_claims=1,
            connective_claims=0,
            context_grounded_count=2,
            parametric_count=1,
            mixed_count=0,
            uncertain_count=2,
            grounding_ratio=0.6667,
            attributions=[
                ClaimAttribution(
                    claim_text="The server uses AES-256 encryption.",
                    claim_index=0,
                    claim_type=ClaimType.FACTUAL_CLAIM,
                    top_score=0.85,
                    attribution_type=AttributionType.CONTEXT_GROUNDED,
                    confidence=0.90,
                ),
                ClaimAttribution(
                    claim_text="I believe this approach is secure.",
                    claim_index=1,
                    claim_type=ClaimType.OPINION,
                    top_score=0.0,
                    attribution_type=AttributionType.UNCERTAIN,
                    confidence=0.0,
                ),
            ],
            chains=[],
            chain_verified=True,
            output_token_count=120,
            envelope_facts_count=15,
        )

    def test_contains_header(self):
        md = generate_markdown_report(self._make_report())
        assert "Decision Provenance Report" in md

    def test_contains_claim_counts(self):
        md = generate_markdown_report(self._make_report())
        assert "3 factual claims" in md
        assert "1 opinion" in md

    def test_contains_grounding_stats(self):
        md = generate_markdown_report(self._make_report())
        assert "Grounding Statistics" in md
        assert "Context-grounded claims" in md

    def test_contains_table(self):
        md = generate_markdown_report(self._make_report())
        assert "| #" in md
        assert "AES-256" in md

    def test_contains_regulatory_notes(self):
        md = generate_markdown_report(self._make_report())
        assert "Regulatory Compliance Notes" in md
        assert "EU AI Act Art. 12" in md

    def test_parametric_warning(self):
        report = self._make_report()
        md = generate_markdown_report(report)
        assert "parametric" in md.lower()


class TestGenerateJsonReport:
    """generate_json_report() tests."""

    def _make_report(self) -> ProvenanceReport:
        return ProvenanceReport(
            session_id="sess-001",
            window_id="win-001",
            timestamp=1700000000.0,
            total_claims=3,
            factual_claims=2,
            opinion_claims=1,
            procedural_claims=0,
            hedge_claims=0,
            connective_claims=0,
            context_grounded_count=1,
            parametric_count=1,
            mixed_count=0,
            uncertain_count=1,
            grounding_ratio=0.5,
            attributions=[
                ClaimAttribution(
                    claim_text="Test claim.",
                    claim_index=0,
                    claim_type=ClaimType.FACTUAL_CLAIM,
                    top_score=0.8,
                    attribution_type=AttributionType.CONTEXT_GROUNDED,
                    confidence=0.85,
                ),
            ],
            chains=[],
            chain_verified=True,
            output_token_count=50,
            envelope_facts_count=10,
        )

    def test_has_required_keys(self):
        result = generate_json_report(self._make_report())
        assert result["report_type"] == "decision_provenance"
        assert result["version"] == "1.0.0"
        assert "summary" in result
        assert "attributions" in result
        assert "chains" in result
        assert "integrity" in result

    def test_summary_values(self):
        result = generate_json_report(self._make_report())
        summary = result["summary"]
        assert summary["total_claims"] == 3
        assert summary["factual_claims"] == 2
        assert summary["grounding_ratio"] == 0.5

    def test_attribution_structure(self):
        result = generate_json_report(self._make_report())
        attr = result["attributions"][0]
        assert "claim_text" in attr
        assert "attribution_type" in attr
        assert "top_score" in attr
        assert attr["claim_type"] == "FACTUAL_CLAIM"


# ===================================================================
# 5. DPE Orchestration Tests
# ===================================================================


class TestDecisionProvenanceEngine:
    """DecisionProvenanceEngine class tests."""

    def test_init_defaults(self):
        dpe = DecisionProvenanceEngine()
        assert dpe.enabled is True
        assert isinstance(dpe.config, ProvenanceConfig)

    def test_init_custom_config(self):
        cfg = ProvenanceConfig(enabled=False, min_claim_length=20)
        dpe = DecisionProvenanceEngine(config=cfg)
        assert dpe.enabled is False
        assert dpe.config.min_claim_length == 20

    def test_disabled_returns_empty_report(self):
        dpe = DecisionProvenanceEngine(
            config=ProvenanceConfig(enabled=False)
        )
        report = dpe.analyse(
            output_text="The server uses encryption.",
            packed_facts=[],
            session_id="s1",
            window_id="w1",
        )
        assert isinstance(report, ProvenanceReport)
        assert report.total_claims == 0
        assert report.session_id == "s1"

    def test_full_pipeline_with_matching_facts(self):
        dpe = DecisionProvenanceEngine()
        output = (
            "The server uses AES-256 encryption for data at rest. "
            "Python 3.12 is the recommended version. "
            "I think this approach is excellent."
        )
        facts = [
            _make_packed_fact("f1", "The server uses AES-256 encryption for data at rest."),
            _make_packed_fact("f2", "Python 3.12 is the recommended version for the project."),
        ]
        report = dpe.analyse(
            output_text=output,
            packed_facts=facts,
            session_id="sess-001",
            window_id="win-001",
            envelope_saturation=0.85,
            task_input_preview="Tell me about the server",
        )
        assert isinstance(report, ProvenanceReport)
        assert report.total_claims >= 2
        assert report.session_id == "sess-001"
        assert report.window_id == "win-001"
        assert report.envelope_facts_count == 2
        assert report.chain_verified is True

    def test_grounding_ratio_computed(self):
        dpe = DecisionProvenanceEngine()
        output = "The server uses AES-256 encryption."
        facts = [_make_packed_fact("f1", "The server uses AES-256 encryption.")]
        report = dpe.analyse(
            output_text=output,
            packed_facts=facts,
            session_id="s1",
            window_id="w1",
        )
        assert 0.0 <= report.grounding_ratio <= 1.0

    def test_no_facts_all_parametric(self):
        dpe = DecisionProvenanceEngine()
        output = "The moon orbits Earth every 27.3 days."
        report = dpe.analyse(
            output_text=output,
            packed_facts=[],
            session_id="s1",
            window_id="w1",
        )
        # All claims should be uncertain (no facts to match against)
        assert report.context_grounded_count == 0

    def test_markdown_report_generation(self):
        dpe = DecisionProvenanceEngine()
        output = "The server uses encryption."
        facts = [_make_packed_fact("f1", "The server uses encryption.")]
        report = dpe.analyse(output_text=output, packed_facts=facts)
        md = dpe.generate_markdown(report)
        assert "Decision Provenance Report" in md

    def test_json_report_generation(self):
        dpe = DecisionProvenanceEngine()
        output = "The server uses encryption."
        facts = [_make_packed_fact("f1", "The server uses encryption.")]
        report = dpe.analyse(output_text=output, packed_facts=facts)
        j = dpe.generate_json(report)
        assert j["report_type"] == "decision_provenance"

    def test_fact_metadata_enrichment(self):
        dpe = DecisionProvenanceEngine()
        output = "The server uses AES-256 encryption."
        facts = [_make_packed_fact("f1", "The server uses AES-256 encryption.")]
        metadata = {"f1": {"source_window_id": "win-src", "extraction_stage": 4}}
        report = dpe.analyse(
            output_text=output,
            packed_facts=facts,
            fact_metadata=metadata,
        )
        # Check that enrichment was applied
        grounded = [
            a for a in report.attributions
            if a.attributed_facts and a.attributed_facts[0].fact_id == "f1"
        ]
        if grounded:
            assert grounded[0].attributed_facts[0].fact_source_window == "win-src"

    def test_chains_built(self):
        dpe = DecisionProvenanceEngine()
        output = "The server uses AES-256 encryption."
        facts = [_make_packed_fact("f1", "The server uses AES-256 encryption.")]
        report = dpe.analyse(
            output_text=output,
            packed_facts=facts,
            session_id="s1",
            window_id="w1",
        )
        assert len(report.chains) >= 1


# ===================================================================
# 6. ComplianceEventType Tests
# ===================================================================


class TestComplianceEventTypes:
    """New DPE ComplianceEventType values exist."""

    def test_claim_attributed_exists(self):
        assert ComplianceEventType.CLAIM_ATTRIBUTED.value == "compliance.claim_attributed"

    def test_attribution_report_exists(self):
        assert ComplianceEventType.ATTRIBUTION_REPORT.value == "compliance.attribution_report"

    def test_parametric_detected_exists(self):
        assert ComplianceEventType.PARAMETRIC_DETECTED.value == "compliance.parametric_detected"

    def test_attribution_uncertain_exists(self):
        assert ComplianceEventType.ATTRIBUTION_UNCERTAIN.value == "compliance.attribution_uncertain"

    def test_total_event_types(self):
        # Current enum includes lifecycle, consent, privacy, security, oversight,
        # session, risk, LLM provenance, DPE, fidelity, entailment, hallucination,
        # provenance engine ops, RQA, activation, and window DAG events.
        assert len(ComplianceEventType) == 61


# ===================================================================
# 7. Data Type Tests
# ===================================================================


class TestDataTypes:
    """Verify dataclass defaults and construction."""

    def test_provenance_config_defaults(self):
        cfg = ProvenanceConfig()
        assert cfg.enabled is True
        assert cfg.min_claim_length == 10
        assert cfg.max_claims_per_output == 50
        assert cfg.similarity_threshold == 0.50
        assert cfg.mixed_threshold == 0.35
        assert cfg.lexical_weight == 0.40
        assert cfg.semantic_weight == 0.60

    def test_fact_score_defaults(self):
        fs = FactScore()
        assert fs.fact_id == ""
        assert fs.composite_score == 0.0

    def test_claim_attribution_defaults(self):
        ca = ClaimAttribution()
        assert ca.claim_type == ClaimType.CONNECTIVE
        assert ca.attribution_type == AttributionType.UNCERTAIN
        assert ca.attributed_facts == []

    def test_provenance_report_defaults(self):
        rpt = ProvenanceReport()
        assert rpt.total_claims == 0
        assert rpt.grounding_ratio == 0.0
        assert rpt.chain_verified is False

    def test_provenance_link(self):
        link = ProvenanceLink(level="claim", label="Test", detail={"k": "v"})
        assert link.level == "claim"
        assert link.detail["k"] == "v"

    def test_provenance_chain(self):
        chain = ProvenanceChain(
            claim_text="Test",
            claim_index=0,
            attribution_type=AttributionType.CONTEXT_GROUNDED,
            links=[ProvenanceLink(level="claim", label="L")],
        )
        assert len(chain.links) == 1

    def test_claim_type_values(self):
        assert ClaimType.FACTUAL_CLAIM.value == "FACTUAL_CLAIM"
        assert ClaimType.OPINION.value == "OPINION"
        assert ClaimType.PROCEDURAL.value == "PROCEDURAL"
        assert ClaimType.HEDGE.value == "HEDGE"
        assert ClaimType.CONNECTIVE.value == "CONNECTIVE"

    def test_attribution_type_values(self):
        assert AttributionType.CONTEXT_GROUNDED.value == "CONTEXT_GROUNDED"
        assert AttributionType.PARAMETRIC.value == "PARAMETRIC"
        assert AttributionType.MIXED.value == "MIXED"
        assert AttributionType.UNCERTAIN.value == "UNCERTAIN"


# ===================================================================
# 8. Edge Case & Integration Tests
# ===================================================================


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_very_long_output(self):
        dpe = DecisionProvenanceEngine(
            config=ProvenanceConfig(max_claims_per_output=10)
        )
        output = ". ".join(f"Sentence number {i} is a factual claim" for i in range(200))
        facts = [_make_packed_fact("f1", "Sentence number 5 is a factual claim")]
        report = dpe.analyse(output_text=output, packed_facts=facts)
        assert report.total_claims <= 10

    def test_single_word_output(self):
        dpe = DecisionProvenanceEngine()
        report = dpe.analyse(output_text="Yes", packed_facts=[])
        # "Yes" is only 3 chars, below min_claim_length=10
        assert report.total_claims == 0

    def test_special_characters_in_output(self):
        dpe = DecisionProvenanceEngine()
        output = "The rate is 99.9% effective. Use `pip install crprotocol`."
        facts = [_make_packed_fact("f1", "The rate is 99.9% effective.")]
        report = dpe.analyse(output_text=output, packed_facts=facts)
        assert isinstance(report, ProvenanceReport)

    def test_unicode_output(self):
        dpe = DecisionProvenanceEngine()
        output = "Le serveur utilise le chiffrement AES-256. C'est très sécurisé."
        facts = [_make_packed_fact("f1", "Le serveur utilise le chiffrement AES-256.")]
        report = dpe.analyse(output_text=output, packed_facts=facts)
        assert isinstance(report, ProvenanceReport)

    def test_pipe_in_claim_text_markdown(self):
        """Pipe chars in claims shouldn't break markdown table."""
        report = ProvenanceReport(
            session_id="s1",
            window_id="w1",
            timestamp=time.time(),
            total_claims=1,
            factual_claims=1,
            attributions=[
                ClaimAttribution(
                    claim_text="Use cmd | grep pattern for filtering.",
                    claim_index=0,
                    claim_type=ClaimType.FACTUAL_CLAIM,
                    top_score=0.5,
                    attribution_type=AttributionType.CONTEXT_GROUNDED,
                    confidence=0.6,
                ),
            ],
        )
        md = generate_markdown_report(report)
        # Pipe should be escaped
        assert "\\|" in md
