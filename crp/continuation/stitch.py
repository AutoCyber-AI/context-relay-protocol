# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Stitch algorithm — echo detection, content-aware stitching, validation (§4.8, §04 §3.4)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ContentBoundary(str, Enum):
    """Content type for boundary-aware stitching."""

    PROSE = "prose"
    CODE = "code"
    MARKDOWN = "markdown"
    STRUCTURED = "structured"


@dataclass
class StitchResult:
    """Result of stitching two outputs together."""

    text: str
    echo_removed: int  # chars of echo removed
    boundary_type: ContentBoundary
    bridge_inserted: bool
    trimmed_fragments: list[str]  # never silently discard
    validation_warnings: list[str]


@dataclass
class StitchConfig:
    """Configuration for the stitch algorithm."""

    echo_window: int = 2000  # chars to compare for echo
    min_echo_length: int = 20  # minimum echo to detect
    semantic_echo_threshold: float = 0.85
    max_bridge_tokens: int = 50


# ── LCS-based echo detection (§04 §3.4) ──────────────────────────

def _longest_common_suffix_prefix(prior_tail: str, continuation_head: str) -> str:
    """Find the longest common substring where prior ends and continuation starts.

    Uses a suffix-of-prior / prefix-of-continuation match approach.
    """
    if not prior_tail or not continuation_head:
        return ""

    best = ""
    # Check progressively longer overlaps
    max_len = min(len(prior_tail), len(continuation_head))
    for length in range(1, max_len + 1):
        if prior_tail[-length:] == continuation_head[:length]:
            best = prior_tail[-length:]

    return best


def _lcs_dynamic(a: str, b: str) -> str:
    """Longest Common Substring via dynamic programming.

    Used for echo detection between last 2000 chars of prior
    and first 2000 chars of continuation.
    """
    if not a or not b:
        return ""

    m, n = len(a), len(b)
    # Optimize: only need current and previous row
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    longest = 0
    end_pos = 0

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
                if curr[j] > longest:
                    longest = curr[j]
                    end_pos = i
            else:
                curr[j] = 0
        prev, curr = curr, [0] * (n + 1)

    if longest == 0:
        return ""
    return a[end_pos - longest:end_pos]


def detect_echo(
    prior: str,
    continuation: str,
    config: StitchConfig | None = None,
) -> str:
    """Detect echoed content at the start of continuation.

    Strategy:
    1. Suffix-prefix overlap (exact boundary echo)
    2. LCS on last/first 2000 chars (partial echo)
    """
    cfg = config or StitchConfig()
    window = cfg.echo_window

    prior_tail = prior[-window:] if len(prior) > window else prior
    cont_head = continuation[:window] if len(continuation) > window else continuation

    # Strategy 1: exact suffix-prefix overlap
    overlap = _longest_common_suffix_prefix(prior_tail, cont_head)
    if len(overlap) >= cfg.min_echo_length:
        return overlap

    # Strategy 2: LCS
    lcs = _lcs_dynamic(prior_tail, cont_head)
    if len(lcs) >= cfg.min_echo_length:
        # Only count as echo if it appears at/near the start of continuation
        pos = continuation.find(lcs)
        if pos >= 0 and pos < cfg.echo_window // 2:
            return lcs

    # Strategy 3: Semantic echo — word-overlap similarity (§5E.5)
    prior_words = set(prior_tail.lower().split())
    cont_words = set(cont_head.lower().split())
    if prior_words and cont_words:
        overlap = len(prior_words & cont_words) / min(len(prior_words), len(cont_words))  # type: ignore[assignment]
        if overlap >= cfg.semantic_echo_threshold:  # type: ignore[operator]
            # Find the overlapping segment in continuation
            # Use first sentence that significantly overlaps
            cont_sentences = [s.strip() for s in cont_head.split(".") if len(s.strip()) >= cfg.min_echo_length]
            for sent in cont_sentences[:5]:
                sent_words = set(sent.lower().split())
                if prior_words and sent_words:
                    s_overlap = len(prior_words & sent_words) / max(1, len(sent_words))
                    if s_overlap >= 0.7:
                        return sent

    return ""


# ── Content-type boundary detection ──────────────────────────────

