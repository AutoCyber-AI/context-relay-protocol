# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Strategy 2 — RAG (Retrieval-Augmented Generation).

Simulates what a real RAG pipeline does during long-document generation:
1. As each section is written, its content is split into chunks and indexed
   into an in-memory vector store using TF-IDF cosine similarity.
2. For each new section, the top-k most relevant chunks from ALL prior
   sections are retrieved and injected as "retrieved context".
3. The model generates the new section conditioned on that retrieved context.

This accurately represents RAG's strengths (targeted retrieval) and
weaknesses (retrieval noise, cold-start on first sections, no narrative
continuation signal).

No external dependencies: TF-IDF is computed with pure Python/stdlib.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Callable

from .base import (
    BaseStrategy,
    StrategyResult,
    WindowMetrics,
    coherence_score,
    count_headings,
    duplicate_sentence_ratio,
    ngram_repetition,
    unique_word_ratio,
    word_count,
)
from .crp_strategy import _make_wm


# ── Lightweight TF-IDF retriever ────────────────────────────────────────────

class _TFIDFRetriever:
    """In-memory TF-IDF vector store for chunk retrieval."""

    def __init__(self) -> None:
        self._chunks: list[str] = []
        self._tfidf: list[dict[str, float]] = []
        self._df: Counter = Counter()
        self._n = 0

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\b[a-z]{3,}\b", text.lower())

    def add(self, text: str, chunk_size: int = 200) -> None:
        """Add text by splitting into ~chunk_size word chunks."""
        words = self._tokenize(text)
        for i in range(0, max(1, len(words)), chunk_size):
            chunk_words = words[i: i + chunk_size]
            if len(chunk_words) < 10:
                continue
            chunk_text = text[i * 5: (i + chunk_size) * 5]  # approximate char slice
            # Use original text slice instead — grab sentences
            self._chunks.append(" ".join(chunk_words))
            tf = Counter(chunk_words)
            total = len(chunk_words)
            tf_norm = {w: c / total for w, c in tf.items()}
            self._tfidf.append(tf_norm)
            for w in set(chunk_words):
                self._df[w] += 1
        self._n = len(self._chunks)

    def _idf(self, word: str) -> float:
        df = self._df.get(word, 0)
        if df == 0 or self._n == 0:
            return 0.0
        return math.log((self._n + 1) / (df + 1)) + 1.0

    def _score(self, query_tokens: list[str], doc_tf: dict[str, float]) -> float:
        score = 0.0
        for t in set(query_tokens):
            score += doc_tf.get(t, 0.0) * self._idf(t)
        return score

    def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        if not self._chunks:
            return []
        q_tokens = self._tokenize(query)
        scored = [(self._score(q_tokens, tf), i) for i, tf in enumerate(self._tfidf)]
        scored.sort(reverse=True)
        return [self._chunks[i] for _, i in scored[:top_k] if _ > 0]


# ── RAG Strategy ─────────────────────────────────────────────────────────

class RAGStrategy(BaseStrategy):
    name = "rag"
    label = "RAG (Retrieval-Augmented)"
    description = (
        "TF-IDF in-memory retrieval: chunks prior sections, retrieves top-5 "
        "relevant passages per new section, injects as context."
    )
    color = "#10b981"  # green

    def __init__(self, *args, top_k: int = 5, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.top_k = top_k

    def run(
        self,
        on_chunk: Callable[[str], None] | None = None,
        on_metrics: Callable[[dict], None] | None = None,
        on_window_done: Callable[[int, str, dict], None] | None = None,
    ) -> StrategyResult:
        retriever = _TFIDFRetriever()
        sections = self.sections
        accumulated_text = ""
        window_texts: list[str] = []
        window_metrics: list[WindowMetrics] = []
        total_prompt_tokens = 0
        total_output_tokens = 0
        total_latency = 0.0
        errors: list[str] = []

        doc_title = "# Technical Reference Guide\n\n"
        if on_chunk:
            on_chunk(doc_title)
        accumulated_text += doc_title

        for i, section in enumerate(sections):
            # Retrieve relevant context from what's been written so far
            retrieved = retriever.retrieve(section, top_k=self.top_k)
            retrieved_block = ""
            if retrieved:
                retrieved_block = (
                    "\n\n=== RETRIEVED CONTEXT (top relevant passages) ===\n"
                    + "\n---\n".join(f"[Chunk {j+1}] {chunk}" for j, chunk in enumerate(retrieved))
                    + "\n=== END RETRIEVED CONTEXT ===\n"
                )

            system = (
                "You are writing one section of a comprehensive technical reference guide. "
                "You have been provided retrieved context passages from prior sections. "
                "Use this context to maintain consistency but write new, unique content. "
                "Do NOT copy the retrieved passages verbatim. Use markdown headings."
            )
            user = (
                f"{retrieved_block}\n"
                f"Write section {i+1} of {len(sections)}: **{section}**\n"
                f"Target: ~{max(300, self.target_words // len(sections))} words.\n"
                f"Include: key concepts, trade-offs, implementation patterns, real-world considerations.\n"
                f"Start with '## {i+1}. {section}'"
            )

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]

            window_chunks: list[str] = []

            def _sink(chunk: str, _buf: list = window_chunks) -> None:
                _buf.append(chunk)
                if on_chunk:
                    on_chunk(chunk)

            text, reason, pt, ot, lat = self._chat(
                messages, max_tokens=self.max_tokens_per_window, on_chunk=_sink
            )
            if not text:
                text = "".join(window_chunks)

            total_prompt_tokens += pt
            total_output_tokens += ot
            total_latency += lat

            # Index the newly written section for future retrieval
            if text:
                retriever.add(text)

            accumulated_text += "\n\n" + text
            window_texts.append(text)

            prev_window_text = window_texts[-2] if len(window_texts) >= 2 else ""
            note = f"retrieved={len(retrieved)} chunks"
            wm = _make_wm(self.name, i+1, pt, ot, lat, accumulated_text,
                          prev_window_text=prev_window_text,
                          section_title=section, note=note)
            window_metrics.append(wm)
            if on_metrics:
                on_metrics(wm.__dict__)
            if on_window_done:
                on_window_done(i+1, text, wm.__dict__)

        wc = word_count(accumulated_text)
        rep = ngram_repetition(accumulated_text)
        dup = duplicate_sentence_ratio(accumulated_text)
        uwr_list = [m.unique_word_ratio for m in window_metrics] or [0.0]
        uwr_avg = sum(uwr_list) / len(uwr_list)
        total_toks = max(1, total_prompt_tokens + total_output_tokens)

        return StrategyResult(
            strategy=self.name,
            full_text=accumulated_text,
            total_words=wc,
            total_prompt_tokens=total_prompt_tokens,
            total_output_tokens=total_output_tokens,
            total_latency_s=total_latency,
            windows=len(window_metrics),
            final_repetition_6gram=rep,
            final_dup_sentence_ratio=dup,
            avg_unique_word_ratio=uwr_avg,
            sections_completed=count_headings(accumulated_text),
            context_efficiency=total_output_tokens / total_toks,
            window_metrics=window_metrics,
            errors=errors,
        )
