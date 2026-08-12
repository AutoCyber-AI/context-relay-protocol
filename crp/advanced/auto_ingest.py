# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Auto-ingest — oversized input handling with structure-aware chunking (§4.6).

Triggers when system_tokens + task_tokens > context_window - gen_reserve.
Zero LLM cost by default: uses graduated extraction (stages 1-5) per chunk,
then reconciles boundary duplicates/complements via embedding similarity.
"""

from __future__ import annotations

import math
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants (§4.6)
# ---------------------------------------------------------------------------

ENVELOPE_OVERHEAD_RESERVE = 500  # tokens reserved for envelope framing
DUP_SIMILARITY = 0.95
COMPLEMENT_SIMILARITY = 0.75
TOKEN_OVERLAP_THRESHOLD = 0.3

# Protected structure patterns
_CODE_BLOCK = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)
_JSON_BLOCK = re.compile(r"\{[^}]{50,}\}", re.DOTALL)
_NUMBERED_LIST = re.compile(r"(?:^|\n)\d+\.\s.+(?:\n\d+\.\s.+){2,}", re.MULTILINE)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ProtectedSpan:
    """Region that must not be split mid-structure."""

    start: int
    end: int
    span_type: str  # "code_block" | "table" | "json_block" | "numbered_list"


@dataclass
class Chunk:
    """One chunk of the oversized input."""

    index: int
    text: str
    offset_start: int
    offset_end: int
    token_count: int = 0


@dataclass
class IngestResult:
    """Summary returned by auto_ingest()."""

    chunks_created: int = 0
    facts_extracted: int = 0
    facts_after_reconciliation: int = 0
    synthesized_task: str = ""
    raw_stored: bool = False


@dataclass
class IngestFact:
    """Lightweight fact from per-chunk extraction."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    confidence: float = 0.0
    chunk_index: int = 0
    chunk_offset_start: int = 0
    chunk_offset_end: int = 0
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protected structure detection
# ---------------------------------------------------------------------------


def detect_protected_structures(text: str) -> list[ProtectedSpan]:
    """Find code blocks, tables, JSON blocks, numbered lists."""
    spans: list[ProtectedSpan] = []
    for m in _CODE_BLOCK.finditer(text):
        spans.append(ProtectedSpan(m.start(), m.end(), "code_block"))
    # Tables: contiguous runs of | lines
    table_lines: list[tuple[int, int]] = []
    for m in _TABLE_ROW.finditer(text):
        table_lines.append((m.start(), m.end()))
    if table_lines:
        run_start = table_lines[0][0]
        run_end = table_lines[0][1]
        for s, e in table_lines[1:]:
            if s - run_end <= 2:
                run_end = e
            else:
                if run_end - run_start > 20:
                    spans.append(ProtectedSpan(run_start, run_end, "table"))
                run_start, run_end = s, e
        if run_end - run_start > 20:
            spans.append(ProtectedSpan(run_start, run_end, "table"))
    for m in _JSON_BLOCK.finditer(text):
        spans.append(ProtectedSpan(m.start(), m.end(), "json_block"))
    for m in _NUMBERED_LIST.finditer(text):
        spans.append(ProtectedSpan(m.start(), m.end(), "numbered_list"))
    return merge_overlapping_spans(spans)


def merge_overlapping_spans(spans: list[ProtectedSpan]) -> list[ProtectedSpan]:
    """Merge overlapping/adjacent protected spans."""
    if not spans:
        return []
    sorted_spans = sorted(spans, key=lambda s: s.start)
    merged: list[ProtectedSpan] = [sorted_spans[0]]
    for s in sorted_spans[1:]:
        prev = merged[-1]
        if s.start <= prev.end:
            prev.end = max(prev.end, s.end)
            prev.span_type = f"{prev.span_type}+{s.span_type}"
        else:
            merged.append(s)
    return merged


# ---------------------------------------------------------------------------
# Structure-aware splitting
# ---------------------------------------------------------------------------


def _in_protected(pos: int, spans: list[ProtectedSpan]) -> bool:
    return any(s.start <= pos < s.end for s in spans)


