# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""STL Orchestrator — the full positioning execution cycle (SPEC-031 §7).

1. RECEIVE user request
2. CLASSIFY → sequence of operations
3. PROPOSE depth
4. DECOMPOSE into operation plan
5. FOR each operation: BUILD frame → POSITION model → VERIFY → INTEGRATE
6. ASSEMBLE final response
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from crp.stl.classifier import STLOperation, classify_operations
from crp.stl.depth_model import DepthLevel, negotiate_depth, renegotiate_depth
from crp.stl.frame_builder import OperationFrame, build_operation_frame
from crp.stl.goal_compass import build_goal_compass

logger = logging.getLogger("crp.stl.orchestrator")


@dataclass
class STLResult:
    """The result of an STL execution cycle."""

    text: str = ""
    operations_executed: list[str] = field(default_factory=list)
    depth_proposed: str = ""
    depth_final: str = ""
    frame_tokens_total: int = 0
    injection_equivalent_tokens: int = 0  # for Frame-Vs-Inject ratio
    renegotiations: int = 0
    headers: dict[str, str] = field(default_factory=dict)


def stl_execute(
    user_request: str,
    session: Any,
    context_facts: list[str] | None = None,
) -> STLResult:
    """Execute the full STL positioning cycle (SPEC-031 §7.1).

    Args:
        user_request: The user's natural-language request.
        session: CRP session object (for CSO integration, etc.).
        context_facts: Optional pre-retrieved facts from CKF.

    Returns:
        STLResult with assembled text, operation log, and efficiency metrics.
    """
    facts = context_facts or []
    result = STLResult()

    # ── 2. CLASSIFY ──
    operations = classify_operations(user_request)
    result.operations_executed = [op.value for op in operations]

    # ── 3. PROPOSE depth ──
    depth, depth_meta = negotiate_depth(user_request, operations)
    result.depth_proposed = depth.value
    result.depth_final = depth.value

    # Estimate injection-equivalent tokens (full context dump)
    injection_equiv = _estimate_injection_tokens(user_request, facts)
    result.injection_equivalent_tokens = injection_equiv

    # ── 4. DECOMPOSE & 5. EXECUTE operations ──
    operation_outputs: list[str] = []
    prior_ops: list[str] = []
    renegotiation_count = 0

    for idx, op in enumerate(operations, start=1):
        # Build goal-compass
        compass = build_goal_compass(op.value, user_request, prior_ops)

        # Build minimal frame
        frame = build_operation_frame(
            operation=op,
            user_request=user_request,
            context_facts=facts,
            depth=depth,
            goal_compass=compass,
        )
        result.frame_tokens_total += frame.estimated_tokens

        # POSITION the model (simulated — real call goes to provider)
        logger.debug("Positioning on %s (%d/%d)", op.value, idx, len(operations))
        output = _simulate_positioned_call(frame, session)
        operation_outputs.append(output)
        prior_ops.append(op.value)

        # VERIFY output (placeholder — DPE integration in production)
        # INTEGRATE into CSO (placeholder — CSO relay integration)

        # RENEGOTIATE depth if needed (heuristic trigger)
        if _should_renegotiate(output, depth):
            depth, reneg_meta = renegotiate_depth(depth, "unresolved-complexity", renegotiation_count)
            if reneg_meta.get("renegotiated"):
                renegotiation_count += 1
                result.depth_final = depth.value
                result.renegotiations = renegotiation_count

    # ── 6. ASSEMBLE final response ──
    result.text = _assemble_response(user_request, operations, operation_outputs)

    # ── 8. HEADERS ──
    frame_vs_inject = (
        round(result.frame_tokens_total / max(result.injection_equivalent_tokens, 1), 2)
        if result.injection_equivalent_tokens > 0
        else 0.0
    )
    result.headers = {
        "CRP-STL-Operations": ",".join(result.operations_executed),
        "CRP-STL-Operation-Current": f"{operations[-1].value}/{len(operations)}" if operations else "none",
        "CRP-STL-Depth-Proposed": result.depth_proposed,
        "CRP-STL-Depth-Final": result.depth_final,
        "CRP-STL-Frame-Tokens": str(result.frame_tokens_total),
        "CRP-STL-Frame-Vs-Inject": str(frame_vs_inject),
        "CRP-STL-Goal-Compass-Tokens": str(sum(
            build_goal_compass(op.value, user_request, prior_ops).token_estimate()
            for op in operations
        )),
    }

    logger.info(
        "STL completed: %d ops, depth %s→%s, frame %d tok vs inject %d tok (ratio %s)",
        len(operations),
        result.depth_proposed,
        result.depth_final,
        result.frame_tokens_total,
        result.injection_equivalent_tokens,
        frame_vs_inject,
    )
    return result


# ── Internal helpers ───────────────────────────────────────────────────────


def _estimate_injection_tokens(request: str, facts: list[str]) -> int:
    """Estimate what full context injection would have cost."""
    # Rough: user request + all facts + system overhead
    total = len(request.split())
    for f in facts:
        total += len(f.split())
    # Add overhead for prose wrapping
    total += 200
    return total


def _simulate_positioned_call(frame: OperationFrame, session: Any) -> str:
    """Simulate a positioned LLM call.

    In production this dispatches to the configured provider with the frame
    as the prompt. For the STL layer, we return a placeholder that shows the
    frame was constructed correctly.
    """
    # The real implementation would do:
    #   output = session.provider.generate_chat(frame.to_prompt())
    # Here we return a minimal placeholder for unit testing.
    return f"[{frame.operation_type.value.upper()} output at {frame.depth.value}]"


def _should_renegotiate(output: str, current_depth: DepthLevel) -> bool:
    """Heuristic: trigger renegotiation if output signals unresolved complexity."""
    # In production, DPE completeness_score < threshold triggers this.
    # Simplified heuristic for the scaffold:
    uncertainty_markers = {"unclear", "ambiguous", "insufficient", "need more", "complex"}
    return any(m in output.lower() for m in uncertainty_markers)


def _assemble_response(
    request: str,
    operations: list[STLOperation],
    outputs: list[str],
) -> str:
    """Assemble final response from operation outputs."""
    if not outputs:
        return ""
    if len(outputs) == 1:
        return outputs[0]

    # Multi-operation: join with section headers
    parts: list[str] = []
    for op, out in zip(operations, outputs):
        parts.append(f"## {op.value.upper()}\n{out}")
    return "\n\n".join(parts)
