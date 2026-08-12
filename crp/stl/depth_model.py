# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""STL Depth Model — D1–D5 depth negotiation (SPEC-031 §4).

Depth is negotiated: proposed, executed, and revised mid-flight if needed.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from crp.stl.classifier import STLOperation

logger = logging.getLogger("crp.stl.depth_model")

MAX_DEPTH_RENEGOTIATIONS = 2


class DepthLevel(str, Enum):
    """Five depth levels (SPEC-031 §4.2)."""

    D1 = "D1"  # Lookup — single RETRIEVE
    D2 = "D2"  # Composition — RETRIEVE + SYNTHESISE
    D3 = "D3"  # Examination — + ANALYSE / COMPARE / VERIFY
    D4 = "D4"  # Investigation — multi-pass, cross-checking
    D5 = "D5"  # Deep synthesis — full decomposition, revision loops


# ── Depth proposal signals ─────────────────────────────────────────────────


def _detect_explicit_depth(request: str) -> DepthLevel | None:
    """Check for explicit depth cues in the request."""
    req_lower = request.lower()
    shallow_markers = {"briefly", "quickly", "short", "simple", "just", "only"}
    deep_markers = {
        "thorough", "exhaustive", "deep", "comprehensive", "detailed",
        "in depth", "fully", "rigorous", "extensive",
    }
    if any(m in req_lower for m in shallow_markers):
        return DepthLevel.D1
    if any(m in req_lower for m in deep_markers):
        return DepthLevel.D4
    return None


def _operation_complexity(operations: list[STLOperation]) -> DepthLevel:
    """Infer depth from the operation mix."""
    op_set = set(operations)
    if op_set == {STLOperation.RETRIEVE}:
        return DepthLevel.D1
    if op_set <= {STLOperation.RETRIEVE, STLOperation.SYNTHESISE, STLOperation.CLARIFY}:
        return DepthLevel.D2
    if STLOperation.ANALYSE in op_set or STLOperation.COMPARE in op_set:
        return DepthLevel.D3
    if STLOperation.VERIFY in op_set and len(op_set) > 2:
        return DepthLevel.D4
    return DepthLevel.D3


def _count_distinct_subjects(request: str) -> int:
    """Rough count of distinct subjects (nouns) in request."""
    # Simplified: count capitalised words and quoted phrases
    import re
    quoted = re.findall(r'"([^"]+)"', request)
    return max(1, len(quoted))


def _detect_stakes(request: str) -> float:
    """Detect if request implies high stakes (regulator, medical, legal)."""
    high_stakes = {
        "regulator", "compliance", "audit", "medical", "clinical",
        "legal", "lawsuit", "contract", "financial", "investment",
    }
    req_lower = request.lower()
    return 1.0 if any(s in req_lower for s in high_stakes) else 0.0


# ── Public API ─────────────────────────────────────────────────────────────


def negotiate_depth(
    request: str,
    operations: list[STLOperation],
    current_depth: DepthLevel | None = None,
    renegotiation_count: int = 0,
) -> tuple[DepthLevel, dict[str, Any]]:
    """Propose initial depth and return metadata (SPEC-031 §4.3).

    Returns:
        (proposed_depth, metadata_dict)
    """
    if current_depth is not None and renegotiation_count >= MAX_DEPTH_RENEGOTIATIONS:
        logger.info("Depth renegotiation capped at %d — committing to %s", MAX_DEPTH_RENEGOTIATIONS, current_depth.value)
        return current_depth, {"renegotiated": False, "reason": "max-renegotiations-reached"}

    explicit = _detect_explicit_depth(request)
    if explicit is not None:
        depth = explicit
    else:
        depth = _operation_complexity(operations)
        # Broad scope pushes depth up
        if _count_distinct_subjects(request) >= 3:
            depth = _bump_depth(depth)
        # High stakes pushes depth up
        if _detect_stakes(request) > 0.5:
            depth = _bump_depth(depth)

    meta = {
        "renegotiated": renegotiation_count > 0,
        "renegotiation_count": renegotiation_count,
        "reason": "initial-proposal" if renegotiation_count == 0 else "renegotiation",
    }
    logger.debug("Proposed depth %s for request %r", depth.value, request[:60])
    return depth, meta


def renegotiate_depth(
    current_depth: DepthLevel,
    reason: str,
    renegotiation_count: int = 0,
) -> tuple[DepthLevel, dict[str, Any]]:
    """Revise depth mid-execution (SPEC-031 §4.4).

    Reasons:
        "unresolved-complexity" → deepen
        "high-confidence-fast" → shallow
    """
    if renegotiation_count >= MAX_DEPTH_RENEGOTIATIONS:
        return current_depth, {"renegotiated": False, "reason": "capped"}

    if reason in ("unresolved-complexity", "contradiction-found", "goal-divergence"):
        new_depth = _bump_depth(current_depth)
        meta = {"renegotiated": True, "direction": "deepen", "reason": reason}
    elif reason in ("high-confidence-fast", "simpler-than-expected"):
        new_depth = _lower_depth(current_depth)
        meta = {"renegotiated": True, "direction": "shallow", "reason": reason}
    else:
        new_depth = current_depth
        meta = {"renegotiated": False, "reason": reason}

    logger.info("Depth renegotiated %s → %s (%s)", current_depth.value, new_depth.value, reason)
    return new_depth, meta


# ── Helpers ────────────────────────────────────────────────────────────────


def _bump_depth(d: DepthLevel) -> DepthLevel:
    order = [DepthLevel.D1, DepthLevel.D2, DepthLevel.D3, DepthLevel.D4, DepthLevel.D5]
    idx = order.index(d)
    return order[min(idx + 1, len(order) - 1)]


def _lower_depth(d: DepthLevel) -> DepthLevel:
    order = [DepthLevel.D1, DepthLevel.D2, DepthLevel.D3, DepthLevel.D4, DepthLevel.D5]
    idx = order.index(d)
    return order[max(idx - 1, 0)]
