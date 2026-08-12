# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Session data types — SessionHandle, SessionStatus, CostEstimate.

These dataclasses implement the JSON schemas used by the CRP session API:
``session-handle.json``, ``session-status.json``, ``cost-estimate.json``,
``quality-report.json``, ``envelope-preview.json``, ``stream-event.json``,
and ``persisted-state-header.json``.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from crp._version import __version__


@dataclass
class SessionHandle:
    """Session identity and lifetime metadata.

    Implements the ``session-handle.json`` schema. The ``session_key`` is
    managed separately by ``SessionBindingManager`` and is never serialised
    to JSON or cold storage.

    Attributes:
        session_id: Unique UUID for this session.
        protocol_version: CRP protocol version running.
        capabilities: Operations the session supports.
        created_at: Unix timestamp of creation.
        expires_at: Unix timestamp after which the session is invalid.
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    protocol_version: str = __version__
    capabilities: list[str] = field(default_factory=lambda: ["dispatch", "ingest", "status"])
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def __post_init__(self) -> None:
        """Apply the 24-hour default expiry if none was provided."""
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + 86400  # 24h default

    @property
    def is_expired(self) -> bool:
        """Return True if the current time is past ``expires_at``."""
        return time.time() > self.expires_at


@dataclass
class RemainingBudget:
    """Remaining quota for a session.

    Attributes:
        windows_remaining: Windows left before ``max_windows_per_session``.
        input_tokens_remaining: Input tokens left before ``max_total_input_tokens``.
        output_tokens_remaining: Output tokens left before ``max_total_output_tokens``.
    """

    windows_remaining: int | None = None
    input_tokens_remaining: int | None = None
    output_tokens_remaining: int | None = None


@dataclass
class SessionStatus:
    """Live session metrics returned by ``session_status()``.

    Implements the ``session-status.json`` schema.

    Attributes:
        session_id: Session identifier.
        windows_completed: Number of primary + continuation windows completed.
        total_input_tokens: Cumulative input tokens across all windows.
        total_output_tokens: Cumulative output tokens across all windows.
        facts_in_warm_state: Current number of facts in the warm store.
        overhead_ratio: Ratio of continuation windows to total windows.
        remaining_budget: Remaining quota, or None if no caps configured.
        total_cost: Estimated USD cost, or None if provider pricing unknown.
    """

    session_id: str = ""
    windows_completed: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    facts_in_warm_state: int = 0
    overhead_ratio: float = 0.0
    remaining_budget: RemainingBudget | None = None
    total_cost: float | None = None  # USD, None if pricing unknown


@dataclass
class CostEstimate:
    """Pre-flight cost estimate returned by ``estimate_session()``.

    Implements the ``cost-estimate.json`` schema.

    Attributes:
        estimated_windows: Number of dispatches estimated.
        estimated_input_tokens: Total input tokens estimated.
        estimated_output_tokens: Total output tokens estimated.
        estimated_cost_usd: Estimated USD cost, or None if pricing unknown.
        confidence: "high", "medium", or "low" depending on input completeness.
    """

    estimated_windows: int = 1
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_cost_usd: float | None = None
    confidence: str = "low"  # "high" | "medium" | "low"


@dataclass
class SecurityFlags:
    """Security validation results — always present in QualityReport (§7.4).

    Attributes:
        injection_markers_detected: Count of injection patterns found.
        injection_marker_details: Details for each detected marker.
        unicode_normalized: Whether unicode input was normalised.
        control_chars_stripped: Number of control characters removed.
        input_truncated: Whether input was truncated to fit budget.
        integrity_violations: Count of provenance-chain violations.
        output_injection_facts_penalized: Output-side injection detections (§7.5.2).
    """

    injection_markers_detected: int = 0
    injection_marker_details: list[dict[str, Any]] = field(default_factory=list)
    unicode_normalized: bool = False
    control_chars_stripped: int = 0
    input_truncated: bool = False
    integrity_violations: int = 0
    # Output-side injection detection (§7.5.2)
    output_injection_facts_penalized: int = 0


@dataclass
class QualityReport:
    """Governance summary returned by every ``dispatch()`` call.

    Implements the ``quality-report.json`` schema. ``output`` is the COMPLETE,
    UNMODIFIED LLM output (Axiom 9).

    Attributes:
        session_id: Session identifier.
        window_id: Window identifier for this dispatch.
        output: Raw LLM output.
        facts_extracted: Number of facts extracted from the output.
        security_flags: Security validation results.
        continuation_windows: Number of continuation windows triggered.
        envelope_saturation: Envelope token utilisation ratio.
        quality_tier: "S", "A", "B", "C", or "D".
        telemetry: Optional per-window telemetry dict.
    """

    session_id: str = ""
    window_id: str = ""
    output: str = ""
    facts_extracted: int = 0
    security_flags: SecurityFlags = field(default_factory=SecurityFlags)
    continuation_windows: int = 0
    envelope_saturation: float = 0.0
    quality_tier: str | None = None  # "S" | "A" | "B" | "C" | "D"
    telemetry: dict[str, Any] | None = None


@dataclass
class EnvelopePreview:
    """Envelope inspection result returned by ``preview_envelope()``.

    Implements the ``envelope-preview.json`` schema.

    Attributes:
        total_tokens: System + task + envelope tokens.
        envelope_tokens: Tokens consumed by the constructed envelope.
        generation_reserve: Tokens reserved for LLM generation.
        facts_included: Facts packed into the envelope.
        facts_available: Total facts available in the warm store.
        saturation: Envelope token utilisation ratio.
    """

    total_tokens: int = 0
    envelope_tokens: int = 0
    generation_reserve: int = 0
    facts_included: int = 0
    facts_available: int = 0
    saturation: float = 0.0


@dataclass
class StreamEvent:
    """Single event emitted by ``dispatch_stream()`` / ``async_dispatch_stream()``.

    Implements the ``stream-event.json`` schema. Concatenating all ``token``
    events' ``data`` values MUST produce the same string as non-streaming output.

    Attributes:
        event_type: One of "token", "extraction", "continuation",
            "window_complete", "done", or "error".
        data: Event payload (string for tokens, dict for other events).
    """

    event_type: str = "token"  # "token"|"extraction"|"continuation"|"window_complete"|"done"|"error"
    data: Any = None


@dataclass
class PersistedStateHeader:
    """Header for all persisted state data.

    Implements the ``persisted-state-header.json`` schema.

    Attributes:
        schema_version: Data schema version.
        protocol_version: CRP protocol version.
        created_at: Unix timestamp of persistence.
        checksum: BLAKE3 hash of the payload.
    """

    schema_version: str = __version__
    protocol_version: str = __version__
    created_at: float = field(default_factory=time.time)
    checksum: str = ""  # BLAKE3 hash of payload
