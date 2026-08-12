# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Gap analysis — L1/L2/L3 requirement extraction and fulfillment scoring (§3.5)."""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger("crp.continuation.gap")
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crp.extraction.types import Fact


@dataclass
class Requirement:
    """A single task requirement at a specific analysis level."""

    text: str
    level: int  # 1=structural, 2=semantic, 3=LLM-assisted
    category: str = ""
    weight: float = 1.0
    fulfilled: bool = False
    fulfillment_score: float = 0.0


@dataclass
class GapResult:
    """Result of gap analysis between requirements and output facts."""

    requirements: list[Requirement]
    gap_score: float  # 0.0 = all fulfilled, 1.0 = nothing fulfilled
    fulfilled_count: int
    total_count: int
    unfulfilled: list[Requirement]
    details: dict[str, object] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Return whether this object is complete."""
        return self.gap_score <= 0.0


# ── L1: Structural requirement extraction ──────────────────────────

_STRUCTURAL_PATTERNS: list[tuple[str, str]] = [
    (r"\b(\d+)\s+(?:\w+\s+){0,2}(?:items?|points?|steps?|sections?|parts?)\b", "enumerated_items"),
    (r"\b(?:list|enumerate|outline)\b", "list_structure"),
    (r"\b(?:compare|contrast|versus|vs\.?)\b", "comparison"),
    (r"\b(?:table|matrix|grid)\b", "tabular"),
    (r"\b(?:code|implement|function|class|module)\b", "code_output"),
    (r"\b(?:explain|describe|elaborate)\b", "explanation"),
    (r"\b(?:summarize|summary|brief|concise)\b", "summary"),
    (r"\b(?:analyze|analysis|evaluate)\b", "analysis"),
    (r"\b(?:example|demonstrate|illustrate)\b", "example"),
    (r"\b(?:pros?\s+(?:and|&)\s+cons?|advantages?\s+(?:and|&)\s+disadvantages?)\b", "pro_con"),
]


def _extract_l1_structural(task_text: str) -> list[Requirement]:
    """L1: regex-based structural requirement extraction.

    When the task requests N numbered sections/items AND those items are
    individually listed (e.g. ``1. Foo — description\\n2. Bar — ...``),
    each item becomes its own requirement so gap analysis can track
    per-section fulfillment rather than a single coarse "N sections" req.
    """
    reqs: list[Requirement] = []
    seen_categories: set[str] = set()

    for pattern, category in _STRUCTURAL_PATTERNS:
        match = re.search(pattern, task_text, re.IGNORECASE)
        if match and category not in seen_categories:
            seen_categories.add(category)

            # If this is an enumerated-items match (e.g. "30 sections"),
            # try to expand into per-item requirements by parsing the
            # numbered list that typically follows in the task text.
            if category == "enumerated_items":
                expanded = _expand_enumerated_items(task_text, match)
                if expanded:
                    reqs.extend(expanded)
                    continue  # skip the coarse "N sections" requirement

            reqs.append(Requirement(
                text=match.group(0),
                level=1,
                category=category,
                weight=1.0,
            ))

    return reqs


def _expand_enumerated_items(task_text: str, enum_match: re.Match) -> list[Requirement]:
    """Expand an 'N sections/items/steps' match into per-item requirements.

    Looks for a numbered list in the task text (``1. Foo\\n2. Bar\\n...``)
    and creates one Requirement per item with the item's title/description.
    Returns empty list if no numbered list is found, letting the caller
    fall back to the coarse requirement.
    """
    # Parse numbered list items: "N. Title" or "N. Title — description"
    items: list[tuple[int, str]] = []
    for m in re.finditer(
        r"(?:^|\n)\s*(\d{1,3})[.)]\s+(.+?)(?=\n\s*\d{1,3}[.)]\s|\n\n|\Z)",
        task_text,
        re.DOTALL,
    ):
        num = int(m.group(1))
        # Take the first line as the item title (strip sub-lines)
        title = m.group(2).split("\n")[0].strip()
        if title:
            items.append((num, title))

    if len(items) < 3:
        return []  # Not enough items to justify expansion

    reqs: list[Requirement] = []
    for num, title in items:
        # Extract just the section name (before any " — " description)
        section_name = title.split(" — ")[0].split(" - ")[0].strip()
        reqs.append(Requirement(
            text=f"Section {num}: {section_name}",
            level=1,
            category=f"section_{num}",
            weight=1.0,
        ))
    return reqs


# ── L2: Semantic requirement extraction ────────────────────────────

_SEMANTIC_MARKERS: list[tuple[str, str, float]] = [
    (r"\b(?:must|shall|required?|need)\b", "mandatory", 1.5),
    (r"\b(?:should|recommend|prefer)\b", "recommended", 1.0),
    (r"\b(?:may|optional|consider)\b", "optional", 0.5),
    (r"\b(?:don't|do not|avoid|never)\b", "constraint", 1.2),
    (r"\b(?:include|contain|cover|address)\b", "inclusion", 1.0),
    (r"\b(?:first|then|finally|next|after)\b", "sequential", 0.8),
]


def _extract_l2_semantic(task_text: str) -> list[Requirement]:
    """L2: semantic marker extraction for intent decomposition."""
    reqs: list[Requirement] = []
    sentences = re.split(r"[.!?]\s+", task_text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        for pattern, category, weight in _SEMANTIC_MARKERS:
            if re.search(pattern, sentence, re.IGNORECASE):
                reqs.append(Requirement(
                    text=sentence,
                    level=2,
                    category=category,
                    weight=weight,
                ))
                break  # one marker per sentence

    return reqs


# ── Requirement extraction (public) ────────────────────────────────

_requirement_cache: dict[str, list[Requirement]] = {}


def extract_task_requirements(
    task_intent: str,
    l3_extractor: Callable[[str], list[Requirement]] | None = None,
) -> list[Requirement]:
    """Extract requirements at L1 (structural) and L2 (semantic) levels.

    L3 (LLM-assisted) can be provided via *l3_extractor* callback (§5B.1).
    Results are cached by content hash (singleton pattern per §3.5).
    """
    # V11 fix: Use deterministic MD5 hash instead of Python's hash()
    # which varies across interpreter runs (PYTHONHASHSEED).
    cache_key = hashlib.md5(task_intent.encode()).hexdigest()
    if cache_key in _requirement_cache:
        return _requirement_cache[cache_key]

    l1 = _extract_l1_structural(task_intent)
    l2 = _extract_l2_semantic(task_intent)

    # Deduplicate: L1 takes priority for same category
    l1_categories = {r.category for r in l1}
    combined = l1 + [r for r in l2 if r.category not in l1_categories]

    # L3: LLM-assisted extraction when provider available (§5B.1)
    if l3_extractor is not None:
        try:
            l3 = l3_extractor(task_intent)
            existing_texts = {r.text.lower() for r in combined}
            for r in l3:
                if r.text.lower() not in existing_texts:
                    combined.append(r)
                    existing_texts.add(r.text.lower())
        except Exception:  # noqa: BLE001
            logger.warning("L3 requirement extraction failed", exc_info=True)

    if not combined:
        combined = [Requirement(
            text=task_intent[:200],
            level=1,
            category="general",
            weight=1.0,
        )]

    _requirement_cache[cache_key] = combined
    return combined


def clear_requirement_cache() -> None:
    """Clear the requirement cache (for testing)."""
    _requirement_cache.clear()


# ── Adaptive requirement discovery (GAP H) ────────────────────────

def discover_adaptive_requirements(
    existing_reqs: list[Requirement],
    document_headings: list[str] | None = None,
) -> list[Requirement]:
    """Discover new requirements from document headings not yet covered.

    As continuation windows produce new sections, the DocumentMap tracks
    headings. This function creates L2 requirements for sections that
    appeared in the output but were not anticipated by the original task
    analysis, ensuring the gap score tracks actual document completeness.
    """
    if not document_headings:
        return existing_reqs

    existing_lower = {r.text.lower() for r in existing_reqs}
    existing_sections = set()
    for r in existing_reqs:
        m = re.match(r"section\s+(\d+)", r.text, re.IGNORECASE)
        if m:
            existing_sections.add(m.group(1))

    new_reqs: list[Requirement] = []
    for heading in document_headings:
        heading_stripped = heading.strip().lstrip("#").strip()
        if not heading_stripped:
            continue
        # Extract section number if present (e.g. "2. Background")
        m = re.match(r"(\d+)\.\s*(.*)", heading_stripped)
        if m:
            sec_num, sec_title = m.group(1), m.group(2).strip()
            if sec_num in existing_sections:
                continue
            req_text = f"Section {sec_num}: {sec_title}" if sec_title else f"Section {sec_num}"
        else:
            req_text = f"Cover: {heading_stripped}"

        if req_text.lower() in existing_lower:
            continue

        new_reqs.append(Requirement(
            text=req_text,
            level=2,
            category="adaptive_discovery",
            weight=0.8,  # slightly lower weight than original requirements
            fulfilled=True,  # already fulfilled since they came from output
            fulfillment_score=1.0,
        ))
        existing_lower.add(req_text.lower())

    return existing_reqs + new_reqs


# ── Fulfillment scoring ───────────────────────────────────────────

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _text_overlap(req_text: str, fact_text: str) -> float:
    """Word overlap ratio as fallback similarity.

    For section-level requirements (``Section N: Title``), also checks
    whether the fact references the section number or title keywords,
    enabling per-section fulfillment tracking.
    """
    req_lower = req_text.lower()
    fact_lower = fact_text.lower()

    # Fast path: section-level requirement matching
    sec_match = re.match(r"section\s+(\d+):\s*(.+)", req_lower)
    if sec_match:
        sec_num = sec_match.group(1)
        sec_title = sec_match.group(2).strip()

        # Check if fact references this section number in a heading
        if re.search(rf"(?:^|\n)\s*#{{1,3}}\s*{sec_num}\.", fact_lower):
            return 1.0

        # Check if fact contains the section title keywords
        title_words = {w for w in sec_title.split() if len(w) > 3}
        if title_words:
            fact_words = set(fact_lower.split())
            title_overlap = len(title_words & fact_words) / len(title_words)
            if title_overlap >= 0.5:
                return max(0.7, title_overlap)

    # General word overlap
    req_words = set(req_lower.split())
    fact_words = set(fact_lower.split())
    if not req_words:
        return 0.0
    overlap = req_words & fact_words
    return len(overlap) / len(req_words)


FULFILLMENT_THRESHOLD = 0.65


def gap_analysis(
    task_intent: str,
    output_facts: list[Fact],
    requirements: list[Requirement] | None = None,
    embedding_fn: Callable[[str], list[float]] | None = None,
    document_headings: list[str] | None = None,
) -> GapResult:
    """Compute gap between task requirements and produced facts (§3.5).

    For each requirement, find best-matching fact. Uses cosine similarity
    when *embedding_fn* is provided (§5B.3), otherwise falls back to word
    overlap. Threshold: 0.65.

    When *document_headings* is provided (from the DocumentMap), section-
    level requirements are also matched against actual headings produced,
    enabling accurate per-section tracking.
    """
    if requirements is None:
        requirements = extract_task_requirements(task_intent)

    # GAP H: Adaptive requirement discovery from document headings
    requirements = discover_adaptive_requirements(requirements, document_headings)

    reqs = [Requirement(
        text=r.text, level=r.level, category=r.category,
        weight=r.weight, fulfilled=r.fulfilled,
        fulfillment_score=r.fulfillment_score,
    ) for r in requirements]

    fact_texts = [f.text for f in output_facts]

    # If document headings are available, add them as pseudo-facts
    # so section-level requirements can be matched against actual headings
    if document_headings:
        fact_texts = fact_texts + document_headings

    # Pre-compute embeddings if embedding_fn available (§5B.3)
    req_embeddings: list[list[float] | None] = []
    fact_embeddings: list[list[float] | None] = []
    if embedding_fn is not None:
        try:
            req_embeddings = [embedding_fn(r.text) for r in reqs]
            fact_embeddings = [embedding_fn(ft) for ft in fact_texts]
        except Exception:  # noqa: BLE001
            logger.warning("Embedding computation failed, falling back to text overlap", exc_info=True)
            req_embeddings = []
            fact_embeddings = []

    use_embeddings = bool(req_embeddings and fact_embeddings)

    for i, req in enumerate(reqs):
        best_score = 0.0
        for j, ft in enumerate(fact_texts):
            # Always compute text_overlap (has section-level fast paths)
            text_score = _text_overlap(req.text, ft)
            if use_embeddings:
                re_emb = req_embeddings[i]
                fe_emb = fact_embeddings[j]
                if re_emb and fe_emb:
                    cos_score = _cosine_similarity(re_emb, fe_emb)
                    # Use max of both: text_overlap catches section-number matches,
                    # cosine catches semantic similarity with different vocabulary
                    score = max(text_score, cos_score)
                else:
                    score = text_score
            else:
                score = text_score
            best_score = max(best_score, score)

        req.fulfillment_score = best_score
        req.fulfilled = best_score >= FULFILLMENT_THRESHOLD

    fulfilled = [r for r in reqs if r.fulfilled]
    unfulfilled = [r for r in reqs if not r.fulfilled]

    total_weight = sum(r.weight for r in reqs) or 1.0
    fulfilled_weight = sum(r.weight for r in fulfilled)
    gap_score = 1.0 - (fulfilled_weight / total_weight)

    return GapResult(
        requirements=reqs,
        gap_score=max(0.0, min(1.0, gap_score)),
        fulfilled_count=len(fulfilled),
        total_count=len(reqs),
        unfulfilled=unfulfilled,
    )
