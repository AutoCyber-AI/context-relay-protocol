# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 1 — Multi-aspect task decomposition (§3.2).

Decomposes TaskIntent into explicit + implicit aspects, each with an embedding
vector.  Falls back to lightweight word-overlap vectors when sentence-transformers
is unavailable.
"""

from __future__ import annotations

import hashlib
import math
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from crp.core.task_intent import TaskIntent

# ---------------------------------------------------------------------------
# Embedding abstraction — lightweight fallback when ML deps absent
# ---------------------------------------------------------------------------

# Sentinel that indicates sentence-transformers is available
_ST_AVAILABLE: bool = False
_EMBED_MODEL: object | None = None
_EMBED_DIM: int = 384  # all-MiniLM-L6-v2 output dim


def _try_load_sentence_transformer() -> bool:
    """Attempt lazy load of sentence-transformers model.  Returns True on success."""
    global _ST_AVAILABLE, _EMBED_MODEL  # noqa: PLW0603
    if _ST_AVAILABLE:
        return True
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

        _EMBED_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        _ST_AVAILABLE = True
        if sys.platform == "win32":
            # crp/__init__ caps OMP_NUM_THREADS=1 process-wide as a *load-time*
            # OpenMP crash guard. Loading is done — restore parallel inference
            # or every embedding call runs ~3-4x slower than it should.
            try:
                import os as _os

                import torch  # type: ignore[import-untyped]

                torch.set_num_threads(max(1, _os.cpu_count() or 1))
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    return _ST_AVAILABLE


def get_embedding_fn() -> Callable[[str], list[float]] | None:
    """Return a text→embedding function using the loaded model, or None.

    This is the canonical embedding function for the CRP pipeline.
    Used by: set_embedding_function(), gap_analysis(), CKF semantic mode.
    """
    if not _try_load_sentence_transformer() or _EMBED_MODEL is None:
        return None
    model = _EMBED_MODEL

    def _embed(text: str) -> list[float]:
        return model.encode([text], show_progress_bar=False).tolist()[0]  # type: ignore[attr-defined]

    return _embed


# -- lightweight fallback vectors (word-overlap, normalised) -----------------

_STOP = frozenset(
    ["a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "is", "it", "its", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "shall", "should", "may", "might", "can", "could", "this", "that", "these", "those", "i", "we", "you", "he", "she", "they", "me", "us", "him", "her", "them", "my", "our", "your", "his", "its", "their", "with", "from", "by", "as", "not", "no"]
)


def _tokenize(text: str) -> list[str]:
    """Lower-case word tokeniser (alphanum only)."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP]


def _bag_vector(tokens: Sequence[str], vocab: dict[str, int], dim: int) -> list[float]:
    """Sparse bag-of-words vector projected to *dim* via hashing."""
    vec = [0.0] * dim
    for tok in tokens:
        idx = vocab.get(tok)
        if idx is None:
            idx = int(hashlib.sha256(tok.encode()).hexdigest(), 16) % dim
        vec[idx] += 1.0
    # L2 normalise
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _build_vocab(all_tokens: list[str]) -> dict[str, int]:
    """Deterministic vocabulary mapping (ordered by first occurrence)."""
    vocab: dict[str, int] = {}
    for tok in all_tokens:
        if tok not in vocab:
            vocab[tok] = len(vocab) % _EMBED_DIM
    return vocab


# ---------------------------------------------------------------------------
# Public result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DecompositionResult:
    """Output of ``decompose_task_aspects``."""

    aspects: list[str] = field(default_factory=list)
    aspect_embeddings: list[list[float]] = field(default_factory=list)
    full_embedding: list[float] = field(default_factory=list)
    used_ml_model: bool = False


# ---------------------------------------------------------------------------
# Noun-phrase extraction (lightweight, no ML)
# ---------------------------------------------------------------------------