def _detect_boundary_type(text: str) -> ContentBoundary:
    """Detect content type from the tail of text."""
    tail = text[-500:] if len(text) > 500 else text

    # Code: triple backticks, indentation patterns
    if "```" in tail or re.search(r"^\s{4,}\S", tail, re.MULTILINE):
        return ContentBoundary.CODE

    # Markdown: headings, lists, links
    if re.search(r"^#{1,6}\s", tail, re.MULTILINE) or re.search(r"^\s*[-*]\s", tail, re.MULTILINE):
        return ContentBoundary.MARKDOWN

    # Structured: JSON/YAML-like
    if re.search(r"[{}\[\]]", tail) or re.search(r"^\s+\w+:", tail, re.MULTILINE):
        return ContentBoundary.STRUCTURED

    return ContentBoundary.PROSE


def _find_clean_boundary(text: str, boundary_type: ContentBoundary) -> int:
    """Find the best position to end the prior output for clean stitching."""
    if boundary_type == ContentBoundary.PROSE:
        # End at last sentence boundary
        for pattern in [r"[.!?]\s*$", r"[.!?]\s+\S", r"\n\n", r"\n"]:
            match = list(re.finditer(pattern, text[-500:]))
            if match:
                return len(text) - 500 + match[-1].end()
        return len(text)

    elif boundary_type == ContentBoundary.CODE:
        # End at last complete line or code block boundary
        idx = text.rfind("\n```\n")
        if idx > len(text) - 500:
            return idx + 4
        idx = text.rfind("\n\n")
        if idx > len(text) - 200:
            return idx + 2
        return len(text)

    elif boundary_type == ContentBoundary.MARKDOWN:
        # End at last double-newline or heading
        idx = text.rfind("\n\n")
        if idx > len(text) - 300:
            return idx + 2
        return len(text)

    else:  # STRUCTURED
        # End at last complete line
        idx = text.rfind("\n")
        if idx > len(text) - 200:
            return idx + 1
        return len(text)


# ── Bridge insertion (no-echo fallback) ──────────────────────────

def _build_bridge(boundary_type: ContentBoundary, structural_hint: str = "") -> str:
    """Build a small bridge text for no-echo stitching."""
    if boundary_type == ContentBoundary.CODE:
        return "\n\n"
    elif boundary_type == ContentBoundary.MARKDOWN:
        return "\n\n"
    elif boundary_type == ContentBoundary.STRUCTURED:
        return "\n"
    else:
        return "\n\n"


# ── Post-stitch validation (§04 §3.4) ────────────────────────────

def _validate_stitch(text: str) -> list[str]:
    """Post-stitch validation: duplicates, brackets, heading hierarchy."""
    warnings: list[str] = []

    # Duplicate paragraph detection (exact match of 50+ char paragraphs)
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
    seen: set[str] = set()
    for p in paragraphs:
        if p in seen:
            warnings.append(f"duplicate_paragraph: {p[:60]}...")
        seen.add(p)

    # Bracket balance
    for open_c, close_c, name in [("(", ")", "paren"), ("[", "]", "bracket"), ("{", "}", "brace")]:
        balance = text.count(open_c) - text.count(close_c)
        if balance != 0:
            warnings.append(f"unbalanced_{name}: {'+' if balance > 0 else ''}{balance}")

    # Heading hierarchy (no skipped levels: # → ### without ##)
    headings = re.findall(r"^(#{1,6})\s", text, re.MULTILINE)
    if headings:
        prev_level = 0
        for h in headings:
            level = len(h)
            if prev_level > 0 and level > prev_level + 1:
                warnings.append(f"heading_skip: h{prev_level}→h{level}")
            prev_level = level

    return warnings


def _dedup_sections(text: str) -> tuple[str, int]:
    """Remove duplicate sections by heading number (GAP C fix).

    When the same numbered section (e.g. '## 7. Data Protection') appears
    multiple times, keep the LAST occurrence (most recent/complete) and
    remove earlier duplicates.

    Returns (deduped_text, sections_removed).
    """
    # Split text into section blocks keyed by heading number
    section_pattern = re.compile(r"^(#{1,6})\s+(\d{1,3})\.\s+", re.MULTILINE)
    matches = list(section_pattern.finditer(text))

    if not matches:
        return text, 0

    # Track section number → list of (start, end) positions
    section_spans: dict[int, list[tuple[int, int]]] = {}
    for i, m in enumerate(matches):
        sec_num = int(m.group(2))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_spans.setdefault(sec_num, []).append((start, end))

    # Find sections with duplicates — remove all but last occurrence
    ranges_to_remove: list[tuple[int, int]] = []
    for sec_num, spans in section_spans.items():
        if len(spans) > 1:
            # Keep last, remove earlier ones
            for start, end in spans[:-1]:
                ranges_to_remove.append((start, end))

    if not ranges_to_remove:
        return text, 0

    # Remove in reverse order to preserve positions
    ranges_to_remove.sort(reverse=True)
    result = text
    for start, end in ranges_to_remove:
        result = result[:start] + result[end:]

    # Clean up multiple blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result, len(ranges_to_remove)


