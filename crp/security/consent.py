# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Consent & data rights management — GDPR + EU AI Act transparency (§7.13).

Implements:
  - Consent state management (opt-in, opt-out, withdrawal)
  - Purpose limitation (data processing tied to declared purposes)
  - Processing records (GDPR Article 30 / EU AI Act Art. 12)
  - Data portability support (export in standard format)
  - Human oversight controls (EU AI Act Art. 14)

EU AI Act: Art. 13 (transparency), Art. 14 (human oversight), Art. 12 (record-keeping)
ISO 42001: A.6.2.3 (human oversight), A.6.2.5 (data collection), A.6.2.7 (data subject rights)
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("crp.security.consent")


# ---------------------------------------------------------------------------
# Consent management
# ---------------------------------------------------------------------------


class ConsentStatus(str, Enum):
    """Consent states (§7.13.1)."""

    NOT_GIVEN = "not_given"  # Default — no consent recorded
    GRANTED = "granted"  # Consent explicitly given
    WITHDRAWN = "withdrawn"  # Consent was given then withdrawn
    DENIED = "denied"  # Consent explicitly denied


class ProcessingPurpose(str, Enum):
    """Data processing purposes — must be declared before processing (§7.13.2).

    EU AI Act Art. 10: Data governance requires clear purpose limitation.
    """

    CONTEXT_MANAGEMENT = "context_management"  # Core CRP functionality
    FACT_EXTRACTION = "fact_extraction"  # Extracting knowledge from text
    KNOWLEDGE_GRAPH = "knowledge_graph"  # Building knowledge graphs
    QUALITY_ASSESSMENT = "quality_assessment"  # Assessing output quality
    SECURITY_SCANNING = "security_scanning"  # Injection detection, PII scanning
    ANALYTICS = "analytics"  # Usage analytics (opt-in only)
    IMPROVEMENT = "improvement"  # Service improvement (opt-in only)
    EXPORT = "export"  # Data export / portability


# Default purposes that CRP requires for core functionality
_REQUIRED_PURPOSES: frozenset[ProcessingPurpose] = frozenset(
    {
        ProcessingPurpose.CONTEXT_MANAGEMENT,
        ProcessingPurpose.FACT_EXTRACTION,
        ProcessingPurpose.KNOWLEDGE_GRAPH,
        ProcessingPurpose.QUALITY_ASSESSMENT,
        ProcessingPurpose.SECURITY_SCANNING,
    }
)

# Purposes that require explicit opt-in
_OPT_IN_PURPOSES: frozenset[ProcessingPurpose] = frozenset(
    {
        ProcessingPurpose.ANALYTICS,
        ProcessingPurpose.IMPROVEMENT,
    }
)


@dataclass
class ConsentRecord:
    """Records a consent decision (§7.13.1)."""

    consent_id: str
    purpose: ProcessingPurpose
    status: ConsentStatus
    recorded_at: float = field(default_factory=time.time)
    expires_at: float = 0.0  # 0 = no expiry
    reason: str = ""  # Why consent was granted/denied/withdrawn


@dataclass
class ConsentState:
    """Aggregate consent state for a session."""

    session_id: str
    records: dict[ProcessingPurpose, ConsentRecord] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def is_granted(self, purpose: ProcessingPurpose) -> bool:
        """Check if consent is currently granted for a purpose.

        Args:
            purpose: Processing purpose to check.

        Returns:
            True if consent is granted and not expired. Required purposes
            return True by default.
        """
        rec = self.records.get(purpose)
        if rec is None:
            # Required purposes are implicitly consented (core functionality)
            return purpose in _REQUIRED_PURPOSES
        if rec.status != ConsentStatus.GRANTED:
            return False
        # Check expiry
        return not (rec.expires_at > 0 and time.time() > rec.expires_at)

    def denied_purposes(self) -> list[ProcessingPurpose]:
        """Return purposes that have been explicitly denied or withdrawn.

        Returns:
            List of purposes with ``DENIED`` or ``WITHDRAWN`` status.
        """
        denied = []
        for purpose, rec in self.records.items():
            if rec.status in (ConsentStatus.DENIED, ConsentStatus.WITHDRAWN):
                denied.append(purpose)
        return denied

    def to_dict(self) -> dict[str, Any]:
        """Serialise the consent state to a JSON-safe dict.

        Returns:
            Dict with session id, creation time, and purpose records.
        """
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "purposes": {
                p.value: {
                    "status": r.status.value,
                    "recorded_at": r.recorded_at,
                    "reason": r.reason,
                }
                for p, r in self.records.items()
            },
        }


