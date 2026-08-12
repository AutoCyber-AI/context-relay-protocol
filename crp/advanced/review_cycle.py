# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Review cycle management — active LLM review patterns (§14).

Three interaction patterns:
  1. Pre-generation planning (predict chain > 5 windows)
  2. Checkpoint review (periodic, Tier 3 models only)
  3. Post-generation self-assessment (quality scoring + targeted re-gen)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ReviewGuidance:
    """Output from a checkpoint review."""

    on_track: bool = True
    contradictions: list[str] = field(default_factory=list)
    priorities: list[str] = field(default_factory=list)
    new_gaps: list[str] = field(default_factory=list)
    raw_output: str = ""


@dataclass
class AssessmentResult:
    """Output from post-generation self-assessment."""

    score: float = 0.0  # 0-10
    issues: list[str] = field(default_factory=list)
    needs_correction: bool = False
    corrections_applied: int = 0
    raw_output: str = ""


@dataclass
class PlannedSection:
    """One section in the generation plan."""

    title: str = ""
    key_points: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    estimated_tokens: int = 0


@dataclass
class DocumentPlan:
    """Full generation plan from pre-generation planning."""

    sections: list[PlannedSection] = field(default_factory=list)
    total_estimated_tokens: int = 0
    estimated_windows: int = 0


# ---------------------------------------------------------------------------
# ReviewCycleManager
# ---------------------------------------------------------------------------


