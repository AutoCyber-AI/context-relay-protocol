# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Stage 1 — Regex extraction (~1ms, MUST).

Extracts structured entities: IPs, CVEs, URLs, emails, JSON blocks,
error codes, versions, ports, and cryptographic hashes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from crp.extraction.types import Fact

# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegexPattern:
    """A single extraction pattern."""

    name: str
    pattern: re.Pattern[str]
    category: str
    confidence: float = 0.95


# Compiled patterns — order matters for priority in case of overlapping spans.
_BUILTIN_PATTERNS: list[RegexPattern] = [
    RegexPattern(
        name="ipv4_address",
        pattern=re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
        category="network_entity",
    ),
    RegexPattern(
        name="ipv6_address",
        pattern=re.compile(
            r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"
            r"|"
            r"\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b"
            r"|"
            r"\b::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}\b"
        ),
        category="network_entity",
    ),
    RegexPattern(
        name="cve_id",
        pattern=re.compile(r"\bCVE-\d{4}-\d{4,7}\b"),
        category="vulnerability",
    ),
    RegexPattern(
        name="url",
        pattern=re.compile(
            r"https?://[^\s\"'<>\])}]+",
            re.ASCII,
        ),
        category="resource",
    ),
    RegexPattern(
        name="email",
        pattern=re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
        ),
        category="contact",
    ),
    RegexPattern(
        name="json_block",
        pattern=re.compile(r"\{[^{}]{10,}\}", re.DOTALL),
        category="structured_data",
    ),
    RegexPattern(
        name="error_code",
        pattern=re.compile(
            r"\b(?:ERR|ERROR|WARN|FATAL|CRITICAL|E|W)[-_]?\d{3,6}\b",
            re.IGNORECASE,
        ),
        category="error_code",
    ),
    RegexPattern(
        name="semver",
        pattern=re.compile(
            r"\bv?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.]+)?\b"
        ),
        category="version",
    ),
    RegexPattern(
        name="port",
        pattern=re.compile(
            r"\b(?:port\s+|:)(\d{1,5})\b", re.IGNORECASE
        ),
        category="network_endpoint",
    ),
    RegexPattern(
        name="hash_sha256",
        pattern=re.compile(r"\b[0-9a-fA-F]{64}\b"),
        category="identifier",
    ),
    RegexPattern(
        name="hash_md5",
        pattern=re.compile(r"\b[0-9a-fA-F]{32}\b"),
        category="identifier",
    ),
]


class RegexExtractor:
    """Stage 1 — fast regex extraction with extensible pattern registry."""

    def __init__(self) -> None:
        self._patterns: list[RegexPattern] = list(_BUILTIN_PATTERNS)
        self._custom_patterns: list[RegexPattern] = []

    # -- Public API ---------------------------------------------------------

    def register_pattern(
        self,
        name: str,
        pattern: str | re.Pattern[str],
        category: str,
        confidence: float = 0.90,
    ) -> None:
        """Add a user-defined extraction pattern."""
        compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
        rp = RegexPattern(name=name, pattern=compiled, category=category, confidence=confidence)
        self._custom_patterns.append(rp)

    def extract(
        self,
        text: str,
        source_window_id: str = "",
    ) -> list[Fact]:
        """Extract all regex-matched facts from *text*.

        Returns de-duplicated facts ordered by position in text.
        """
        seen_spans: set[tuple[int, int]] = set()
        facts: list[tuple[int, Fact]] = []  # (start_pos, Fact)

        for rp in self._all_patterns:
            for m in rp.pattern.finditer(text):
                span = (m.start(), m.end())
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                matched = m.group(0)
                facts.append((
                    m.start(),
                    Fact(
                        text=matched,
                        category=rp.category,
                        source_window_id=source_window_id,
                        confidence=rp.confidence,
                        extraction_stage=1,
                        metadata={"pattern": rp.name, "span": list(span)},
                    ),
                ))

        # Stable sort by position
        facts.sort(key=lambda t: t[0])
        return [f for _, f in facts]

    @property
    def _all_patterns(self) -> list[RegexPattern]:
        return self._patterns + self._custom_patterns

    @property
    def pattern_count(self) -> int:
        """Return the current pattern count."""
        return len(self._all_patterns)
