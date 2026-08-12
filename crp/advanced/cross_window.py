# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Cross-window validation — 3-tier consistency checks (§13; CRP-SPEC-019).

Tier 1: Extraction-based (always, zero LLM cost)
Tier 2: LLM-targeted (2B+ models)
Tier 3: Full LLM review (7B+ models)

Relevant specifications:
  - CRP specification §13: Cross-window validation
  - CRP-SPEC-019: Cognitive Quality Recognition (CQR)
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_CONTRADICTION_SIM = 0.85
EMBEDDING_CONTRADICTION_EDIT = 0.3
TIER_1_INTERVAL = 5
TIER_2_INTERVAL = 10
TIER_3_INTERVAL = 20
MAX_CORRECTION_WINDOWS = 3


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ConsistencyIssue:
    """Single consistency issue found during validation.

    Attributes:
        issue_type: Category of issue, such as ``numerical_contradiction``,
            ``semantic_contradiction``, ``undefined_reference``, or
            ``structural_gap``.
        description: Human-readable explanation of the issue.
        severity: Severity label ("low", "medium", or "high").
        windows: Window numbers involved in the issue, if known.
        confirmed: Whether the issue has been confirmed by a higher tier.
        facts: Indices or identifiers of facts involved in the issue.
    """

    issue_type: str  # numerical_contradiction, semantic_contradiction,
    #                  undefined_reference, structural_gap
    description: str = ""
    severity: str = "medium"  # "low" | "medium" | "high"
    windows: list[int] | None = None
    confirmed: bool = False
    facts: list[Any] | None = None


@dataclass
class ValidationResult:
    """Output of a validation tier.

    Attributes:
        tier: Tier number (1, 2, or 3).
        issues: Issues produced by this tier.
        timestamp: Unix timestamp of the validation run.
        window_range: Inclusive window range that was validated.
    """

    tier: int = 1
    issues: list[ConsistencyIssue] = field(default_factory=list)
    timestamp: float = 0.0
    window_range: tuple[int, int] = (0, 0)

    @property
    def has_issues(self) -> bool:
        """Return True when the result contains at least one issue."""
        return len(self.issues) > 0

    @property
    def high_severity_count(self) -> int:
        """Return the number of high-severity issues."""
        return sum(1 for i in self.issues if i.severity == "high")


@dataclass
class ReviewCycleConfig:
    """Configuration for review cycles.

    Attributes:
        enabled: Master switch for review cycles.
        tier_1_interval: Window interval between Tier 1 validations.
        tier_2_enabled: Enable Tier 2 LLM-targeted validation.
        tier_2_interval: Window interval between Tier 2 validations.
        tier_3_enabled: Enable Tier 3 full LLM review.
        tier_3_interval: Window interval between Tier 3 validations.
        tier_3_min_model_capability: Minimum model capability for Tier 3.
        correction_mode: Correction behaviour ("flag" or "correct").
        max_correction_windows: Maximum windows to attempt correcting.
    """

    enabled: bool = True
    tier_1_interval: int = TIER_1_INTERVAL
    tier_2_enabled: bool = True
    tier_2_interval: int = TIER_2_INTERVAL
    tier_3_enabled: bool = True
    tier_3_interval: int = TIER_3_INTERVAL
    tier_3_min_model_capability: int = 3
    correction_mode: str = "flag"     # "flag" | "correct"
    max_correction_windows: int = MAX_CORRECTION_WINDOWS


# ---------------------------------------------------------------------------
# Tier 1 — Extraction-based (ALWAYS, zero LLM cost)
# ---------------------------------------------------------------------------

# Regex for extracting numbers with context
_NUMBER_PATTERN = re.compile(r"(\b\d+(?:\.\d+)?(?:\s*(?:%|percent|GB|MB|KB|ms|seconds?|minutes?|hours?))?)")


def _extract_numbers(text: str) -> list[tuple[str, str]]:
    """Extract numbers + surrounding context from text.

    Args:
        text: Text to analyse.

    Returns:
        List of (number_string, context) tuples.
    """
    results: list[tuple[str, str]] = []
    for m in _NUMBER_PATTERN.finditer(text):
        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 30)
        context = text[start:end].strip()
        results.append((m.group(1), context))
    return results


def _normalized_edit_distance(a: str, b: str) -> float:
    """Levenshtein edit distance normalized to [0, 1].

    Args:
        a: First string.
        b: Second string.

    Returns:
        Normalised edit distance; 0.0 means identical, 1.0 means completely
        different.
    """
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0
    n, m = len(a), len(b)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            tmp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = tmp
    return dp[m] / max(n, m)


