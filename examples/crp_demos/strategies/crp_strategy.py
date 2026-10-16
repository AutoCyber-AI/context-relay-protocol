# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Strategy 1 - CRP Context Relay Protocol (real engine).

This arm drives the actual protocol: ``CRPOrchestrator.dispatch_stream`` -
6-phase envelope construction over the Contextual Knowledge Fabric, the
graduated extraction pipeline, and the ContinuationManager loop (gap
analysis, residual task anchor, stitching). Streaming is native
(``dispatch_stream`` token events), and per-window metrics come from the
engine's own ``window_complete`` events. The done event's ``QualityReport``
telemetry supplies the aggregate token totals.

Contrast arms (injection / RAG / hierarchical) deliberately emulate weaker
approaches - this one must never do so. There is deliberately no fallback
prompt loop here: if the real engine fails, the strategy fails visibly and
``comparison_backend`` records a ``strategy_error`` event.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Generator
from typing import Any

from crp.providers.llamacpp import LlamaCppAdapter

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


class _StreamingLlamaCpp(LlamaCppAdapter):  # type: ignore[misc]
    """LlamaCppAdapter + real SSE streaming for dispatch_stream.

    The base default yields the whole response as one chunk; this override
    streams tokens so the comparison UI sees live output from the real
    engine.
    """

    def __init__(self, *, model: str, api_key: str = "local", **kw: Any):
        super().__init__(**kw)
        self._demo_model = model
        self._demo_api_key = api_key

    def generate_chat_stream(  # type: ignore[override]
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Generator[str, None, str]:
        import json as _json
        import urllib.request

        max_tokens = kwargs.pop("max_tokens", None) or self._max_tokens
        payload = {
            "model": self._demo_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "stream": True,
        }
        url = f"{(self._server_url or '').rstrip('/')}/v1/chat/completions"
        req = urllib.request.Request(
            url,
            data=_json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._demo_api_key}",
            },
            method="POST",
        )
        finish = "stop"
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
                except ValueError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content") or ""
                if content:
                    yield content
                if choices[0].get("finish_reason"):
                    finish = choices[0]["finish_reason"]
        return finish


def _trim_dangling_sentence(text: str) -> tuple[str, bool]:
    """Cut a segment that ends mid-sentence back to its last sentence end.

    Wall-hit windows can stop anywhere — observed live: a window ended
    "...exercise control over their actions in a way that is necessary" and
    the fragment dangled in the deliverable forever. Returns (trimmed, True)
    when a partial trailing sentence was removed; (text, False) otherwise.
    The removed fragment is still relayed to the next window through the
    continuation envelope's [TRUNCATION POINT] section, so the sentence can
    be completed there.
    """
    t = text.rstrip()
    if not t or t[-1] in ".!?\"')\"]":
        return text, False
    idx = max(t.rfind("."), t.rfind("!"), t.rfind("?"))
    if idx <= 0:
        return text, False  # single unterminated sentence — nothing to cut
    return t[: idx + 1] + "\n", True


_SENTENCE_SPLIT_KEEP = re.compile(r"((?<=[.!?])\s+)")


def _dedup_repeat_sentences(text: str) -> tuple[str, int]:
    """Drop exact duplicate sentences beyond their first occurrence.

    Small models reuse whole sentences across sections ("However, this view
    faces significant challenges in explaining how such..."). The acceptance
    gate penalises duplicate sentences; the document should meet the gate's
    own bar. Only exact duplicates of substantial sentences (>40 chars) are
    dropped — shared terminology and stock phrases inside otherwise
    different sentences are untouched. Separators (including newlines) are
    captured so the markdown structure survives intact.
    """
    parts = _SENTENCE_SPLIT_KEEP.split(text)
    seen: set[str] = set()
    out: list[str] = []
    dropped = 0
    for i in range(0, len(parts), 2):
        sent = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        key = " ".join(sent.split()).lower()
        if len(key) > 40:
            if key in seen:
                dropped += 1
                continue  # drop the sentence AND its separator
            seen.add(key)
        out.append(sent)
        out.append(sep)
    if dropped:
        return "".join(out), dropped
    return text, 0


def _strip_trailing_bare_headings(text: str) -> tuple[str, int]:
    """Remove trailing heading lines that have no body under them.

    Observed live: the token budget cut a window right after
    '### Conclusion (Summarizing the Guide) (at least 400 words)' — a bare
    heading advertising content that does not exist. A heading with nothing
    after it carries no content and reads as a bug in the deliverable.
    """
    t = text.rstrip()
    lines = t.split("\n")
    stripped = 0
    while lines and lines[-1].lstrip().startswith("#"):
        lines.pop()
        stripped += 1
    if stripped:
        return "\n".join(lines).rstrip() + "\n", stripped
    return text, 0


