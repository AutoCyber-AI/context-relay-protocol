# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Operation Frame Builder — minimal frame assembly per cognitive operation (SPEC-031 §5).

The frame is built UP from what the operation requires, not trimmed DOWN
from everything available. This is the structural token-efficiency primitive.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crp.stl.classifier import STLOperation
from crp.stl.depth_model import DepthLevel
from crp.stl.goal_compass import GoalCompass

logger = logging.getLogger("crp.stl.frame_builder")


@dataclass
class OperationFrame:
    """The minimal focused assignment that positions the model (SPEC-031 §5.1).

    Attributes:
        operation_type: Which of the 8 cognitive operations.
        assignment: The ONE thing to do, imperatively stated.
        frame_content: ONLY the context THIS operation needs.
        goal_compass: Anchored positioning for coherence.
        success_test: How the STL will judge the output.
        output_contract: Expected form of the output.
        depth: D1–D5, how far to take this operation.
    """

    operation_type: STLOperation
    assignment: str = ""
    frame_content: str = ""
    goal_compass: GoalCompass = field(default_factory=GoalCompass)
    success_test: str = ""
    output_contract: str = ""
    depth: DepthLevel = DepthLevel.D3

    def to_prompt(self) -> str:
        """Render the complete frame as a prompt for the LLM."""
        lines = [
            f"Operation: {self.operation_type.value.upper()}",
            f"Depth: {self.depth.value}",
            "",
            "Assignment:",
            self.assignment,
            "",
        ]
        if self.frame_content:
            lines.extend(["Context:", self.frame_content, ""])
        if self.goal_compass.ultimate_goal:
            lines.extend([self.goal_compass.to_prompt_text(), ""])
        if self.success_test:
            lines.extend(["Success criteria:", self.success_test, ""])
        if self.output_contract:
            lines.extend(["Output format:", self.output_contract, ""])
        return "\n".join(lines)

    @property
    def estimated_tokens(self) -> int:
        """Rough word-count estimate of the frame size."""
        total = len(self.to_prompt().split())
        return total


# Max context facts surfaced per operation, by depth (SPEC-031 §4.2). Deeper
# reasoning sees more evidence; shallow lookups see only the minimum. This is a
# real protocol control — depth changes the positioned frame, not just a label.
_DEPTH_FACT_BUDGET: dict[DepthLevel, int] = {
    DepthLevel.D1: 2,
    DepthLevel.D2: 3,
    DepthLevel.D3: 6,   # matches the previous per-op maximum → default behaviour unchanged
    DepthLevel.D4: 8,
    DepthLevel.D5: 10,  # effectively unbounded; per-op limits apply
}


def build_operation_frame(
    operation: STLOperation,
    user_request: str,
    context_facts: list[str] | None = None,
    depth: DepthLevel = DepthLevel.D3,
    goal_compass: GoalCompass | None = None,
    reasoning_guidance: str = "",
) -> OperationFrame:
    """Build a minimal Operation Frame for the given operation (SPEC-031 §5.2).

    Args:
        operation: The cognitive operation to position on.
        user_request: The original user request.
        context_facts: Retrieved facts relevant to THIS operation only.
        depth: Depth level D1–D5 — controls the evidence budget, not just a label.
        goal_compass: Pre-built compass, or None to build default.
        reasoning_guidance: Optional per-phase guidance (from a CognitivePreset
            reasoning phase) injected into this step's frame so the model reasons
            with the current phase's instructions, not just a global system prompt.
    """
    facts = context_facts or []
    compass = goal_compass or GoalCompass()

    assignment = _build_assignment(operation, user_request, depth)
    if reasoning_guidance:
        # Anchor the phase's guidance to THIS step so each reasoning phase is
        # active in the frame the model actually sees, not only listed in the
        # preset-wide system prompt.
        assignment = f"{reasoning_guidance.rstrip()}\n\n{assignment}"
    frame_content = _build_frame_content(operation, facts, depth)
    success_test = _build_success_test(operation)
    output_contract = _build_output_contract(operation)

    return OperationFrame(
        operation_type=operation,
        assignment=assignment,
        frame_content=frame_content,
        goal_compass=compass,
        success_test=success_test,
        output_contract=output_contract,
        depth=depth,
    )


# ── Frame component builders ───────────────────────────────────────────────


def _build_assignment(op: STLOperation, request: str, depth: DepthLevel) -> str:
    """Create the imperative assignment sentence."""
    if op == STLOperation.RETRIEVE:
        return f"Find and list the specific facts needed to answer: {request[:120]}"
    if op == STLOperation.COMPARE:
        return f"Compare the relevant items along clear dimensions for: {request[:120]}"
    if op == STLOperation.ANALYSE:
        return f"Analyse the subject to identify structure, causes, and implications: {request[:120]}"
    if op == STLOperation.SYNTHESISE:
        return f"Combine the provided facts into a coherent conclusion for: {request[:120]}"
    if op == STLOperation.GENERATE:
        return f"Produce the requested output following the specification: {request[:120]}"
    if op == STLOperation.VERIFY:
        return "Check the prior output against the provided evidence. Flag any unsupported claims."
    if op == STLOperation.CLARIFY:
        return f"Clarify the following ambiguity concisely: {request[:120]}"
    if op == STLOperation.REVISE:
        return "Revise the prior output, preserving what is correct and fixing what is wrong."
    if op == STLOperation.TRANSFORM:
        return f"Convert the provided data into the requested form for: {request[:120]}"
    if op == STLOperation.PLAN:
        return f"Decompose into an ordered, checkable plan of steps for: {request[:120]}"
    return f"Execute the {op.value} operation for: {request[:120]}"


