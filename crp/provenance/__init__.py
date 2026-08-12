# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Decision Provenance Engine (DPE) — §7.14.3.

Orchestrates claim detection, attribution scoring, provenance chain
construction, and report generation for every LLM dispatch window.

Usage::

    from crp.provenance import DecisionProvenanceEngine, ProvenanceConfig

    dpe = DecisionProvenanceEngine(config=ProvenanceConfig())
    report = dpe.analyse(
        output_text="The server uses AES-256 encryption...",
        packed_facts=envelope_result.packed_facts,
        session_id=session.id,
        window_id=window.id,
    )
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from crp.envelope.packer import PackedFact

from ._types import (
    AttributionType,
    ClaimAttribution,
    ClaimType,
    EntailmentResult,
    FactScore,
    FidelityReport,
    HallucinationRiskReport,
    OmissionSeverity,
    ProvenanceChain,
    ProvenanceConfig,
    ProvenanceLink,
    ProvenanceReport,
)
from .amplifiers import AmplifierContext, AmplifierResult, apply_amplifiers
from .attribution_scorer import score_all_claims
from .claim_detector import DetectedClaim, detect_claims
from .contradiction_detector import detect_contradictions
from .distortion_detector import detect_distortions
from .entailment_verifier import verify_entailment
from .fabrication_detector import detect_fabrications
from .hallucination_scorer import score_hallucination_risk
from .omission_analyzer import analyze_omissions
from .provenance_chain import build_all_chains, enrich_fact_metadata
from .report_generator import generate_json_report, generate_markdown_report
from .rqa import RQAResult, RQASignals, compute_quality_score, downgrade_tier
from .rqa_stages import (
    CoherenceResult,
    CompletenessResult,
    FlowResult,
    RedispatchDecision,
    RepetitionResult,
    analyze_flow,
    detect_cross_window_contradictions,
    detect_repetition,
    evaluate_redispatch,
    verify_completeness,
)
from .window_chain import (
    ChainIntegrity,
    ChainVerification,
    WindowChainRecord,
    WindowHmacInput,
    build_fan_in_window_hmac,
    build_window_hmac,
    verify_window_chain,
    verify_window_partial,
)

__all__ = [
    "DecisionProvenanceEngine",
    "ProvenanceConfig",
    "ProvenanceReport",
    "FidelityReport",
    "ClaimAttribution",
    "ClaimType",
    "AttributionType",
    "FactScore",
    "ProvenanceChain",
    "ProvenanceLink",
    "DetectedClaim",
    "detect_claims",
    "score_all_claims",
    "build_all_chains",
    "enrich_fact_metadata",
    "generate_markdown_report",
    "generate_json_report",
    "detect_distortions",
    "detect_fabrications",
    "analyze_omissions",
    "detect_contradictions",
    "verify_entailment",
    "score_hallucination_risk",
    "EntailmentResult",
    "HallucinationRiskReport",
    "apply_amplifiers",
    "AmplifierContext",
    "AmplifierResult",
    "compute_quality_score",
    "downgrade_tier",
    "RQASignals",
    "RQAResult",
    "CoherenceResult",
    "RepetitionResult",
    "CompletenessResult",
    "FlowResult",
    "RedispatchDecision",
    "detect_cross_window_contradictions",
    "detect_repetition",
    "verify_completeness",
    "analyze_flow",
    "evaluate_redispatch",
    "collect_quality_headers",
    "ChainIntegrity",
    "ChainVerification",
    "WindowChainRecord",
    "WindowHmacInput",
    "build_fan_in_window_hmac",
    "build_window_hmac",
    "verify_window_chain",
    "verify_window_partial",
]


