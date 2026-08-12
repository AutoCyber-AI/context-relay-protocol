# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Goal Compass — anchored positioning for global coherence (SPEC-031 §6).

Three sentences (~60–100 tokens) that keep locally-focused operations
globally coherent without re-injecting full context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("crp.stl.goal_compass")


@dataclass
class GoalCompass:
    """The minimal anchor that prevents incoherence across operations (SPEC-031 §6.2).

    Attributes:
        ultimate_goal: One sentence — what the user ultimately wants.
        this_operation_serves: One sentence — how THIS operation contributes.
        fit_constraint: One sentence — what makes this output fit the whole.
    """

    ultimate_goal: str = ""
    this_operation_serves: str = ""
    fit_constraint: str = ""

    def to_prompt_text(self) -> str:
        """Render as compact prompt text."""
        lines = [
            "Goal context:",
            f"- Ultimate goal: {self.ultimate_goal}",
            f"- This operation produces: {self.this_operation_serves}",
            f"- Fit constraint: {self.fit_constraint}",
        ]
        return "\n".join(lines)

    def token_estimate(self) -> int:
        """Rough token count for the compass."""
        total = len(self.ultimate_goal.split())
        total += len(self.this_operation_serves.split())
        total += len(self.fit_constraint.split())
        return total


def build_goal_compass(
    operation: str,
    user_request: str,
    prior_operations: list[str] | None = None,
) -> GoalCompass:
    """Construct a goal-compass for the current operation (SPEC-031 §6).

    Args:
        operation: The STL operation name, e.g. "ANALYSE".
        user_request: The original user request.
        prior_operations: List of already-completed operations.
    """
    prior = prior_operations or []

    ultimate_goal = _summarise_ultimate_goal(user_request)
    this_serves = _describe_operation_contribution(operation, prior, user_request)
    fit = _describe_fit_constraint(operation, prior)

    return GoalCompass(
        ultimate_goal=ultimate_goal,
        this_operation_serves=this_serves,
        fit_constraint=fit,
    )


# ── Compass sentence builders ──────────────────────────────────────────────


def _summarise_ultimate_goal(request: str) -> str:
    """Extract the ultimate goal in one sentence."""
    # Heuristic: remove filler, keep the core ask
    req = request.strip()
    if req.endswith("?"):
        return f"Answer the user's question: {req}"
    if any(v in req.lower() for v in ("write", "create", "draft", "produce")):
        return f"Produce the requested deliverable: {req[:100]}"
    return f"Satisfy the user's request: {req[:100]}"


def _describe_operation_contribution(
    operation: str, prior: list[str], request: str
) -> str:
    """Describe how this specific operation contributes to the whole."""
    op = operation.upper()
    if op == "RETRIEVE":
        return "Gather the specific facts and evidence needed for subsequent operations."
    if op == "ANALYSE":
        return "Examine the gathered facts for structure, causes, and implications."
    if op == "COMPARE":
        return "Contrast the relevant alternatives to support a decision."
    if op == "SYNTHESISE":
        return "Combine findings into coherent intermediate conclusions."
    if op == "GENERATE":
        if prior:
            return f"Produce the final output based on {len(prior)} prior operation(s)."
        return "Produce the final output matching the user's specification."
    if op == "VERIFY":
        return "Check prior findings against available evidence for accuracy."
    if op == "CLARIFY":
        return "Resolve ambiguity so subsequent operations can proceed accurately."
    if op == "REVISE":
        return "Correct or refine prior output based on new information or feedback."
    return f"Execute the {op} step toward the overall goal."


def _describe_fit_constraint(operation: str, prior: list[str]) -> str:
    """Describe what makes this output fit the whole."""
    op = operation.upper()
    if op == "RETRIEVE":
        return "Facts must be relevant to the specific sub-question, not tangential."
    if op == "ANALYSE":
        return "Analysis must use the same framing and definitions as prior sections."
    if op == "COMPARE":
        return "Comparison must use consistent dimensions and criteria."
    if op == "SYNTHESISE":
        return "Synthesis must acknowledge uncertainty where evidence is weak."
    if op == "GENERATE":
        return "Final output must follow the user's requested format, tone, and constraints."
    if op == "VERIFY":
        return "Verification must cite specific evidence, not general confidence."
    if op == "CLARIFY":
        return "Clarification must resolve without introducing new ambiguity."
    if op == "REVISE":
        return "Revision must preserve what was correct while fixing what was wrong."
    return "Output must be consistent with prior operations and the overall goal."
