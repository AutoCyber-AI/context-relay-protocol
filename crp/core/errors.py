# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP error taxonomy — codes 1001-1031 per §6.8.

This module defines the structured exception hierarchy used throughout the
SDK. Every error carries a numeric ``code`` that can be serialised into the
``crp-error.json`` schema and propagated across Gateway / Comply boundaries.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class ErrorCode(IntEnum):
    """All CRP error codes used in ``CRPError.code``.

    Codes are grouped by subsystem:
    - 1001-1005: budget and session lifecycle
    - 1010-1013: validation and security
    - 1020-1021: LLM provider failures
    - 1030-1031: state integrity and provenance chain
    - 1040-1041: context-source attestation (CRP 2.1+, §7.14.3)
    """

    # Budget / session (1001-1005)
    BUDGET_EXHAUSTED = 1001
    RATE_LIMIT_EXCEEDED = 1002
    SESSION_EXPIRED = 1003
    SESSION_LIMIT_EXCEEDED = 1004
    SESSION_CLOSED = 1005

    # Validation / security (1010-1013)
    VALIDATION_ERROR = 1010
    SECURITY_INVARIANT_ERROR = 1011
    SIGNATURE_INVALID = 1012
    RBAC_DENIED = 1013

    # Provider (1020-1021)
    PROVIDER_ERROR = 1020
    PROVIDER_TIMEOUT = 1021

    # State integrity (1030-1031)
    STATE_CORRUPTED = 1030
    CHAIN_VERIFICATION_FAILED = 1031

    # Context-source attestation (1040-1041, added in CRP 2.1 — §7.14.3)
    CONTEXT_ATTESTATION_MISMATCH = 1040
    CONTEXT_MANIFEST_INVALID = 1041


class CRPError(Exception):
    """Base exception for all CRP errors.

    Each error carries a numeric code (1001-1031) per §6.8, a human-readable
    ``message``, and an optional ``details`` dict for structured logging and
    downstream Gateway responses.

    Args:
        code: Numeric error code or ``ErrorCode`` enum member.
        message: Human-readable error description.
        details: Optional structured context (limits, ids, reasons, etc.).
    """

    def __init__(
        self,
        code: int | ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = int(code)
        self.message = message
        self.details: dict[str, Any] = details or {}
        super().__init__(f"CRP-{self.code}: {message}")


class BudgetExhaustedError(CRPError):
    """Raised when a session-level budget cap is exceeded.

    Covers windows-per-session, total input tokens, total output tokens, and
    rate-limit budgets. ``details`` typically contains ``limit``, ``used``,
    and optionally ``requested``.

    Args:
        message: Human-readable description.
        **details: Structured context for logging and headers.
    """

    def __init__(self, message: str = "Budget exhausted", **details: Any) -> None:
        super().__init__(ErrorCode.BUDGET_EXHAUSTED, message, details)


class RateLimitExceededError(CRPError):
    """Raised when a per-session rate limit or RBAC quota is hit."""

    def __init__(self, message: str = "Rate limit exceeded", **details: Any) -> None:
        super().__init__(ErrorCode.RATE_LIMIT_EXCEEDED, message, details)


class SessionExpiredError(CRPError):
    """Raised when an operation is attempted on an expired session handle."""

    def __init__(self, message: str = "Session expired", **details: Any) -> None:
        super().__init__(ErrorCode.SESSION_EXPIRED, message, details)


class SessionClosedError(CRPError):
    """Raised when an operation is attempted after the session was closed."""

    def __init__(self, message: str = "Session is closed", **details: Any) -> None:
        super().__init__(ErrorCode.SESSION_CLOSED, message, details)


class ValidationError(CRPError):
    """Raised for structural validation failures (§7.4)."""

    def __init__(self, message: str = "Validation error", **details: Any) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details)


class ProviderError(CRPError):
    """Raised when the underlying LLM provider returns an error."""

    def __init__(self, message: str = "Provider error", **details: Any) -> None:
        super().__init__(ErrorCode.PROVIDER_ERROR, message, details)


class ProviderTimeoutError(CRPError):
    """Raised when the LLM provider fails to respond within the configured timeout."""

    def __init__(self, message: str = "Provider timeout", **details: Any) -> None:
        super().__init__(ErrorCode.PROVIDER_TIMEOUT, message, details)


class StateCorruptedError(CRPError):
    """Raised when cold-state integrity verification fails."""

    def __init__(self, message: str = "State corrupted", **details: Any) -> None:
        super().__init__(ErrorCode.STATE_CORRUPTED, message, details)


class ChainVerificationFailedError(CRPError):
    """Raised when the window DAG HMAC chain integrity check fails (§7.6)."""

    def __init__(self, message: str = "Chain verification failed", **details: Any) -> None:
        super().__init__(ErrorCode.CHAIN_VERIFICATION_FAILED, message, details)


class SecurityInvariantError(CRPError):
    """Raised when a CRP security invariant is violated (§7.4)."""

    def __init__(self, message: str = "Security invariant violated", **details: Any) -> None:
        super().__init__(ErrorCode.SECURITY_INVARIANT_ERROR, message, details)


class SignatureInvalidError(CRPError):
    """Raised when cryptographic signature verification fails (§7.3)."""

    def __init__(self, message: str = "Signature invalid", **details: Any) -> None:
        super().__init__(ErrorCode.SIGNATURE_INVALID, message, details)
