# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Structured logging with correlation IDs for CRP pipeline (§audit H9).

Provides:
- Per-request correlation IDs propagated across dispatch pipeline stages
- JSON-structured log formatter for machine-parseable logs
- Context-local storage for request metadata
"""

from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from typing import Any

# Context variable for correlation ID — propagated across async boundaries
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "crp_correlation_id", default=""
)
_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "crp_session_id", default=""
)


def new_correlation_id() -> str:
    """Generate and set a new correlation ID for the current context."""
    cid = uuid.uuid4().hex[:12]
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str:
    """Get the current correlation ID (empty string if none set)."""
    return _correlation_id.get()


def set_session_context(session_id: str) -> None:
    """Set the session ID for the current logging context."""
    _session_id.set(session_id)


class StructuredFormatter(logging.Formatter):
    """JSON log formatter with automatic correlation ID injection."""

    def format(self, record: logging.LogRecord) -> str:
        """Format *record* as a JSON log line with correlation IDs.

        Args:
            record: Standard library log record.

        Returns:
            JSON-encoded log entry.
        """
        entry: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        cid = _correlation_id.get()
        if cid:
            entry["correlation_id"] = cid

        sid = _session_id.get()
        if sid:
            entry["session_id"] = sid

        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])

        return json.dumps(entry, separators=(",", ":"))


def configure_structured_logging(level: int = logging.INFO) -> None:
    """Configure the root 'crp' logger with structured JSON output.

    Call once at application startup for machine-parseable logs.
    """
    root_logger = logging.getLogger("crp")
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(handler)
    root_logger.setLevel(level)