class ConsentManager:
    """Manage consent state for data processing purposes (§7.13.1).

    EU AI Act Art. 13: Transparency requires clear communication about
    how data is processed and for what purposes.

    Usage::

        cm = ConsentManager("session-123")
        cm.grant(ProcessingPurpose.ANALYTICS, reason="User opted in")
        if cm.check(ProcessingPurpose.ANALYTICS):
            # Process analytics data
            ...
        cm.withdraw(ProcessingPurpose.ANALYTICS, reason="User opted out")
    """

    def __init__(self, session_id: str) -> None:
        self._state = ConsentState(session_id=session_id)

    @property
    def state(self) -> ConsentState:
        """Return the state."""
        return self._state

    def grant(
        self,
        purpose: ProcessingPurpose,
        reason: str = "",
        expires_hours: float = 0.0,
    ) -> ConsentRecord:
        """Grant consent for a processing purpose.

        Args:
            purpose: Processing purpose being consented to.
            reason: Human-readable reason for the grant.
            expires_hours: Optional expiry in hours; 0 means no expiry.

        Returns:
            The created ``ConsentRecord``.
        """
        now = time.time()
        record = ConsentRecord(
            consent_id=f"consent-{uuid.uuid4().hex[:8]}",
            purpose=purpose,
            status=ConsentStatus.GRANTED,
            recorded_at=now,
            expires_at=now + (expires_hours * 3600) if expires_hours > 0 else 0.0,
            reason=reason,
        )
        self._state.records[purpose] = record

        logger.info(
            "Consent granted: purpose=%s, session=%s, reason=%s",
            purpose.value,
            self._state.session_id,
            reason or "(none)",
        )
        return record

    def deny(
        self,
        purpose: ProcessingPurpose,
        reason: str = "",
    ) -> ConsentRecord:
        """Deny consent for a processing purpose.

        Args:
            purpose: Processing purpose being denied.
            reason: Human-readable reason for the denial.

        Returns:
            The created ``ConsentRecord``.
        """
        if purpose in _REQUIRED_PURPOSES:
            logger.warning(
                "Consent denied for required purpose %s — core functionality "
                "may be degraded. Session=%s",
                purpose.value,
                self._state.session_id,
            )

        record = ConsentRecord(
            consent_id=f"consent-{uuid.uuid4().hex[:8]}",
            purpose=purpose,
            status=ConsentStatus.DENIED,
            recorded_at=time.time(),
            reason=reason,
        )
        self._state.records[purpose] = record

        logger.info(
            "Consent denied: purpose=%s, session=%s, reason=%s",
            purpose.value,
            self._state.session_id,
            reason or "(none)",
        )
        return record

    def withdraw(
        self,
        purpose: ProcessingPurpose,
        reason: str = "",
    ) -> ConsentRecord:
        """Withdraw previously granted consent.

        Args:
            purpose: Processing purpose being withdrawn.
            reason: Human-readable reason for the withdrawal.

        Returns:
            The created ``ConsentRecord``.
        """
        record = ConsentRecord(
            consent_id=f"consent-{uuid.uuid4().hex[:8]}",
            purpose=purpose,
            status=ConsentStatus.WITHDRAWN,
            recorded_at=time.time(),
            reason=reason,
        )
        self._state.records[purpose] = record

        logger.info(
            "Consent withdrawn: purpose=%s, session=%s, reason=%s",
            purpose.value,
            self._state.session_id,
            reason or "(none)",
        )
        return record

    def check(self, purpose: ProcessingPurpose) -> bool:
        """Check if consent is granted for a purpose.

        Args:
            purpose: Processing purpose to check.

        Returns:
            True if consent is granted. Required purposes return True by default;
            opt-in purposes return False until explicitly granted.
        """
        return self._state.is_granted(purpose)

    def check_required(self, purpose: ProcessingPurpose) -> bool:
        """Check consent and raise if denied for a required purpose.

        Args:
            purpose: Processing purpose to check.

        Returns:
            True if consent is granted.

        Raises:
            ConsentRequiredError: If the purpose is required and consent is missing.
        """
        if self.check(purpose):
            return True
        if purpose in _REQUIRED_PURPOSES:
            raise ConsentRequiredError(
                f"Consent required for '{purpose.value}' — this is a core "
                f"CRP function. Grant consent or accept degraded functionality."
            )
        return False

    def to_dict(self) -> dict[str, Any]:
        """Export consent state for compliance reporting.

        Returns:
            Serialised consent state dict.
        """
        return self._state.to_dict()


