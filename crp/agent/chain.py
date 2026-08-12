# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Cross-agent provenance linking (CRP-SPEC-012 §8; CRP-SPEC-011).

Links two sessions' HMAC provenance chains without merging them: when a
sub-agent result is consumed, its chain tip is folded into the orchestrator's
next window HMAC, and a ``SUB_AGENT_RESULT`` event records the linkage for
auditor traversal.

Relevant specifications:
  - CRP-SPEC-011: Audit Trail
  - CRP-SPEC-012: Multi-Agent Safety

PRIVATE REFERENCE IMPLEMENTATION — SPEC-012 internals are not published.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SubAgentResult:
    """A ``SUB_AGENT_RESULT`` audit event linking a sub-agent's chain (§8.1).

    Attributes:
        sub_agent_session_id: Session identifier of the sub-agent that produced
            the result.
        sub_agent_chain_tip: Independently-verified HMAC chain tip of the
            sub-agent session.
        timestamp: ISO-8601 UTC timestamp when the linkage event was created.
        event_type: Audit event type, always ``SUB_AGENT_RESULT``.
    """

    sub_agent_session_id: str
    sub_agent_chain_tip: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str = "SUB_AGENT_RESULT"

    def to_dict(self) -> dict[str, str]:
        """Serialize the event to a JSON-friendly dictionary.

        Returns:
            Dictionary with event type, sub-agent session id, chain tip, and
            timestamp.
        """
        return {
            "event_type": self.event_type,
            "sub_agent_session_id": self.sub_agent_session_id,
            "sub_agent_chain_tip": self.sub_agent_chain_tip,
            "timestamp": self.timestamp,
        }


def link_sub_agent_hmac(
    *,
    orchestrator_session_id: str,
    window_number: int,
    response_hash: str,
    prev_window_hmac: str,
    sub_agent_chain_tip: str,
    key: bytes,
) -> str:
    """Compute the orchestrator window HMAC incorporating a sub-agent tip (§8.1).

    ``HMAC-SHA256(session_id ‖ window ‖ response_hash ‖ prev_hmac ‖ sub_tip, key)``
    creates a cryptographic link between the two chains without merging them.

    Args:
        orchestrator_session_id: Identifier of the orchestrator session.
        window_number: Window index being sealed.
        response_hash: Hash of the response content for this window.
        prev_window_hmac: HMAC of the previous orchestrator window.
        sub_agent_chain_tip: HMAC chain tip from the sub-agent session.
        key: HMAC signing key.

    Returns:
        Hexadecimal HMAC-SHA256 digest linking the orchestrator window to the
        sub-agent chain.
    """
    msg = "\u241f".join(
        [
            orchestrator_session_id,
            str(window_number),
            response_hash,
            prev_window_hmac,
            sub_agent_chain_tip,
        ]
    ).encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_sub_agent_link(event: SubAgentResult, verified_chain_tip: str) -> bool:
    """Confirm a sub-agent's independently-verified tip matches the record (§8.2).

    Args:
        event: Audit event containing the recorded sub-agent chain tip.
        verified_chain_tip: Tip obtained by independently verifying the
            sub-agent's chain.

    Returns:
        True when the recorded tip equals the verified tip in constant time.
    """
    return hmac.compare_digest(event.sub_agent_chain_tip, verified_chain_tip)


def fan_in_hmac(parent_hmacs: list[str], key: bytes) -> str:
    """Merge multiple parent window HMACs into one fan-in HMAC (sorted, §3 / SPEC-004).

    Sorting makes the merge order-independent so the same set of parents always
    produces the same fan-in tip.

    Args:
        parent_hmacs: List of parent window HMACs to merge.
        key: HMAC signing key.

    Returns:
        Hexadecimal HMAC-SHA256 digest of the sorted parent tips.
    """
    concat = "\u241f".join(sorted(parent_hmacs)).encode("utf-8")
    return hmac.new(key, concat, hashlib.sha256).hexdigest()


@dataclass
class FanInQualityResult:
    """Aggregate coherence/completeness over fan-in sub-agent responses (§8.3).

    When an orchestrator merges several sub-agent results it must check that the
    combined answer is internally consistent (no cross-agent contradictions) and
    that, together, the sub-agents covered the parent query.  This reuses RQA
    Stage 6 (cross-window coherence) and Stage 8 (completeness).

    Attributes:
        coherence: Result of cross-agent coherence checking, or None if not run.
        completeness: Completeness result versus the parent query, or None.
        contradiction_count: Total number of contradictions detected across
            all pairwise comparisons.
    """

    coherence: object | None = None        # CoherenceResult across sub-agents
    completeness: object | None = None      # CompletenessResult vs parent query
    contradiction_count: int = 0

    @property
    def is_coherent(self) -> bool:
        """Return True when no contradictions were detected."""
        return self.contradiction_count == 0

    @property
    def has_critical(self) -> bool:
        """Return True if the coherence result reports a critical contradiction."""
        return bool(getattr(self.coherence, "has_critical", False))

    @property
    def headers(self) -> dict[str, str]:
        """Collect CRP headers from nested coherence/completeness results.

        Returns:
            Merged header dictionary produced by nested result objects, if any.
        """
        out: dict[str, str] = {}
        for part in (self.coherence, self.completeness):
            headers = getattr(part, "headers", None)
            if headers:
                out.update(headers)
        return out


def aggregate_sub_agent_quality(
    parent_query: str,
    sub_agent_responses: list[str],
    *,
    embedder: object | None = None,
    nli: object | None = None,
) -> FanInQualityResult:
    """Run cross-agent coherence + completeness over fan-in responses (§8.3).

    Detects contradictions *between* sub-agent responses (each response is
    checked against the ones merged before it) and verifies that the union of
    responses answers *parent_query*.  Imported lazily so :mod:`crp.agent`
    stays independent of the provenance package at import time.

    Args:
        parent_query: Original query the sub-agents were asked to address.
        sub_agent_responses: Individual response strings from each sub-agent.
        embedder: Optional embedding function for completeness verification.
        nli: Optional natural-language inference helper for contradiction
            detection.

    Returns:
        A ``FanInQualityResult`` summarising coherence, completeness, and
        contradiction counts.
    """
    from crp.provenance.rqa_stages import (
        detect_cross_window_contradictions,
        verify_completeness,
    )

    responses = [r for r in sub_agent_responses if r and r.strip()]

    # Stage 6 — cross-agent contradiction (pairwise, accumulated).
    contradictions: list = []
    worst = None
    for i, resp in enumerate(responses):
        result = detect_cross_window_contradictions(resp, responses[:i], nli=nli)
        contradictions.extend(getattr(result, "contradictions", []) or [])
        if getattr(result, "has_critical", False):
            worst = result
    coherence = worst
    if coherence is None and responses:
        # No critical contradiction found — reuse the last comparison (or a clean one).
        coherence = detect_cross_window_contradictions(
            responses[-1], responses[:-1], nli=nli
        )

    # Stage 8 — combined completeness against the parent query.
    completeness = (
        verify_completeness(parent_query, responses, embedder=embedder)
        if parent_query and responses
        else None
    )

    return FanInQualityResult(
        coherence=coherence,
        completeness=completeness,
        contradiction_count=len(contradictions),
    )
