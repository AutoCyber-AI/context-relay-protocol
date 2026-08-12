# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CQS — Context Quality Signaling, detect LLM context hunger (§12; CRP-SPEC-019).

Three signal types: hedging, reference_miss, repetition.
Preserves Model Ignorance (Axiom 4): signals are detected structurally
from generation output, never by injecting meta-protocol into the LLM.

Relevant specifications:
  - CRP specification §12: Context Quality Signaling
  - CRP-SPEC-019: Cognitive Quality Recognition (CQR)
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants (§12)
# ---------------------------------------------------------------------------

HEDGING_THRESHOLD = 3
HEDGING_STRENGTH_DIVISOR = 5
PLACEHOLDER_THRESHOLD = 2
PLACEHOLDER_STRENGTH_DIVISOR = 3
REPETITION_THRESHOLD = 3

CQS_HEDGING_BUDGET = 2000       # tokens
CQS_REFERENCE_MISS_BUDGET = 3000
CQS_REPETITION_BUDGET = 2000

REDISPATCH_STRENGTH = 0.8
REDISPATCH_TOKEN_LIMIT = 500


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_HEDGING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"it is unclear whether",
        r"without (?:more|additional|further) information",
        r"cannot (?:determine|confirm|verify)",
        r"(?:may|might|could) (?:be|have)",
        r"insufficient (?:data|evidence|context)",
        r"further (?:analysis|investigation) (?:is )?needed",
        r"based on (?:limited|available) (?:information|data|context)",
    ]
]

_REFERENCE_MISS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\[(?:need|missing|TODO|TBD|citation needed)\]",
        r"as (?:discussed|mentioned|noted|shown|described) (?:earlier|previously|above|before)",
        r"(?:per|according to|referring to) the (?:previous|prior|earlier) (?:analysis|section|findings)",
        r"(?:see|refer to) (?:section|chapter|part) \d+",
    ]
]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ContextHungerSignal:
    """Single context hunger signal detected from LLM output.

    Attributes:
        signal_type: Signal category ("hedging", "reference_miss", or
            "repetition").
        strength: Normalised signal strength in the range [0.0, 1.0].
        topic: Short text snippet identifying the affected topic.
        window_id: Identifier of the window that produced the generation.
        token_offset: Token offset where the signal was observed.
        details: Additional structured details about the signal.
    """

    signal_type: str  # "hedging" | "reference_miss" | "repetition"
    strength: float = 0.0  # 0.0–1.0
    topic: str = ""
    window_id: str = ""
    token_offset: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CQSResponse:
    """Response after CQS processing.

    Attributes:
        action: Recommended action ("abandon_and_redispatch", "enrich_next",
            or "none").
        signals: Detected hunger signals that led to the action.
        enrichment_budget: Suggested token budget for the next enrichment pass.
        enrichment_topics: Topics to target during enrichment.
    """

    action: str = "enrich_next"  # "abandon_and_redispatch" | "enrich_next" | "none"
    signals: list[ContextHungerSignal] = field(default_factory=list)
    enrichment_budget: int = 0
    enrichment_topics: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CQSDetector
# ---------------------------------------------------------------------------


