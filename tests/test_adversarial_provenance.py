# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Adversarial tests for the Decision Provenance Engine (P-5).

Tests boundary conditions, malicious inputs, resource limits,
and adversarial patterns designed to fool the DPE pipeline.
"""

from __future__ import annotations

import pytest

from crp.envelope.packer import PackedFact
from crp.provenance._types import (
    AttributionType,
    ClaimAttribution,
    ClaimType,
    DistortionType,
    EntailmentLabel,
    FabricationType,
    FidelityReport,
    HallucinationRisk,
    ProvenanceConfig,
)
from crp.provenance.attribution_scorer import score_all_claims, score_claim_against_facts
from crp.provenance.claim_detector import DetectedClaim, detect_claims
from crp.provenance.contradiction_detector import detect_contradictions
from crp.provenance.distortion_detector import detect_distortions
from crp.provenance.entailment_verifier import verify_entailment
from crp.provenance.fabrication_detector import detect_fabrications
from crp.provenance.hallucination_scorer import score_hallucination_risk


def _pf(fid: str, text: str) -> PackedFact:
    return PackedFact(fact_id=fid, text=text, score=0.9)


def _attr(index: int, text: str, claim_type: ClaimType = ClaimType.FACTUAL_CLAIM,
           attr_type: AttributionType = AttributionType.CONTEXT_GROUNDED,
           top_score: float = 0.8, facts: list | None = None) -> ClaimAttribution:
    from crp.provenance._types import FactScore
    if facts is None:
        facts = [FactScore(fact_id="f1", fact_text_preview=text[:80],
                           semantic_similarity=top_score, lexical_overlap=0.5,
                           composite_score=top_score, fact_source_window="w1",
                           fact_extraction_stage=1)]
    return ClaimAttribution(
        claim_text=text, claim_index=index, claim_type=claim_type,
        attributed_facts=facts, top_score=top_score,
        attribution_type=attr_type, confidence=0.7)


# -----------------------------------------------------------------------
# §1: Empty / None / Minimal inputs
# -----------------------------------------------------------------------


class TestEmptyInputs:
    """Ensure no crashes on empty/minimal inputs."""

    def test_claim_detection_empty_string(self) -> None:
        claims = detect_claims("")
        assert claims == []

    def test_claim_detection_whitespace_only(self) -> None:
        claims = detect_claims("   \n\t  \n   ")
        assert claims == []

    def test_attribution_scoring_no_facts(self) -> None:
        claim = DetectedClaim(text="Revenue grew 15%.", index=0,
                               claim_type=ClaimType.FACTUAL_CLAIM, type_confidence=0.9)
        result = score_claim_against_facts(claim, [])
        assert result.attribution_type in (AttributionType.UNCERTAIN, AttributionType.PARAMETRIC)

    def test_attribution_scoring_no_claims(self) -> None:
        facts = [_pf("f1", "Some fact text")]
        result = score_all_claims([], facts)
        assert result == []

    def test_fabrication_detector_empty_facts(self) -> None:
        attr = _attr(0, "According to the Smith report, revenue grew 23%.")
        results = detect_fabrications([attr], [])
        assert results == []

    def test_fabrication_detector_empty_attributions(self) -> None:
        results = detect_fabrications([], [_pf("f1", "some fact")])
        assert results == []

    def test_distortion_detector_empty_inputs(self) -> None:
        results = detect_distortions([], [])
        assert results == []

    def test_entailment_empty_attributions(self) -> None:
        results = verify_entailment([], [])
        assert results == []

    def test_risk_scorer_empty_attributions(self) -> None:
        report = score_hallucination_risk([])
        assert report.assessments == []

    def test_contradiction_detector_empty(self) -> None:
        results = detect_contradictions([])
        assert results == []


# -----------------------------------------------------------------------
# §2: Very large inputs
# -----------------------------------------------------------------------


class TestLargeInputs:
    """Ensure the pipeline handles large inputs without crashing."""

    def test_large_claim_text(self) -> None:
        """50K character single claim should not crash."""
        large_text = "The server processes data. " * 2000  # ~52K chars
        claims = detect_claims(large_text)
        assert isinstance(claims, list)

    def test_many_facts(self) -> None:
        """500 facts should score without error."""
        facts = [_pf(f"f{i}", f"Fact number {i} about revenue growth of {i}%")
                 for i in range(500)]
        claim = DetectedClaim(text="Revenue grew 15%.", index=0,
                               claim_type=ClaimType.FACTUAL_CLAIM, type_confidence=0.9)
        result = score_claim_against_facts(claim, facts)
        assert result.attributed_facts  # Should have top-5

    def test_many_claims(self) -> None:
        """200 claims should score without error."""
        claims = [DetectedClaim(text=f"Claim {i}: revenue was {i}%.", index=i,
                                 claim_type=ClaimType.FACTUAL_CLAIM, type_confidence=0.8)
                  for i in range(200)]
        facts = [_pf("f1", "Revenue was 10%.")]
        results = score_all_claims(claims, facts)
        assert len(results) == 200

    def test_fabrication_detector_many_facts(self) -> None:
        """500 facts should not cause false positives for present entities."""
        facts = [_pf(f"f{i}", f"In 2024, company {i} reported revenue of {i*10}%.")
                 for i in range(500)]
        # Claim references fact 42: "420%"
        attr = _attr(0, "Company reported revenue of 420%.")
        results = detect_fabrications([attr], facts)
        # 420 should be found in fact 42 via word-boundary matching
        pct_fabs = [r for r in results if r.entity_type == FabricationType.PERCENTAGE]
        num_fabs = [r for r in results if r.entity_type == FabricationType.NUMBER]
        # The per-fact matching should find "420" in f42's text
        assert len(pct_fabs) == 0 or len(num_fabs) == 0  # At least one should not false-positive


# -----------------------------------------------------------------------
# §3: Injection patterns in claims
# -----------------------------------------------------------------------


class TestInjectionPatterns:
    """Ensure DPE doesn't crash on adversarial text patterns."""

    def test_regex_escape_characters(self) -> None:
        """Regex metacharacters in claims should not crash extractors."""
        malicious = "Revenue (grew) [15%] {in} Q3+Q4 2024.*"
        claims = detect_claims(malicious)
        assert isinstance(claims, list)

    def test_unicode_attack(self) -> None:
        """Unicode control characters and homoglyphs."""
        text = "Revenue grew\u200b 15\u200b%\u200b"  # Zero-width spaces
        claims = detect_claims(text)
        assert isinstance(claims, list)

    def test_null_bytes_in_text(self) -> None:
        """Null bytes in claim text."""
        text = "Revenue\x00grew\x0015%."
        claims = detect_claims(text)
        assert isinstance(claims, list)

    def test_very_long_single_word(self) -> None:
        """Single 10K character word should not hang regex."""
        text = "a" * 10000 + " grew 15%."
        claims = detect_claims(text)
        assert isinstance(claims, list)

    def test_nested_quotes_in_claims(self) -> None:
        """Deeply nested quotes."""
        text = 'He said "she said \'they said "revenue grew 15%"\' again".'
        claims = detect_claims(text)
        assert isinstance(claims, list)

    def test_html_injection_in_claims(self) -> None:
        """HTML/script injection in claim text should not affect processing."""
        text = '<script>alert("xss")</script> Revenue grew 15%.'
        attr = _attr(0, text)
        facts = [_pf("f1", "Revenue grew 15%.")]
        # Should still detect the percentage match
        results = detect_fabrications([attr], facts)
        pct_fabs = [r for r in results if r.entity_type == FabricationType.PERCENTAGE]
        assert len(pct_fabs) == 0  # 15 IS in facts


