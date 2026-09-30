# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Demo D backend — long-context document generation (CRP continuation).

Drives :class:`CRPStrategy` in a background thread so the browser demo can
stream every generated chunk, watch windows complete one by one, and receive
the acceptance gate at the end. Mirrors the CLI proof in
``run_benchmark.py --strategies crp`` (guide section 12A).

API (used by ``server.py``):

  POST /api/longgen/start    → {"run_id"}              body: sections, words, tokens_per_window
  GET  /api/longgen/stream   → SSE (run_id query param)
  GET  /api/longgen/status   → run state (run_id query param)
  POST /api/longgen/cancel   → {"cancelled": bool}
  POST /api/longgen/poll     → {"events": [...]}        non-SSE drain

Events: run_started, chunk {text}, window_done {window, metrics},
run_done {result, full_text, acceptance}, run_error {error}.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from typing import Any

from .strategies.base import (
    BENCHMARK_SECTIONS,
    count_headings,
    duplicate_sentence_ratio,
    ngram_repetition,
    word_count,
)
from .strategies.crp_strategy import CRPStrategy

logger = logging.getLogger("crp.demos.longgen")

_RUNS: dict[str, _LongGenRun] = {}
_RUNS_LOCK = threading.Lock()


class _LongGenRun:
    def __init__(self, run_id: str, config: dict[str, Any]) -> None:
        self.run_id = run_id
        self.config = config
        self.status = "pending"  # pending | running | done | cancelled | error
        self.started_at = 0.0
        self.ended_at = 0.0
        self.error: str | None = None
        self.events: queue.Queue = queue.Queue(maxsize=4000)
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    def emit(self, event_type: str, data: Any) -> None:
        try:
            self.events.put_nowait({"type": event_type, "data": data, "ts": time.time()})
        except queue.Full:
            pass  # a slow viewer must not stall generation

    def cancel(self) -> None:
        self._cancel.set()
        self.status = "cancelled"


def acceptance_gate(full_text: str, result: dict[str, Any], target_words: int,
                    sections_planned: int) -> dict[str, Any]:
    """The Demo D proof gate (guide 12A.2), scaled to the run's own config.

    Repetition and duplicate-sentence checks stay absolute - they are the
    quality guards against padding. Heading count scales with the number of
    sections requested, and a conclusion is only demanded of documents long
    enough to need one (4+ sections)."""
    words = word_count(full_text)
    headings = count_headings(full_text)
    rep6 = ngram_repetition(full_text, 6)
    dup = duplicate_sentence_ratio(full_text)
    has_conclusion = "conclusion" in full_text.lower()
    min_headings = max(3, sections_planned * 2)
    checks = [
        {"check": "word count", "value": words, "threshold": f">= {target_words:,}",
         "pass": words >= target_words},
        {"check": "headings", "value": headings, "threshold": f">= {min_headings}",
         "pass": headings >= min_headings},
        {"check": "6-gram repetition", "value": f"{rep6 * 100:.2f}%",
         "threshold": "< 1%", "pass": rep6 < 0.01},
        {"check": "duplicate sentences", "value": f"{dup * 100:.2f}%",
         "threshold": "< 2%", "pass": dup < 0.02},
    ]
    if sections_planned >= 4:
        checks.append({"check": "conclusion section",
                       "value": "present" if has_conclusion else "missing",
                       "threshold": "present", "pass": has_conclusion})
    return {"pass": all(c["pass"] for c in checks), "checks": checks,
            "words": words, "headings": headings}


def _run_longgen(run: _LongGenRun) -> None:
    run.status = "running"
    run.started_at = time.time()
    cfg = run.config
    sections_n = max(1, min(10, int(cfg.get("sections", 5))))
    target_words = max(500, int(cfg.get("words", 2500)))
    tokens_per_window = max(200, int(cfg.get("tokens_per_window", 700)))
    endpoint = str(cfg.get("endpoint", "http://127.0.0.1:1234"))
    model = str(cfg.get("model", "meta-llama-3.1-8b-instruct"))
    context_size = int(cfg.get("context_size", 4096))
    # Optional user-defined section titles replace the built-in topic.
    custom_sections = [
        str(s).strip() for s in (cfg.get("section_titles") or [])
        if str(s).strip()
    ]
    chosen_sections = custom_sections[:sections_n] if custom_sections \
        else BENCHMARK_SECTIONS[:sections_n]

    strategy = CRPStrategy(
        endpoint=endpoint,
        model=model,
        context_size=context_size,
        max_tokens_per_window=tokens_per_window,
        target_words=target_words,
        sections=chosen_sections,
    )
    run.emit("run_started", {
        "run_id": run.run_id, "model": model, "context_size": context_size,
        "sections": len(chosen_sections), "target_words": target_words,
        "tokens_per_window": tokens_per_window,
        "section_titles": chosen_sections,
    })

    def on_chunk(chunk: str) -> None:
        if not run._cancel.is_set():
            run.emit("chunk", {"text": chunk})

    def on_metrics(metrics: dict) -> None:
        run.emit("window_metrics", {"metrics": metrics})

    def on_window_done(window: int, text: str, metrics: dict) -> None:
        run.emit("window_done", {
            "window": window,
            "words_in_window": len(text.split()),
            "metrics": metrics,
        })

    try:
        result = strategy.run(on_chunk=on_chunk, on_metrics=on_metrics,
                              on_window_done=on_window_done)
    except Exception as exc:  # noqa: BLE001
        logger.exception("longgen run failed")
        run.error = str(exc)
        run.status = "error"
        run.emit("run_error", {"error": str(exc)})
        return

    if run._cancel.is_set():
        run.status = "cancelled"
        return

    result_dict = result.to_dict()
    gate = acceptance_gate(result.full_text, result_dict, target_words, len(chosen_sections))
    run.status = "done"
    run.ended_at = time.time()
    run.emit("run_done", {
        "run_id": run.run_id,
        "result": result_dict,
        "acceptance": gate,
        "elapsed_s": round(run.ended_at - run.started_at, 1),
    })


def start_run(config: dict[str, Any]) -> str:
    run_id = str(uuid.uuid4())
    run = _LongGenRun(run_id, config)
    with _RUNS_LOCK:
        _RUNS[run_id] = run
    t = threading.Thread(target=_run_longgen, args=(run,), daemon=True)
    run._thread = t
    t.start()
    return run_id


def get_run(run_id: str) -> _LongGenRun | None:
    with _RUNS_LOCK:
        return _RUNS.get(run_id)


def cancel_run(run_id: str) -> bool:
    run = get_run(run_id)
    if run:
        run.cancel()
        return True
    return False


def get_status(run_id: str) -> dict[str, Any]:
    run = get_run(run_id)
    if not run:
        return {"error": "run not found"}
    return {
        "run_id": run_id,
        "status": run.status,
        "started_at": run.started_at,
        "elapsed_s": round(time.time() - run.started_at, 1) if run.started_at else 0,
        "error": run.error,
    }


def stream_events(run_id: str, timeout: float = 60.0) -> list[dict[str, Any]]:
    """Drain up to 100 pending events; used for SSE and polling."""
    run = get_run(run_id)
    if not run:
        return []
    events = []
    deadline = time.time() + timeout
    while time.time() < deadline and len(events) < 100:
        try:
            evt = run.events.get(timeout=0.1)
            events.append(evt)
            if evt.get("type") in ("run_done", "run_error"):
                break
        except queue.Empty:
            if run.status in ("done", "cancelled", "error"):
                break
    return events
