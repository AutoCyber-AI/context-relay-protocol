# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Input validation — Layer 1 structural validation, CANNOT be disabled (§7.4).

Enforces:
- Size limit: 50 MB
- Unicode NFC normalization
- Null byte stripping
- Control character stripping (preserves \\n, \\t, \\r)
- MIME type validation
- Metadata key count ≤ 50
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Result of input validation."""

    valid: bool
    sanitized_text: str
    warnings: list[str] = field(default_factory=list)
    original_size: int = 0
    sanitized_size: int = 0
    null_bytes_removed: int = 0
    control_chars_removed: int = 0
    metadata_keys_truncated: int = 0


# Allowed MIME types for fact ingestion
ALLOWED_MIME_TYPES = frozenset({
    "text/plain",
    "text/markdown",
    "text/html",
    "text/csv",
    "application/json",
    "application/xml",
    "text/xml",
    "application/yaml",
    "text/yaml",
})

# Size limits
MAX_INPUT_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_METADATA_KEYS = 50

# Control character regex: match all control chars except \n \t \r
_CONTROL_CHAR_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)


class InputValidator:
    """Structural input validation — Layer 1, cannot be disabled (§7.4).

    This validator ALWAYS runs on all input. It cannot be turned off.
    It performs structural sanitization without modifying semantic content.

    Usage:
        validator = InputValidator()
        result = validator.validate("input text")
        if result.valid:
            use(result.sanitized_text)
    """

    def __init__(
        self,
        max_size: int = MAX_INPUT_SIZE,
        max_metadata_keys: int = MAX_METADATA_KEYS,
    ) -> None:
        self._max_size = max_size
        self._max_metadata_keys = max_metadata_keys

    def validate(
        self,
        text: str,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """Validate and sanitize input text (§7.4).

        Steps:
        1. Size check (50 MB limit)
        2. Unicode NFC normalization
        3. Null byte stripping
        4. Control character stripping (keep \\n, \\t, \\r)
        5. MIME type validation (if provided)
        6. Metadata key count check (≤ 50)
        """
        warnings: list[str] = []
        original_size = len(text.encode("utf-8"))

        # 1. Size limit (§6D.2)
        if original_size > self._max_size:
            return ValidationResult(
                valid=False,
                sanitized_text="",
                warnings=[f"Input exceeds size limit: {original_size} > {self._max_size} bytes"],
                original_size=original_size,
            )

        # 2. Unicode NFC normalization (§6D.2)
        sanitized = unicodedata.normalize("NFC", text)

        # 3. Null byte stripping (§6D.2)
        null_count = sanitized.count("\x00")
        if null_count > 0:
            sanitized = sanitized.replace("\x00", "")
            warnings.append(f"Stripped {null_count} null bytes")

        # 4. Control character stripping — keep \n \t \r (§6D.3)
        control_matches = _CONTROL_CHAR_RE.findall(sanitized)
        control_count = len(control_matches)
        if control_count > 0:
            sanitized = _CONTROL_CHAR_RE.sub("", sanitized)
            warnings.append(f"Stripped {control_count} control characters")

        # 5. MIME type validation (§6D.4)
        if mime_type is not None and mime_type not in ALLOWED_MIME_TYPES:
            warnings.append(f"Unrecognized MIME type: {mime_type}")

        # 6. Metadata key count (§6D.4)
        metadata_truncated = 0
        if metadata is not None and len(metadata) > self._max_metadata_keys:
            metadata_truncated = len(metadata) - self._max_metadata_keys
            warnings.append(
                f"Metadata has {len(metadata)} keys, max {self._max_metadata_keys}; "
                f"excess keys will be ignored"
            )

        sanitized_size = len(sanitized.encode("utf-8"))

        return ValidationResult(
            valid=True,
            sanitized_text=sanitized,
            warnings=warnings,
            original_size=original_size,
            sanitized_size=sanitized_size,
            null_bytes_removed=null_count,
            control_chars_removed=control_count,
            metadata_keys_truncated=metadata_truncated,
        )

    def validate_metadata(self, metadata: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """Validate and truncate metadata keys (§6D.4).

        Returns (sanitized_metadata, warnings).
        """
        warnings: list[str] = []
        if len(metadata) <= self._max_metadata_keys:
            return dict(metadata), warnings

        warnings.append(
            f"Metadata truncated: {len(metadata)} → {self._max_metadata_keys} keys"
        )
        # Keep first N keys (deterministic order)
        truncated = dict(list(metadata.items())[:self._max_metadata_keys])
        return truncated, warnings
