# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Base class and shared utilities for all context management strategies.

Every strategy implements :class:`BaseStrategy` and exposes a
``generate(prompt, on_chunk, on_metrics)`` coroutine that:
- calls the local LLM in bounded windows
- streams text chunks to ``on_chunk(text)``
- emits live per-window metric snapshots to ``on_metrics(dict)``
- returns a :class:`StrategyResult` when done.

All strategies run against the *same* local LLM endpoint and the *same*
section list so comparisons are fair.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

# ── Shared topic sections for the benchmark task ─────────────────────────────
BENCHMARK_SECTIONS = [
    "Foundations of Distributed Systems",
    "Service Architecture Patterns",
    "API Design and Versioning",
    "Data Modeling and Storage",
    "Caching Strategies",
    "Message Queues and Streaming",
    "Concurrency and Async Runtimes",
    "Reliability Engineering",
    "Observability and Telemetry",
    "Security Architecture",
]

BENCHMARK_PROMPT = (
    "Write a comprehensive technical reference guide on '{topic}' aimed at senior "
    "engineers. Each section should be detailed, specific, and actionable — covering "
    "key concepts, trade-offs, implementation patterns, and real-world considerations. "
    "Target at least {per_section} words per section."
)


# ── Text quality helpers ────────────────────────────────────────────

def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def ngram_repetition(text: str, n: int = 6) -> float:
    """Fraction of n-grams that are duplicates. 0 = none."""
    words = re.findall(r"\b\w+\b", text.lower())
    if len(words) < n + 1:
        return 0.0
    grams = [" ".join(words[i: i + n]) for i in range(len(words) - n + 1)]
    counts = Counter(grams)
    duplicates = sum(c - 1 for c in counts.values() if c > 1)
    return duplicates / len(grams)


def duplicate_sentence_ratio(text: str) -> float:
    """Fraction of sentences repeated almost verbatim."""
    sentences = _split_sentences(text)
    if not sentences:
        return 0.0
    seen: set[str] = set()
    dupes = 0
    for s in sentences:
        key = re.sub(r"\s+", " ", s.lower())[:100]
        if key in seen:
            dupes += 1
        else:
            seen.add(key)
    return dupes / len(sentences)


def _split_sentences(text: str) -> list[str]:
    body = re.sub(r"(?m)^#{1,6}\s.*$", " ", text)
    body = re.sub(r"[`*_>#]", " ", body)
    parts = re.split(r"(?<=[.!?])\s+", body)
    return [p.strip() for p in parts if len(p.strip()) > 40]


def count_headings(text: str) -> int:
    return len(re.findall(r"(?m)^#{2,3}\s+\S", text))


def unique_word_ratio(text: str) -> float:
    words = re.findall(r"\b\w{4,}\b", text.lower())
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def coherence_score(prev_text: str, curr_text: str) -> float:
    """Bigram overlap between adjacent windows — proxy for topical continuity."""
    def bigrams(t: str) -> set[str]:
        ws = re.findall(r"\b\w+\b", t.lower())
        return {f"{ws[i]} {ws[i+1]}" for i in range(len(ws)-1)}
    prev_bg = bigrams(prev_text[-800:] if len(prev_text) > 800 else prev_text)
    curr_bg = bigrams(curr_text[:800] if len(curr_text) > 800 else curr_text)
    if not prev_bg or not curr_bg:
        return 0.0
    return len(prev_bg & curr_bg) / len(prev_bg | curr_bg)


# ── Strategy result ────────────────────────────────────────────────

@dataclass
class WindowMetrics:
    window: int
    tokens_prompt: int
    tokens_output: int
    latency_s: float
    running_words: int
    repetition_6gram: float
    dup_sentence_ratio: float
    unique_word_ratio: float
    coherence_with_prev: float
    strategy: str
    section_title: str = ""
    note: str = ""