def _build_frame_content(op: STLOperation, facts: list[str], depth: DepthLevel = DepthLevel.D3) -> str:
    """Assemble ONLY the context this operation needs, bounded by depth.

    Depth is an enforced evidence budget (``_DEPTH_FACT_BUDGET``): a D1 lookup
    positions the model on at most 2 candidate facts, D5 deep synthesis on up to
    8. This makes depth a real protocol control over the positioned frame.
    """
    if not facts:
        return ""
    budget = _DEPTH_FACT_BUDGET.get(depth, 5)

    if op == STLOperation.RETRIEVE:
        # RETRIEVE gets candidate facts to select from
        return "Candidate facts:\n" + "\n".join(f"- {f[:200]}" for f in facts[:min(5, budget)])

    if op == STLOperation.COMPARE:
        return "Items to compare:\n" + "\n".join(f"- {f[:200]}" for f in facts[:min(4, budget)])

    if op == STLOperation.ANALYSE:
        return "Evidence to analyse:\n" + "\n".join(f"- {f[:200]}" for f in facts[:min(6, budget)])

    if op == STLOperation.SYNTHESISE:
        return "Facts to synthesise:\n" + "\n".join(f"- {f[:200]}" for f in facts[:min(6, budget)])

    if op == STLOperation.GENERATE:
        return "Relevant background:\n" + "\n".join(f"- {f[:150]}" for f in facts[:min(4, budget)])

    if op == STLOperation.VERIFY:
        return "Claims and evidence:\n" + "\n".join(f"- {f[:200]}" for f in facts[:min(6, budget)])

    if op == STLOperation.CLARIFY:
        return "Context:\n" + "\n".join(f"- {f[:200]}" for f in facts[:min(3, budget)])

    if op == STLOperation.REVISE:
        return "Prior output and corrections:\n" + "\n".join(f"- {f[:200]}" for f in facts[:min(4, budget)])

    if op == STLOperation.TRANSFORM:
        return "Data to transform:\n" + "\n".join(f"- {f[:200]}" for f in facts[:min(4, budget)])

    if op == STLOperation.PLAN:
        return "Goals and constraints to plan around:\n" + "\n".join(f"- {f[:200]}" for f in facts[:min(6, budget)])

    return "\n".join(f"- {f[:200]}" for f in facts[:min(5, budget)])


def _build_success_test(op: STLOperation) -> str:
    """Define how the STL will judge the output."""
    tests = {
        STLOperation.RETRIEVE: "All requested facts are present and accurate.",
        STLOperation.COMPARE: "Comparison uses consistent dimensions and covers all items.",
        STLOperation.ANALYSE: "Analysis identifies structure or causes with supporting evidence.",
        STLOperation.SYNTHESISE: "Conclusion follows from the provided facts without invention.",
        STLOperation.GENERATE: "Output matches the requested format, scope, and constraints.",
        STLOperation.VERIFY: "Every claim is checked; unsupported claims are flagged explicitly.",
        STLOperation.CLARIFY: "Ambiguity is resolved without introducing new confusion.",
        STLOperation.REVISE: "Errors are fixed; correct content is preserved; tone is consistent.",
        STLOperation.TRANSFORM: "Output is the same information in the requested form, lossless.",
        STLOperation.PLAN: "Plan is ordered, complete, and each step is checkable.",
    }
    return tests.get(op, "Output is coherent, accurate, and relevant.")


def _build_output_contract(op: STLOperation) -> str:
    """Define expected output form."""
    contracts = {
        STLOperation.RETRIEVE: "Bullet list of facts with sources if known.",
        STLOperation.COMPARE: "Structured comparison (similarities, differences, conclusion).",
        STLOperation.ANALYSE: "Structured analysis (observation, evidence, implication).",
        STLOperation.SYNTHESISE: "Concise synthesis paragraph or structured conclusion.",
        STLOperation.GENERATE: "Follow the user's requested format (paragraph, table, code, etc.).",
        STLOperation.VERIFY: "Pass/fail per claim with specific evidence citations.",
        STLOperation.CLARIFY: "Short, direct clarification (1–3 sentences).",
        STLOperation.REVISE: "Full revised text with tracked changes if possible.",
        STLOperation.TRANSFORM: "The converted data in the target format only.",
        STLOperation.PLAN: "Numbered list of steps, each with a clear done-condition.",
    }
    return contracts.get(op, "Clear, relevant prose.")
