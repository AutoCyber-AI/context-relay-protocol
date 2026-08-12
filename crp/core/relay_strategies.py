# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Novel context relay strategies — beyond push and pull (§21).

Three fundamentally different approaches to providing context to LLMs:

§21.1  REFLEXIVE DISPATCH — Verify-then-Refine
       Generate first with zero context (pure parametric knowledge).
       CRP analyzes the output against its knowledge base, identifying
       factual errors, unsupported claims, and missing information.
       A targeted correction payload is assembled and sent back with
       the model's own output — the model refines with surgical
       precision instead of drowning in pre-loaded context.

       Analogy: A fact-checker reviews your first draft and hands
       you a marked-up copy with corrections and sources.

§21.2  PROGRESSIVE DISCLOSURE — Index → Detail on Demand
       Instead of full facts, send a compact CONTEXT INDEX — one-line
       summaries of every available fact, grouped by topic. The model
       sees WHAT knowledge exists without the full payload. It generates
       with awareness of available resources, and CRP detects which
       indexed items were referenced. A second pass provides full
       detail for only the referenced items.

       Analogy: A library card catalog — you browse titles first,
       then check out only the books you need.

§21.3  STREAM-AUGMENTED GENERATION — Real-time Context Injection
       Stream tokens from the LLM. Buffer into sentences. After each
       sentence, CRP runs real-time fact-matching against the knowledge
       base. When relevant facts are found, generation is paused, the
       partial output + injected context are sent as a new prompt, and
       the model continues from where it left off — now informed.

       Analogy: A research assistant who watches you write and slides
       relevant papers across the desk exactly when you need them.

Each strategy has fundamentally different characteristics:
  - Reflexive:   Best for ACCURACY — catches and corrects hallucinations
  - Progressive:  Best for EFFICIENCY — minimal token usage, max coverage
  - Stream-aug:   Best for COHERENCE — context arrives at point-of-need
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from crp.extraction.types import Fact
    from crp.state.warm_store import WarmStateStore
    from crp.ckf.fabric import ContextualKnowledgeFabric

logger = logging.getLogger("crp.relay_strategies")


# ═══════════════════════════════════════════════════════════════════════
# §21.1  REFLEXIVE DISPATCH — Verify-then-Refine
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class FactCorrection:
    """A correction identified by comparing output against knowledge base."""
    claim_text: str             # What the model said
    matching_fact: str          # What the knowledge base says
    fact_id: str                # Traceable fact ID
    confidence: float           # How confident CRP is in the match
    correction_type: str        # "contradiction", "unsupported", "partial", "enrichment"


@dataclass
class ReflexiveAnalysis:
    """Result of analyzing model output against CRP knowledge base."""
    corrections: list[FactCorrection] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    enrichment_facts: list[str] = field(default_factory=list)
    coverage_score: float = 0.0        # 0-1: how much of the output is KB-supported
    claims_checked: int = 0
    claims_supported: int = 0
    claims_contradicted: int = 0

    @property
    def needs_refinement(self) -> bool:
        """Whether the output needs a refinement pass."""
        return (
            len(self.corrections) > 0
            or len(self.unsupported_claims) > 2
            or self.coverage_score < 0.3
        )