def _find_split_point(
    text: str, start: int, end: int, spans: list[ProtectedSpan],
) -> int:
    """Find best split point in [start, end) following priority order."""
    region = text[start:end]
    # Priority 1: heading break
    for m in re.finditer(r"\n# ", region):
        pos = start + m.start()
        if not _in_protected(pos, spans):
            return pos
    # Priority 2: paragraph break
    for m in re.finditer(r"\n\n", region):
        pos = start + m.start()
        if not _in_protected(pos, spans):
            return pos
    # Priority 3: between protected structures
    for i in range(len(spans) - 1):
        gap_start = spans[i].end
        if start <= gap_start < end:
            return gap_start
    # Priority 4: sentence boundary
    for m in re.finditer(r"\.\s", region):
        pos = start + m.start() + 1
        if not _in_protected(pos, spans):
            return pos
    # Priority 5: line break
    for m in re.finditer(r"\n", region):
        pos = start + m.start()
        if not _in_protected(pos, spans):
            return pos
    # Priority 6: word boundary (last resort)
    for m in re.finditer(r" ", region):
        pos = start + m.start()
        if not _in_protected(pos, spans):
            return pos
    return end


def split_at_boundaries(
    text: str,
    chunk_size_chars: int,
    overlap_chars: int,
    protected_spans: list[ProtectedSpan],
) -> list[Chunk]:
    """Split text into chunks respecting protected structures."""
    chunks: list[Chunk] = []
    pos = 0
    idx = 0
    text_len = len(text)

    while pos < text_len:
        end = min(pos + chunk_size_chars, text_len)
        if end < text_len:
            split = _find_split_point(text, pos, end, protected_spans)
            if split <= pos:
                split = end  # Fallback: force split
        else:
            split = end

        chunks.append(Chunk(
            index=idx,
            text=text[pos:split],
            offset_start=pos,
            offset_end=split,
        ))
        idx += 1
        # Advance with overlap
        pos = max(pos + 1, split - overlap_chars)

    return chunks


# ---------------------------------------------------------------------------
# Boundary reconciliation
# ---------------------------------------------------------------------------