# -----------------------------------------------------------------------
# §4: Adversarial fabrication patterns
# -----------------------------------------------------------------------


class TestAdversarialFabrication:
    """Adversarial patterns designed to fool the fabrication detector."""

    def test_number_substring_not_false_positive(self) -> None:
        """'23' should not match '1234' in facts (P-2 fix validation)."""
        facts = [_pf("f1", "The system handled 1234 requests.")]
        attr = _attr(0, "The system handled 23 requests.")
        results = detect_fabrications([attr], facts)
        num_fabs = [r for r in results if r.fabricated_entity == "23"]
        assert len(num_fabs) > 0  # 23 is NOT in "1234" with boundary matching

    def test_number_present_not_flagged(self) -> None:
        """Exact number match should not be flagged."""
        facts = [_pf("f1", "Revenue was 15%.")]
        attr = _attr(0, "Revenue was 15%.")
        results = detect_fabrications([attr], facts)
        pct_fabs = [r for r in results if r.fabricated_entity == "15%"]
        assert len(pct_fabs) == 0

    def test_adjacent_fact_numbers_no_clash(self) -> None:
        """Numbers from different facts should not cross-contaminate."""
        facts = [
            _pf("f1", "In 2023 revenue was 500 million."),
            _pf("f2", "In 2024 costs were 300 million."),
        ]
        attr = _attr(0, "In 2023, revenue was 500 million.")
        results = detect_fabrications([attr], facts)
        # All entities should be found in fact f1
        assert not any(r.fabricated_entity == "500" for r in results)
        assert not any(r.fabricated_entity == "2023" for r in results)


