# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Stage 2 — Statistical NLP extraction (~5ms, MUST).

Pure-Python: TextRank key-sentence extraction, noun-phrase heuristics,
section-header detection, list-item extraction, and numerical-value extraction.
No ML model dependencies.
"""

from __future__ import annotations

import math
import re

from crp.extraction.types import Fact

# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_WORD_SPLIT = re.compile(r"\w+", re.UNICODE)

# Simple stop-word set (top ~100 English)
_STOP_WORDS: frozenset[str] = frozenset(
    ["a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "get", "got", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it", "its", "itself", "just", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "shouldn't", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "were", "weren't", "what", "when", "where", "which", "while", "who", "whom", "why", "will", "with", "won't", "would", "wouldn't", "you", "your", "yours", "yourself", "yourselves"]
)


def _sentences(text: str) -> list[str]:
    """Split text into sentences."""
    raw = _SENT_SPLIT.split(text.strip())
    return [s.strip() for s in raw if len(s.strip()) > 5]


def _words(text: str) -> list[str]:
    return _WORD_SPLIT.findall(text.lower())


def _content_words(text: str) -> list[str]:
    return [w for w in _words(text) if w not in _STOP_WORDS and len(w) > 2]


# ---------------------------------------------------------------------------
# TextRank (simplified, no external deps)
# ---------------------------------------------------------------------------

def _sentence_similarity(s1_words: list[str], s2_words: list[str]) -> float:
    """Jaccard-like overlap between content-word sets."""
    if not s1_words or not s2_words:
        return 0.0
    set1, set2 = set(s1_words), set(s2_words)
    overlap = len(set1 & set2)
    return overlap / (math.log(len(set1) + 1) + math.log(len(set2) + 1) + 1e-9)


def textrank_sentences(
    sentences: list[str],
    top_k: int = 5,
    damping: float = 0.85,
    iterations: int = 30,
    convergence: float = 1e-4,
) -> list[tuple[int, float]]:
    """Return indices + scores of top-K sentences via TextRank.

    Steps:
    1. Build sentence similarity graph.
    2. Run PageRank-style iteration.
    3. Return top-K by score (original order preserved).
    """
    n = len(sentences)
    if n == 0:
        return []
    if n <= top_k:
        return [(i, 1.0) for i in range(n)]

    # Tokenise once
    tokenised = [_content_words(s) for s in sentences]

    # Build adjacency weights
    weights: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            sim = _sentence_similarity(tokenised[i], tokenised[j])
            weights[i][j] = sim
            weights[j][i] = sim

    # Row sums for normalisation
    row_sums = [sum(row) for row in weights]

    # PageRank iteration
    scores = [1.0 / n] * n
    for _ in range(iterations):
        new_scores = [0.0] * n
        max_delta = 0.0
        for i in range(n):
            rank_sum = 0.0
            for j in range(n):
                if row_sums[j] > 0:
                    rank_sum += weights[j][i] / row_sums[j] * scores[j]
            new_scores[i] = (1 - damping) / n + damping * rank_sum
            max_delta = max(max_delta, abs(new_scores[i] - scores[i]))
        scores = new_scores
        if max_delta < convergence:
            break

    # Top-K indices sorted by score descending, then stable-sort by original position
    ranked = sorted(range(n), key=lambda i: scores[i], reverse=True)[:top_k]
    ranked.sort()  # Restore document order
    return [(i, scores[i]) for i in ranked]


# ---------------------------------------------------------------------------
# Noun-phrase heuristic (regex, no POS tagger)
# ---------------------------------------------------------------------------

_NP_PATTERN = re.compile(
    r"\b(?:[A-Z][a-z]+(?:\s+(?:of|the|and|for|in|on|with|to)\s+)?){1,4}"
    r"[A-Z][a-z]+\b"
)


def _extract_noun_phrases(text: str) -> list[str]:
    """Extract capitalised multi-word noun phrases."""
    return list({m.group(0) for m in _NP_PATTERN.finditer(text)})


# ---------------------------------------------------------------------------
# Section headers
# ---------------------------------------------------------------------------

_MARKDOWN_HEADER = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_UNDERLINE_HEADER = re.compile(r"^(.+)\n[=\-]{3,}$", re.MULTILINE)


def _extract_headers(text: str) -> list[str]:
    headers: list[str] = []
    for m in _MARKDOWN_HEADER.finditer(text):
        headers.append(m.group(2).strip())
    for m in _UNDERLINE_HEADER.finditer(text):
        headers.append(m.group(1).strip())
    return headers


# ---------------------------------------------------------------------------
# List items
# ---------------------------------------------------------------------------

_LIST_ITEM = re.compile(
    r"^[ \t]*(?:[-*+]|\d+[.)])\s+(.+)$", re.MULTILINE
)


def _extract_list_items(text: str) -> list[str]:
    return [m.group(1).strip() for m in _LIST_ITEM.finditer(text)]


# ---------------------------------------------------------------------------
# Numerical values with context
# ---------------------------------------------------------------------------

_NUMBER_CONTEXT = re.compile(
    r"(\b\d+(?:\.\d+)?)\s*(%|ms|s|sec|min|hr|hours?|days?|bytes?|[KMGT]B"
    r"|tokens?|requests?|errors?|users?|GB|MB|KB)\b",
    re.IGNORECASE,
)


def _extract_numerical(text: str) -> list[str]:
    """Extract numbers with trailing unit context."""
    return [f"{m.group(1)} {m.group(2)}" for m in _NUMBER_CONTEXT.finditer(text)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class StatisticalExtractor:
    """Stage 2 — statistical NLP extraction (no ML models)."""

    def __init__(self, top_k_sentences: int = 5) -> None:
        self._top_k = top_k_sentences

    def extract(
        self,
        text: str,
        source_window_id: str = "",
    ) -> list[Fact]:
        """Extract key sentences, noun phrases, headers, list items, numbers."""
        facts: list[Fact] = []

        # --- Key sentences (TextRank) ---
        sentences = _sentences(text)
        for idx, score in textrank_sentences(sentences, self._top_k):
            facts.append(Fact(
                text=sentences[idx],
                category="key_sentence",
                source_window_id=source_window_id,
                confidence=min(0.85, 0.75 + score),
                extraction_stage=2,
                metadata={"textrank_score": round(score, 4), "sentence_index": idx},
            ))

        # --- Noun phrases ---
        for np_text in _extract_noun_phrases(text):
            facts.append(Fact(
                text=np_text,
                category="noun_phrase",
                source_window_id=source_window_id,
                confidence=0.75,
                extraction_stage=2,
            ))

        # --- Section headers ---
        for header in _extract_headers(text):
            facts.append(Fact(
                text=header,
                category="section_header",
                source_window_id=source_window_id,
                confidence=0.85,
                extraction_stage=2,
            ))

        # --- List items ---
        for item in _extract_list_items(text):
            facts.append(Fact(
                text=item,
                category="list_item",
                source_window_id=source_window_id,
                confidence=0.80,
                extraction_stage=2,
            ))

        # --- Numerical values ---
        for num in _extract_numerical(text):
            facts.append(Fact(
                text=num,
                category="numerical_value",
                source_window_id=source_window_id,
                confidence=0.80,
                extraction_stage=2,
            ))

        return facts
