# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Input-side continuation planner — split oversized tasks into full windows (§4.6).

When a task or input context exceeds a single model window, this module plans
a sequence of input-processing windows.  Each window consumes a chunk of the
input, extracts facts, and relays them to the next chunk.  After all chunks
have been processed, the accumulated facts replace the bulky input so the
final answer window can run inside a normal context budget.

This realizes the CRP unbounded-context guarantee for *inputs*: a 4K model
can transparently process a 12K prompt across three full windows rather than
silently compacting or truncating it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class InputChunk:
    """A single input-continuation window payload."""

    index: int
    total: int
    text: str
    prefix: str = ""
    suffix: str = ""


@dataclass
class InputContinuationPlan:
    """Plan produced for an oversized input."""

    chunks: list[InputChunk] = field(default_factory=list)
    directive_tokens: int = 0
    chunk_tokens: int = 0


class InputContinuationPlanner:
    """Plan how to process an oversized input across multiple full windows.

    The planner respects natural boundaries (paragraphs, then sentences, then
    words) so that chunks are semantically coherent.  It leaves room for the
    system prompt, a small generation reserve (the model only extracts facts),
    and a fixed continuation directive.
    """

    # Tokens reserved for the per-chunk directive and any relay envelope.
    DEFAULT_DIRECTIVE_TOKENS = 180
    # Generation reserve for input windows — small because we only extract.
    DEFAULT_INPUT_GENERATION_RESERVE = 256

    def __init__(
        self,
        count_tokens: Callable[[str], int],
        directive_tokens: int | None = None,
        input_generation_reserve: int | None = None,
    ) -> None:
        """Initialize planner.

        Args:
            count_tokens: Provider-specific token counter.
            directive_tokens: Tokens to reserve for continuation directives.
            input_generation_reserve: Generation reserve for extraction windows.
        """
        self._count_tokens = count_tokens
        self._directive_tokens = directive_tokens or self.DEFAULT_DIRECTIVE_TOKENS
        self._input_g = input_generation_reserve or self.DEFAULT_INPUT_GENERATION_RESERVE

    def plan(
        self,
        task_input: str,
        system_prompt: str,
        context_window: int,
    ) -> InputContinuationPlan:
        """Create a multi-window plan for ``task_input``.

        Args:
            task_input: The oversized user task or context.
            system_prompt: System prompt that will be included in every window.
            context_window: Model context window size.

        Returns:
            InputContinuationPlan with semantically-bounded chunks.
        """
        s_tokens = self._count_tokens(system_prompt)
        per_chunk_budget = context_window - s_tokens - self._directive_tokens - self._input_g
        if per_chunk_budget <= 0:
            # The system prompt alone leaves no room; fall back to one giant
            # chunk and let downstream compaction deal with it.
            per_chunk_budget = max(256, context_window - s_tokens - self._input_g)

        chunks = self._split_text(task_input, per_chunk_budget)
        directive_text = self._chunk_directive(0, 1)
        return InputContinuationPlan(
            chunks=chunks,
            directive_tokens=self._count_tokens(directive_text),
            chunk_tokens=sum(self._count_tokens(c.text) for c in chunks),
        )

    def _split_text(self, text: str, max_tokens: int) -> list[InputChunk]:
        """Split ``text`` into chunks that each fit inside ``max_tokens``.

        Prefers paragraph boundaries, then sentence boundaries, then words.
        """
        if self._count_tokens(text) <= max_tokens:
            return [InputChunk(index=1, total=1, text=text)]

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[InputChunk] = []
        current: list[str] = []
        current_tokens = 0
        idx = 0

        def _flush() -> None:
            nonlocal current, current_tokens, idx
            if not current:
                return
            idx += 1
            chunks.append(InputChunk(index=idx, total=0, text="\n\n".join(current)))
            current = []
            current_tokens = 0

        for para in paragraphs:
            para_tokens = self._count_tokens(para)
            if para_tokens > max_tokens:
                # Oversized paragraph — split by sentences.
                _flush()
                for sentence_chunk in self._split_sentences(para, max_tokens):
                    idx += 1
                    chunks.append(InputChunk(index=idx, total=0, text=sentence_chunk))
                continue
            if current_tokens + para_tokens > max_tokens and current:
                _flush()
            current.append(para)
            current_tokens += para_tokens

        _flush()

        # Resolve totals now that we know the count.
        total = len(chunks)
        for c in chunks:
            c.total = total
        return chunks

    def _split_sentences(self, text: str, max_tokens: int) -> list[str]:
        """Split a long paragraph by sentence boundaries."""
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for sent in sentences:
            sent_tokens = self._count_tokens(sent)
            if sent_tokens > max_tokens:
                # Oversized sentence — split by words.
                if current:
                    chunks.append(" ".join(current))
                    current = []
                    current_tokens = 0
                chunks.extend(self._split_words(sent, max_tokens))
                continue
            if current_tokens + sent_tokens > max_tokens and current:
                chunks.append(" ".join(current))
                current = []
                current_tokens = 0
            current.append(sent)
            current_tokens += sent_tokens

        if current:
            chunks.append(" ".join(current))
        return chunks

    def _split_words(self, text: str, max_tokens: int) -> list[str]:
        """Last-resort word-level split."""
        words = text.split()
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for word in words:
            word_tokens = self._count_tokens(word)
            if current_tokens + word_tokens > max_tokens and current:
                chunks.append(" ".join(current))
                current = []
                current_tokens = 0
            current.append(word)
            current_tokens += word_tokens

        if current:
            chunks.append(" ".join(current))
        return chunks

    def build_chunk_task(
        self,
        chunk: InputChunk,
        original_task_summary: str,
        prior_summary: str | None = None,
    ) -> str:
        """Build the task text for a single input-continuation window.

        Args:
            chunk: Chunk to process.
            original_task_summary: Short summary of the overall task/question.
            prior_summary: Optional summary of facts from prior chunks.

        Returns:
            Task text ready for dispatch.
        """
        parts = [
            self._chunk_directive(chunk.index, chunk.total),
            f"\n=== ORIGINAL TASK ===\n{original_task_summary}",
        ]
        if prior_summary:
            parts.append(f"\n=== FACTS FROM PRIOR CHUNKS ===\n{prior_summary}")
        parts.append(f"\n=== INPUT CHUNK {chunk.index} OF {chunk.total} ===\n{chunk.text}")
        parts.append("\n=== END INPUT CHUNK ===")
        return "\n".join(parts)

    def _chunk_directive(self, index: int, total: int) -> str:
        return (
            f"You are processing part {index} of {total} of a long input. "
            "Read the input chunk carefully, extract key facts, entities, "
            "requirements, and any information needed to answer the original task. "
            "Do NOT write the final answer yet — only extract and summarize "
            "relevant findings."
        )

    def build_final_task_reference(self, original_task_input: str) -> str:
        """Build a compact reference to the original task after input processing.

        The original bulky input has been replaced by extracted facts in the
        warm store / CKF.  This reference reminds the model of the question.
        """
        summary = original_task_input[:400]
        if len(original_task_input) > 400:
            summary += " ..."
        return (
            f"Answer the following task using the facts extracted from the "
            f"processed input sections:\n{summary}"
        )


def default_input_planner(count_tokens: Callable[[str], int]) -> InputContinuationPlanner:
    """Factory for the default planner."""
    return InputContinuationPlanner(count_tokens=count_tokens)
