# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Clarification lifecycle handler (CRP-SPEC-053 §5.3.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crp.clr.response import ClarificationRequired


@dataclass
class ClarificationSession:
    """Holds a pending clarification and re-enters the resolved turn."""

    pending: ClarificationRequired | None = None
    raw_turn: str = ""
    resolved_turn: str = ""
    selections: list[int] = field(default_factory=list)

    def set_pending(
        self, pending: ClarificationRequired, raw_turn: str, resolved_turn: str
    ) -> None:
        """Store a clarification request awaiting user resolution."""
        self.pending = pending
        self.raw_turn = raw_turn
        self.resolved_turn = resolved_turn
        self.selections = []

    def resolve(self, index: int) -> str:
        """Resolve by candidate index and return the re-entered turn.

        Raises:
            IndexError: when ``index`` is out of range.
        """
        if self.pending is None:
            raise RuntimeError("no pending clarification")
        if not 0 <= index < len(self.pending.interpretations):
            raise IndexError("interpretation index out of range")
        self.selections.append(index)
        choice = self.pending.interpretations[index]
        # Re-enter the turn anchored to the selected reading.
        return f"{self.resolved_turn} (clarified: {choice.reading})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_turn": self.raw_turn,
            "resolved_turn": self.resolved_turn,
            "pending": self.pending.to_dict() if self.pending else None,
            "selections": list(self.selections),
        }


def header_value(clarification: ClarificationRequired) -> str:
    """Build the ``X-CRP-Clarification`` header value."""
    count = len(clarification.interpretations)
    return f'required; candidates={count}; reason="{clarification.reason}"'
