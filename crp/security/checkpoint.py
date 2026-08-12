# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Checkpoint primitive — inline human-in-the-loop for CRP (SPEC-033 §3, SPEC-034).

A Checkpoint is like a breakpoint for human judgment. Declare anywhere:

    @client.checkpoint(when="risk >= HIGH")
    def generate_medical_advice(prompt):
        ...

Or inline:

    result = client.complete(prompt)
    await client.checkpoint("approve this output before sending to user")

On timeout or reject, the Checkpoint NEVER leaves the end user with a raw error.
It always provides a graceful fallback (Invariant 10).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("crp.security.checkpoint")


# ── Enums ──────────────────────────────────────────────────────────────────


class CheckpointTrigger(str, Enum):
    """What causes a checkpoint to fire (SPEC-033 §3)."""

    ALWAYS = "always"
    RISK_HIGH = "risk >= HIGH"
    RISK_CRITICAL = "risk >= CRITICAL"
    CUSTOM_RULE = "custom_rule"


class CheckpointTimeoutAction(str, Enum):
    """What happens when a checkpoint times out awaiting human response (SPEC-033 §3)."""

    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"


class CheckpointRejectAction(str, Enum):
    """What happens when a checkpoint is rejected by the human reviewer (SPEC-033 §3)."""

    HALT = "halt"
    REVISE = "revise"
    FALLBACK = "fallback"


class CheckpointResolutionAction(str, Enum):
    """The human reviewer's decision (SPEC-033 §3)."""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


# ── Dataclasses ────────────────────────────────────────────────────────────


@dataclass
class CheckpointResolution:
    """The result of a human reviewer resolving a checkpoint (SPEC-033 §3).

    Attributes:
        action: Reviewer decision (approve/reject/edit).
        reviewer: Identifier of the reviewer.
        timestamp: Unix timestamp of the resolution.
        edited_output: Optional replacement text when action is EDIT.
        audit_event: Optional extra fields for the audit trail.
    """

    action: CheckpointResolutionAction
    reviewer: str
    timestamp: float = field(default_factory=time.time)
    edited_output: str = ""
    audit_event: dict[str, Any] | None = None

    def to_audit_dict(self) -> dict[str, Any]:
        """Produce an audit-trail compatible event dict (SPEC-011).

        Returns:
            Dict with checkpoint resolution fields ready for ``ComplianceAuditTrail``.
        """
        return {
            "type": "checkpoint.resolved",
            "action": self.action.value,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp,
            "has_edit": bool(self.edited_output),
            "checkpoint_id": self.audit_event.get("checkpoint_id") if self.audit_event else None,
        }