class DecisionProvenanceEngine:
    """Main entry point for the Decision Provenance Engine.

    Ties together claim detection → attribution scoring → provenance chain
    construction → report generation into a single ``analyse()`` call.
    """

    def __init__(self, *, config: ProvenanceConfig | None = None) -> None:
        self._config = config or ProvenanceConfig()

    # -- Properties ---------------------------------------------------------

    @property
    def config(self) -> ProvenanceConfig:
        """Current provenance configuration."""
        return self._config

    @property
    def enabled(self) -> bool:
        """Whether the DPE pipeline is enabled."""
        return self._config.enabled

    # -- Main pipeline ------------------------------------------------------

    def analyse(
        self,
        output_text: str,
        packed_facts: Sequence[PackedFact],
        *,
        session_id: str = "",
        window_id: str = "",
        envelope_saturation: float = 0.0,
        task_input_preview: str = "",
        fact_metadata: dict[str, dict[str, object]] | None = None,
        query: str = "",
        window_number: int = 1,
        prior_window_texts: Sequence[str] | None = None,
        envelope_tier: str = "",
        amplifier_context: AmplifierContext | None = None,
        upgrade_on_risk: bool = False,
        revision_round: int = 0,
        embedder: Callable[[str], Sequence[float]] | None = None,
        nli: Callable[[str, str], float] | None = None,
    ) -> ProvenanceReport:
        """Run the full DPE pipeline and return a provenance report.

        Args:
            output_text: Raw LLM output text for this window.
            packed_facts: Facts that were packed into the envelope.
            session_id: Current CRP session ID.
            window_id: Current dispatch window ID.
            envelope_saturation: Envelope token saturation ratio (0.0-1.0).
            task_input_preview: First 120 chars of the task input.
            fact_metadata: Optional mapping of fact_id → metadata dict
                           containing ``source_window_id`` and
                           ``extraction_stage`` for chain enrichment.
            query: Original task query (used for RQA completeness analysis).
            window_number: Current window number in the session.
            prior_window_texts: Previous window outputs for cross-window analysis.
            envelope_tier: Envelope quality tier assigned by the packer.
            amplifier_context: Regulatory amplifier context for risk scoring.
            upgrade_on_risk: Whether to trigger re-dispatch on elevated risk.
            revision_round: Current revision iteration count.
            embedder: Optional embedding callable for semantic RQA stages.
            nli: Optional NLI callable for contradiction detection.

        Returns:
            ``ProvenanceReport`` with attribution data, chains, fidelity, risk,
            and RQA results.
        """
        if not self._config.enabled:
            return ProvenanceReport(
                session_id=session_id,
                window_id=window_id,
                timestamp=time.time(),
            )

        facts_list = list(packed_facts)

        # Step 1: Detect claims
        claims = detect_claims(
            output_text,
            min_length=self._config.min_claim_length,
            max_claims=self._config.max_claims_per_output,
        )

        # Step 2: Score claims against facts
        attributions = score_all_claims(claims, facts_list, config=self._config)

        # Step 3: Enrich with fact metadata (if available)
        if fact_metadata:
            enrich_fact_metadata(attributions, fact_metadata)

        # Step 4: Build provenance chains
        chains = build_all_chains(
            attributions,
            session_id=session_id,
            window_id=window_id,
            envelope_saturation=envelope_saturation,
            envelope_facts_included=len(facts_list),
            task_input_preview=task_input_preview,
        )

        # Step 5: Fidelity verification
        distortions = detect_distortions(attributions, facts_list)
        omissions = analyze_omissions(attributions, facts_list)
        fabrications = detect_fabrications(attributions, facts_list)
        contradictions = detect_contradictions(attributions)

        critical_omissions = sum(
            1 for o in omissions if o.severity == OmissionSeverity.CRITICAL
        )

        # Composite fidelity score: start at 1.0, deduct for issues
        # Normalize penalties by total claims to avoid score collapse on
        # long outputs.  With 30 claims, 3 distortions should not
        # obliterate the score the same way it would for 3 claims.
        _total = max(len(attributions), 1)
        fidelity_score = 1.0
        fidelity_score -= (len(distortions) / _total) * 0.40
        fidelity_score -= (len(fabrications) / _total) * 0.35
        fidelity_score -= (critical_omissions / _total) * 0.25
        fidelity_score -= (len(contradictions) / _total) * 0.50
        fidelity_score = max(0.0, round(fidelity_score, 4))

        fidelity = FidelityReport(
            distortions=distortions,
            fabrications=fabrications,
            omissions=omissions,
            contradictions=contradictions,
            distortion_count=len(distortions),
            fabrication_count=len(fabrications),
            critical_omission_count=critical_omissions,
            contradiction_count=len(contradictions),
            fidelity_score=fidelity_score,
        )

        # Step 6: Semantic entailment verification
        entailment_results: list[EntailmentResult] = []
        if self._config.entailment_enabled:
            entailment_results = verify_entailment(
                attributions, facts_list, config=self._config,
            )

        # Step 7: Hallucination risk scoring
        risk_report: HallucinationRiskReport | None = None
        if self._config.risk_scoring_enabled:
            risk_report = score_hallucination_risk(
                attributions,
                fidelity=fidelity,
                entailment_results=entailment_results,
                config=self._config,
            )

        # Step 8: Compute counts and build report
        report = self._build_report(
            claims=claims,
            attributions=attributions,
            chains=chains,
            session_id=session_id,
            window_id=window_id,
            output_text=output_text,
            facts_count=len(facts_list),
            fidelity=fidelity,
            entailment_results=entailment_results,
            risk_report=risk_report,
        )

        # Step 9: Response Quality Assurance — Stages 6-9 (CRP-SPEC-005 §8-11)
        if self._config.rqa_enabled:
            self._run_rqa(
                report,
                output_text=output_text,
                query=query,
                window_number=window_number,
                prior_window_texts=list(prior_window_texts or []),
                envelope_tier=envelope_tier or self._fallback_tier(report),
                amplifier_context=amplifier_context,
                risk_report=risk_report,
                upgrade_on_risk=upgrade_on_risk,
                revision_round=revision_round,
                embedder=embedder,
                nli=nli,
            )

        return report

    # -- RQA pipeline (Stages 6-9) ------------------------------------------

    @staticmethod
    def _fallback_tier(report: ProvenanceReport) -> str:
        """Derive a coarse envelope tier from grounding when none was supplied.

        Args:
            report: Provenance report whose grounding ratio is used.

        Returns:
            Tier string S/A/B/C/D based on the grounding ratio.
        """
        g = report.grounding_ratio
        if g >= 0.90:
            return "S"
        if g >= 0.75:
            return "A"
        if g >= 0.50:
            return "B"
        if g >= 0.30:
            return "C"
        return "D"

    def _run_rqa(
        self,
        report: ProvenanceReport,
        *,
        output_text: str,
        query: str,
        window_number: int,
        prior_window_texts: list[str],
        envelope_tier: str,
        amplifier_context: AmplifierContext | None,
        risk_report: HallucinationRiskReport | None,
        upgrade_on_risk: bool,
        revision_round: int,
        embedder: Callable[[str], Sequence[float]] | None,
        nli: Callable[[str, str], float] | None,
    ) -> None:
        """Run RQA Stages 6-9, the composite quality score, regulatory
        amplifiers, tier downgrade, and the re-dispatch decision; attach all
        results to *report* (CRP-SPEC-005 §8-11, §17-19)."""
        # Stage 6 — cross-window coherence.
        coherence = detect_cross_window_contradictions(
            output_text, prior_window_texts, nli=nli
        )
        # Stage 7 — repetition.
        repetition = detect_repetition(output_text, prior_window_texts, embedder=embedder)
        # Stage 8 — completeness (cumulative across the session).
        all_responses = [*prior_window_texts, output_text]
        completeness = (
            verify_completeness(query, all_responses, embedder=embedder)
            if query
            else CompletenessResult(total_sub_queries=0)
        )
        # Stage 9 — flow (continuation windows only).
        prior_text = prior_window_texts[-1] if prior_window_texts else ""
        flow = analyze_flow(
            output_text, prior_text, window_number=window_number, embedder=embedder
        )

        report.coherence = coherence
        report.repetition = repetition
        report.completeness = completeness
        report.flow = flow

        # Composite quality score (§18) + tier downgrade (§18.4).
        signals = RQASignals(
            repetition_ratio=repetition.repetition_ratio,
            completeness_score=completeness.score,
            flow_score=flow.flow_score,
            contradiction_ratio=coherence.contradiction_ratio,
        )
        rqa = compute_quality_score(signals, config=self._config)
        report.rqa = rqa
        report.quality_tier = downgrade_tier(envelope_tier, rqa.quality_score)

        # Regulatory amplifiers (§17) applied to the composite hallucination score.
        if risk_report is not None and amplifier_context is not None:
            ctx = amplifier_context
            # Fold RQA-derived signals into the amplifier context.
            ctx.cross_window_contradiction = (
                ctx.cross_window_contradiction or bool(coherence.contradictions)
            )
            ctx.severe_repetition = ctx.severe_repetition or repetition.triggers_redispatch
            report.amplifier_result = apply_amplifiers(
                risk_report.mean_risk_score, ctx, config=self._config
            )

        # Re-dispatch decision (§19).
        risk_upgrade = bool(
            risk_report
            and getattr(risk_report, "window_risk_level", None)
            and str(getattr(risk_report.window_risk_level, "value", "")) in ("HIGH", "CRITICAL")
        )
        report.redispatch = evaluate_redispatch(
            repetition=repetition,
            coherence=coherence,
            flow=flow,
            risk_upgrade_triggered=risk_upgrade,
            upgrade_on_risk=upgrade_on_risk,
            revision_round=revision_round,
        )

    # -- Report assembly ----------------------------------------------------

    def _build_report(
        self,
        *,
        claims: list[DetectedClaim],
        attributions: list[ClaimAttribution],
        chains: list[ProvenanceChain],
        session_id: str,
        window_id: str,
        output_text: str,
        facts_count: int,
        fidelity: FidelityReport | None = None,
        entailment_results: list[EntailmentResult] | None = None,
        risk_report: HallucinationRiskReport | None = None,
    ) -> ProvenanceReport:
        """Assemble counts and build the ProvenanceReport."""
        # Claim type counts
        factual = sum(1 for c in claims if c.claim_type == ClaimType.FACTUAL_CLAIM)
        opinion = sum(1 for c in claims if c.claim_type == ClaimType.OPINION)
        procedural = sum(1 for c in claims if c.claim_type == ClaimType.PROCEDURAL)
        hedge = sum(1 for c in claims if c.claim_type == ClaimType.HEDGE)
        connective = sum(1 for c in claims if c.claim_type == ClaimType.CONNECTIVE)

        # Attribution type counts
        grounded = sum(
            1 for a in attributions
            if a.attribution_type == AttributionType.CONTEXT_GROUNDED
        )
        parametric = sum(
            1 for a in attributions
            if a.attribution_type == AttributionType.PARAMETRIC
        )
        mixed = sum(
            1 for a in attributions
            if a.attribution_type == AttributionType.MIXED
        )
        uncertain = sum(
            1 for a in attributions
            if a.attribution_type == AttributionType.UNCERTAIN
        )

        # Grounding ratio: context-grounded factual claims / total factual claims
        scorable = sum(
            1 for a in attributions
            if a.claim_type in (ClaimType.FACTUAL_CLAIM, ClaimType.HEDGE)
        )
        grounding_ratio = grounded / scorable if scorable > 0 else 0.0

        return ProvenanceReport(
            session_id=session_id,
            window_id=window_id,
            timestamp=time.time(),
            total_claims=len(claims),
            factual_claims=factual,
            opinion_claims=opinion,
            procedural_claims=procedural,
            hedge_claims=hedge,
            connective_claims=connective,
            context_grounded_count=grounded,
            parametric_count=parametric,
            mixed_count=mixed,
            uncertain_count=uncertain,
            grounding_ratio=round(grounding_ratio, 4),
            attributions=attributions,
            chains=chains,
            chain_verified=True,
            output_token_count=len(output_text.split()),
            envelope_facts_count=facts_count,
            fidelity=fidelity,
            entailment_results=entailment_results or [],
            risk_report=risk_report,
        )

    # -- Report formatting helpers ------------------------------------------

    def generate_markdown(self, report: ProvenanceReport) -> str:
        """Generate a human-readable markdown provenance report.

        Args:
            report: Provenance report to render.

        Returns:
            Markdown-formatted provenance report string.
        """
        return generate_markdown_report(report)

    def generate_json(self, report: ProvenanceReport) -> dict:
        """Generate a machine-readable JSON provenance report.

        Args:
            report: Provenance report to serialise.

        Returns:
            Dict representation of the provenance report.
        """
        return generate_json_report(report)


def collect_quality_headers(report: ProvenanceReport) -> dict[str, str]:
    """Merge every RQA quality/safety header emitted by the stage results.

    Includes ``CRP-Quality-Repetition`` / ``-Completeness`` / ``-Flow`` /
    ``-Score`` and ``CRP-Safety-Contradictions`` when the corresponding stage
    ran (CRP-SPEC-005 §8-11, §18, §20).
    """
    out: dict[str, str] = {}
    for stage in (
        report.coherence,
        report.repetition,
        report.completeness,
        report.flow,
        report.rqa,
    ):
        headers = getattr(stage, "headers", None)
        if headers:
            out.update(headers)
    if report.quality_tier:
        out["CRP-Context-Quality-Tier"] = report.quality_tier
    return out