class ConsentRequiredError(Exception):
    """Raised when a required consent is missing.

    Required purposes cannot be disabled without degrading core CRP functionality.
    """


# ---------------------------------------------------------------------------
# Processing records (GDPR Article 30)
# ---------------------------------------------------------------------------


@dataclass
class ProcessingActivity:
    """Records a single data processing activity (GDPR Art. 30) (§7.13.3).

    EU AI Act Art. 12: Systems must automatically record events relevant
    for identifying risks and substantial modifications.
    """

    activity_id: str
    purpose: ProcessingPurpose
    data_categories: list[str]  # e.g. ["text_input", "extracted_facts"]
    legal_basis: str  # e.g. "legitimate_interest", "consent", "contract"
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""
    input_size_bytes: int = 0
    output_size_bytes: int = 0
    data_subjects: str = "user"  # Who the data relates to
    retention_period: str = ""  # e.g. "24h", "30d", "session"
    automated_decision: bool = False  # Was there automated decision-making?
    human_oversight: bool = False  # Was human oversight available?


class ProcessingRecordKeeper:
    """Maintain GDPR Article 30 processing records (§7.13.3).

    Every data processing activity within a CRP session is recorded
    with its purpose, legal basis, data categories, and retention.

    Usage::

        keeper = ProcessingRecordKeeper("session-123")
        keeper.record(
            purpose=ProcessingPurpose.FACT_EXTRACTION,
            data_categories=["text_input"],
            legal_basis="legitimate_interest",
            input_size_bytes=4096,
        )
        records = keeper.export()
    """

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._activities: list[ProcessingActivity] = []

    def record(
        self,
        purpose: ProcessingPurpose,
        data_categories: list[str],
        legal_basis: str = "legitimate_interest",
        input_size_bytes: int = 0,
        output_size_bytes: int = 0,
        automated_decision: bool = False,
        human_oversight: bool = False,
        retention_period: str = "session",
    ) -> ProcessingActivity:
        """Record a data processing activity.

        Args:
            purpose: Processing purpose for the activity.
            data_categories: Categories of data processed (e.g. ["text_input"]).
            legal_basis: GDPR legal basis string.
            input_size_bytes: Size of input data in bytes.
            output_size_bytes: Size of output data in bytes.
            automated_decision: Whether automated decision-making occurred.
            human_oversight: Whether human oversight was available.
            retention_period: Retention descriptor (e.g. "session", "30d").

        Returns:
            The created ``ProcessingActivity``.
        """
        activity = ProcessingActivity(
            activity_id=f"proc-{uuid.uuid4().hex[:8]}",
            purpose=purpose,
            data_categories=data_categories,
            legal_basis=legal_basis,
            timestamp=time.time(),
            session_id=self._session_id,
            input_size_bytes=input_size_bytes,
            output_size_bytes=output_size_bytes,
            automated_decision=automated_decision,
            human_oversight=human_oversight,
            retention_period=retention_period,
        )
        self._activities.append(activity)
        return activity

    @property
    def activity_count(self) -> int:
        """Number of recorded processing activities."""
        return len(self._activities)

    def export(self) -> list[dict[str, Any]]:
        """Export all processing records for regulatory review.

        Returns:
            List of dicts representing every recorded activity.
        """
        return [
            {
                "activity_id": a.activity_id,
                "purpose": a.purpose.value,
                "data_categories": a.data_categories,
                "legal_basis": a.legal_basis,
                "timestamp": a.timestamp,
                "session_id": a.session_id,
                "input_size_bytes": a.input_size_bytes,
                "output_size_bytes": a.output_size_bytes,
                "data_subjects": a.data_subjects,
                "retention_period": a.retention_period,
                "automated_decision": a.automated_decision,
                "human_oversight": a.human_oversight,
            }
            for a in self._activities
        ]

    def summary(self) -> dict[str, Any]:
        """Summarize processing activities for compliance dashboard.

        Returns:
            Dict with totals, per-purpose counts, input/output byte sums, and
            oversight/decision counts.
        """
        by_purpose: dict[str, int] = {}
        total_input = 0
        total_output = 0
        for a in self._activities:
            by_purpose[a.purpose.value] = by_purpose.get(a.purpose.value, 0) + 1
            total_input += a.input_size_bytes
            total_output += a.output_size_bytes

        return {
            "session_id": self._session_id,
            "total_activities": len(self._activities),
            "by_purpose": by_purpose,
            "total_input_bytes": total_input,
            "total_output_bytes": total_output,
            "automated_decisions": sum(
                1 for a in self._activities if a.automated_decision
            ),
            "human_oversight_available": sum(
                1 for a in self._activities if a.human_oversight
            ),
        }


