# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Clarification bridge — the CLARIFY operation's human-in-the-loop (CRP-SPEC-033/034 + v5).

When a positioned agent does not know something, or is about to use a gated capability,
it raises a :class:`ClarificationRequest` to the user instead of guessing. This is the
synchronous companion to the async :class:`crp.security.checkpoint.Checkpoint`, designed
for the positioned-tool-loop.

Invariant 10 (never leave the user with a raw error): ``resolve_clarification`` ALWAYS
returns a resolution — if no handler is registered, or the handler raises, it degrades
gracefully to a SKIP (best-effort continuation), never an exception.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("crp.security.clarify")


class ClarificationAction(str, Enum):
    """The user's response to a clarification request."""

    ANSWER = "answer"   # the user supplied information / approval
    SKIP = "skip"       # proceed best-effort without an answer
    ABORT = "abort"     # stop the task


@dataclass
class ClarificationRequest:
    """A request for user input raised by a CLARIFY operation or an oversight gate."""

    question: str
    operation_type: str = ""
    reason: str = ""  # "missing_information" | "oversight_required" | ...
    options: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: f"clar_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        """Render for streaming / audit / a reviewer UI."""
        return {
            "request_id": self.request_id,
            "question": self.question,
            "operation_type": self.operation_type,
            "reason": self.reason,
            "options": self.options,
            "context": self.context,
        }


@dataclass
class ClarificationResolution:
    """The outcome of resolving a clarification request."""

    action: ClarificationAction
    answer: str = ""
    reviewer: str = "user"

    @property
    def approved(self) -> bool:
        """True when the resolution is an affirmative answer (for oversight gates)."""
        return self.action is ClarificationAction.ANSWER and self.answer.strip().lower() in {
            "approve", "approved", "yes", "y", "allow", "ok", "true",
        }


# A handler turns a request into a resolution (e.g. prompt the user, call a webhook).
ClarificationHandler = Callable[[ClarificationRequest], ClarificationResolution]


def resolve_clarification(
    request: ClarificationRequest, handler: ClarificationHandler | None
) -> ClarificationResolution:
    """Resolve a clarification request with a graceful fallback (Invariant 10).

    Never raises to the caller: a missing or failing handler degrades to SKIP so the
    agent continues best-effort rather than crashing the end user's session.
    """
    if handler is None:
        return ClarificationResolution(ClarificationAction.SKIP, reviewer="auto-fallback")
    try:
        resolution = handler(request)
    except Exception as exc:  # noqa: BLE001 — handler failure must never crash the loop
        logger.warning("Clarification handler raised for %s: %s", request.request_id, exc)
        return ClarificationResolution(ClarificationAction.SKIP, reviewer="auto-fallback")
    if not isinstance(resolution, ClarificationResolution):
        logger.warning("Clarification handler returned %r — falling back to SKIP", type(resolution))
        return ClarificationResolution(ClarificationAction.SKIP, reviewer="auto-fallback")
    return resolution
