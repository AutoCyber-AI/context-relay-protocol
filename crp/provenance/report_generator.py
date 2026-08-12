# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Report Generator — human-readable provenance reports (§7.14.3).

Produces regulator-auditable decision provenance reports in markdown and
JSON formats.  Reports answer: "For each claim in the AI output, what
evidence supported it and how confident are we in that attribution?"
"""

from __future__ import annotations

import time
from typing import Any

from ._types import (
    AttributionType,
    ClaimType,
    EntailmentLabel,
    HallucinationRisk,
    OmissionSeverity,
    ProvenanceReport,
)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def generate_markdown_report(report: ProvenanceReport) -> str:
    """Generate a human-readable markdown provenance report.

    Suitable for regulatory audit, compliance review, or integration into
    documentation.  Format follows EU AI Act Article 12 logging requirements.

    Args:
        report: Complete provenance report from the DPE pipeline.

    Returns:
        Markdown-formatted report string.
    """
    lines: list[str] = []

    # Header
    lines.append("## Decision Provenance Report")
    session_short = report.session_id[:12] + "..." if len(report.session_id) > 12 else report.session_id
    window_short = report.window_id[:12] + "..." if len(report.window_id) > 12 else report.window_id
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(report.timestamp))
    lines.append(f"### Session: {session_short} | Window: {window_short} | Generated: {ts}")
    lines.append("")

    # Output summary
    lines.append("### Output Summary")
    lines.append(f"The model generated output containing **{report.total_claims}** identifiable claims.")
    lines.append(f"- {report.factual_claims} factual claims (require attribution)")
    lines.append(f"- {report.opinion_claims} opinions")
    lines.append(f"- {report.procedural_claims} procedural instructions")
    lines.append(f"- {report.hedge_claims} hedged/qualified statements")
    lines.append(f"- {report.connective_claims} connective/structural")
    lines.append("")

    # Attribution summary table
    lines.append("### Attribution Summary")
    grounding_pct = f"{report.grounding_ratio * 100:.1f}%" if report.factual_claims > 0 else "N/A"

    lines.append("")
    lines.append("| # | Claim (preview) | Type | Source | Score | Confidence |")
    lines.append("|---|-----------------|------|--------|-------|------------|")

    for i, attr in enumerate(report.attributions, 1):
        preview = attr.claim_text[:60] + "..." if len(attr.claim_text) > 60 else attr.claim_text
        preview = preview.replace("|", "\\|")
        source = attr.attribution_type.value if attr.attribution_type != AttributionType.UNCERTAIN else "—"
        score = f"{attr.top_score:.2f}" if attr.top_score > 0 else "—"
        conf = f"{attr.confidence:.2f}" if attr.confidence > 0 else "—"
        lines.append(f"| {i} | {preview} | {attr.claim_type.value} | {source} | {score} | {conf} |")

    lines.append("")

    # Grounding statistics
    lines.append("### Grounding Statistics")
    lines.append(f"- **Context-grounded claims:** {report.context_grounded_count}")
    lines.append(f"- **Parametric claims (training data):** {report.parametric_count}")
    lines.append(f"- **Mixed attribution:** {report.mixed_count}")
    lines.append(f"- **Uncertain attribution:** {report.uncertain_count}")
    lines.append(f"- **Grounding ratio:** {grounding_pct}")
    lines.append("")

    # Provenance chains
    if report.chains:
        lines.append("### Provenance Chains (Top Factual Claims)")
        for chain in report.chains:
            if chain.attribution_type in (AttributionType.CONTEXT_GROUNDED, AttributionType.MIXED):
                claim_preview = chain.claim_text[:80]
                lines.append(f"\n**Claim #{chain.claim_index}:** \"{claim_preview}...\"")
                for link in chain.links:
                    indent = "  " if link.level != "claim" else ""
                    lines.append(f"{indent}← **{link.level.upper()}:** {link.label}")
        lines.append("")

    # Integrity
    lines.append("### Provenance Chain Integrity")
    status = "✅" if report.chain_verified else "⚠️ Not verified"
    lines.append(f"- Audit chain integrity: {status}")
    lines.append(f"- Envelope facts available: {report.envelope_facts_count}")
    lines.append("")

    # Regulatory notes
    lines.append("### Regulatory Compliance Notes")
    lines.append("- **EU AI Act Art. 12:** Activity logging ✅")
    if report.factual_claims > 0:
        lines.append(
            f"- {report.context_grounded_count}/{report.factual_claims} factual claims "
            f"grounded in provided context ({grounding_pct})"
        )
    if report.parametric_count > 0:
        lines.append(
            f"- {report.parametric_count} claim(s) flagged as potentially from "
            f"parametric knowledge — may need manual verification"
        )
    if report.uncertain_count > 0:
        lines.append(
            f"- {report.uncertain_count} claim(s) with uncertain attribution "
            f"— manual review recommended"
        )
    lines.append("")

    # Fidelity verification section
    fid = report.fidelity
    if fid is not None:
        lines.append("### Fidelity Verification")
        lines.append(f"**Fidelity score:** {fid.fidelity_score:.2f} / 1.00")
        lines.append("")

        if fid.distortions:
            lines.append("#### Distortions Detected")
            lines.append("| # | Claim (preview) | Type | Severity | Detail |")
            lines.append("|---|-----------------|------|----------|--------|")
            for i, d in enumerate(fid.distortions, 1):
                preview = d.claim_text[:50].replace("|", "\\|")
                lines.append(
                    f"| {i} | {preview} | {d.distortion_type.value} "
                    f"| {d.severity:.2f} | {d.detail[:80]} |"
                )
            lines.append("")

        if fid.fabrications:
            lines.append("#### Fabrications Detected")
            lines.append("| # | Claim (preview) | Entity | Type | Severity |")
            lines.append("|---|-----------------|--------|------|----------|")
            for i, f in enumerate(fid.fabrications, 1):
                preview = f.claim_text[:50].replace("|", "\\|")
                lines.append(
                    f"| {i} | {preview} | `{f.fabricated_entity}` "
                    f"| {f.entity_type.value} | {f.severity:.2f} |"
                )
            lines.append("")

        critical_omissions = [
            o for o in fid.omissions
            if o.severity in (OmissionSeverity.CRITICAL, OmissionSeverity.HIGH)
        ]
        if critical_omissions:
            lines.append("#### Critical/High Omissions")
            lines.append("| # | Fact (preview) | Relevance | Severity |")
            lines.append("|---|----------------|-----------|----------|")
            for i, o in enumerate(critical_omissions, 1):
                preview = o.fact_text_preview[:60].replace("|", "\\|")
                lines.append(
                    f"| {i} | {preview} | {o.fact_relevance_score:.2f} "
                    f"| {o.severity.value} |"
                )
            lines.append("")

        if fid.contradictions:
            lines.append("#### Contradictions Detected")
            for i, c in enumerate(fid.contradictions, 1):
                lines.append(
                    f"{i}. **{c.contradiction_type}** (severity {c.severity:.2f}): "
                    f"Claim #{c.claim_a_index} vs Claim #{c.claim_b_index} — {c.detail[:120]}"
                )
            lines.append("")

        if not (fid.distortions or fid.fabrications or critical_omissions or fid.contradictions):
            lines.append("No fidelity issues detected. ✅")
            lines.append("")

    # Semantic entailment section
    if report.entailment_results:
        lines.append("### Semantic Entailment Verification")
        contradictions = [
            er for er in report.entailment_results
            if er.label == EntailmentLabel.CONTRADICTION
        ]
        if contradictions:
            lines.append(f"**{len(contradictions)} semantic contradiction(s) detected** ⚠️")
            lines.append("")
            lines.append("| # | Claim (preview) | vs Fact | P(contra) | P(entail) | Method |")
            lines.append("|---|-----------------|---------|-----------|-----------|--------|")
            for i, er in enumerate(contradictions, 1):
                preview = er.claim_text[:50].replace("|", "\\|")
                method = "NLI model" if er.used_model else "Heuristic"
                lines.append(
                    f"| {i} | {preview} | {er.fact_id[:12]} "
                    f"| {er.contradiction_score:.2f} | {er.entailment_score:.2f} "
                    f"| {method} |"
                )
            lines.append("")
        else:
            entailed = sum(
                1 for er in report.entailment_results
                if er.label == EntailmentLabel.ENTAILED
            )
            lines.append(
                f"All {len(report.entailment_results)} claim-fact pairs checked. "
                f"{entailed} entailed, 0 contradictions. ✅"
            )
            lines.append("")

    # Hallucination risk section
    risk = report.risk_report
    if risk is not None and risk.assessments:
        lines.append("### Hallucination Risk Assessment")
        risk_emoji = {
            HallucinationRisk.LOW: "🟢",
            HallucinationRisk.MEDIUM: "🟡",
            HallucinationRisk.HIGH: "🟠",
            HallucinationRisk.CRITICAL: "🔴",
        }
        lines.append(
            f"**Window risk level:** {risk_emoji.get(risk.window_risk_level, '')} "
            f"{risk.window_risk_level.value} "
            f"(mean score: {risk.mean_risk_score:.2f})"
        )
        if risk.critical_risk_count > 0:
            lines.append(f"- **{risk.critical_risk_count}** CRITICAL risk claim(s)")
        if risk.high_risk_count > 0:
            lines.append(f"- **{risk.high_risk_count}** HIGH risk claim(s)")
        lines.append("")

        # Show high/critical risk claims
        high_risk = [
            a for a in risk.assessments
            if a.risk_level in (HallucinationRisk.HIGH, HallucinationRisk.CRITICAL)
        ]
        if high_risk:
            lines.append("#### High/Critical Risk Claims")
            lines.append("| # | Claim (preview) | Risk | Score | Factors |")
            lines.append("|---|-----------------|------|-------|---------|")
            for a in high_risk:
                preview = a.claim_text[:50].replace("|", "\\|")
                factors = "; ".join(a.risk_factors[:3])
                lines.append(
                    f"| {a.claim_index} | {preview} "
                    f"| {a.risk_level.value} | {a.risk_score:.2f} "
                    f"| {factors[:100]} |"
                )
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------


def generate_json_report(report: ProvenanceReport) -> dict[str, Any]:
    """Generate a machine-readable JSON provenance report.

    Suitable for API responses, database storage, or integration with
    compliance management systems.

    Args:
        report: Complete provenance report from the DPE pipeline.

    Returns:
        JSON-serializable dictionary.
    """
    return {
        "report_type": "decision_provenance",
        "version": "1.0.0",
        "session_id": report.session_id,
        "window_id": report.window_id,
        "timestamp": report.timestamp,
        "summary": {
            "total_claims": report.total_claims,
            "factual_claims": report.factual_claims,
            "opinion_claims": report.opinion_claims,
            "procedural_claims": report.procedural_claims,
            "hedge_claims": report.hedge_claims,
            "connective_claims": report.connective_claims,
            "context_grounded": report.context_grounded_count,
            "parametric": report.parametric_count,
            "mixed": report.mixed_count,
            "uncertain": report.uncertain_count,
            "grounding_ratio": report.grounding_ratio,
        },
        "attributions": [
            {
                "claim_text": attr.claim_text[:200],
                "claim_index": attr.claim_index,
                "claim_type": attr.claim_type.value,
                "attribution_type": attr.attribution_type.value,
                "top_score": attr.top_score,
                "confidence": attr.confidence,
                "top_facts": [
                    {
                        "fact_id": fs.fact_id,
                        "fact_preview": fs.fact_text_preview,
                        "semantic_similarity": fs.semantic_similarity,
                        "lexical_overlap": fs.lexical_overlap,
                        "composite_score": fs.composite_score,
                        "source_window": fs.fact_source_window,
                        "extraction_stage": fs.fact_extraction_stage,
                    }
                    for fs in attr.attributed_facts[:3]
                ],
            }
            for attr in report.attributions
        ],
        "chains": [
            {
                "claim_text": chain.claim_text[:200],
                "claim_index": chain.claim_index,
                "attribution_type": chain.attribution_type.value,
                "links": [
                    {
                        "level": link.level,
                        "label": link.label,
                        "detail": link.detail,
                    }
                    for link in chain.links
                ],
            }
            for chain in report.chains
        ],
        "integrity": {
            "chain_verified": report.chain_verified,
            "envelope_facts_count": report.envelope_facts_count,
            "output_token_count": report.output_token_count,
        },
        "fidelity": _serialize_fidelity(report.fidelity),
        "entailment": [
            {
                "claim_index": er.claim_index,
                "claim_text": er.claim_text[:200],
                "fact_id": er.fact_id,
                "label": er.label.value,
                "confidence": er.confidence,
                "entailment_score": er.entailment_score,
                "contradiction_score": er.contradiction_score,
                "neutral_score": er.neutral_score,
                "used_model": er.used_model,
            }
            for er in report.entailment_results
        ],
        "risk_assessment": _serialize_risk(report.risk_report),
    }


def _serialize_risk(risk: object) -> dict[str, object] | None:
    """Serialize HallucinationRiskReport for JSON output."""
    if risk is None:
        return None
    return {
        "window_risk_level": risk.window_risk_level.value,  # type: ignore[union-attr]
        "mean_risk_score": risk.mean_risk_score,  # type: ignore[union-attr]
        "high_risk_count": risk.high_risk_count,  # type: ignore[union-attr]
        "critical_risk_count": risk.critical_risk_count,  # type: ignore[union-attr]
        "assessments": [
            {
                "claim_index": a.claim_index,
                "claim_text": a.claim_text[:200],
                "risk_level": a.risk_level.value,
                "risk_score": a.risk_score,
                "attribution_signal": a.attribution_signal,
                "fidelity_signal": a.fidelity_signal,
                "entailment_signal": a.entailment_signal,
                "specificity_signal": a.specificity_signal,
                "risk_factors": a.risk_factors,
            }
            for a in risk.assessments  # type: ignore[union-attr]
        ],
    }


def _serialize_fidelity(fid: object) -> dict[str, Any] | None:
    """Serialize FidelityReport for JSON output."""
    if fid is None:
        return None
    # fid is a FidelityReport but we avoid import cycle via duck typing
    return {
        "fidelity_score": fid.fidelity_score,  # type: ignore[union-attr]
        "distortion_count": fid.distortion_count,  # type: ignore[union-attr]
        "fabrication_count": fid.fabrication_count,  # type: ignore[union-attr]
        "critical_omission_count": fid.critical_omission_count,  # type: ignore[union-attr]
        "contradiction_count": fid.contradiction_count,  # type: ignore[union-attr]
        "distortions": [
            {
                "claim_index": d.claim_index,
                "claim_text": d.claim_text[:200],
                "distortion_type": d.distortion_type.value,
                "severity": d.severity,
                "detail": d.detail,
                "claim_value": d.claim_value,
                "fact_value": d.fact_value,
            }
            for d in fid.distortions  # type: ignore[union-attr]
        ],
        "fabrications": [
            {
                "claim_index": f.claim_index,
                "claim_text": f.claim_text[:200],
                "fabricated_entity": f.fabricated_entity,
                "entity_type": f.entity_type.value,
                "severity": f.severity,
            }
            for f in fid.fabrications  # type: ignore[union-attr]
        ],
        "omissions": [
            {
                "fact_id": o.fact_id,
                "fact_text_preview": o.fact_text_preview[:120],
                "relevance_score": o.fact_relevance_score,
                "severity": o.severity.value,
            }
            for o in fid.omissions  # type: ignore[union-attr]
        ],
        "contradictions": [
            {
                "claim_a_index": c.claim_a_index,
                "claim_b_index": c.claim_b_index,
                "contradiction_type": c.contradiction_type,
                "severity": c.severity,
                "detail": c.detail,
            }
            for c in fid.contradictions  # type: ignore[union-attr]
        ],
    }
