# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Strategy 3 — Naive Context Injection (full-context stuffing).

The simplest possible approach: stuff the entire accumulated document (or as
much of it as fits in the context window) directly into every prompt.

This represents what developers reach for first — "just send everything".

Key properties:
- Prompt tokens grow linearly with document length
- Once accumulated text + task > context window, content is truncated from
  the *beginning* (oldest sections fall out first)
- No semantic routing, no repetition guard, no continuation directives
- Prone to: verbose rehashing of what's already there, context overflow
  causing earlier sections to be "forgotten"
- Context efficiency plummets as document grows (most tokens are re-sending
  already-written content)

This is the baseline that makes CRP and RAG look good.
"""

from __future__ import annotations

from typing import Callable

from .base import (
    BaseStrategy,
    StrategyResult,
    WindowMetrics,
    count_headings,
    duplicate_sentence_ratio,
    ngram_repetition,
    unique_word_ratio,
    word_count,
)
from .crp_strategy import _make_wm


class InjectionStrategy(BaseStrategy):
    name = "injection"
    label = "Context Injection (Naive)"
    description = (
        "Full-context stuffing: sends the entire accumulated document in "
        "every prompt. Simple, but token-inefficient and degrades as the "
        "document grows beyond the context window."
    )
    color = "#f59e0b"  # amber

    # Leave ~20% of context for output
    _OUTPUT_RESERVE = 0.20

    def run(
        self,
        on_chunk: Callable[[str], None] | None = None,
        on_metrics: Callable[[dict], None] | None = None,
        on_window_done: Callable[[int, str, dict], None] | None = None,
    ) -> StrategyResult:
        sections = self.sections
        accumulated_text = ""
        window_texts: list[str] = []
        window_metrics: list[WindowMetrics] = []
        total_prompt_tokens = 0
        total_output_tokens = 0
        total_latency = 0.0
        errors: list[str] = []

        # Token budget: reserve output tokens, spend the rest on the prompt
        # 1 token ≈ 4 chars (rough estimate)
        max_prompt_chars = int(self.context_size * 4 * (1 - self._OUTPUT_RESERVE))

        doc_title = "# Technical Reference Guide\n\n"
        if on_chunk:
            on_chunk(doc_title)
        accumulated_text += doc_title

        for i, section in enumerate(sections):
            # Build the prompt with as much existing document as fits
            task_suffix = (
                f"\n\n---\nContinue the document. Write section {i+1} of {len(sections)}: "
                f"**{section}**. "
                f"Target: ~{max(300, self.target_words // len(sections))} words. "
                f"Start with '## {i+1}. {section}'. "
                f"Do NOT repeat what is already written above."
            )

            # Truncate accumulated text from the front if too long
            max_doc_chars = max_prompt_chars - len(task_suffix) - 200
            doc_fragment = accumulated_text
            truncated = False
            if len(doc_fragment) > max_doc_chars:
                # Keep the last max_doc_chars chars (most recent context)
                doc_fragment = "...[earlier content truncated]...\n" + doc_fragment[-max_doc_chars:]
                truncated = True

            system = (
                "You are writing a comprehensive technical guide section by section. "
                "The document so far is provided below. Continue from where it left off. "
                "Use markdown headings. Write detailed, unique content."
            )
            user = doc_fragment + task_suffix

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

            accumulated_text += "\n\n" + text
            window_texts.append(text)

            note = "truncated" if truncated else f"doc_chars={len(doc_fragment)}"
            prev_window_text = window_texts[-2] if len(window_texts) >= 2 else ""
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
