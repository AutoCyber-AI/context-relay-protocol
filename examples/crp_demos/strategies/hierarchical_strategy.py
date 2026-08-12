# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Strategy 4 — Hierarchical Summarization (trending approach, 2025–2026).

One of the most popular long-context solutions outside RAG: after each window,
the model recursively summarizes what was written into a compressed "memory
buffer". The next window receives only the compressed summary + the task, not
the raw content. This mirrors:

- MemGPT / OS-style memory management (Packer et al., 2023)
- LangChain's ConversationSummaryBufferMemory
- Recursive summarization chains (used in Anthropic Claude's long-form tasks)
- KV-cache eviction with summary replacement

Key characteristics:
- Prompt tokens stay nearly CONSTANT across windows (summary size is bounded)
- But the summary is lossy: fine-grained details and specific examples from
  earlier sections can be lost, reducing coherence
- The "compression ratio" (summary size / original size) is a key tuning knob
- Multi-level: after N sections, sections are grouped and summarized together
  (a "hierarchical" summarization tree)

This strategy often performs well on token efficiency but poorly on factual
consistency — important context for the CRP comparison.
"""

from __future__ import annotations

import re
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


class HierarchicalSummarizationStrategy(BaseStrategy):
    name = "hierarchical"
    label = "Hierarchical Summarization"
    description = (
        "Trending (2025–2026): recursively compress completed sections into a "
        "bounded memory buffer. Constant prompt size, lossy but token-efficient. "
        "Mirrors MemGPT/OS-style memory and LangChain SummaryBufferMemory."
    )
    color = "#8b5cf6"  # purple

    def __init__(
        self,
        *args,
        summary_max_words: int = 300,
        group_size: int = 3,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.summary_max_words = summary_max_words
        self.group_size = group_size  # How many sections to summarize together

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

        # Memory buffer: hierarchical summary of what was written
        memory_buffer = ""
        section_summaries: list[tuple[str, str]] = []  # (section_name, summary)

        doc_title = "# Technical Reference Guide\n\n"
        if on_chunk:
            on_chunk(doc_title)
        accumulated_text += doc_title

        for i, section in enumerate(sections):
            # Build current memory state
            if section_summaries:
                mem_lines = "\n".join(
                    f"  [{j+1}. {name}]: {summary[:200]}"
                    for j, (name, summary) in enumerate(section_summaries)
                )
                memory_block = (
                    f"=== MEMORY BUFFER ({len(section_summaries)} sections summarized) ===\n"
                    f"{mem_lines}\n"
                    f"=== END MEMORY BUFFER ===\n"
                )
            else:
                memory_block = ""

            system = (
                "You are writing a section of a technical reference guide. "
                "A memory buffer containing compressed summaries of all prior sections "
                "is provided for context. Use it to maintain consistency. "
                "Write detailed, unique content. Use markdown headings."
            )
            user = (
                f"{memory_block}\n"
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

            accumulated_text += "\n\n" + text
            window_texts.append(text)

            # Summarize this section and add to memory buffer
            summary = self._summarize(section, text, on_chunk=None)
            total_prompt_tokens += summary[1]
            total_output_tokens += summary[2]
            total_latency += summary[3]
            section_summaries.append((section, summary[0]))

            # Every group_size sections, re-compress the summaries hierarchically
            if len(section_summaries) % self.group_size == 0 and len(section_summaries) > self.group_size:
                compressed = self._group_compress(section_summaries[-self.group_size:])
                total_prompt_tokens += compressed[1]
                total_output_tokens += compressed[2]
                total_latency += compressed[3]
                # Replace the last group_size summaries with one compressed entry
                section_summaries = section_summaries[:-self.group_size] + [
                    (f"[Group: sections {i-self.group_size+2}–{i+1}]", compressed[0])
                ]

            note = f"mem_buf={len(section_summaries)} entries, summary_len={len(summary[0])}"
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

    def _summarize(
        self, section_name: str, text: str, on_chunk: Callable | None
    ) -> tuple[str, int, int, float]:
        """Summarize a single section into a compact memory entry.
        Returns (summary_text, prompt_tokens, output_tokens, latency_s)."""
        import time as _time
        max_words = self.summary_max_words
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a document memory manager. Summarize the following section "
                    f"in at most {max_words} words. Preserve key concepts, specific patterns "
                    f"and important facts. Be dense and precise."
                ),
            },
            {
                "role": "user",
                "content": f"Section: {section_name}\n\n{text[:3000]}",
            },
        ]
        summary, _, pt, ot, lat = self._chat(messages, max_tokens=max_words * 2)
        return summary or f"[Summary of {section_name}]", pt, ot, lat

    def _group_compress(
        self, summaries: list[tuple[str, str]]
    ) -> tuple[str, int, int, float]:
        """Compress multiple section summaries into one hierarchical summary."""
        combined = "\n\n".join(f"[{name}]:\n{s}" for name, s in summaries)
        max_words = self.summary_max_words * 2
        messages = [
            {
                "role": "system",
                "content": (
                    f"Compress these section summaries into a single coherent memory entry "
                    f"of at most {max_words} words. Preserve the most important cross-cutting "
                    f"themes and technical facts."
                ),
            },
            {
                "role": "user",
                "content": combined[:3000],
            },
        ]
        summary, _, pt, ot, lat = self._chat(messages, max_tokens=max_words * 2)
        return summary or "[Compressed group summary]", pt, ot, lat
