# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Circuit breaker for LLM provider calls (§audit H4).

Implements the CLOSED → OPEN → HALF-OPEN pattern to prevent
cascading failures when a provider is unavailable.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("crp.core.circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing — reject calls immediately
    HALF_OPEN = "half_open"  # Testing recovery — allow one probe call


@dataclass
class CircuitBreakerConfig:
    """Configuration for the circuit breaker."""
    failure_threshold: int = 5       # consecutive failures to trip OPEN
    recovery_timeout: float = 30.0   # seconds before OPEN → HALF-OPEN
    success_threshold: int = 2       # successes in HALF-OPEN to close


class CircuitBreaker:
    """Thread-safe circuit breaker for LLM providers."""

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()
        self._half_open_probing = False  # Only allow one probe (§audit2 CB-M10)

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may transition OPEN → HALF-OPEN on read)."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self._config.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    self._half_open_probing = False
                    logger.info("Circuit breaker → HALF-OPEN (recovery timeout elapsed)")
            return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        with self._lock:
            current = self._state
            if current == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self._config.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    self._half_open_probing = False
                    current = CircuitState.HALF_OPEN
            if current == CircuitState.CLOSED:
                return True
            if current == CircuitState.HALF_OPEN:
                if self._half_open_probing:
                    return False  # Only one probe at a time (§audit2 CB-M10)
                self._half_open_probing = True
                return True
            return False  # OPEN — reject

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._half_open_probing = False
                if self._success_count >= self._config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker → CLOSED (recovery confirmed)")
            else:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Single failure in half-open immediately trips back to open
                self._state = CircuitState.OPEN
                self._half_open_probing = False
                logger.warning("Circuit breaker → OPEN (half-open probe failed)")
            elif self._failure_count >= self._config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker → OPEN after %d consecutive failures",
                    self._failure_count,
                )

    def reset(self) -> None:
        """Reset to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_probing = False
