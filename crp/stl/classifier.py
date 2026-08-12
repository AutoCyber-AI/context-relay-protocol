# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""STL Operation Classifier — 8-operation taxonomy (SPEC-031 §3).

Fast semantic check: verb-anchored + keyword heuristics, sub-millisecond.
No model call required for classification.
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("crp.stl.classifier")


class STLOperation(str, Enum):
    """The ten canonical cognitive operations (SPEC-031 §3.1; CRP v5 taxonomy).

    Reconciled in CRP v5 so the STL classifier, the capability-descriptor schema
    (CRP-SPEC-050), and the operation-type headers (CRP-SPEC-049 §4.8) all share
    ONE taxonomy. ``TRANSFORM`` and ``PLAN`` were added for agentic tool use; the
    legacy schema value ``EVALUATE`` maps to ``VERIFY`` (see ``operation_from_token``).
    """

    RETRIEVE = "retrieve"           # surface facts from CKF / tools
    COMPARE = "compare"             # contrast alternatives
    ANALYSE = "analyse"             # break down structure / causes
    SYNTHESISE = "synthesise"       # combine across sources
    GENERATE = "generate"           # produce output
    VERIFY = "verify"               # check against CKF / constraints / evidence
    TRANSFORM = "transform"         # reshape or convert data between forms
    PLAN = "plan"                   # decompose into an ordered operation plan
    CLARIFY = "clarify"             # resolve ambiguity — prompt the user
    REVISE = "revise"               # correct a prior decision or output


# ── Keyword markers per operation ──────────────────────────────────────────

_RETRIEVE_MARKERS = {
    "what is", "what are", "find", "look up", "get", "fetch", "search",
    "retrieve", "who is", "when did", "where is", "how many", "list",
    "show me", "tell me about",
}

_COMPARE_MARKERS = {
    "compare", "versus", "vs", "difference", "similarities", "contrast",
    "pros and cons", "better", "worse", "advantages", "disadvantages",
    "which one", "which is", "how do they differ",
}

_ANALYSE_MARKERS = {
    "why", "how does", "implications", "causes", "reasons", "explain why",
    "root cause", "break down", "analyse", "analyze", "what factors",
    "what led to", "what drives", "underlying",
}

_SYNTHESISE_MARKERS = {
    "summarise", "summarize", "combine", "synthesize", "synthesise",
    "integrate", "pull together", "overall", "big picture", "in summary",
    "what is the main", "key takeaways",
}

_GENERATE_MARKERS = {
    "write", "create", "draft", "produce", "compose", "generate",
    "make a", "build a", "design", "formulate",
}

_VERIFY_MARKERS = {
    "verify", "check", "validate", "confirm", "is it true", "does this",
    "accuracy", "correct", "fact check", "proofread",
}

_CLARIFY_MARKERS = {
    "clarify", "explain", "what do you mean", "elaborate", "rephrase",
    "in other words", "simplify", "make it clearer", "i don't understand",
}

_REVISE_MARKERS = {
    "revise", "edit", "fix", "correct", "update", "change", "modify",
    "improve", "refine", "rewrite", "redo",
}

_TRANSFORM_MARKERS = {
    "convert", "transform", "translate", "reformat", "turn this into",
    "to json", "to csv", "to yaml", "format as", "encode", "decode",
}

_PLAN_MARKERS = {
    "plan", "create a plan", "make a plan", "checklist", "roadmap",
    "outline the steps", "devise a strategy", "step-by-step plan",
    "break this down into steps", "plan of action",
}

_ALL_MARKERS: dict[STLOperation, set[str]] = {
    STLOperation.RETRIEVE: _RETRIEVE_MARKERS,
    STLOperation.COMPARE: _COMPARE_MARKERS,
    STLOperation.ANALYSE: _ANALYSE_MARKERS,
    STLOperation.SYNTHESISE: _SYNTHESISE_MARKERS,
    STLOperation.GENERATE: _GENERATE_MARKERS,
    STLOperation.VERIFY: _VERIFY_MARKERS,
    STLOperation.TRANSFORM: _TRANSFORM_MARKERS,
    STLOperation.PLAN: _PLAN_MARKERS,
    STLOperation.CLARIFY: _CLARIFY_MARKERS,
    STLOperation.REVISE: _REVISE_MARKERS,
}


def classify_operations(user_request: str) -> list[STLOperation]:
    """Classify a user request into a sequence of cognitive operations (SPEC-031 §3.3).

    Returns a list of operations in suggested execution order.
    """
    req_lower = user_request.lower()
    scores: dict[STLOperation, float] = {}

    for op, markers in _ALL_MARKERS.items():
        score = sum(1.0 for m in markers if m in req_lower)
        if score > 0:
            scores[op] = score

    if not scores:
        # Default: treat as GENERATE if no clear signal
        logger.debug("No clear operation markers — defaulting to GENERATE")
        return [STLOperation.GENERATE]

    # Sort by score descending
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Heuristic ordering: RETRIEVE before everything else if present
    # SYNTHESISE / GENERATE typically come last
    operations = [op for op, _ in ranked]

    # Canonical ordering heuristic
    def _sort_key(op: STLOperation) -> int:
        order = [
            STLOperation.PLAN,
            STLOperation.RETRIEVE,
            STLOperation.VERIFY,
            STLOperation.CLARIFY,
            STLOperation.COMPARE,
            STLOperation.ANALYSE,
            STLOperation.TRANSFORM,
            STLOperation.SYNTHESISE,
            STLOperation.REVISE,
            STLOperation.GENERATE,
        ]
        try:
            return order.index(op)
        except ValueError:
            return 99

    operations.sort(key=_sort_key)
    logger.debug("Classified %r → %s", user_request[:60], [o.value for o in operations])
    return operations


# ── Canonical taxonomy normalisation (CRP v5 — TCF / header interop) ─────────

# Legacy / alias operation tokens accepted on input and mapped to canonical ops.
_OPERATION_ALIASES: dict[str, STLOperation] = {
    "EVALUATE": STLOperation.VERIFY,   # CRP-SPEC-050 legacy schema value
    "ASSESS": STLOperation.VERIFY,
    "EXTRACT": STLOperation.RETRIEVE,
}


def operation_from_token(token: str) -> STLOperation | None:
    """Map an operation-type token (any casing) to a canonical operation.

    Accepts the canonical names used by the capability-descriptor schema
    (CRP-SPEC-050) and the ``CRP-Agent-Operation-Type`` header (CRP-SPEC-049),
    plus legacy aliases (e.g. ``EVALUATE`` → ``VERIFY``). Returns ``None`` for
    unknown tokens so callers can skip/warn rather than crash.
    """
    if not token:
        return None
    key = token.strip().upper()
    if key in _OPERATION_ALIASES:
        return _OPERATION_ALIASES[key]
    try:
        return STLOperation[key]
    except KeyError:
        try:
            return STLOperation(token.strip().lower())
        except ValueError:
            return None


def operation_to_token(op: STLOperation) -> str:
    """Render an operation as its canonical uppercase token (schema/header form)."""
    return op.name