def analyze_output_against_kb(
    output: str,
    warm_store: WarmStateStore,
    count_tokens: Callable[[str], int],
    embed_fn: Callable[[str], list[float]] | None = None,
) -> ReflexiveAnalysis:
    """Compare LLM output against CRP knowledge base.

    Extracts claims/sentences from the output and cross-references
    each against the WarmStore facts.  Identifies:
    - Supported claims (fact backing exists)
    - Contradicted claims (conflicting evidence)
    - Unsupported claims (no evidence either way)
    - Enrichment opportunities (related facts not mentioned)
    """
    analysis = ReflexiveAnalysis()

    # Split output into sentences (claim units)
    sentences = _split_into_sentences(output)
    if not sentences:
        return analysis

    # Get all ranked facts
    all_facts = warm_store.get_ranked_facts(limit=100)
    if not all_facts:
        # No knowledge base — everything is unsupported
        analysis.unsupported_claims = sentences[:10]
        analysis.claims_checked = len(sentences)
        return analysis

    # Build a simple term index over facts for fast matching
    fact_index: dict[str, list[Any]] = {}
    for f in all_facts:
        for term in _extract_key_terms(f.text):
            fact_index.setdefault(term, []).append(f)

    supported_count = 0
    for sentence in sentences:
        sentence_stripped = sentence.strip()
        if len(sentence_stripped) < 15:  # Skip trivial fragments
            continue

        analysis.claims_checked += 1
        sentence_terms = _extract_key_terms(sentence_stripped)

        # Find facts with overlapping terms
        candidate_facts: dict[str, int] = {}  # fact_id → overlap count
        for term in sentence_terms:
            for f in fact_index.get(term, []):
                candidate_facts[f.id] = candidate_facts.get(f.id, 0) + 1

        if not candidate_facts:
            analysis.unsupported_claims.append(sentence_stripped[:200])
            continue

        # Score candidates
        best_id = max(candidate_facts, key=candidate_facts.get)
        best_overlap = candidate_facts[best_id]
        best_fact = next(f for f in all_facts if f.id == best_id)

        overlap_ratio = best_overlap / max(len(sentence_terms), 1)

        if overlap_ratio >= 0.4:
            # Well-supported claim
            supported_count += 1

            # Check for contradiction: if the fact says something
            # quantitatively different, flag it
            if _detect_contradiction(sentence_stripped, best_fact.text):
                analysis.corrections.append(FactCorrection(
                    claim_text=sentence_stripped[:200],
                    matching_fact=best_fact.text,
                    fact_id=best_fact.id,
                    confidence=best_fact.confidence,
                    correction_type="contradiction",
                ))
                analysis.claims_contradicted += 1
            else:
                analysis.claims_supported += 1
        elif overlap_ratio >= 0.15:
            # Partial match — could be enriched
            analysis.corrections.append(FactCorrection(
                claim_text=sentence_stripped[:200],
                matching_fact=best_fact.text,
                fact_id=best_fact.id,
                confidence=best_fact.confidence,
                correction_type="enrichment",
            ))
        else:
            analysis.unsupported_claims.append(sentence_stripped[:200])

    # Find enrichment facts: high-confidence facts NOT referenced in output
    output_lower = output.lower()
    for f in all_facts[:20]:  # Top-ranked, high-confidence
        if f.confidence >= 0.8:
            fact_terms = _extract_key_terms(f.text)
            # If most fact terms don't appear in output, it's enrichment
            hits = sum(1 for t in fact_terms if t in output_lower)
            if hits < len(fact_terms) * 0.3:
                analysis.enrichment_facts.append(f.text)
                if len(analysis.enrichment_facts) >= 5:
                    break

    analysis.coverage_score = (
        analysis.claims_supported / max(analysis.claims_checked, 1)
    )

    logger.info(
        "Reflexive analysis: %d claims checked, %d supported, %d contradicted, "
        "%d unsupported, %d corrections, coverage=%.2f",
        analysis.claims_checked, analysis.claims_supported,
        analysis.claims_contradicted, len(analysis.unsupported_claims),
        len(analysis.corrections), analysis.coverage_score,
    )

    return analysis