@dataclass
class StrategyResult:
    strategy: str
    full_text: str
    total_words: int
    total_prompt_tokens: int
    total_output_tokens: int
    total_latency_s: float
    windows: int
    final_repetition_6gram: float
    final_dup_sentence_ratio: float
    avg_unique_word_ratio: float
    sections_completed: int
    context_efficiency: float            # output tokens / total tokens
    window_metrics: list[WindowMetrics] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "total_words": self.total_words,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_latency_s": round(self.total_latency_s, 2),
            "windows": self.windows,
            "final_repetition_6gram": round(self.final_repetition_6gram, 4),
            "final_dup_sentence_ratio": round(self.final_dup_sentence_ratio, 4),
            "avg_unique_word_ratio": round(self.avg_unique_word_ratio, 4),
            "sections_completed": self.sections_completed,
            "context_efficiency": round(self.context_efficiency, 4),
            "errors": self.errors,
            "window_metrics": [
                {
                    "window": m.window,
                    "tokens_prompt": m.tokens_prompt,
                    "tokens_output": m.tokens_output,
                    "latency_s": round(m.latency_s, 2),
                    "running_words": m.running_words,
                    "repetition_6gram": round(m.repetition_6gram, 4),
                    "dup_sentence_ratio": round(m.dup_sentence_ratio, 4),
                    "unique_word_ratio": round(m.unique_word_ratio, 4),
                    "coherence_with_prev": round(m.coherence_with_prev, 4),
                    "section_title": m.section_title,
                    "note": m.note,
                }
                for m in self.window_metrics
            ],
        }


# ── Base strategy ────────────────────────────────────────────────

class BaseStrategy:
    """Abstract base for all four context management strategies."""

    name: str = "base"
    label: str = "Base"
    description: str = ""
    color: str = "#888"

    def __init__(
        self,
        endpoint: str,
        model: str,
        context_size: int,
        api_key: str = "local",
        max_tokens_per_window: int = 900,
        target_words: int = 5000,
        sections: list[str] | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.context_size = context_size
        self.api_key = api_key
        self.max_tokens_per_window = max_tokens_per_window
        self.target_words = target_words
        self.sections = sections if sections is not None else BENCHMARK_SECTIONS

    # ── LLM call ───────────────────────────────────────────────
    def _chat(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> tuple[str, str, int, int, float]:
        """Call the local LLM. Returns (text, finish_reason, prompt_tokens, output_tokens, latency_s)."""
        import urllib.request
        import json as _json

        mt = max_tokens or self.max_tokens_per_window
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": mt,
            "temperature": 0.7,
            "stream": on_chunk is not None,
        }
        # Crude token estimate: 1 token ≈ 4 chars
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        prompt_tokens_est = max(1, prompt_chars // 4)

        url = (self.endpoint if self.endpoint.endswith("/v1") else self.endpoint + "/v1") + "/chat/completions"
        req = urllib.request.Request(
            url,
            data=_json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        t0 = time.monotonic()
        try:
            if on_chunk is not None:
                # Streaming
                collected = []
                with urllib.request.urlopen(req, timeout=300) as resp:
                    for raw_line in resp:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = _json.loads(data_str)
                        except Exception:
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        content = delta.get("content") or ""
                        if content:
                            collected.append(content)
                            on_chunk(content)
                text = "".join(collected)
                finish_reason = "stop"
            else:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    result = _json.loads(resp.read())
                choices = result.get("choices") or [{}]
                message = choices[0].get("message", {})
                text = message.get("content") or ""
                finish_reason = choices[0].get("finish_reason", "stop")
                usage = result.get("usage", {})
                prompt_tokens_est = usage.get("prompt_tokens", prompt_tokens_est)
                output_tokens = usage.get("completion_tokens", max(1, len(text) // 4))
                latency = time.monotonic() - t0
                return text, finish_reason, prompt_tokens_est, output_tokens, latency
        except Exception as exc:  # noqa: BLE001
            return f"[error: {exc}]", "error", prompt_tokens_est, 0, time.monotonic() - t0

        latency = time.monotonic() - t0
        output_tokens = max(1, len(text) // 4)
        return text, finish_reason, prompt_tokens_est, output_tokens, latency

    def run(
        self,
        on_chunk: Callable[[str], None] | None = None,
        on_metrics: Callable[[dict], None] | None = None,
        on_window_done: Callable[[int, str, dict], None] | None = None,
    ) -> StrategyResult:
        raise NotImplementedError