# ---------------------------------------------------------------------------
# Human oversight controls (EU AI Act Art. 14)
# ---------------------------------------------------------------------------


class HumanOversightLevel(str, Enum):
    """Levels of human oversight (EU AI Act Art. 14) (§7.13.4)."""

    NONE = "none"  # Fully autonomous (CRP default for context management)
    INFORMED = "informed"  # Human is informed of AI actions (logging/alerts)
    APPROVAL = "approval"  # Human must approve before action
    CONTROL = "control"  # Human can intervene and override at any point


@dataclass
class OversightConfig:
    """Human oversight configuration (§7.13.4).

    EU AI Act Art. 14: High-risk AI systems must be designed to allow
    effective human oversight during their period of use.
    """

    level: HumanOversightLevel = HumanOversightLevel.INFORMED
    require_approval_for_dispatch: bool = False
    require_approval_for_ingest: bool = False
    require_approval_for_export: bool = False
    require_approval_for_deletion: bool = False
    halt_on_injection_detection: bool = False  # Halt if injection detected
    halt_on_pii_detection: bool = False  # Halt if PII detected
    max_autonomous_dispatches: int = 0  # 0 = unlimited
    alert_on_quality_below: str = ""  # Quality tier threshold (e.g. "C")


@dataclass
class OversightEvent:
    """Records a human oversight event."""

    event_id: str
    event_type: str  # "approval_requested", "approved", "denied", "halted"
    operation: str  # "dispatch", "ingest", "export", "deletion"
    timestamp: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)
    approved_by: str = ""  # Hash of approver identity


