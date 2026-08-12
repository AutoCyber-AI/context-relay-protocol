# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Human-in-the-loop feedback — fact override, confidence adjustment (§18, MAY)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FeedbackEntry:
    """Single human feedback action."""

    feedback_id: str = ""
    fact_id: str = ""
    action: str = ""  # "override" | "boost" | "penalize" | "reject"
    original_text: str = ""
    corrected_text: str | None = None
    confidence_delta: float = 0.0
    reason: str = ""
    timestamp: float = field(default_factory=time.time)
    applied: bool = False


class FeedbackLoop:
    """Human-in-the-loop corrections for facts in warm state."""

    def __init__(self) -> None:
        self._entries: list[FeedbackEntry] = []
        self._fact_adjustments: dict[str, float] = {}  # fact_id → cumulative delta

    @property
    def entry_count(self) -> int:
        """Return the current entry count."""
        return len(self._entries)

    def override_fact(
        self,
        fact_id: str,
        corrected_text: str,
        reason: str = "",
    ) -> FeedbackEntry:
        """Replace fact text with human-provided correction."""
        entry = FeedbackEntry(
            feedback_id=f"fb-{len(self._entries)}",
            fact_id=fact_id,
            action="override",
            corrected_text=corrected_text,
            reason=reason,
            applied=True,
        )
        self._entries.append(entry)
        return entry

    def boost_confidence(
        self,
        fact_id: str,
        delta: float = 0.1,
        reason: str = "",
    ) -> FeedbackEntry:
        """Increase fact confidence based on human validation."""
        self._fact_adjustments[fact_id] = (
            self._fact_adjustments.get(fact_id, 0.0) + delta
        )
        entry = FeedbackEntry(
            feedback_id=f"fb-{len(self._entries)}",
            fact_id=fact_id,
            action="boost",
            confidence_delta=delta,
            reason=reason,
            applied=True,
        )
        self._entries.append(entry)
        return entry

    def penalize_confidence(
        self,
        fact_id: str,
        delta: float = -0.2,
        reason: str = "",
    ) -> FeedbackEntry:
        """Decrease fact confidence based on human rejection."""
        self._fact_adjustments[fact_id] = (
            self._fact_adjustments.get(fact_id, 0.0) + delta
        )
        entry = FeedbackEntry(
            feedback_id=f"fb-{len(self._entries)}",
            fact_id=fact_id,
            action="penalize",
            confidence_delta=delta,
            reason=reason,
            applied=True,
        )
        self._entries.append(entry)
        return entry

    def reject_fact(
        self,
        fact_id: str,
        reason: str = "",
    ) -> FeedbackEntry:
        """Mark fact as rejected (confidence → 0)."""
        self._fact_adjustments[fact_id] = -1.0  # Signal full rejection
        entry = FeedbackEntry(
            feedback_id=f"fb-{len(self._entries)}",
            fact_id=fact_id,
            action="reject",
            confidence_delta=-1.0,
            reason=reason,
            applied=True,
        )
        self._entries.append(entry)
        return entry

    def get_adjusted_confidence(
        self,
        fact_id: str,
        base_confidence: float,
    ) -> float:
        """Get confidence after applying all feedback adjustments."""
        delta = self._fact_adjustments.get(fact_id, 0.0)
        if delta <= -1.0:
            return 0.0
        return max(0.0, min(1.0, base_confidence + delta))

    def get_entries_for_fact(self, fact_id: str) -> list[FeedbackEntry]:
        """Return all feedback entries associated with *fact_id*."""
        return [e for e in self._entries if e.fact_id == fact_id]

    def to_dict(self) -> dict[str, Any]:
        """Serialize all feedback entries and cumulative adjustments to a dict."""
        return {
            "entries": [
                {
                    "feedback_id": e.feedback_id,
                    "fact_id": e.fact_id,
                    "action": e.action,
                    "corrected_text": e.corrected_text,
                    "confidence_delta": e.confidence_delta,
                    "reason": e.reason,
                    "timestamp": e.timestamp,
                    "applied": e.applied,
                }
                for e in self._entries
            ],
            "adjustments": dict(self._fact_adjustments),
        }