def _text_overlap_ratio(a: str, b: str) -> float:
    """Token-level overlap ratio between two texts."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / min(len(words_a), len(words_b))


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def reconcile_chunk_boundaries(
    per_chunk_facts: list[list[IngestFact]],
    embedding_fn: Callable[[str], list[float]] | None = None,
) -> list[IngestFact]:
    """Deduplicate/merge facts at chunk boundaries.

    - cosine_similarity > 0.95 → duplicate → skip
    - cosine_similarity > 0.75 AND token_overlap > 0.3 → complement → merge
    - Otherwise → new fact → keep
    """
    if not per_chunk_facts:
        return []
    result = list(per_chunk_facts[0])

    for chunk_idx in range(1, len(per_chunk_facts)):
        for fact in per_chunk_facts[chunk_idx]:
            is_dup = False
            merge_target = None

            for existing in result:
                if embedding_fn:
                    emb_a = embedding_fn(existing.text)
                    emb_b = embedding_fn(fact.text)
                    sim = _cosine_sim(emb_a, emb_b)
                else:
                    sim = _text_overlap_ratio(existing.text, fact.text)

                if sim > DUP_SIMILARITY:
                    is_dup = True
                    break
                if sim > COMPLEMENT_SIMILARITY:
                    tok_overlap = _text_overlap_ratio(existing.text, fact.text)
                    if tok_overlap > TOKEN_OVERLAP_THRESHOLD:
                        merge_target = existing
                        break

            if is_dup:
                continue
            if merge_target is not None:
                merge_target.text = merge_fact_texts(merge_target.text, fact.text)
                merge_target.confidence = max(merge_target.confidence, fact.confidence)
            else:
                result.append(fact)

    return result


def merge_fact_texts(a: str, b: str) -> str:
    """Merge two complementary fact texts, keeping unique content."""
    words_a = a.split()
    words_b = b.split()
    seen = set(w.lower() for w in words_a)
    extra = [w for w in words_b if w.lower() not in seen]
    if extra:
        return a + " " + " ".join(extra)
    return a


# ---------------------------------------------------------------------------
# Main auto_ingest function
# ---------------------------------------------------------------------------


def auto_ingest(
    system_prompt: str,
    task_input: str,
    task_intent_text: str,
    context_window: int,
    count_tokens: Callable[[str], int],
    extract_fn: Callable[[str, str], list[IngestFact]] | None = None,
    embedding_fn: Callable[[str], list[float]] | None = None,
    store_raw_fn: Callable[[str, str], None] | None = None,
    session_id: str = "",
) -> tuple[list[IngestFact], IngestResult]:
    """Handle oversized inputs with structure-aware chunking.

    Args:
        system_prompt: The system prompt (not modified).
        task_input: Raw oversized input text.
        task_intent_text: Short description of task intent.
        context_window: Total context window in tokens.
        count_tokens: Token counting function.
        extract_fn: Per-chunk fact extractor (stages 1-5). If None, returns dummy facts.
        embedding_fn: Optional embedding function for reconciliation.
        store_raw_fn: Optional function to store raw input in cold storage.
        session_id: Current session ID.

    Returns:
        (reconciled_facts, ingest_result)
    """
    # Step 1: Compute available space
    sys_tokens = count_tokens(system_prompt)
    gen_reserve = max(context_window // 4, 1024)
    available_tokens = context_window - sys_tokens - gen_reserve
    if available_tokens <= 0:
        available_tokens = 1024  # Minimum sane value

    # Step 2: Detect protected structures
    protected_spans = detect_protected_structures(task_input)

    # Step 3: Chunk with structure-aware boundaries
    chunk_budget = available_tokens - ENVELOPE_OVERHEAD_RESERVE
    # Approximate chars-per-token ratio
    total_chars = len(task_input)
    total_tokens = count_tokens(task_input)
    chars_per_token = total_chars / max(total_tokens, 1)
    chunk_size_chars = int(chunk_budget * chars_per_token)
    overlap_chars = min(chunk_size_chars // 10, int(500 * chars_per_token))

    chunks = split_at_boundaries(task_input, chunk_size_chars, overlap_chars, protected_spans)

    # Step 4: Per-chunk extraction (zero LLM)
    per_chunk_facts: list[list[IngestFact]] = []
    total_extracted = 0
    for chunk in chunks:
        chunk.token_count = count_tokens(chunk.text)
        if extract_fn:
            facts = extract_fn(chunk.text, task_intent_text)
        else:
            # Minimal fallback: treat entire chunk as one fact
            facts = [IngestFact(
                text=chunk.text[:500],
                confidence=0.5,
                chunk_index=chunk.index,
                chunk_offset_start=chunk.offset_start,
                chunk_offset_end=chunk.offset_end,
                source=f"input_chunk_{chunk.index + 1}_of_{len(chunks)}",
            )]
        for f in facts:
            f.chunk_index = chunk.index
            f.chunk_offset_start = chunk.offset_start
            f.chunk_offset_end = chunk.offset_end
            f.source = f"input_chunk_{chunk.index + 1}_of_{len(chunks)}"
        per_chunk_facts.append(facts)
        total_extracted += len(facts)

    # Step 5: Boundary reconciliation
    reconciled = reconcile_chunk_boundaries(per_chunk_facts, embedding_fn)

    # Step 6: Store raw input in cold storage
    raw_stored = False
    if store_raw_fn and session_id:
        store_raw_fn(task_input, session_id)
        raw_stored = True

    # Step 7: Synthesize task
    synthesized = (
        f"Process the following material ({len(chunks)} sections ingested, "
        f"{len(reconciled)} facts extracted). Original request: "
        f"{task_intent_text[:500]}"
    )

    result = IngestResult(
        chunks_created=len(chunks),
        facts_extracted=total_extracted,
        facts_after_reconciliation=len(reconciled),
        synthesized_task=synthesized,
        raw_stored=raw_stored,
    )

    return reconciled, result