class ReviewCycleManager:
    """Active LLM review cycles — planning, checkpoint, assessment."""

    def __init__(
        self,
        dispatch_fn: Callable[[str, str], tuple[str, Any]] | None = None,
        model_review_capability: int = 1,
        correction_mode: str = "flag",
        max_correction_windows: int = 3,
    ) -> None:
        self._dispatch_fn = dispatch_fn
        self._model_capability = model_review_capability
        self._correction_mode = correction_mode
        self._max_corrections = max_correction_windows

    # ------------------------------------------------------------------
    # 1. Pre-generation planning
    # ------------------------------------------------------------------

    def pre_generation_plan(
        self,
        task_intent: str,
        predicted_chain_length: int = 0,
    ) -> DocumentPlan | None:
        """Generate document plan when chain > 5 windows.

        Returns None if chain is short or no dispatch_fn.
        """
        if predicted_chain_length <= 5:
            return None
        if not self._dispatch_fn:
            return None

        prompt = (
            "Create an outline for the following task. For each section provide:\n"
            "- Section title\n"
            "- 2-3 key points to cover\n"
            "- Dependencies on other sections\n\n"
            f"Task: {task_intent}\n"
            f"Estimated length: {predicted_chain_length} windows\n\n"
            "Format: numbered sections."
        )

        try:
            output, _ = self._dispatch_fn(prompt, "")
        except Exception:
            return None

        return self._parse_plan(output, predicted_chain_length)

    def _parse_plan(self, output: str, windows: int) -> DocumentPlan:
        """Parse LLM output into a DocumentPlan."""
        sections: list[PlannedSection] = []
        current_title = ""
        current_points: list[str] = []

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            # New section: starts with number
            if re.match(r"\d+[\.\)]\s", line):
                if current_title:
                    sections.append(PlannedSection(
                        title=current_title,
                        key_points=current_points,
                    ))
                current_title = re.sub(r"^\d+[\.\)]\s*", "", line)
                current_points = []
            elif line.startswith("-") or line.startswith("•"):
                current_points.append(line.lstrip("-•").strip())

        if current_title:
            sections.append(PlannedSection(
                title=current_title,
                key_points=current_points,
            ))

        return DocumentPlan(
            sections=sections,
            estimated_windows=windows,
        )

    # ------------------------------------------------------------------
    # 2. Checkpoint review
    # ------------------------------------------------------------------

    def checkpoint_review(
        self,
        window_index: int,
        review_interval: int = 20,
        task_intent: str = "",
        top_facts: list[str] | None = None,
        gap_summary: str = "",
    ) -> ReviewGuidance | None:
        """Periodic review at checkpoint windows.

        Gate: model_capability < 3 → None
        Gate: window_index not at interval → None
        """
        if self._model_capability < 3:
            return None
        if window_index % review_interval != 0:
            return None
        if not self._dispatch_fn:
            return None

        facts_section = ""
        if top_facts:
            facts_section = "\n".join(f"- {f}" for f in top_facts[:30])

        prompt = (
            "Review checkpoint. Assess the following:\n"
            "1. Are we on track for the task?\n"
            "2. Any contradictions in the findings?\n"
            "3. What should be prioritized next?\n"
            "4. Any new gaps identified?\n\n"
            f"Task: {task_intent}\n\n"
            f"Key facts so far:\n{facts_section}\n\n"
            f"Gap summary: {gap_summary}\n\n"
            "Be concise."
        )

        try:
            output, _ = self._dispatch_fn(prompt, "")
        except Exception:
            return None

        return self._parse_review(output)

    def _parse_review(self, output: str) -> ReviewGuidance:
        """Parse checkpoint review output."""
        guidance = ReviewGuidance(raw_output=output)
        lines = output.split("\n")
        for line in lines:
            line_lower = line.lower().strip()
            if "not on track" in line_lower or "off track" in line_lower:
                guidance.on_track = False
            if "contradict" in line_lower:
                guidance.contradictions.append(line.strip())
            if "priorit" in line_lower or "next" in line_lower:
                guidance.priorities.append(line.strip())
            if "gap" in line_lower or "missing" in line_lower:
                guidance.new_gaps.append(line.strip())
        return guidance

    # ------------------------------------------------------------------
    # 3. Post-generation self-assessment
    # ------------------------------------------------------------------

    def post_generation_assessment(
        self,
        accumulated_output: str,
        task_intent: str,
    ) -> AssessmentResult:
        """Score output quality and flag issues.

        Weak model → basic heuristic scoring.
        Strong model → full LLM self-assessment.
        """
        if self._model_capability < 3 or not self._dispatch_fn:
            return self._heuristic_assessment(accumulated_output, task_intent)

        prompt = (
            "Score the following output on a scale of 1-10 for completeness, "
            "accuracy, and coherence. Start your response with 'SCORE: X/10'. "
            "Then list any issues as numbered items.\n\n"
            f"Task: {task_intent}"
        )

        try:
            output, _ = self._dispatch_fn(prompt, accumulated_output[:5000])
        except Exception:
            return self._heuristic_assessment(accumulated_output, task_intent)

        return self._parse_assessment(output)

    def _parse_assessment(self, output: str) -> AssessmentResult:
        """Parse LLM assessment output."""
        result = AssessmentResult(raw_output=output)

        # Extract score
        score_match = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*10", output, re.IGNORECASE)
        if score_match:
            result.score = float(score_match.group(1))
        else:
            result.score = 5.0  # Default if can't parse

        # Extract issues
        for line in output.split("\n"):
            line = line.strip()
            if re.match(r"\d+\.", line):
                result.issues.append(re.sub(r"^\d+\.\s*", "", line))

        result.needs_correction = (
            result.score < 6
            and self._correction_mode == "correct"
        )

        return result

    def _heuristic_assessment(
        self, output: str, task_intent: str,
    ) -> AssessmentResult:
        """Basic quality scoring without LLM."""
        score = 5.0
        issues: list[str] = []

        # Length heuristic
        words = len(output.split())
        if words < 50:
            score -= 2
            issues.append("Output is very short")
        elif words > 200:
            score += 1

        # Check for task keyword coverage
        task_words = set(task_intent.lower().split())
        output_words = set(output.lower().split())
        coverage = len(task_words & output_words) / max(len(task_words), 1)
        if coverage < 0.3:
            score -= 1
            issues.append("Low task keyword coverage")
        elif coverage > 0.7:
            score += 1

        score = max(1.0, min(10.0, score))

        return AssessmentResult(
            score=score,
            issues=issues,
            needs_correction=score < 6 and self._correction_mode == "correct",
        )

    # ------------------------------------------------------------------
    # Targeted re-generation
    # ------------------------------------------------------------------

    def targeted_regeneration(
        self,
        issues: list[str],
        task_intent: str,
    ) -> list[str]:
        """Re-generate targeted fixes for each issue (capped at max_corrections)."""
        if not self._dispatch_fn:
            return []

        corrections: list[str] = []
        for issue in issues[:self._max_corrections]:
            prompt = (
                f"Fix this specific issue in the output: {issue}\n"
                f"Original task: {task_intent}\n"
                "Provide only the corrected section."
            )
            try:
                output, _ = self._dispatch_fn(prompt, "")
                corrections.append(output)
            except Exception:
                corrections.append(f"[correction failed for: {issue}]")

        return corrections