class CRPStrategy(BaseStrategy):
    name = "crp"
    label = "CRP Context Relay"
    description = (
        "Real CRP engine: CRPOrchestrator.dispatch_stream - CKF-grounded "
        "envelopes, graduated extraction, ContinuationManager loop."
    )
    color = "#3b82f6"  # blue

    def __init__(self, *args: Any, research: list[str] | None = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        # Optional retrieved source material (e.g. Wikipedia intros per
        # section). Kept in the system prompt so every continuation window
        # sees it; grounded material counters parametric-memory drift.
        self.research = research or []

    def run(
        self,
        on_chunk: Callable[[str], None] | None = None,
        on_metrics: Callable[[dict], None] | None = None,
        on_window_done: Callable[[int, str, dict], None] | None = None,
        on_document: Callable[[str], None] | None = None,
    ) -> StrategyResult:
        """Drive the real CRP continuation engine. No silent fallback."""
        return self._run_crp(on_chunk, on_metrics, on_window_done, on_document)

    def _run_crp(
        self,
        on_chunk: Callable[[str], None] | None,
        on_metrics: Callable[[dict], None] | None,
        on_window_done: Callable[[int, str, dict], None] | None,
        on_document: Callable[[str], None] | None,
    ) -> StrategyResult:
        """Invoke CRPOrchestrator.dispatch_stream and translate its event
        stream into the strategy result shape the comparison UI consumes."""
        from crp.continuation.manager import collapse_duplicate_blocks
        from crp.core.orchestrator import CRPOrchestrator

        server_url = self.endpoint[:-3] if self.endpoint.endswith("/v1") \
            else self.endpoint
        provider = _StreamingLlamaCpp(
            server_url=server_url,
            model=self.model,
            api_key=self.api_key,
            context_size=self.context_size,
            max_tokens=self.max_tokens_per_window,
        )
        # Bound the continuation budget to the word target: estimate ~1.4
        # tokens per word and allow the planned sections plus a margin.
        # Without this the loop keeps opening windows on word-count gaps the
        # model can only fill by rephrasing earlier sections. The margin is
        # +3: +2 covered a thin window, live runs (6.2.2 era) showed a single
        # underperforming window (~250 words vs ~500 estimated) still
        # stranding the doc below target — the third window is the cheapest
        # insurance and the near-duplicate / low-novelty guards (6.1.7+,
        # 6.2.2) prevent runaway.
        # NOTE: the engine's trigger counts the INITIAL window inside
        # max_continuations (continuation_count == window_count) and fires at
        # >=, so total windows == max_continuations exactly. Passing
        # planned_windows - 1 silently cut the last window — the run stopped
        # before the word target and before the conclusion every time.
        est_words_per_window = max(150, int(self.max_tokens_per_window / 1.4))
        planned_windows = max(
            len(self.sections) + 1,
            -(-self.target_words // est_words_per_window) + 3,
        )
        orch = CRPOrchestrator(
            provider=provider,
            max_continuations=planned_windows,
        )

        per_section = max(300, self.target_words // len(self.sections))
        numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(self.sections))
        system = (
            "You are writing a comprehensive technical reference guide for "
            "senior engineers. Cover every requested section in order, in "
            "depth, with concrete implementation details, trade-offs, and "
            "real-world patterns. Never rewrite a completed section."
        )
        if self.research:
            source_block = "\n\n".join(
                f"[Source {i+1}]\n{snippet}" for i, snippet in enumerate(self.research[:6])
            )
            system += (
                "\n\nREFERENCE MATERIAL retrieved for this guide. Ground the "
                "content in these sources; use specific facts from them instead "
                "of restating general knowledge:\n" + source_block
            )
        task = (
            f"Write a comprehensive technical reference guide covering ALL of "
            f"the following {len(self.sections)} sections, in order, each at "
            f"least {per_section} words:\n\n{numbered}\n\n"
            "Begin immediately with '# Technical Reference Guide'. "
            "After the final numbered section, add a short '## Conclusion' "
            "summarising the guide. "
            "Do not rewrite completed sections."
        )

        collected: list[str] = []
        seg_buf: list[str] = []
        stitched_doc = ""  # document assembled via the real stitcher
        window_metrics: list[WindowMetrics] = []
        errors: list[str] = []
        report = None
        window_idx = 0
        prev_text = ""

        t0 = time.monotonic()
        for evt in orch.dispatch_stream(system_prompt=system, task_input=task):
            et = evt.event_type
            if et == "token":
                collected.append(evt.data)
                seg_buf.append(evt.data)
                if on_chunk:
                    on_chunk(evt.data)
            elif et == "window_complete":
                window_idx += 1
                seg_text = "".join(seg_buf)
                seg_buf = []
                summary = evt.data
                full_so_far = "".join(collected)
                # The raw token stream concatenates window outputs with no
                # boundary handling ("...Serverless## 3. API Design..."),
                # which breaks markdown headings at every stitch point in
                # the rendered document. The deliverable is assembled
                # separately: newline-safe join plus document-level
                # duplicate-block collapse. (The full prose stitcher is NOT
                # used here — measured on real segments it over-trims: its
                # section dedup kills same-titled subsections under
                # different parents and echo detection can swallow a whole
                # rewritten section, ~1150 words lost on one live run.)
                # Mid-sentence fragments: a wall-hit window can stop anywhere
                # ("...in a way that is necessary"). Cut the dangling partial
                # sentence back to the last complete one — the fragment is
                # still relayed to the next window via the continuation
                # envelope's [TRUNCATION POINT] section, which quotes it
                # verbatim and asks the model to complete it there.
                seg_text, _trimmed = _trim_dangling_sentence(seg_text)
                sep = ""
                if stitched_doc:
                    sep = "\n" if stitched_doc.endswith("\n") else "\n\n"
                combined = stitched_doc + sep + seg_text
                combined, _dropped = collapse_duplicate_blocks(combined, "")
                # Document-level polish: exact duplicate sentences beyond the
                # first occurrence (the gate penalises these — the document
                # should meet the gate's own bar), and bare heading lines at
                # the very end advertising content the token budget cut off.
                combined, _sd = _dedup_repeat_sentences(combined)
                combined, _sh = _strip_trailing_bare_headings(combined)
                stitched_doc = combined
                if on_document:
                    on_document(stitched_doc)
                wm = _make_wm(
                    self.name, window_idx,
                    summary.input_tokens, summary.output_tokens,
                    summary.wall_time_ms / 1000.0, full_so_far,
                    prev_window_text=prev_text,
                    section_title=(
                        self.sections[window_idx - 1]
                        if window_idx - 1 < len(self.sections)
                        else f"continuation (beyond the {len(self.sections)} planned sections)"
                    ),
                    note="CRP continuation engine (real dispatch_stream)",
                )
                prev_text = seg_text
                window_metrics.append(wm)
                if on_metrics:
                    on_metrics(wm.__dict__)
                if on_window_done:
                    on_window_done(window_idx, seg_text, wm.__dict__)
            elif et == "error":
                errors.append(str(evt.data))
            elif et == "done":
                report = evt.data

        full_text = stitched_doc
        total_latency = time.monotonic() - t0

        telemetry = dict(getattr(report, "telemetry", None) or {})
        total_prompt_tokens = int(
            telemetry.get("total_input_tokens")
            or (telemetry.get("system_tokens", 0)
                + telemetry.get("task_tokens", 0)
                + telemetry.get("envelope_tokens", 0))
            or 0
        )
        total_output_tokens = int(
            telemetry.get("total_output_tokens")
            or telemetry.get("generation_tokens", 0) or 0
        )
        rep_cont = int(getattr(report, "continuation_windows", 0) or 0)
        windows = max(window_idx, rep_cont + 1, 1)
        termination_reason = str(
            telemetry.get("continuation_termination_reason") or ""
        )

        wc = word_count(full_text)
        rep = ngram_repetition(full_text)
        dup = duplicate_sentence_ratio(full_text)
        uwr_list = [m.unique_word_ratio for m in window_metrics] or [0.0]
        uwr_avg = sum(uwr_list) / len(uwr_list)
        total_toks = max(1, total_prompt_tokens + total_output_tokens)

        return StrategyResult(
            strategy=self.name,
            full_text=full_text,
            total_words=wc,
            total_prompt_tokens=total_prompt_tokens,
            total_output_tokens=total_output_tokens,
            total_latency_s=total_latency,
            windows=windows,
            final_repetition_6gram=rep,
            final_dup_sentence_ratio=dup,
            avg_unique_word_ratio=uwr_avg,
            sections_completed=count_headings(full_text),
            context_efficiency=total_output_tokens / total_toks,
            termination_reason=termination_reason,
            window_metrics=window_metrics,
            errors=errors,
        )


def _make_wm(
    strategy: str,
    window: int,
    pt: int,
    ot: int,
    lat: float,
    full_so_far: str,
    prev_window_text: str = "",
    section_title: str = "",
    note: str = "",
) -> WindowMetrics:
    curr_window_text = full_so_far[-2000:] if len(full_so_far) > 2000 else full_so_far
    return WindowMetrics(
        window=window,
        tokens_prompt=pt,
        tokens_output=ot,
        latency_s=lat,
        running_words=word_count(full_so_far),
        repetition_6gram=ngram_repetition(full_so_far),
        dup_sentence_ratio=duplicate_sentence_ratio(full_so_far),
        unique_word_ratio=unique_word_ratio(curr_window_text),
        coherence_with_prev=coherence_score(prev_window_text, curr_window_text),
        strategy=strategy,
        section_title=section_title,
        note=note,
    )
