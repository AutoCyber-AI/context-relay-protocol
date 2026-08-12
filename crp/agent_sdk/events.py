# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Agent-side event vocabulary emitted by ``crp.Agent`` (CRP-SPEC-056 §4).

These events are the raw material for the Transparency Emission Layer. They are
lean, serialisable, and provider-agnostic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentEventKind(str, Enum):
    """Canonical agent lifecycle events (SPEC-056 §4.1)."""

    INTENT_CLASSIFIED = "intent_classified"
    OPERATION_POSITIONED = "operation_positioned"
    TOOL_SELECTED = "tool_selected"
    TOOL_CALLED = "tool_called"
    OBSERVATION_RECEIVED = "observation_received"
    OPERATION_VERIFIED = "operation_verified"
    INTEGRATED = "integrated"
    HALT = "halt"
    CLARIFICATION_REQUESTED = "clarification_requested"
    FINAL = "final"


@dataclass
class AgentEvent:
    """A single event in the agent run stream."""

    kind: AgentEventKind
    operation: str | None = None
    operation_index: int = 0
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Render as a JSON-serialisable dict."""
        return {
            "kind": self.kind.value,
            "operation": self.operation,
            "operation_index": self.operation_index,
            "detail": self.detail,
            "data": self.data,
            "timestamp": self.timestamp,
        }
