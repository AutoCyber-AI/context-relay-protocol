# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Emergency kill-switch + forensic incident recorder (SPEC-033 §3.4, SPEC-012 §5).

A kill-switch is an auditable emergency stop.  Once fired, the session it guards
is terminated, no further agent actions are dispatched, and a tamper-evident
incident record is produced for post-mortem analysis.  It is the last line of
defense in the graduated safety response (trust decay → constrain → gate → kill).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger("crp.security.kill_switch")


class KillSwitchState(str, Enum):
    """Kill-switch lifecycle states."""

    ARMED = "armed"
    DISARMED = "disarmed"
    FIRED = "fired"


class KillSwitchReason(str, Enum):
    """Canonical reasons a kill-switch can fire."""

    MANUAL = "manual"
    SAFETY_BUDGET_DEPLETED = "safety_budget_depleted"
    TRUST_THRESHOLD_CROSSED = "trust_threshold_crossed"
    UNAUTHORIZED_WRITE = "unauthorized_write"
    RUNTIME_ANOMALY = "runtime_anomaly"
    POLICY_VIOLATION = "policy_violation"
    DELEGATION_BREACH = "delegation_breach"


@dataclass
class KillIncident:
    """Forensic record of a kill-switch fire event."""

    incident_id: str
    session_id: str
    reason: str
    triggered_by: str
    timestamp: float
    snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize incident to a JSON-safe dict."""
        return {
            "incident_id": self.incident_id,
            "session_id": self.session_id,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "timestamp": self.timestamp,
            "snapshot": self.snapshot,
        }


class KillSwitch:
    """Auditable emergency stop for a CRP session or agent.

    Attributes:
        state: Current ``KillSwitchState``.
        audit_callback: Optional callable ``fn(incident: KillIncident)`` that
            receives every fired incident (e.g., to append to an audit trail).
        on_fire: Optional callable ``fn(incident: KillIncident)`` invoked when
            the switch fires; useful to terminate the caller's runtime loop.
    """

    def __init__(
        self,
        *,
        audit_callback: Callable[[KillIncident], Any] | None = None,
        on_fire: Callable[[KillIncident], Any] | None = None,
    ) -> None:
        self._state = KillSwitchState.ARMED
        self._incidents: list[KillIncident] = []
        self._audit_callback = audit_callback
        self._on_fire = on_fire

    @property
    def state(self) -> KillSwitchState:
        """Current state of the kill-switch."""
        return self._state

    @property
    def is_fired(self) -> bool:
        """True once the switch has fired."""
        return self._state == KillSwitchState.FIRED

    @property
    def incidents(self) -> list[KillIncident]:
        """All incidents recorded by this switch (typically one after firing)."""
        return list(self._incidents)

    def arm(self) -> None:
        """Re-arm a disarmed switch.  Cannot re-arm a fired switch."""
        if self._state == KillSwitchState.FIRED:
            logger.warning("Cannot re-arm a fired kill-switch")
            return
        self._state = KillSwitchState.ARMED

    def disarm(self) -> None:
        """Disarm the switch — it will not fire until re-armed."""
        if self._state == KillSwitchState.FIRED:
            logger.warning("Cannot disarm a fired kill-switch")
            return
        self._state = KillSwitchState.DISARMED

    def fire(
        self,
        session_id: str,
        reason: str,
        triggered_by: str,
        snapshot: dict[str, Any] | None = None,
    ) -> KillIncident:
        """Fire the kill-switch and record an incident.

        Args:
            session_id: Identifier of the guarded session.
            reason: Canonical or human-readable reason for firing.
            triggered_by: Identifier of the subsystem / user that triggered it.
            snapshot: Arbitrary serialisable context captured at the moment of
                firing (e.g., last window id, safety budget, trust score).

        Returns:
            The recorded ``KillIncident``.  If the switch was already fired or
            disarmed, a synthetic incident is returned without side effects.
        """
        if self._state != KillSwitchState.ARMED:
            logger.warning(
                "Kill-switch ignored for session %s: state=%s",
                session_id,
                self._state.value,
            )
            return KillIncident(
                incident_id=str(uuid.uuid4()),
                session_id=session_id,
                reason=reason,
                triggered_by=triggered_by,
                timestamp=time.time(),
                snapshot={"ignored": True, "state": self._state.value},
            )

        self._state = KillSwitchState.FIRED
        incident = KillIncident(
            incident_id=f"kill-{uuid.uuid4().hex[:16]}",
            session_id=session_id,
            reason=reason,
            triggered_by=triggered_by,
            timestamp=time.time(),
            snapshot=snapshot or {},
        )
        self._incidents.append(incident)

        logger.critical(
            "Kill-switch fired: session=%s reason=%s incident=%s",
            session_id,
            reason,
            incident.incident_id,
        )

        if self._audit_callback is not None:
            try:
                self._audit_callback(incident)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Kill-switch audit callback failed: %s", exc)

        if self._on_fire is not None:
            try:
                self._on_fire(incident)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Kill-switch on_fire callback failed: %s", exc)

        return incident

    def latest_incident(self) -> KillIncident | None:
        """Return the most recent incident, or None if the switch never fired."""
        return self._incidents[-1] if self._incidents else None