# Simple regex pattern for noun-phrase-like chunks: sequences of adjectives/nouns
_NP_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"  # Capitalised phrases
    r"|"
    r"\b([a-z]+(?:[-_][a-z]+)+)\b"  # Hyphenated/underscored compound terms
)


def _extract_noun_phrases(text: str) -> list[str]:
    """Extract candidate noun phrases from *text*."""
    phrases: list[str] = []
    for m in _NP_PATTERN.finditer(text):
        phrase = (m.group(1) or m.group(2) or "").strip()
        if phrase and len(phrase) > 2:
            phrases.append(phrase)
    # Also grab quoted strings as explicit aspects
    for m in re.finditer(r'"([^"]{3,80})"', text):
        phrases.append(m.group(1))
    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for p in phrases:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


# ---------------------------------------------------------------------------
# Implicit aspect expansion (word-based when no embeddings)
# ---------------------------------------------------------------------------

def _expand_aspects_implicit(aspects: list[str], full_text: str) -> list[str]:
    """Add implicit aspects derived from the full text that aren't in *aspects*.

    When ML embeddings are unavailable, uses word co-occurrence: finds bigrams
    from the full text that share a word with an existing aspect.
    """
    if not aspects:
        # Fallback: use first N significant tokens as aspects
        tokens = _tokenize(full_text)
        # Pick unique tokens in order, up to 5
        seen: set[str] = set()
        result: list[str] = []
        for t in tokens:
            if t not in seen and len(t) > 2:
                seen.add(t)
                result.append(t)
                if len(result) >= 5:
                    break
        return result

    aspect_words = set()
    for a in aspects:
        aspect_words.update(_tokenize(a))

    words = _tokenize(full_text)
    new_aspects: list[str] = []
    seen_lower = {a.lower() for a in aspects}
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i + 1]}"
        if bigram.lower() not in seen_lower:
            # At least one word overlaps with existing aspects
            if words[i] in aspect_words or words[i + 1] in aspect_words:
                seen_lower.add(bigram.lower())
                new_aspects.append(bigram)
                if len(new_aspects) >= 3:  # cap expansion
                    break
    return aspects + new_aspects


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def decompose_task_aspects(task_intent: TaskIntent) -> DecompositionResult:
    """Decompose *task_intent* into aspects with embedding vectors.

    Algorithm (§3.2 Phase 1):
    1. Concatenate system_prompt + task_input
    2. Extract noun phrases as explicit aspects
    3. Expand with implicit aspects via dependency analysis
    4. Compute embedding for each aspect + full text
    """
    system = task_intent.system_prompt or ""
    task = task_intent.task_input or ""
    full_text = f"{system} {task}".strip()

    if not full_text:
        return DecompositionResult()

    # Step 1-2: extract explicit aspects from noun phrases
    explicit = _extract_noun_phrases(full_text)

    # Step 3: implicit expansion
    expanded = _expand_aspects_implicit(explicit, full_text)
    if not expanded:
        expanded = [full_text[:200]]  # absolute fallback

    # Step 4: compute embeddings
    use_ml = _try_load_sentence_transformer()

    if use_ml and _EMBED_MODEL is not None:
        model = _EMBED_MODEL
        texts_to_embed = expanded + [full_text]
        embeddings = model.encode(texts_to_embed, show_progress_bar=False).tolist()  # type: ignore[attr-defined]
        aspect_embs = embeddings[:-1]
        full_emb = embeddings[-1]
    else:
        # Fallback: bag-of-words vectors
        all_tokens = _tokenize(full_text)
        for a in expanded:
            all_tokens.extend(_tokenize(a))
        vocab = _build_vocab(all_tokens)
        aspect_embs = [_bag_vector(_tokenize(a), vocab, _EMBED_DIM) for a in expanded]
        full_emb = _bag_vector(_tokenize(full_text), vocab, _EMBED_DIM)

    return DecompositionResult(
        aspects=expanded,
        aspect_embeddings=aspect_embs,
        full_embedding=full_emb,
        used_ml_model=use_ml,
    )