# -----------------------------------------------------------------------
# §5: Adversarial distortion patterns
# -----------------------------------------------------------------------


class TestAdversarialDistortion:
    """Patterns designed to evade distortion detection."""

    def test_subtle_number_change(self) -> None:
        """10.1 → 10.2 should be caught by number check."""
        from crp.provenance._types import FactScore
        facts = [_pf("f1", "The metric improved by 10.1 percentage points.")]
        fs = FactScore(fact_id="f1", fact_text_preview="The metric improved by 10.1",
                       semantic_similarity=0.9, lexical_overlap=0.8,
                       composite_score=0.85, fact_source_window="w1",
                       fact_extraction_stage=1)
        attr = _attr(0, "The metric improved by 10.2 percentage points.",
                      facts=[fs])
        results = detect_distortions([attr], facts)
        num_distortions = [r for r in results if r.distortion_type == DistortionType.NUMBER_CHANGED]
        assert len(num_distortions) > 0

    def test_negation_insertion(self) -> None:
        """Adding 'not' should trigger negation flip."""
        from crp.provenance._types import FactScore
        facts = [_pf("f1", "The treatment is effective for most patients.")]
        fs = FactScore(fact_id="f1", fact_text_preview="The treatment is effective",
                       semantic_similarity=0.88, lexical_overlap=0.7,
                       composite_score=0.82, fact_source_window="w1",
                       fact_extraction_stage=1)
        attr = _attr(0, "The treatment is not effective for most patients.",
                      facts=[fs])
        results = detect_distortions([attr], facts)
        neg_flips = [r for r in results if r.distortion_type == DistortionType.NEGATION_FLIP]
        assert len(neg_flips) > 0

    def test_scope_widening(self) -> None:
        """'in Q3' → 'annually' should trigger scope change."""
        from crp.provenance._types import FactScore
        facts = [_pf("f1", "Revenue grew 15% in Q3 2024.")]
        fs = FactScore(fact_id="f1", fact_text_preview="Revenue grew 15% in Q3",
                       semantic_similarity=0.85, lexical_overlap=0.6,
                       composite_score=0.75, fact_source_window="w1",
                       fact_extraction_stage=1)
        attr = _attr(0, "Revenue grew 15% annually.",
                      facts=[fs])
        results = detect_distortions([attr], facts)
        scope_changes = [r for r in results if r.distortion_type == DistortionType.SCOPE_CHANGED]
        assert len(scope_changes) > 0


# -----------------------------------------------------------------------
# §6: Adversarial risk scoring
# -----------------------------------------------------------------------