class CQSDetector:
    """Detect implicit context hunger from LLM generation output."""

    def detect_context_hunger(
        self,
        generation_text: str,
        window_id: str = "",
        tokens_generated: int | None = None,
    ) -> list[ContextHungerSignal]:
        """Scan generation output for context hunger signals.

        Args:
            generation_text: Raw text produced by the LLM.
            window_id: Identifier of the originating window.
            tokens_generated: Number of tokens generated, if known.

        Returns:
            List of detected signals (may be empty).
        """
        signals: list[ContextHungerSignal] = []

        # --- Type 1: Hedging ---
        hedging_count = 0
        hedging_topic = ""
        for pat in _HEDGING_PATTERNS:
            matches = pat.findall(generation_text)
            hedging_count += len(matches)
            if matches and not hedging_topic:
                hedging_topic = _extract_uncertain_topic(generation_text, matches[0])

        if hedging_count >= HEDGING_THRESHOLD:
            signals.append(ContextHungerSignal(
                signal_type="hedging",
                strength=min(hedging_count / HEDGING_STRENGTH_DIVISOR, 1.0),
                topic=hedging_topic,
                window_id=window_id,
                details={"hedging_count": hedging_count},
            ))

        # --- Type 2: Reference miss ---
        placeholder_count = 0
        ref_topic = ""
        for pat in _REFERENCE_MISS_PATTERNS:
            matches = pat.findall(generation_text)
            placeholder_count += len(matches)
            if matches and not ref_topic:
                ref_topic = _extract_referenced_topic(generation_text, matches[0])

        if placeholder_count >= PLACEHOLDER_THRESHOLD:
            signals.append(ContextHungerSignal(
                signal_type="reference_miss",
                strength=min(placeholder_count / PLACEHOLDER_STRENGTH_DIVISOR, 1.0),
                topic=ref_topic,
                window_id=window_id,
                details={"placeholder_count": placeholder_count},
            ))

        # --- Type 3: Repetition ---
        repeated = _detect_repetition(generation_text)
        if repeated:
            rep_topic = max(repeated, key=lambda k: repeated[k])
            signals.append(ContextHungerSignal(
                signal_type="repetition",
                strength=min(len(set(repeated)) / 3, 1.0),
                topic=rep_topic,
                window_id=window_id,
                details={"repeated_items": dict(repeated)},
            ))

        return signals

    def respond_to_context_hunger(
        self,
        signals: list[ContextHungerSignal],
        tokens_generated: int = 0,
    ) -> CQSResponse:
        """Determine action based on detected signals.

        §12.4: If max(strength) >= 0.8 AND tokens < 500 → abandon + redispatch.
        Otherwise → enrich next window.

        Args:
            signals: Signals returned by :meth:`detect_context_hunger`.
            tokens_generated: Number of tokens already generated for the
                current response.

        Returns:
            A ``CQSResponse`` describing the recommended action, budget, and
            enrichment topics.
        """
        if not signals:
            return CQSResponse(action="none")

        max_strength = max(s.strength for s in signals)
        topics = [s.topic for s in signals if s.topic]

        # Calculate total enrichment budget
        budget = 0
        for s in signals:
            if s.signal_type == "hedging":
                budget += CQS_HEDGING_BUDGET
            elif s.signal_type == "reference_miss":
                budget += CQS_REFERENCE_MISS_BUDGET
            elif s.signal_type == "repetition":
                budget += CQS_REPETITION_BUDGET

        if max_strength >= REDISPATCH_STRENGTH and tokens_generated < REDISPATCH_TOKEN_LIMIT:
            return CQSResponse(
                action="abandon_and_redispatch",
                signals=signals,
                enrichment_budget=budget,
                enrichment_topics=topics,
            )

        return CQSResponse(
            action="enrich_next",
            signals=signals,
            enrichment_budget=budget,
            enrichment_topics=topics,
        )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _extract_uncertain_topic(text: str, match: str) -> str:
    """Extract the topic surrounding a hedging match.

    Args:
        text: Full generation text.
        match: Matched hedging phrase.

    Returns:
        Text snippet around the match, or an empty string if not found.
    """
    idx = text.lower().find(match.lower())
    if idx < 0:
        return ""
    start = max(0, idx - 50)
    end = min(len(text), idx + len(match) + 50)
    return text[start:end].strip()


def _extract_referenced_topic(text: str, match: str) -> str:
    """Extract the topic surrounding a reference miss.

    Args:
        text: Full generation text.
        match: Matched reference-miss phrase.

    Returns:
        Text snippet around the match, or an empty string if not found.
    """
    idx = text.lower().find(match.lower())
    if idx < 0:
        return ""
    start = max(0, idx - 50)
    end = min(len(text), idx + len(match) + 50)
    return text[start:end].strip()


def _detect_repetition(text: str) -> dict[str, int]:
    """Find inline facts mentioned >= 3 times.

    Extracts 2–4 word n-gram-like segments and returns those that occur at
    least ``REPETITION_THRESHOLD`` times.

    Args:
        text: Generation text to scan.

    Returns:
        Mapping of repeated phrases to their occurrence counts.
    """
    # Extract noun-phrase-like segments (simplified: 2-4 word sequences)
    words = text.split()
    ngrams: Counter[str] = Counter()
    for n in (2, 3, 4):
        for i in range(len(words) - n + 1):
            gram = " ".join(words[i:i + n])
            if len(gram) > 8:  # Skip short fragments
                ngrams[gram.lower()] += 1
    return {k: v for k, v in ngrams.items() if v >= REPETITION_THRESHOLD}
