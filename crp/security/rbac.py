# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""RBAC & rate limiting — role-based access control + per-session limits (§7.10).

Roles: OBSERVER (read-only), OPERATOR (dispatch + ingest), ADMIN (full).
Rate limits: 60 req/min dispatch, 100 MB/min ingest, per-session token cap.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum


class Role(IntEnum):
    """RBAC roles with increasing privilege (§6G.1)."""

    OBSERVER = 0  # Read-only: inspect state, read facts
    OPERATOR = 1  # Dispatch + ingest: all observer + dispatch, ingest
    ADMIN = 2  # Full: all operator + config, delete, export


class Permission(str):
    """Named permission strings."""

    # Observer permissions
    READ_FACTS = "read_facts"
    READ_STATE = "read_state"
    READ_ENVELOPE = "read_envelope"
    READ_EVENTS = "read_events"

    # Operator permissions
    DISPATCH = "dispatch"
    INGEST = "ingest"
    STORE_FACTS = "store_facts"

    # Admin permissions
    DELETE_FACTS = "delete_facts"
    EXPORT_STATE = "export_state"
    CONFIGURE = "configure"
    MANAGE_SESSIONS = "manage_sessions"


# Role → allowed permissions
_ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.OBSERVER: frozenset({
        Permission.READ_FACTS,
        Permission.READ_STATE,
        Permission.READ_ENVELOPE,
        Permission.READ_EVENTS,
    }),
    Role.OPERATOR: frozenset({
        Permission.READ_FACTS,
        Permission.READ_STATE,
        Permission.READ_ENVELOPE,
        Permission.READ_EVENTS,
        Permission.DISPATCH,
        Permission.INGEST,
        Permission.STORE_FACTS,
        Permission.EXPORT_STATE,
        Permission.CONFIGURE,
    }),
    Role.ADMIN: frozenset({
        Permission.READ_FACTS,
        Permission.READ_STATE,
        Permission.READ_ENVELOPE,
        Permission.READ_EVENTS,
        Permission.DISPATCH,
        Permission.INGEST,
        Permission.STORE_FACTS,
        Permission.DELETE_FACTS,
        Permission.EXPORT_STATE,
        Permission.CONFIGURE,
        Permission.MANAGE_SESSIONS,
    }),
}


@dataclass
class RateLimitConfig:
    """Rate limiting configuration (§6G.2)."""

    dispatch_per_minute: int = 60
    ingest_mb_per_minute: float = 100.0
    session_token_cap: int = 0  # 0 = unlimited


@dataclass
class RateLimitState:
    """Sliding-window rate limit tracking."""

    dispatch_timestamps: deque[float] = field(default_factory=deque)
    ingest_bytes: deque[tuple[float, int]] = field(default_factory=deque)
    session_tokens_used: int = 0


@dataclass
class AccessResult:
    """Result of an RBAC check."""

    allowed: bool
    reason: str = ""
    role: Role = Role.OBSERVER


class RBACEnforcer:
    """Role-based access control + rate limiting (§7.10).

    Usage:
        rbac = RBACEnforcer(role=Role.OPERATOR)
        result = rbac.check_permission("dispatch")
        if not result.allowed:
            raise PermissionError(result.reason)
        result = rbac.check_rate_limit("dispatch")
        if not result.allowed:
            raise RateLimitError(result.reason)
        rbac.record_dispatch()
    """

    def __init__(
        self,
        role: Role = Role.OPERATOR,
        config: RateLimitConfig | None = None,
    ) -> None:
        self._role = role
        self._config = config or RateLimitConfig()
        self._limits = RateLimitState()
        self._permissions = _ROLE_PERMISSIONS[role]

    @property
    def role(self) -> Role:
        """Return the role."""
        return self._role

    @role.setter
    def role(self, value: Role) -> None:
        self._role = value
        self._permissions = _ROLE_PERMISSIONS[value]

    # ── Permission checks (§6G.1) ─────────────────────────────

    def check_permission(self, permission: str) -> AccessResult:
        """Check if current role has the given permission."""
        if permission in self._permissions:
            return AccessResult(allowed=True, role=self._role)
        return AccessResult(
            allowed=False,
            reason=f"Role {self._role.name} lacks permission '{permission}'",
            role=self._role,
        )

    def has_permission(self, permission: str) -> bool:
        """Return True if the current role has *permission*."""
        return permission in self._permissions

    # ── Rate limiting (§6G.2) ─────────────────────────────────

    def check_rate_limit(self, operation: str, payload_bytes: int = 0) -> AccessResult:
        """Check if the operation is within rate limits."""
        now = time.time()
        window_start = now - 60.0  # 1-minute sliding window

        if operation == Permission.DISPATCH:
            # Clean old entries
            while self._limits.dispatch_timestamps and self._limits.dispatch_timestamps[0] < window_start:
                self._limits.dispatch_timestamps.popleft()

            if len(self._limits.dispatch_timestamps) >= self._config.dispatch_per_minute:
                return AccessResult(
                    allowed=False,
                    reason=f"Dispatch rate limit exceeded: {self._config.dispatch_per_minute}/min",
                    role=self._role,
                )

        elif operation == Permission.INGEST:
            # Clean old entries
            while self._limits.ingest_bytes and self._limits.ingest_bytes[0][0] < window_start:
                self._limits.ingest_bytes.popleft()

            total_mb = sum(b for _, b in self._limits.ingest_bytes) / (1024 * 1024)
            incoming_mb = payload_bytes / (1024 * 1024)
            if total_mb + incoming_mb > self._config.ingest_mb_per_minute:
                return AccessResult(
                    allowed=False,
                    reason=f"Ingest rate limit exceeded: {self._config.ingest_mb_per_minute} MB/min",
                    role=self._role,
                )

        # Session token cap
        if self._config.session_token_cap > 0:
            if self._limits.session_tokens_used >= self._config.session_token_cap:
                return AccessResult(
                    allowed=False,
                    reason=f"Session token cap reached: {self._config.session_token_cap}",
                    role=self._role,
                )

        return AccessResult(allowed=True, role=self._role)

    # ── Recording operations ──────────────────────────────────

    def record_dispatch(self, tokens_used: int = 0) -> None:
        """Record a dispatch operation for rate limiting."""
        self._limits.dispatch_timestamps.append(time.time())
        self._limits.session_tokens_used += tokens_used

    def record_ingest(self, payload_bytes: int) -> None:
        """Record an ingest operation for rate limiting."""
        self._limits.ingest_bytes.append((time.time(), payload_bytes))

    def record_tokens(self, count: int) -> None:
        """Record token consumption."""
        self._limits.session_tokens_used += count

    @property
    def session_tokens_used(self) -> int:
        """Return the session tokens used."""
        return self._limits.session_tokens_used

    def reset_limits(self) -> None:
        """Reset all rate limit counters."""
        self._limits = RateLimitState()