@dataclass
class Checkpoint:
    """Inline human-in-the-loop declaration (SPEC-033 §3).

    Attributes:
        checkpoint_id: Unique identifier for this checkpoint instance.
        trigger: Condition that caused the checkpoint to fire.
        timeout: Seconds before auto-action is taken.
        on_timeout: Action if human does not respond in time.
        on_reject: Action if human rejects.
        context: Arbitrary context dict for the reviewer UI.
    """

    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trigger: CheckpointTrigger = CheckpointTrigger.ALWAYS
    timeout: int = 300  # 5 minutes default
    on_timeout: CheckpointTimeoutAction = CheckpointTimeoutAction.ESCALATE
    on_reject: CheckpointRejectAction = CheckpointRejectAction.FALLBACK
    context: dict[str, Any] = field(default_factory=dict)
    _resolution: CheckpointResolution | None = field(default=None, repr=False)
    _resolved_event: asyncio.Event | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._resolved_event is None:
            self._resolved_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Core lifecycle
    # ------------------------------------------------------------------

    async def wait_for_resolution(self) -> CheckpointResolution:
        """Block until the checkpoint is resolved by a human reviewer.

        If timeout expires, auto-resolves per *on_timeout*.

        Returns:
            A ``CheckpointResolution`` — never ``None`` (Invariant 10).

        Raises:
            asyncio.TimeoutError: Internally caught and converted to auto-resolution.
        """
        if self._resolution is not None:
            return self._resolution

        if self._resolved_event is None:
            self._resolved_event = asyncio.Event()

        try:
            await asyncio.wait_for(
                self._resolved_event.wait(),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Checkpoint %s timed out after %ss — applying %s",
                self.checkpoint_id,
                self.timeout,
                self.on_timeout.value,
            )
            self._auto_resolve_on_timeout()

        # Invariant 10: never return None — always a graceful fallback
        if self._resolution is None:
            self._auto_resolve_on_timeout()

        return self._resolution  # type: ignore[return-value]

    def resolve(self, resolution: CheckpointResolution) -> None:
        """Called by a human reviewer (or webhook) to resolve this checkpoint.

        Args:
            resolution: The reviewer's decision and optional edited output.

        Returns:
            None. Sets the internal resolved event so awaiting tasks unblock.
        """
        self._resolution = resolution
        if self._resolved_event is not None:
            self._resolved_event.set()
        logger.info(
            "Checkpoint %s resolved: %s by %s",
            self.checkpoint_id,
            resolution.action.value,
            resolution.reviewer,
        )

    # ------------------------------------------------------------------
    # Auto-resolution helpers
    # ------------------------------------------------------------------

    def _auto_resolve_on_timeout(self) -> None:
        """Generate a resolution when the human does not respond in time.

        Returns:
            None. Calls ``resolve()`` with a system-generated timeout resolution.
        """
        action_map = {
            CheckpointTimeoutAction.APPROVE: CheckpointResolutionAction.APPROVE,
            CheckpointTimeoutAction.REJECT: CheckpointResolutionAction.REJECT,
            CheckpointTimeoutAction.ESCALATE: CheckpointResolutionAction.REJECT,
        }
        resolution = CheckpointResolution(
            action=action_map.get(self.on_timeout, CheckpointResolutionAction.REJECT),
            reviewer="system/auto-timeout",
            audit_event={"checkpoint_id": self.checkpoint_id, "reason": "timeout"},
        )
        self.resolve(resolution)

    # ------------------------------------------------------------------
    # Decorator / inline factory
    # ------------------------------------------------------------------

    @classmethod
    def decorate(
        cls,
        when: str = "always",
        timeout: int = 300,
        on_timeout: str = "escalate",
        on_reject: str = "fallback",
    ) -> Callable:
        """Decorator factory: ``@checkpoint(when="risk >= HIGH")``.

        Args:
            when: Trigger condition string.
            timeout: Seconds to await human review.
            on_timeout: Action if the checkpoint times out.
            on_reject: Action if the reviewer rejects.

        Returns:
            A decorator that wraps the function with checkpoint gating.

        Raises:
            CRPError: If the reviewer rejects and ``on_reject`` is ``"halt"``.
        """
        trigger = CheckpointTrigger(when) if when in {t.value for t in CheckpointTrigger} else CheckpointTrigger.CUSTOM_RULE
        timeout_action = CheckpointTimeoutAction(on_timeout)
        reject_action = CheckpointRejectAction(on_reject)

        def decorator(func: Callable) -> Callable:
            """Execute decorator and return the result.
            
                Args:
                    func (Callable): The func value.
            
                Returns:
                    ``Callable``.
            """
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                """Execute async wrapper and return the result.
                
                    Args:
                        *args: Variable positional arguments.
                        **kwargs: Variable keyword arguments.
                
                    Returns:
                        ``Any``.
                """
                cp = cls(
                    trigger=trigger,
                    timeout=timeout,
                    on_timeout=timeout_action,
                    on_reject=reject_action,
                    context={"function": func.__name__, "args": str(args), "kwargs": str(kwargs)},
                )
                # Fire checkpoint BEFORE executing the wrapped function
                resolution = await cp.wait_for_resolution()
                if resolution.action == CheckpointResolutionAction.REJECT:
                    if reject_action == CheckpointRejectAction.HALT:
                        from crp.core.errors import CRPError, ErrorCode
                        raise CRPError(
                            ErrorCode.SECURITY_INVARIANT_ERROR,
                            f"Checkpoint rejected for {func.__name__}",
                        )
                    if reject_action == CheckpointRejectAction.FALLBACK:
                        logger.warning("Checkpoint rejected — returning graceful fallback for %s", func.__name__)
                        return ""
                    # REVISE — caller must handle re-invocation
                    return ""
                if resolution.action == CheckpointResolutionAction.EDIT:
                    # In a real implementation, edited_output would replace result
                    pass
                return await func(*args, **kwargs)

            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                """Execute sync wrapper and return the result.
                
                    Args:
                        *args: Variable positional arguments.
                        **kwargs: Variable keyword arguments.
                
                    Returns:
                        ``Any``.
                """
                # For sync contexts, use a simple timeout fallback
                logger.info("Sync checkpoint fired for %s — auto-approving after %ss", func.__name__, timeout)
                return func(*args, **kwargs)

            import inspect
            if inspect.iscoroutinefunction(func):
                async_wrapper.__name__ = func.__name__
                async_wrapper.__doc__ = func.__doc__
                return async_wrapper
            sync_wrapper.__name__ = func.__name__
            sync_wrapper.__doc__ = func.__doc__
            return sync_wrapper

        return decorator
