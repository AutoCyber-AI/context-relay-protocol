# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Provenance Chain Builder — link claims → facts → windows → tasks (§7.14.3).

Constructs full provenance chains from attribution results, tracing each claim
back through the CRP pipeline:

    Claim → attributed Fact → source Window → Envelope → original Task

Also enriches FactScore objects with fact metadata (source_window_id,
extraction_stage) when a WarmStateStore or fact lookup is available.
"""

from __future__ import annotations

from typing import Any

from ._types import (
    AttributionType,
    ClaimAttribution,
    ProvenanceChain,
    ProvenanceLink,
)

# ---------------------------------------------------------------------------
# Fact metadata enrichment
# ---------------------------------------------------------------------------


def enrich_fact_metadata(
    attributions: list[ClaimAttribution],
    fact_metadata: dict[str, dict[str, Any]],
) -> None:
    """Enrich FactScore entries with fact provenance metadata (in-place).

    Args:
        attributions: List of claim attributions to enrich.
        fact_metadata: Dict mapping fact_id → metadata dict. Expected keys
            include ``source_window_id`` (str), ``extraction_stage`` (int),
            and optionally ``confidence`` (float).

    Returns:
        None. Updates ``attributed_facts`` on each attribution in place.
    """
    for attr in attributions:
        for fs in attr.attributed_facts:
            meta = fact_metadata.get(fs.fact_id, {})
            fs.fact_source_window = meta.get("source_window_id", "")
            fs.fact_extraction_stage = meta.get("extraction_stage", 0)


# ---------------------------------------------------------------------------
# Chain construction
# ---------------------------------------------------------------------------


def build_provenance_chain(
    attribution: ClaimAttribution,
    *,
    session_id: str = "",
    window_id: str = "",
    envelope_saturation: float = 0.0,
    envelope_facts_included: int = 0,
    task_input_preview: str = "",
) -> ProvenanceChain:
    """Build a full provenance chain for a single claim attribution.

    The chain traces from the claim back to its source:
        Claim → Fact → Window → Envelope → Task

    For PARAMETRIC claims (no supporting fact), the chain is shorter.

    Args:
        attribution: Scored claim attribution from attribution_scorer.
        session_id: Current session ID.
        window_id: Current window ID.
        envelope_saturation: Envelope saturation ratio.
        envelope_facts_included: Number of facts in the envelope.
        task_input_preview: First 120 chars of the task input.

    Returns:
        ``ProvenanceChain`` with linked provenance levels from claim to task.
    """
    links: list[ProvenanceLink] = []

    # Level 1: The claim itself
    links.append(ProvenanceLink(
        level="claim",
        label=f"Claim #{attribution.claim_index}: {attribution.claim_type.value}",
        detail={
            "claim_text": attribution.claim_text[:200],
            "claim_type": attribution.claim_type.value,
            "attribution_type": attribution.attribution_type.value,
            "confidence": attribution.confidence,
        },
    ))

    # Level 2: Attributed fact(s)
    if attribution.attribution_type in (
        AttributionType.CONTEXT_GROUNDED,
        AttributionType.MIXED,
    ) and attribution.attributed_facts:
        top_fact = attribution.attributed_facts[0]
        links.append(ProvenanceLink(
            level="fact",
            label=f"Fact {top_fact.fact_id[:8]}... (score: {top_fact.composite_score:.2f})",
            detail={
                "fact_id": top_fact.fact_id,
                "fact_preview": top_fact.fact_text_preview,
                "composite_score": top_fact.composite_score,
                "semantic_similarity": top_fact.semantic_similarity,
                "lexical_overlap": top_fact.lexical_overlap,
                "source_window": top_fact.fact_source_window,
                "extraction_stage": top_fact.fact_extraction_stage,
            },
        ))

        # Level 3: Source window (if known)
        if top_fact.fact_source_window:
            links.append(ProvenanceLink(
                level="window",
                label=f"Window {top_fact.fact_source_window[:8]}... (stage {top_fact.fact_extraction_stage})",
                detail={
                    "window_id": top_fact.fact_source_window,
                    "extraction_stage": top_fact.fact_extraction_stage,
                },
            ))
    elif attribution.attribution_type == AttributionType.PARAMETRIC:
        links.append(ProvenanceLink(
            level="fact",
            label="No supporting context fact (likely parametric knowledge)",
            detail={
                "attribution_type": "PARAMETRIC",
                "top_score": attribution.top_score,
                "note": "Claim appears to originate from model training data, "
                        "not from provided context.",
            },
        ))

    # Level 4: Envelope context
    links.append(ProvenanceLink(
        level="envelope",
        label=f"Envelope ({envelope_facts_included} facts, "
              f"saturation: {envelope_saturation:.0%})",
        detail={
            "window_id": window_id,
            "facts_included": envelope_facts_included,
            "saturation": round(envelope_saturation, 4),
        },
    ))

    # Level 5: Task input
    links.append(ProvenanceLink(
        level="task",
        label=f"Session {session_id[:8]}..." if session_id else "Session",
        detail={
            "session_id": session_id,
            "task_preview": task_input_preview[:120],
        },
    ))

    return ProvenanceChain(
        claim_text=attribution.claim_text[:200],
        claim_index=attribution.claim_index,
        attribution_type=attribution.attribution_type,
        links=links,
    )


def build_all_chains(
    attributions: list[ClaimAttribution],
    *,
    session_id: str = "",
    window_id: str = "",
    envelope_saturation: float = 0.0,
    envelope_facts_included: int = 0,
    task_input_preview: str = "",
) -> list[ProvenanceChain]:
    """Build provenance chains for all attributed claims.

    Args:
        attributions: All claim attributions from scorer.
        session_id: Current session ID.
        window_id: Current window ID.
        envelope_saturation: Envelope saturation ratio.
        envelope_facts_included: Facts in envelope.
        task_input_preview: First 120 chars of task input.

    Returns:
        List of ``ProvenanceChain`` objects, one per attribution.
    """
    return [
        build_provenance_chain(
            attr,
            session_id=session_id,
            window_id=window_id,
            envelope_saturation=envelope_saturation,
            envelope_facts_included=envelope_facts_included,
            task_input_preview=task_input_preview,
        )
        for attr in attributions
    ]
