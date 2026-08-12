# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Static linter for CRP-* header usage in source text or header dicts."""

from __future__ import annotations

import re
from typing import Any

from crp.headers import names as header_names

# Build the canonical set of CRP header names (value strings).
_CANONICAL_HEADERS: set[str] = {
    value
    for name, value in vars(header_names).items()
    if name.isupper() and isinstance(value, str) and value.startswith("CRP-")
}


def _find_crp_headers(text: str) -> list[dict[str, Any]]:
    """Return every CRP-like header string found in *text*."""
    found: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in re.finditer(r"CRP-[A-Za-z0-9-]+", line):
            name = match.group(0)
            found.append(
                {
                    "line": line_no,
                    "column": match.start() + 1,
                    "header": name,
                    "canonical": name in _CANONICAL_HEADERS,
                }
            )
    return found


def lint(text: str) -> dict[str, Any]:
    """Lint a snippet of code or headers for CRP header usage."""
    findings = _find_crp_headers(text)
    unknown = [f for f in findings if not f["canonical"]]
    known = [f for f in findings if f["canonical"]]
    issues: list[dict[str, Any]] = []

    if unknown:
        issues.append(
            {
                "severity": "warning",
                "message": (
                    "Unknown CRP-like header names found. "
                    "They may be typos or future headers not in this SDK version."
                ),
                "headers": unknown,
            }
        )

    if known:
        issues.append(
            {
                "severity": "info",
                "message": (
                    "CRP headers detected. Prefer the SDK or the base_url swap; "
                    "do not hand-craft headers unless you are implementing infrastructure."
                ),
                "headers": known,
            }
        )

    return {
        "crp_header_count": len(findings),
        "unknown_count": len(unknown),
        "issues": issues,
        "ok": not unknown,
    }