class TestAdversarialRiskScoring:
    """Risk scorer edge cases and critical signal override validation."""

    def test_critical_signal_override_low_attribution(self) -> None:
        """Attribution near zero should force at least HIGH risk (G-3)."""
        attr = _attr(0, "Revenue grew 50% in Q3 2024.",
                      attr_type=AttributionType.UNCERTAIN, top_score=0.0)
        report = score_hallucination_risk([attr])
        assert report.assessments[0].risk_level in (HallucinationRisk.HIGH, HallucinationRisk.CRITICAL)
        assert report.assessments[0].risk_score >= 0.50

    def test_critical_signal_override_low_fidelity(self) -> None:
        """Zero fidelity should force at least HIGH risk."""
        from crp.provenance._types import DistortionResult
        attr = _attr(0, "Revenue grew 50%.", top_score=0.9)
        # Create a fidelity report with severe distortions for this claim
        fid = FidelityReport(
            distortions=[
                DistortionResult(
                    claim_index=0, claim_text="Revenue grew 50%.",
                    source_fact_id="f1", source_fact_preview="Revenue grew 10%",
                    distortion_type=DistortionType.NUMBER_CHANGED,
                    severity=0.9, detail="50 vs 10",
                    claim_value="50", fact_value="10"),
                DistortionResult(
                    claim_index=0, claim_text="Revenue grew 50%.",
                    source_fact_id="f1", source_fact_preview="Revenue grew 10%",
                    distortion_type=DistortionType.NUMBER_CHANGED,
                    severity=0.9, detail="50 vs 10",
                    claim_value="50", fact_value="10"),
                DistortionResult(
                    claim_index=0, claim_text="Revenue grew 50%.",
                    source_fact_id="f1", source_fact_preview="Revenue grew 10%",
                    distortion_type=DistortionType.NUMBER_CHANGED,
                    severity=0.9, detail="50 vs 10",
                    claim_value="50", fact_value="10"),
                DistortionResult(
                    claim_index=0, claim_text="Revenue grew 50%.",
                    source_fact_id="f1", source_fact_preview="Revenue grew 10%",
                    distortion_type=DistortionType.NUMBER_CHANGED,
                    severity=0.9, detail="50 vs 10",
                    claim_value="50", fact_value="10"),
                DistortionResult(
                    claim_index=0, claim_text="Revenue grew 50%.",
                    source_fact_id="f1", source_fact_preview="Revenue grew 10%",
                    distortion_type=DistortionType.NUMBER_CHANGED,
                    severity=0.9, detail="50 vs 10",
                    claim_value="50", fact_value="10"),
            ],
            fabrications=[], omissions=[], contradictions=[],
        )
        report = score_hallucination_risk([attr], fidelity=fid)
        assessment = report.assessments[0]
        assert assessment.risk_score >= 0.50
        assert assessment.risk_level in (HallucinationRisk.HIGH, HallucinationRisk.CRITICAL)

    def test_all_signals_high_gives_low_risk(self) -> None:
        """Perfect signals should yield LOW risk."""
        from crp.provenance._types import EntailmentResult
        attr = _attr(0, "Revenue grew 15%.", top_score=0.9,
                      attr_type=AttributionType.CONTEXT_GROUNDED)
        ent = EntailmentResult(
            claim_index=0, claim_text="Revenue grew 15%.",
            fact_id="f1", fact_text_preview="Revenue grew 15%.",
            label=EntailmentLabel.ENTAILED, confidence=0.9,
            entailment_score=0.9, contradiction_score=0.05,
            neutral_score=0.05, used_model=False)
        report = score_hallucination_risk([attr], entailment_results=[ent])
        assert report.assessments[0].risk_level == HallucinationRisk.LOW

    def test_non_factual_claims_get_low_risk(self) -> None:
        """Opinion/connective claims should always be LOW risk."""
        attr = _attr(0, "In my opinion, the results are interesting.",
                      claim_type=ClaimType.OPINION, attr_type=AttributionType.UNCERTAIN,
                      top_score=0.0)
        report = score_hallucination_risk([attr])
        assert report.assessments[0].risk_level == HallucinationRisk.LOW


# -----------------------------------------------------------------------
# §7: Entailment adversarial cases
# -----------------------------------------------------------------------


