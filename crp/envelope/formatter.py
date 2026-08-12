# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 3G — Envelope serialization (§2.2).

Formats the envelope as plain text with [BRACKETED_CAPS] section markers.
Section priority tiers (03_ENVELOPE §2.2):

  Tier 1 (always): [GOAL], [PHASE], [BLOCKER], [CONSTRAINT], [WINDOW]
  Tier 2 (include when available): [LLM_SYNTHESIS], [TASK], [OUTPUT_FORMAT]
  Tier 3 (adaptive): [DISCOVERIES], [SOURCE], [DECISIONS], [ERROR_LOG],
      [TOOL_HISTORY], [EXPANDED: {label}], [KNOWLEDGE: {query}],
      [KNOWLEDGE_GRAPH: {seed}], [KNOWLEDGE_COMMUNITY: {name}]
  Tier 4 (weak models only): [REASONING APPROACH], [SIMILAR SOLVED EXAMPLES]

Fact format:
  - {fact text}: {detail} — {source window/evidence}
    ↳ [{RELATION_TYPE}] {target_fact_text}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .packer import PackedFact

if TYPE_CHECKING:
    from ..core.context_source import ContextSource

# ---------------------------------------------------------------------------
# Section definitions
# ---------------------------------------------------------------------------

# Priority tiers — lower number = higher priority
TIER_1_SECTIONS = ("GOAL", "PHASE", "BLOCKER", "CONSTRAINT", "WINDOW")
TIER_2_SECTIONS = ("LLM_SYNTHESIS", "TASK", "OUTPUT_FORMAT")
TIER_3_SECTIONS = (
    "DISCOVERIES",
    "SOURCE",
    "CONTEXT_SOURCES",   # CRP 2.1 — input-side provenance (§7.14.3)
    "DECISIONS",
    "ERROR_LOG",
    "TOOL_HISTORY",
)
# Tier 3 dynamic: EXPANDED, KNOWLEDGE, KNOWLEDGE_GRAPH, KNOWLEDGE_COMMUNITY
# Tier 4: REASONING APPROACH, SIMILAR SOLVED EXAMPLES


@dataclass
class EnvelopeSection:
    """One section of the formatted envelope."""

    name: str = ""  # e.g. "GOAL", "EXPANDED: MySource"
    content: str = ""
    tier: int = 1
    tokens: int = 0


# ---------------------------------------------------------------------------
# Section header formatting
# ---------------------------------------------------------------------------


def _section_header(name: str) -> str:
    """Format a [BRACKETED_CAPS] section header."""
    return f"[{name.upper()}]"


def _classify_tier(name: str) -> int:
    """Determine the tier of a section by its name."""
    upper = name.upper()
    if upper in TIER_1_SECTIONS:
        return 1
    if upper in TIER_2_SECTIONS:
        return 2
    if upper in TIER_3_SECTIONS:
        return 3
    if upper.startswith(("EXPANDED:", "KNOWLEDGE:", "KNOWLEDGE_GRAPH:", "KNOWLEDGE_COMMUNITY:")):
        return 3
    if upper in ("REASONING APPROACH", "SIMILAR SOLVED EXAMPLES"):
        return 4
    return 3  # default to tier 3 for unknown sections


# ---------------------------------------------------------------------------
# Format facts into [DISCOVERIES] section
# ---------------------------------------------------------------------------


def format_facts_section(packed_facts: list[PackedFact]) -> str:
    """Format packed facts into the body of the [DISCOVERIES] section.

    Separates bookend facts with a marker comment.
    """
    main_facts: list[str] = []
    bookend_facts: list[str] = []

    for pf in packed_facts:
        if pf.is_bookend:
            bookend_facts.append(pf.text)
        else:
            main_facts.append(pf.text)

    parts: list[str] = []
    if main_facts:
        parts.extend(main_facts)
    if bookend_facts:
        parts.append("")  # blank line before bookend
        parts.append("--- Key facts (reinforced) ---")
        parts.extend(bookend_facts)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Format context sources into [CONTEXT_SOURCES] section  (CRP 2.1, §14)
# ---------------------------------------------------------------------------


def format_context_sources_section(
    sources: list["ContextSource"],
    *,
    include_benign: bool = False,
) -> str:
    """Render a compact provenance table for the [CONTEXT_SOURCES] section.

    One line per source::

        - {{kind}} [{{origin}}/{{trust}}] id={{source_id}} [pii] [{{region}}]

    Pure user/system turns are elided by default (their provenance travels
    via role) — pass ``include_benign=True`` to emit them anyway.
    """
    from ..core.context_source import SourceKind  # local import avoids cycle

    benign = {SourceKind.USER_TURN, SourceKind.SYSTEM_PROMPT, SourceKind.DEVELOPER_PROMPT}
    lines: list[str] = []
    for src in sources:
        if not include_benign and src.kind in benign:
            continue
        flags: list[str] = []
        if getattr(src, "contains_pii", False):
            flags.append("pii")
        region = getattr(src, "region", "") or ""
        if region:
            flags.append(region)
        flag_str = f" [{' '.join(flags)}]" if flags else ""
        sid = src.source_id or "-"
        lines.append(
            f"- {src.kind.value} [{src.origin.value}/{src.trust_level.value}] "
            f"id={sid}{flag_str}"
        )
    return "\n".join(lines)


def format_envelope(
    sections: dict[str, str],
    packed_facts: list[PackedFact] | None = None,
) -> str:
    """Format *sections* into the final envelope text.

    Parameters
    ----------
    sections : dict[str, str]
        Section name → content text.  Names should be upper-case
        (e.g. ``{"GOAL": "Analyse CVE...", "PHASE": "scanning"}``).
    packed_facts : list[PackedFact] | None
        If provided, formats and inserts as the [DISCOVERIES] section.

    Returns
    -------
    str
        Plain-text envelope: ``[SECTION_NAME]\\ncontent\\n\\n...``
    """
    # Build section objects with tier classification
    envelope_sections: list[EnvelopeSection] = []

    for name, content in sections.items():
        if content and content.strip():
            envelope_sections.append(
                EnvelopeSection(
                    name=name,
                    content=content.strip(),
                    tier=_classify_tier(name),
                )
            )

    # Add packed facts as DISCOVERIES if not already provided
    if packed_facts and "DISCOVERIES" not in sections:
        facts_text = format_facts_section(packed_facts)
        if facts_text.strip():
            envelope_sections.append(
                EnvelopeSection(
                    name="DISCOVERIES",
                    content=facts_text,
                    tier=3,
                )
            )

    # Sort by tier (lower = higher priority), then preserve insertion order within tier
    envelope_sections.sort(key=lambda s: s.tier)

    # Serialize
    parts: list[str] = []
    for sec in envelope_sections:
        header = _section_header(sec.name)
        parts.append(f"{header}\n{sec.content}")

    return "\n\n".join(parts)