class CrossWindowValidator:
    """Three-tier cross-window consistency validation.

    Args:
        dispatch_fn: Callable accepting ``(prompt, context)`` and returning
            ``(output, metadata)``; used for LLM-based tiers.  May be None.
        embedding_fn: Callable that returns an embedding vector for a string;
            used for semantic contradiction detection.  May be None.
        config: ``ReviewCycleConfig`` overrides; defaults are used if None.
    """

    def __init__(
        self,
        dispatch_fn: Callable[[str, str], tuple[str, Any]] | None = None,
        embedding_fn: Callable[[str], list[float]] | None = None,
        config: ReviewCycleConfig | None = None,
    ) -> None:
        self._dispatch_fn = dispatch_fn
        self._embedding_fn = embedding_fn
        self.config = config or ReviewCycleConfig()
        self._model_capability: int | None = None

    # ------------------------------------------------------------------
    # Tier 1: Extraction-based
    # ------------------------------------------------------------------

    def extraction_based_validation(
        self,
        facts: list[dict[str, Any]],
        window_outputs: list[str] | None = None,
        planned_sections: list[str] | None = None,
    ) -> ValidationResult:
        """Zero-cost structural validation. Always runs.

        Args:
            facts: List of fact dictionaries to validate.
            window_outputs: Optional aggregated window outputs, used for
                structural completeness checks.
            planned_sections: Optional list of planned sections to verify.

        Returns:
            A Tier 1 ``ValidationResult``.
        """
        issues: list[ConsistencyIssue] = []

        # Check 1: Numerical consistency
        issues.extend(self._check_numerical_consistency(facts))

        # Check 2: Entity reference integrity
        issues.extend(self._check_entity_references(facts))

        # Check 3: Embedding-based contradiction
        if self._embedding_fn:
            issues.extend(self._check_embedding_contradictions(facts))

        # Check 4: Structural completeness
        if planned_sections and window_outputs:
            issues.extend(self._check_structural_completeness(
                window_outputs, planned_sections,
            ))

        return ValidationResult(tier=1, issues=issues)

    def _check_numerical_consistency(
        self, facts: list[dict[str, Any]],
    ) -> list[ConsistencyIssue]:
        """Find contradicting numbers for the same metric across facts.

        Args:
            facts: Fact dictionaries to check.

        Returns:
            List of numerical-contradiction issues.
        """
        issues: list[ConsistencyIssue] = []
        # Group numbers by broad context (simplified)
        number_groups: dict[str, list[tuple[str, int]]] = {}
        for i, fact in enumerate(facts):
            text = fact.get("text", "")
            for num, ctx in _extract_numbers(text):
                # Use context words as group key
                words = re.findall(r"[a-zA-Z]+", ctx.lower())
                key = " ".join(sorted(set(words)))
                if key and len(key) > 5:
                    number_groups.setdefault(key, []).append((num, i))

        for key, entries in number_groups.items():
            values = set(e[0] for e in entries)
            if len(values) > 1 and len(entries) >= 2:
                issues.append(ConsistencyIssue(
                    issue_type="numerical_contradiction",
                    description=f"Conflicting values {values} for context '{key[:50]}'",
                    severity="high",
                    facts=[e[1] for e in entries],
                ))
        return issues

    def _check_entity_references(
        self, facts: list[dict[str, Any]],
    ) -> list[ConsistencyIssue]:
        """Check entity first-defined vs first-referenced.

        Args:
            facts: Fact dictionaries to check.

        Returns:
            Currently returns an empty list; placeholder for entity-reference
            heuristics.
        """
        issues: list[ConsistencyIssue] = []
        # Track entities: simplified heuristic using capitalized multi-word sequences
        defined: set[str] = set()
        for fact in facts:
            text = fact.get("text", "")
            # Find capitalized terms as entities
            entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)
            for entity in entities:
                ent_lower = entity.lower()
                if ent_lower not in defined:
                    defined.add(ent_lower)
        return issues

    def _check_embedding_contradictions(
        self, facts: list[dict[str, Any]],
    ) -> list[ConsistencyIssue]:
        """Find high-similarity facts with high edit distance.

        Args:
            facts: Fact dictionaries to compare pairwise.

        Returns:
            List of semantic-contradiction issues.
        """
        issues: list[ConsistencyIssue] = []
        if not self._embedding_fn or len(facts) < 2:
            return issues

        # Compute embeddings (limited to first 50 for performance)
        sample = facts[:50]
        embeddings: list[list[float]] = []
        for f in sample:
            embeddings.append(self._embedding_fn(f.get("text", "")))

        for i in range(len(sample)):
            for j in range(i + 1, len(sample)):
                sim = _cosine_sim(embeddings[i], embeddings[j])
                if sim > EMBEDDING_CONTRADICTION_SIM:
                    ed = _normalized_edit_distance(
                        sample[i].get("text", ""),
                        sample[j].get("text", ""),
                    )
                    if ed > EMBEDDING_CONTRADICTION_EDIT:
                        issues.append(ConsistencyIssue(
                            issue_type="semantic_contradiction",
                            description=(
                                f"High similarity ({sim:.2f}) but high edit distance ({ed:.2f}) "
                                f"between facts {i} and {j}"
                            ),
                            severity="high",
                            facts=[i, j],
                        ))
        return issues

    def _check_structural_completeness(
        self,
        window_outputs: list[str],
        planned_sections: list[str],
    ) -> list[ConsistencyIssue]:
        """Check planned sections vs actual content.

        Args:
            window_outputs: Generated output from each window.
            planned_sections: Section names expected in the final output.

        Returns:
            List of structural-gap issues for missing sections.
        """
        issues: list[ConsistencyIssue] = []
        all_output = "\n".join(window_outputs).lower()
        for section in planned_sections:
            if section.lower() not in all_output:
                issues.append(ConsistencyIssue(
                    issue_type="structural_gap",
                    description=f"Planned section '{section}' not found in output",
                    severity="medium",
                ))
        return issues

    # ------------------------------------------------------------------
    # Tier 2: LLM-targeted (2B+ models)
    # ------------------------------------------------------------------

    def targeted_llm_validation(
        self,
        tier1_issues: list[ConsistencyIssue],
    ) -> ValidationResult:
        """Targeted LLM validation for Tier 1 issues.

        Args:
            tier1_issues: Issues produced by Tier 1 validation.

        Returns:
            A Tier 2 ``ValidationResult`` with confirmed/updated issue flags.
        """
        if not self._dispatch_fn:
            return ValidationResult(tier=2, issues=tier1_issues)

        confirmed: list[ConsistencyIssue] = []
        for issue in tier1_issues:
            if issue.issue_type == "numerical_contradiction":
                # Always confirmed (objective)
                issue.confirmed = True
                confirmed.append(issue)
            elif issue.issue_type == "semantic_contradiction":
                # Binary YES/NO question
                prompt = (
                    "Answer ONLY YES or NO: Do the following two statements contradict each other?\n"
                    f"Statement: {issue.description}"
                )
                try:
                    output, _ = self._dispatch_fn(prompt, "")
                    if "YES" in output.upper():
                        issue.confirmed = True
                except Exception:
                    issue.confirmed = False
                confirmed.append(issue)
            else:
                confirmed.append(issue)

        return ValidationResult(tier=2, issues=confirmed)

    # ------------------------------------------------------------------
    # Tier 3: Full LLM review (7B+ models)
    # ------------------------------------------------------------------

    def full_llm_review(
        self,
        accumulated_output: str,
        task_intent: str,
        top_facts: list[dict[str, Any]] | None = None,
    ) -> ValidationResult:
        """Dedicated review window with top facts + document map.

        Args:
            accumulated_output: Full generated output to review.
            task_intent: Original task description.
            top_facts: Optional top facts to ground the review.

        Returns:
            A Tier 3 ``ValidationResult`` parsed from the model's review.
        """
        if not self._dispatch_fn:
            return ValidationResult(tier=3, issues=[])

        facts_section = ""
        if top_facts:
            facts_section = "\n".join(
                f"- {f.get('text', '')}" for f in top_facts[:50]
            )

        prompt = (
            "You are a review assistant. Analyze this output for:\n"
            "1. Contradictions\n2. Unsupported claims\n3. Logical inconsistencies\n"
            "4. Missing connections\n5. Argument drift\n\n"
            f"Task: {task_intent}\n\n"
            f"Top facts:\n{facts_section}\n\n"
            "If no issues found, respond: NO ISSUES FOUND.\n"
            "Otherwise, list numbered issues."
        )

        try:
            output, _ = self._dispatch_fn(prompt, accumulated_output[:5000])
        except Exception:
            return ValidationResult(tier=3, issues=[])

        issues: list[ConsistencyIssue] = []
        if "NO ISSUES FOUND" not in output.upper():
            # Parse numbered issues
            for line in output.split("\n"):
                line = line.strip()
                if re.match(r"\d+\.", line):
                    issues.append(ConsistencyIssue(
                        issue_type="llm_review",
                        description=line,
                        severity="medium",
                        confirmed=True,
                    ))

        return ValidationResult(tier=3, issues=issues)

    # ------------------------------------------------------------------
    # Model capability assessment
    # ------------------------------------------------------------------

    def assess_review_capability(self) -> int:
        """Probe model to determine max validation tier (1, 2, or 3).

        Returns:
            Highest validation tier the configured model can support.
        """
        if self._model_capability is not None:
            return self._model_capability

        if not self._dispatch_fn:
            self._model_capability = 1
            return 1

        # Tier 2 probe: binary contradiction
        try:
            output, _ = self._dispatch_fn(
                "Answer YES or NO only: Does 'the server runs on port 80' "
                "contradict 'the service uses port 443'?",
                "",
            )
            if "YES" in output.upper():
                tier = 2
            else:
                self._model_capability = 1
                return 1
        except Exception:
            self._model_capability = 1
            return 1

        # Tier 3 probe: structured analysis
        try:
            output, _ = self._dispatch_fn(
                "Analyze these two claims and list any contradictions as numbered items:\n"
                "Claim A: All vulnerabilities have been patched.\n"
                "Claim B: CVE-2024-1234 remains exploitable.",
                "",
            )
            has_numbered = bool(re.search(r"\d+\.", output))
            has_contradiction = any(
                w in output.lower()
                for w in ["contradict", "conflict", "inconsist", "exploit"]
            )
            if has_numbered and has_contradiction:
                tier = 3
        except Exception:
            pass

        self._model_capability = tier
        return tier

    # ------------------------------------------------------------------
    # Correction pipeline
    # ------------------------------------------------------------------

    def apply_corrections(
        self,
        issues: list[ConsistencyIssue],
        task_intent: str = "",
        blockers: list[str] | None = None,
    ) -> list[str]:
        """Apply corrections based on config mode.

        Args:
            issues: Issues to process.
            task_intent: Original task description (unused by current logic).
            blockers: Optional list to populate with flagged issue summaries
                when ``correction_mode`` is "flag".

        Returns:
            List of correction actions taken.
        """
        actions: list[str] = []
        sorted_issues = sorted(
            issues,
            key=lambda i: {"high": 0, "medium": 1, "low": 2}.get(i.severity, 3),
        )

        if self.config.correction_mode == "flag":
            if blockers is not None:
                for issue in sorted_issues:
                    blockers.append(f"[{issue.severity}] {issue.description}")
                    actions.append(f"flagged: {issue.description[:80]}")
        elif self.config.correction_mode == "correct" and self._dispatch_fn:
            for issue in sorted_issues[:self.config.max_correction_windows]:
                if issue.issue_type == "numerical_contradiction":
                    prompt = (
                        f"Resolve this numerical contradiction: {issue.description}. "
                        f"Provide the correct value only."
                    )
                    try:
                        output, _ = self._dispatch_fn(prompt, "")
                        actions.append(f"corrected: {issue.description[:80]} → {output[:100]}")
                    except Exception:
                        actions.append(f"correction_failed: {issue.description[:80]}")
                elif issue.issue_type == "semantic_contradiction":
                    prompt = (
                        f"Resolve this contradiction: {issue.description}. "
                        f"Which statement is correct?"
                    )
                    try:
                        output, _ = self._dispatch_fn(prompt, "")
                        actions.append(f"resolved: {issue.description[:80]} → {output[:100]}")
                    except Exception:
                        actions.append(f"resolution_failed: {issue.description[:80]}")
                else:
                    actions.append(f"skipped: {issue.description[:80]}")

        return actions

    def should_run_tier(self, window_index: int, tier: int) -> bool:
        """Check if a validation tier should run at this window index.

        Args:
            window_index: Current window number.
            tier: Tier to evaluate (1, 2, or 3).

        Returns:
            True when the tier is enabled and the window index aligns with its
            configured interval.
        """
        if tier == 1:
            return window_index % self.config.tier_1_interval == 0
        if tier == 2:
            return (
                self.config.tier_2_enabled
                and window_index % self.config.tier_2_interval == 0
            )
        if tier == 3:
            return (
                self.config.tier_3_enabled
                and window_index % self.config.tier_3_interval == 0
            )
        return False


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        Cosine similarity in the range [-1.0, 1.0], or 0.0 for invalid input.
    """
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0