class HumanOversightController:
    """Implements human oversight controls (EU AI Act Art. 14) (§7.13.4).

    ISO 42001 A.6.2.3: Organizations must establish processes for human
    oversight of AI systems appropriate to the risk level.

    Usage::

        hoc = HumanOversightController(OversightConfig(
            level=HumanOversightLevel.APPROVAL,
            require_approval_for_dispatch=True,
        ))

        # Before dispatch:
        if hoc.requires_approval("dispatch"):
            approval = hoc.request_approval("dispatch", {"task": "..."})
            # ... wait for human approval ...
            hoc.record_decision(approval.event_id, approved=True)
    """

    def __init__(self, config: OversightConfig | None = None) -> None:
        self._config = config or OversightConfig()
        self._events: list[OversightEvent] = []
        self._autonomous_count = 0

    @property
    def config(self) -> OversightConfig:
        """Return the config."""
        return self._config

    @property
    def level(self) -> HumanOversightLevel:
        """Return the level."""
        return self._config.level

    def requires_approval(self, operation: str) -> bool:
        """Check if an operation requires human approval.

        Args:
            operation: One of "dispatch", "ingest", "export", "deletion".

        Returns:
            True if the configured oversight level and per-operation flags
            require explicit human approval.
        """
        if self._config.level in (
            HumanOversightLevel.NONE,
            HumanOversightLevel.INFORMED,
        ):
            return False

        if operation == "dispatch":
            return self._config.require_approval_for_dispatch
        if operation == "ingest":
            return self._config.require_approval_for_ingest
        if operation == "export":
            return self._config.require_approval_for_export
        if operation == "deletion":
            return self._config.require_approval_for_deletion
        return False

    def check_autonomous_limit(self) -> bool:
        """Check if the autonomous dispatch limit has been reached.

        Returns:
            True if more autonomous dispatches are allowed (or no limit is set).
        """
        if self._config.max_autonomous_dispatches <= 0:
            return True
        return self._autonomous_count < self._config.max_autonomous_dispatches

    def record_autonomous_dispatch(self) -> None:
        """Record an autonomous dispatch for limit tracking.

        Returns:
            None. Increments the internal autonomous dispatch counter.
        """
        self._autonomous_count += 1

    def request_approval(
        self,
        operation: str,
        details: dict[str, Any] | None = None,
    ) -> OversightEvent:
        """Create an approval request event.

        Args:
            operation: Operation requiring approval.
            details: Arbitrary context for the reviewer.

        Returns:
            The created ``OversightEvent``.
        """
        event = OversightEvent(
            event_id=f"oversight-{uuid.uuid4().hex[:8]}",
            event_type="approval_requested",
            operation=operation,
            details=details or {},
        )
        self._events.append(event)

        logger.info(
            "Human oversight: approval requested for %s (event=%s)",
            operation,
            event.event_id,
        )
        return event

    def record_decision(
        self,
        event_id: str,
        approved: bool,
        approved_by: str = "",
        reason: str = "",
    ) -> OversightEvent:
        """Record a human oversight decision.

        Args:
            event_id: ID of the original approval request.
            approved: True if approved, False if denied.
            approved_by: Identifier of the reviewer.
            reason: Optional reason for the decision.

        Returns:
            The created ``OversightEvent``.
        """
        event = OversightEvent(
            event_id=event_id,
            event_type="approved" if approved else "denied",
            operation="decision",
            details={"reason": reason},
            approved_by=approved_by,
        )
        self._events.append(event)

        logger.info(
            "Human oversight: %s (event=%s, by=%s)",
            "approved" if approved else "DENIED",
            event_id,
            approved_by or "anonymous",
        )
        return event

    def record_halt(
        self,
        operation: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> OversightEvent:
        """Record a halt event (system stopped due to policy).

        Args:
            operation: Operation that was halted.
            reason: Human-readable reason for the halt.
            details: Additional context.

        Returns:
            The created ``OversightEvent``.
        """
        event = OversightEvent(
            event_id=f"halt-{uuid.uuid4().hex[:8]}",
            event_type="halted",
            operation=operation,
            details={"reason": reason, **(details or {})},
        )
        self._events.append(event)

        logger.warning(
            "Human oversight: HALTED %s — %s", operation, reason
        )
        return event

    def should_halt_on_injection(self) -> bool:
        """Check if processing should halt when injection is detected.

        Returns:
            True if ``halt_on_injection_detection`` is enabled.
        """
        return self._config.halt_on_injection_detection

    def should_halt_on_pii(self) -> bool:
        """Check if processing should halt when PII is detected.

        Returns:
            True if ``halt_on_pii_detection`` is enabled.
        """
        return self._config.halt_on_pii_detection

    def to_dict(self) -> dict[str, Any]:
        """Export oversight state for compliance reporting.

        Returns:
            Dict summarising oversight level, autonomous dispatch counts, and
            approval/denial/halt event counts.
        """
        return {
            "level": self._config.level.value,
            "autonomous_dispatches": self._autonomous_count,
            "max_autonomous_dispatches": self._config.max_autonomous_dispatches,
            "total_oversight_events": len(self._events),
            "approvals_requested": sum(
                1 for e in self._events if e.event_type == "approval_requested"
            ),
            "approved": sum(
                1 for e in self._events if e.event_type == "approved"
            ),
            "denied": sum(
                1 for e in self._events if e.event_type == "denied"
            ),
            "halts": sum(
                1 for e in self._events if e.event_type == "halted"
            ),
        }