def build_refinement_prompt(
    original_output: str,
    analysis: ReflexiveAnalysis,
    count_tokens: Callable[[str], int],
    max_correction_tokens: int = 3000,
) -> str:
    """Build the refinement prompt from reflexive analysis.

    Returns a structured correction payload that tells the model
    exactly what to fix, with evidence.
    """
    parts: list[str] = []
    token_budget = max_correction_tokens

    parts.append("=== FACT-CHECK RESULTS ===")
    parts.append(f"Coverage: {analysis.coverage_score:.0%} of your claims are supported by verified evidence.")
    parts.append(f"Corrections needed: {len(analysis.corrections)}")
    parts.append("")

    # Corrections (most important)
    if analysis.corrections:
        parts.append("--- CORRECTIONS (verified evidence differs from your output) ---")
        for c in analysis.corrections:
            entry = (
                f"• YOUR CLAIM: \"{c.claim_text}\"\n"
                f"  VERIFIED FACT: \"{c.matching_fact}\" (confidence: {c.confidence:.0%})\n"
                f"  TYPE: {c.correction_type}"
            )
            entry_tokens = count_tokens(entry)
            if entry_tokens > token_budget:
                break
            token_budget -= entry_tokens
            parts.append(entry)
        parts.append("")

    # Enrichments (additional facts the model missed)
    if analysis.enrichment_facts and token_budget > 200:
        parts.append("--- ADDITIONAL VERIFIED FACTS (consider incorporating) ---")
        for ef in analysis.enrichment_facts:
            entry = f"• {ef}"
            entry_tokens = count_tokens(entry)
            if entry_tokens > token_budget:
                break
            token_budget -= entry_tokens
            parts.append(entry)
        parts.append("")

    parts.append("=== END FACT-CHECK RESULTS ===")
    parts.append("")
    parts.append(
        "Please revise your response incorporating the corrections above. "
        "Keep the same structure and style, but fix factual errors and "
        "incorporate the additional verified facts where relevant."
    )

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# §21.2  PROGRESSIVE DISCLOSURE — Index → Detail on Demand
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ContextIndex:
    """A compact index of available knowledge — titles/summaries only."""
    entries: list[ContextIndexEntry] = field(default_factory=list)
    total_facts: int = 0
    index_tokens: int = 0

    def to_text(self) -> str:
        """Render the index as a compact text block for the LLM."""
        if not self.entries:
            return ""
        lines = ["=== AVAILABLE CONTEXT INDEX ==="]
        lines.append(f"({self.total_facts} verified facts available. "
                     "Reference items by [ID] to receive full details.)")
        lines.append("")
        for e in self.entries:
            lines.append(f"[{e.ref_id}] {e.summary} (confidence: {e.confidence:.0%})")
        lines.append("")
        lines.append("=== END INDEX ===")
        return "\n".join(lines)


@dataclass
class ContextIndexEntry:
    """One entry in the context index."""
    ref_id: str          # Short reference ID like "F1", "F2"
    fact_id: str         # Real CRP fact ID (for lookup)
    summary: str         # One-line summary (compressed)
    confidence: float    # Fact confidence
    full_text: str       # Full text (not sent until referenced)
    tokens: int          # Token cost of full text


def build_context_index(
    warm_store: WarmStateStore,
    count_tokens: Callable[[str], int],
    max_entries: int = 50,
    max_index_tokens: int = 1500,
) -> ContextIndex:
    """Build a compact context index from WarmStore facts.

    Each entry is compressed to a one-line summary (~15 tokens)
    instead of the full fact text (~50-200 tokens). This gives
    the LLM awareness of ALL available knowledge at ~10% of the
    token cost of sending full facts.
    """
    ranked_facts = warm_store.get_ranked_facts(limit=max_entries)
    index = ContextIndex(total_facts=warm_store.fact_count)

    token_budget = max_index_tokens
    for i, f in enumerate(ranked_facts):
        # Compress fact to one-line summary
        summary = _compress_fact_to_summary(f.text)
        ref_id = f"F{i+1}"

        entry_line = f"[{ref_id}] {summary} (confidence: {f.confidence:.0%})"
        entry_tokens = count_tokens(entry_line)

        if entry_tokens > token_budget:
            break
        token_budget -= entry_tokens

        index.entries.append(ContextIndexEntry(
            ref_id=ref_id,
            fact_id=f.id,
            summary=summary,
            confidence=f.confidence,
            full_text=f.text,
            tokens=count_tokens(f.text),
        ))

    index.index_tokens = max_index_tokens - token_budget

    logger.info(
        "Progressive index: %d entries, %d tokens (from %d total facts)",
        len(index.entries), index.index_tokens, index.total_facts,
    )
    return index