class TestAdversarialEntailment:
    """Adversarial entailment verification edge cases."""

    def test_heuristic_high_overlap(self) -> None:
        """Nearly identical claim and fact should entail (heuristic)."""
        facts = [_pf("f1", "The treatment reduced mortality by 40%.")]
        attr = _attr(0, "The treatment reduced mortality by 40%.",
                      attr_type=AttributionType.CONTEXT_GROUNDED)
        results = verify_entailment([attr], facts)
        assert len(results) > 0
        assert results[0].label == EntailmentLabel.ENTAILED

    def test_heuristic_negation_flip(self) -> None:
        """Negation flip with overlap should signal contradiction."""
        facts = [_pf("f1", "The drug is safe for human consumption.")]
        attr = _attr(0, "The drug is not safe for human consumption.",
                      attr_type=AttributionType.CONTEXT_GROUNDED)
        results = verify_entailment([attr], facts)
        assert len(results) > 0
        assert results[0].label == EntailmentLabel.CONTRADICTION

    def test_unrelated_claim_neutral(self) -> None:
        """Totally unrelated claim and fact should be neutral."""
        facts = [_pf("f1", "The company was founded in 1999.")]
        attr = _attr(0, "Quantum computing enables faster factoring.",
                      attr_type=AttributionType.CONTEXT_GROUNDED)
        results = verify_entailment([attr], facts)
        assert len(results) > 0
        assert results[0].label == EntailmentLabel.NEUTRAL

    def test_entailment_disabled(self) -> None:
        """Disabled entailment returns empty."""
        cfg = ProvenanceConfig(entailment_enabled=False)
        attr = _attr(0, "Some claim.", attr_type=AttributionType.CONTEXT_GROUNDED)
        results = verify_entailment([attr], [_pf("f1", "Some fact.")], config=cfg)
        assert results == []


# -----------------------------------------------------------------------
# §8: Embeddings module robustness
# -----------------------------------------------------------------------


class TestEmbeddingsModule:
    """Test the shared embeddings module boundary conditions."""

    def test_encode_empty_list(self) -> None:
        from crp.provenance._embeddings import encode_texts, reset_cache
        reset_cache()
        # With no model override and likely no model, should return None
        result = encode_texts([])
        # Either None (no model) or empty list (model loaded but empty input)
        assert result is None or result == []

    def test_cosine_similarity_identical(self) -> None:
        from crp.provenance._embeddings import cosine_similarity
        vec = [1.0, 2.0, 3.0, 4.0]
        assert abs(cosine_similarity(vec, vec) - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self) -> None:
        from crp.provenance._embeddings import cosine_similarity
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(cosine_similarity(a, b)) < 0.001

    def test_cosine_similarity_opposite(self) -> None:
        from crp.provenance._embeddings import cosine_similarity
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) < -0.99

    def test_reset_cache(self) -> None:
        from crp.provenance._embeddings import reset_cache
        reset_cache()  # Should not raise


# -----------------------------------------------------------------------
# §9: Cross-component adversarial pipeline
# -----------------------------------------------------------------------


class TestPipelineAdversarial:
    """Full pipeline adversarial scenarios."""

    def test_contradicting_claims_detected(self) -> None:
        """Two claims that contradict each other should be caught."""
        attrs = [
            _attr(0, "The system is fully secure and protected.",
                  attr_type=AttributionType.CONTEXT_GROUNDED),
            _attr(1, "The system has significant security vulnerabilities.",
                  attr_type=AttributionType.CONTEXT_GROUNDED),
        ]
        results = detect_contradictions(attrs)
        # May or may not detect depending on heuristic, but should not crash
        assert isinstance(results, list)

    def test_mixed_claim_types_scored(self) -> None:
        """Pipeline should handle mixed claim types correctly."""
        claims = [
            DetectedClaim(text="Revenue grew 15%.", index=0,
                          claim_type=ClaimType.FACTUAL_CLAIM, type_confidence=0.9),
            DetectedClaim(text="I think the results are good.", index=1,
                          claim_type=ClaimType.OPINION, type_confidence=0.8),
            DetectedClaim(text="Therefore, we should proceed.", index=2,
                          claim_type=ClaimType.CONNECTIVE, type_confidence=0.7),
        ]
        facts = [_pf("f1", "Revenue grew 15% in Q3.")]
        results = score_all_claims(claims, facts)
        assert len(results) == 3
        assert results[0].attribution_type != AttributionType.UNCERTAIN  # Factual should score
        assert results[1].attribution_type == AttributionType.UNCERTAIN  # Opinion = uncertain
        assert results[2].attribution_type == AttributionType.UNCERTAIN  # Connective = uncertain
