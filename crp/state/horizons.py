# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Multi-Horizon Context Model — Persistent, Conversational, Ephemeral tiers (SPEC-028).

Three context tiers with fundamentally different lifecycles and retrieval policies:
  PERSISTENT     → CKF (months–years, novelty-weighted CDR/CDGR)
  CONVERSATIONAL → Turn Log (session-scoped, recency + reference resolution)
  EPHEMERAL      → Scratch Buffer (seconds–minutes, freshness-gated)

The envelope assembler blends them per-turn according to detected intent.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("crp.state.horizons")


# ── Context Tier Enum ──────────────────────────────────────────────────────


class ContextTier(str, Enum):
    """The three context tiers of the Multi-Horizon Model (SPEC-028 §2.1)."""

    PERSISTENT = "persistent"       # CKF — months, cross-session
    CONVERSATIONAL = "conversational"  # Turn Log — session-scoped
    EPHEMERAL = "ephemeral"        # Scratch Buffer — single turn


# ── Turn Log Entry ─────────────────────────────────────────────────────────


@dataclass
class TurnEntry:
    """One entry in the Conversational Turn Log (Tier C)."""

    turn_id: int
    role: str  # "user" | "assistant" | "system"
    content: str
    topic_tags: list[str] = field(default_factory=list)
    referenced_turns: list[int] = field(default_factory=list)


# ── MultiHorizonContext ────────────────────────────────────────────────────


@dataclass
class MultiHorizonContext:
    """Unified envelope assembler for the three context tiers (SPEC-028 §2.2).

    Attributes:
        turn_log: Ordered list of turn entries (Tier C).
        max_turn_log: Maximum turns to retain in conversational memory.
    """

    turn_log: list[TurnEntry] = field(default_factory=list)
    max_turn_log: int = 50

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    def classify_intent(self, turn: str) -> dict[str, Any]:
        """Detect topic shift, reference resolution, clarification need (SPEC-028 §5).

        Returns dict with:
            intent: str — "explore" | "drill_down" | "clarify" | "reference"
            confidence: float
        """
        turn_lower = turn.lower()

        # Clarification markers (check before reference to avoid "that" overlap)
        clarify_markers = [
            "clarify", "explain", "what do you mean", "i don't understand",
            "confused", "elaborate", "rephrase",
        ]
        if any(m in turn_lower for m in clarify_markers):
            return {"intent": "clarify", "confidence": 0.80}

        # Reference resolution markers
        reference_markers = [
            "what did you mean", "what you said", "that ", "it ",
            "the second option", "the first one", "earlier", "before",
            "referring to", "talking about", "mentioned",
        ]
        if any(m in turn_lower for m in reference_markers):
            return {"intent": "reference", "confidence": 0.85}

        # Drill-down markers (revisiting prior topic with more depth)
        drill_markers = [
            "more detail", "deeper", "in depth", "specifically",
            "how exactly", "why does", "what about", "tell me more",
        ]
        if any(m in turn_lower for m in drill_markers):
            return {"intent": "drill_down", "confidence": 0.75}

        # Default: explore / new ground
        return {"intent": "explore", "confidence": 0.60}

    # ------------------------------------------------------------------
    # Reference resolution
    # ------------------------------------------------------------------

    def resolve_reference(self, reference: str, turn_history: list[str]) -> str:
        """Resolve "it", "that approach", "what you said about X" etc. (SPEC-028 §4).

        Returns the best-matching prior turn content, or empty string if none.
        """
        if not turn_history:
            return ""

        # Extract key noun phrases from reference
        ref_lower = reference.lower()
        # Remove common anaphoric words
        stripped = re.sub(r"\b(it|that|this|those|these|what you said|what did you mean)\b", "", ref_lower)
        # Remove very common words that pollute matching
        common_words = {"about", "what", "did", "you", "mean", "said", "the", "this", "that", "then", "have", "been", "with", "from", "they", "know", "want", "than", "only", "other", "time", "very", "when", "come", "here", "just", "like", "over", "also", "back", "after", "use", "two", "how", "our", "work", "first", "well", "way", "even", "new", "because", "any", "these", "give", "day", "most", "us"}
        keywords = [w for w in stripped.split() if len(w) > 3 and w not in common_words]

        if not keywords:
            # Fallback: return most recent turn
            return turn_history[-1] if turn_history else ""

        best_match = ""
        best_score = 0.0
        for prior in reversed(turn_history):
            prior_lower = prior.lower()
            score = sum(1 for kw in keywords if kw in prior_lower) / max(len(keywords), 1)
            if score > best_score:
                best_score = score
                best_match = prior

        if best_score >= 0.3:
            return best_match
        return ""

    # ------------------------------------------------------------------
    # Tier blend
    # ------------------------------------------------------------------

    def blend_for_operation(
        self,
        operation: str,
        weights: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Per-turn tier blend: different operations need different balances (SPEC-028 §2.2).

        Args:
            operation: One of the STL operations (RETRIEVE, SYNTHESISE, etc.)
            weights: Optional override weights.

        Returns:
            Dict with keys persistent, conversational, ephemeral summing to 1.0.
        """
        op = operation.upper()
        default_weights: dict[str, dict[str, float]] = {
            "RETRIEVE": {"persistent": 0.80, "conversational": 0.15, "ephemeral": 0.05},
            "SYNTHESISE": {"persistent": 0.60, "conversational": 0.30, "ephemeral": 0.10},
            "ANALYSE": {"persistent": 0.70, "conversational": 0.20, "ephemeral": 0.10},
            "COMPARE": {"persistent": 0.75, "conversational": 0.20, "ephemeral": 0.05},
            "GENERATE": {"persistent": 0.50, "conversational": 0.40, "ephemeral": 0.10},
            "VERIFY": {"persistent": 0.70, "conversational": 0.10, "ephemeral": 0.20},
            "CLARIFY": {"persistent": 0.20, "conversational": 0.70, "ephemeral": 0.10},
            "REVISE": {"persistent": 0.40, "conversational": 0.50, "ephemeral": 0.10},
        }
        blended = default_weights.get(op, {"persistent": 0.60, "conversational": 0.30, "ephemeral": 0.10})
        if weights:
            blended.update(weights)
            # Normalise
            total = sum(blended.values())
            if total > 0:
                blended = {k: v / total for k, v in blended.items()}
        return blended

    # ------------------------------------------------------------------
    # Turn Log management
    # ------------------------------------------------------------------

    def add_turn(self, role: str, content: str, topic_tags: list[str] | None = None) -> TurnEntry:
        """Append a turn to the conversational log."""
        entry = TurnEntry(
            turn_id=len(self.turn_log) + 1,
            role=role,
            content=content,
            topic_tags=topic_tags or [],
        )
        self.turn_log.append(entry)
        if len(self.turn_log) > self.max_turn_log:
            self.turn_log.pop(0)
        return entry

    def get_recent_turns(self, n: int = 5) -> list[TurnEntry]:
        """Return the last n turns."""
        return self.turn_log[-n:]

    def get_turns_by_topic(self, topic: str) -> list[TurnEntry]:
        """Return turns tagged with a given topic."""
        return [t for t in self.turn_log if topic.lower() in [tt.lower() for tt in t.topic_tags]]
