# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""TaskIntent — structured task description for CRP dispatch (§2.3).

This module defines the ``TaskIntent`` dataclass and ``OutputType`` enum,
which together describe what the user wants from a single dispatch. All
fields are optional; CRP infers sensible defaults from raw ``task_input``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutputType(str, Enum):
    """Expected output formats per the task-intent.json schema."""

    TEXT = "text"
    """Plain text response."""
    JSON = "json"
    """Structured JSON response; may be validated against ``output_schema``."""
    MARKDOWN = "markdown"
    """Markdown-formatted response."""
    CODE = "code"
    """Source code response."""


@dataclass
class TaskIntent:
    """Structured task description per §2.3.

    All fields are optional — CRP infers missing values from the raw task input.
    Matches the ``task-intent.json`` schema exactly.

    Attributes:
        description: Optional human-readable summary of the task.
        system_prompt: Optional system prompt override for this dispatch.
        task_input: The user's actual request / question.
        expected_output_type: Desired response format.
        max_windows: Maximum continuation windows allowed.
        max_output_tokens: Maximum tokens to generate in this dispatch.
        output_schema: JSON Schema for structured output validation.
        metadata: Arbitrary key-value context for routing or observability.
    """

    description: str | None = None
    system_prompt: str | None = None
    task_input: str | None = None
    expected_output_type: OutputType | str | None = None
    max_windows: int | None = None
    max_output_tokens: int | None = None
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