def detect_index_references(
    output: str,
    index: ContextIndex,
) -> list[ContextIndexEntry]:
    """Detect which index entries were referenced in the output.

    The LLM may reference entries by [F1], [F2] etc., or by
    mentioning key terms from the summary. Both are detected.
    """
    referenced: list[ContextIndexEntry] = []
    output_lower = output.lower()

    for entry in index.entries:
        # Check for explicit reference [F1], [F2], etc.
        if f"[{entry.ref_id}]" in output or f"[{entry.ref_id.lower()}]" in output_lower:
            referenced.append(entry)
            continue

        # Check for key term overlap with summary
        summary_terms = _extract_key_terms(entry.summary)
        if summary_terms:
            hits = sum(1 for t in summary_terms if t in output_lower)
            if hits >= max(2, len(summary_terms) * 0.5):
                referenced.append(entry)

    logger.info(
        "Progressive disclosure: %d of %d index entries referenced",
        len(referenced), len(index.entries),
    )
    return referenced


def build_detail_injection(
    referenced_entries: list[ContextIndexEntry],
    count_tokens: Callable[[str], int],
    max_tokens: int = 3000,
) -> str:
    """Build the detail payload for referenced index entries.

    Only the entries the model actually referenced get expanded
    to full text. This is maximally efficient — no wasted context.
    """
    if not referenced_entries:
        return ""

    parts: list[str] = ["=== EXPANDED CONTEXT (you referenced these) ==="]
    token_budget = max_tokens

    for entry in referenced_entries:
        detail = f"[{entry.ref_id}] {entry.full_text}"
        detail_tokens = count_tokens(detail)
        if detail_tokens > token_budget:
            break
        token_budget -= detail_tokens
        parts.append(detail)

    parts.append("=== END EXPANDED CONTEXT ===")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# §21.3  STREAM-AUGMENTED — Real-time Context Injection
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class AugmentationEvent:
    """Record of a real-time context injection during streaming."""
    sentence_index: int          # Which sentence triggered it
    trigger_text: str            # The sentence that triggered injection
    facts_injected: int          # How many facts were injected
    injection_tokens: int        # Token cost of injection
    resumption_point: str        # The text sent as resumption anchor


@dataclass
class StreamAugmentationState:
    """Tracks state during stream-augmented generation."""
    sentence_buffer: str = ""
    sentences_completed: int = 0
    augmentation_events: list[AugmentationEvent] = field(default_factory=list)
    total_injections: int = 0
    total_injection_tokens: int = 0
    accumulated_output: str = ""

    @property
    def should_check(self) -> bool:
        """Check after every N sentences to avoid excessive overhead."""
        return self.sentences_completed % 2 == 0  # Every 2 sentences