# ── Main stitch function ─────────────────────────────────────────

def stitch_outputs(
    prior: str,
    continuation: str,
    config: StitchConfig | None = None,
) -> StitchResult:
    """Stitch prior output with continuation output (§4.8, §04 §3.4).

    Algorithm:
    1. Detect echo (LCS on last/first 2000 chars, min 20 chars)
    2. Remove echo from continuation start
    3. Content-type-aware boundary detection
    4. No-echo fallback: structural continuation, bridge insertion
    5. Post-stitch validation
    6. Store any trimmed fragments (never silently discard)
    """
    cfg = config or StitchConfig()
    trimmed: list[str] = []

    if not prior:
        return StitchResult(
            text=continuation,
            echo_removed=0,
            boundary_type=ContentBoundary.PROSE,
            bridge_inserted=False,
            trimmed_fragments=trimmed,
            validation_warnings=[],
        )

    if not continuation:
        return StitchResult(
            text=prior,
            echo_removed=0,
            boundary_type=ContentBoundary.PROSE,
            bridge_inserted=False,
            trimmed_fragments=trimmed,
            validation_warnings=[],
        )

    boundary_type = _detect_boundary_type(prior)

    # Step 1-2: Echo detection and removal
    echo = detect_echo(prior, continuation, cfg)
    echo_len = len(echo)
    bridge_inserted = False

    if echo_len >= cfg.min_echo_length:
        # Remove echo from continuation start
        echo_pos = continuation.find(echo)
        if echo_pos >= 0:
            removed = continuation[:echo_pos + echo_len]
            if echo_pos > 0:
                trimmed.append(removed[:echo_pos])
            continuation = continuation[echo_pos + echo_len:]
    else:
        # No-echo fallback: insert bridge
        bridge = _build_bridge(boundary_type)
        prior_trimmed = prior.rstrip()
        continuation = bridge + continuation.lstrip()
        prior = prior_trimmed
        bridge_inserted = True

    # Step 3: Content-type-aware boundary
    combined = prior + continuation

    # Step 4b: Section-level deduplication (GAP C fix)
    combined, sections_removed = _dedup_sections(combined)
    if sections_removed:
        trimmed.append(f"[dedup: {sections_removed} duplicate section(s) removed]")

    # Step 5: Validation
    warnings = _validate_stitch(combined)

    return StitchResult(
        text=combined,
        echo_removed=echo_len,
        boundary_type=boundary_type,
        bridge_inserted=bridge_inserted,
        trimmed_fragments=trimmed,
        validation_warnings=warnings,
    )


# ── N-way iterative stitch (§04 §3.4) ────────────────────────────

def stitch_many(
    outputs: list[str],
    config: StitchConfig | None = None,
) -> StitchResult:
    """N-way iterative stitch for 50+ windows.

    Applies pairwise stitch left-to-right, accumulating the result.
    """
    if not outputs:
        return StitchResult(
            text="", echo_removed=0, boundary_type=ContentBoundary.PROSE,
            bridge_inserted=False, trimmed_fragments=[], validation_warnings=[],
        )

    cfg = config or StitchConfig()
    accumulated = outputs[0]
    total_echo = 0
    all_trimmed: list[str] = []
    any_bridge = False
    last_boundary = ContentBoundary.PROSE

    for i in range(1, len(outputs)):
        result = stitch_outputs(accumulated, outputs[i], cfg)
        accumulated = result.text
        total_echo += result.echo_removed
        all_trimmed.extend(result.trimmed_fragments)
        if result.bridge_inserted:
            any_bridge = True
        last_boundary = result.boundary_type

    final_warnings = _validate_stitch(accumulated)

    return StitchResult(
        text=accumulated,
        echo_removed=total_echo,
        boundary_type=last_boundary,
        bridge_inserted=any_bridge,
        trimmed_fragments=all_trimmed,
        validation_warnings=final_warnings,
    )