def find_relevant_facts_for_sentence(
    sentence: str,
    warm_store: WarmStateStore,
    already_injected: set[str],
    count_tokens: Callable[[str], int],
    max_facts: int = 3,
    max_tokens: int = 500,
) -> list[tuple[str, str]]:
    """Find WarmStore facts relevant to a sentence that haven't been injected yet.

    Returns [(fact_id, fact_text), ...] — only NEW facts not already served.
    """
    sentence_terms = _extract_key_terms(sentence)
    if not sentence_terms:
        return []

    ranked = warm_store.get_ranked_facts(limit=50)
    scored: list[tuple[float, Any]] = []

    for f in ranked:
        if f.id in already_injected:
            continue
        fact_terms = _extract_key_terms(f.text)
        overlap = sum(1 for t in sentence_terms if t in set(fact_terms))
        if overlap >= max(1, len(sentence_terms) // 4):
            score = overlap / max(len(sentence_terms), 1) * f.confidence
            scored.append((score, f))

    scored.sort(key=lambda x: -x[0])

    results: list[tuple[str, str]] = []
    token_budget = max_tokens
    for _, f in scored[:max_facts]:
        ft = count_tokens(f.text)
        if ft > token_budget:
            break
        token_budget -= ft
        results.append((f.id, f.text))

    return results


def build_augmented_continuation(
    system_prompt: str,
    partial_output: str,
    injected_facts: list[tuple[str, str]],
    task_input: str,
) -> list[dict[str, str]]:
    """Build the message sequence for resuming after a stream augmentation.

    The model receives:
    1. System prompt (unchanged)
    2. Original task
    3. Its own partial output so far (as assistant message)
    4. Injected context (as system/user interjection)
    5. Instruction to continue from where it left off
    """
    facts_text = "\n".join(f"• {text}" for _, text in injected_facts)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_input},
        {"role": "assistant", "content": partial_output},
        {
            "role": "user",
            "content": (
                f"[CONTEXT INJECTION — verified facts relevant to what you just wrote]\n"
                f"{facts_text}\n"
                f"[END INJECTION]\n\n"
                f"Continue writing from exactly where you left off. Do not repeat "
                f"what you already wrote. Incorporate the above facts naturally."
            ),
        },
    ]
    return messages


# ═══════════════════════════════════════════════════════════════════════
# Shared utilities
# ═══════════════════════════════════════════════════════════════════════

# Stop words for term extraction (minimal set for speed)
_STOP_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "and", "but", "or",
    "not", "no", "so", "if", "than", "then", "that", "this", "these",
    "those", "it", "its", "he", "she", "they", "we", "you", "i", "my",
    "his", "her", "their", "our", "your", "which", "what", "who", "whom",
    "how", "when", "where", "why", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "only", "very",
    "also", "just", "about", "up", "out", "over", "own", "same",
})


def _extract_key_terms(text: str) -> list[str]:
    """Extract significant terms from text (lowercased, stop-words removed)."""
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 2]


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using regex (handles common cases)."""
    # Split on sentence-ending punctuation followed by space or newline
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Also split on double newlines (paragraph boundaries)
    result: list[str] = []
    for s in sentences:
        parts = s.split("\n\n")
        result.extend(p.strip() for p in parts if p.strip())
    return result


def _compress_fact_to_summary(text: str) -> str:
    """Compress a fact to a one-line summary (~10-20 words max).

    Strategy: take the first clause/sentence, truncate at ~80 chars.
    """
    # Take first sentence
    match = re.match(r'^([^.!?]+[.!?])', text)
    first_sentence = match.group(1) if match else text

    if len(first_sentence) <= 80:
        return first_sentence

    # Truncate at word boundary near 80 chars
    truncated = first_sentence[:80]
    last_space = truncated.rfind(" ")
    if last_space > 40:
        truncated = truncated[:last_space]
    return truncated + "..."


def _detect_contradiction(claim: str, fact: str) -> bool:
    """Simple heuristic contradiction detection.

    Checks for numeric disagreements and negation patterns.
    Not perfect — serves as a first-pass filter.
    """
    # Extract numbers from both
    claim_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', claim))
    fact_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', fact))

    # If both mention numbers but they differ significantly, likely contradiction
    if claim_numbers and fact_numbers:
        shared_terms = _extract_key_terms(claim)
        fact_terms = set(_extract_key_terms(fact))
        topic_overlap = sum(1 for t in shared_terms if t in fact_terms)
        if topic_overlap >= 2 and claim_numbers != fact_numbers:
            # Same topic, different numbers — likely contradiction
            return True

    # Check negation patterns
    claim_lower = claim.lower()
    fact_lower = fact.lower()
    negation_pairs = [
        ("not ", ""), ("never ", "always "), ("false", "true"),
        ("incorrect", "correct"), ("wrong", "right"),
    ]
    for neg, pos in negation_pairs:
        if neg in claim_lower and pos in fact_lower:
            return True
        if pos in claim_lower and neg in fact_lower:
            return True

    return False
