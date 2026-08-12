# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Context Management Comparison Backend.

Provides HTTP API endpoints for the 4-strategy context comparison demo:

  POST /api/compare/start     → start a benchmark run (returns run_id)
  GET  /api/compare/stream    → SSE stream for a run_id
  GET  /api/compare/status    → current run state + partial results
  POST /api/compare/cancel    → cancel an in-progress run
  GET  /api/compare/detect    → model/context info for pre-flight

All four strategies run against the SAME local LLM in sequence, producing
comparable results. Each strategy streams progress via Server-Sent Events.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid
from typing import Any

from .strategies.base import BENCHMARK_SECTIONS
from .strategies.crp_strategy import CRPStrategy
from .strategies.rag_strategy import RAGStrategy
from .strategies.injection_strategy import InjectionStrategy
from .strategies.hierarchical_strategy import HierarchicalSummarizationStrategy

logger = logging.getLogger("crp.demos.comparison")

# ── Run registry ─────────────────────────────────────────────────────────────

_RUNS: dict[str, "_BenchmarkRun"] = {}
_RUNS_LOCK = threading.Lock()


class _BenchmarkRun:
    def __init__(self, run_id: str, config: dict[str, Any]) -> None:
        self.run_id = run_id
        self.config = config
        self.status = "pending"          # pending | running | done | cancelled | error
        self.started_at: float = 0.0
        self.ended_at: float = 0.0
        self.results: dict[str, Any] = {}
        self.events: queue.Queue = queue.Queue(maxsize=2000)
        self.errors: list[str] = []
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    def emit(self, event_type: str, data: Any) -> None:
        try:
            self.events.put_nowait({"type": event_type, "data": data, "ts": time.time()})
        except queue.Full:
            pass  # Drop if subscriber is slow

    def cancel(self) -> None:
        self._cancel.set()
        self.status = "cancelled"


# ── Benchmark runner ──────────────────────────────────────────────────────────

_STRATEGY_META = {
    "crp":          {"label": "CRP Context Relay",               "color": "#3b82f6"},
    "rag":          {"label": "RAG (Retrieval-Augmented)",        "color": "#10b981"},
    "injection":    {"label": "Context Injection (Naive)",        "color": "#f59e0b"},
    "hierarchical": {"label": "Hierarchical Summarization",       "color": "#8b5cf6"},
}


def _run_benchmark(run: _BenchmarkRun) -> None:
    run.status = "running"
    run.started_at = time.time()
    run.emit("run_started", {"run_id": run.run_id, "strategies": list(_STRATEGY_META.keys())})

    cfg = run.config
    endpoint = cfg.get("endpoint", "http://127.0.0.1:1234")
    model = cfg.get("model", "")
    context_size = int(cfg.get("context_size", 4096))
    target_words = int(cfg.get("target_words", 3000))
    max_tokens_per_window = int(cfg.get("max_tokens_per_window", 800))
    selected = cfg.get("strategies", list(_STRATEGY_META.keys()))
    sections_slice = int(cfg.get("sections", len(BENCHMARK_SECTIONS)))
    sections = BENCHMARK_SECTIONS[:sections_slice]

    strategy_kwargs = dict(
        endpoint=endpoint,
        model=model,
        context_size=context_size,
        max_tokens_per_window=max_tokens_per_window,
        target_words=target_words,
        sections=sections,
    )

    strategies = []
    if "crp" in selected:
        strategies.append(CRPStrategy(**strategy_kwargs))
    if "rag" in selected:
        strategies.append(RAGStrategy(**strategy_kwargs))
    if "injection" in selected:
        strategies.append(InjectionStrategy(**strategy_kwargs))
    if "hierarchical" in selected:
        strategies.append(HierarchicalSummarizationStrategy(**strategy_kwargs))

    all_results: dict[str, Any] = {}

    for strategy in strategies:
        if run._cancel.is_set():
            break

        run.emit("strategy_started", {
            "strategy": strategy.name,
            "label": strategy.label,
            "color": strategy.color,
        })

        def on_chunk(chunk: str, _s: Any = strategy) -> None:
            run.emit("chunk", {"strategy": _s.name, "text": chunk})

        def on_metrics(metrics: dict, _s: Any = strategy) -> None:
            run.emit("window_metrics", {"strategy": _s.name, "metrics": metrics})

        def on_window_done(window: int, text: str, metrics: dict, _s: Any = strategy) -> None:
            run.emit("window_done", {
                "strategy": _s.name,
                "window": window,
                "words_in_window": len(text.split()),
                "metrics": metrics,
            })

        try:
            result = strategy.run(
                on_chunk=on_chunk,
                on_metrics=on_metrics,
                on_window_done=on_window_done,
            )
            result_dict = result.to_dict()
            all_results[strategy.name] = result_dict
            run.emit("strategy_done", {
                "strategy": strategy.name,
                "result": result_dict,
            })
        except Exception as exc:  # noqa: BLE001
            logger.exception("strategy %s failed", strategy.name)
            run.errors.append(f"{strategy.name}: {exc}")
            run.emit("strategy_error", {"strategy": strategy.name, "error": str(exc)})

    run.results = all_results
    run.ended_at = time.time()
    run.status = "done" if not run._cancel.is_set() else "cancelled"

    # Build comparison summary
    summary = _build_comparison_summary(all_results)
    run.emit("run_done", {
        "run_id": run.run_id,
        "results": all_results,
        "summary": summary,
        "elapsed_s": run.ended_at - run.started_at,
    })


def _build_comparison_summary(results: dict[str, Any]) -> dict[str, Any]:
    """Compute a head-to-head comparison table."""
    if not results:
        return {}

    metrics = ["total_words", "total_prompt_tokens", "total_output_tokens",
               "final_repetition_6gram", "final_dup_sentence_ratio",
               "avg_unique_word_ratio", "sections_completed",
               "context_efficiency", "total_latency_s"]

    table = {}
    for m in metrics:
        table[m] = {s: round(r.get(m, 0), 4) for s, r in results.items()}

    # Rankings (lower is better for some, higher for others)
    lower_better = {"final_repetition_6gram", "final_dup_sentence_ratio", "total_prompt_tokens"}
    rankings: dict[str, dict[str, int]] = {}
    for m in metrics:
        vals = {s: r.get(m, 0) for s, r in results.items()}
        sorted_strategies = sorted(vals.keys(), key=lambda s: vals[s],
                                   reverse=(m not in lower_better))
        rankings[m] = {s: rank+1 for rank, s in enumerate(sorted_strategies)}

    # Overall score (average rank, lower = better)
    strategy_names = list(results.keys())
    avg_rank = {}
    for s in strategy_names:
        ranks = [rankings[m][s] for m in metrics if s in rankings.get(m, {})]
        avg_rank[s] = round(sum(ranks) / len(ranks), 2) if ranks else 0

    winner = min(avg_rank, key=lambda s: avg_rank[s]) if avg_rank else None

    return {
        "table": table,
        "rankings": rankings,
        "avg_rank": avg_rank,
        "winner": winner,
        "insights": _generate_insights(results, avg_rank),
    }


def _generate_insights(results: dict[str, Any], avg_rank: dict[str, float]) -> list[str]:
    insights = []
    if not results:
        return insights

    # Context efficiency insight
    effs = {s: r.get("context_efficiency", 0) for s, r in results.items()}
    best_eff = max(effs, key=lambda s: effs[s]) if effs else None
    worst_eff = min(effs, key=lambda s: effs[s]) if effs else None
    if best_eff and worst_eff and best_eff != worst_eff:
        ratio = effs[best_eff] / max(0.001, effs[worst_eff])
        insights.append(
            f"{_STRATEGY_META.get(best_eff, {}).get('label', best_eff)} is "
            f"{ratio:.1f}× more token-efficient than "
            f"{_STRATEGY_META.get(worst_eff, {}).get('label', worst_eff)}."
        )

    # Repetition insight
    reps = {s: r.get("final_repetition_6gram", 0) for s, r in results.items()}
    cleanest = min(reps, key=lambda s: reps[s]) if reps else None
    most_rep = max(reps, key=lambda s: reps[s]) if reps else None
    if cleanest and most_rep:
        insights.append(
            f"{_STRATEGY_META.get(cleanest, {}).get('label', cleanest)} had the least "
            f"repetition ({reps[cleanest]*100:.1f}% 6-gram overlap); "
            f"{_STRATEGY_META.get(most_rep, {}).get('label', most_rep)} the most "
            f"({reps[most_rep]*100:.1f}%)."
        )

    # Word count insight
    wcs = {s: r.get("total_words", 0) for s, r in results.items()}
    most_words = max(wcs, key=lambda s: wcs[s]) if wcs else None
    if most_words:
        insights.append(
            f"{_STRATEGY_META.get(most_words, {}).get('label', most_words)} produced "
            f"the most content ({wcs[most_words]:,} words)."
        )

    # Winner insight
    if avg_rank:
        winner = min(avg_rank, key=lambda s: avg_rank[s])
        insights.append(
            f"Overall winner by average metric rank: "
            f"{_STRATEGY_META.get(winner, {}).get('label', winner)} "
            f"(avg rank {avg_rank[winner]:.2f})."
        )

    return insights


# ── Public API used by the server ─────────────────────────────────────────────

def start_benchmark(config: dict[str, Any]) -> str:
    run_id = str(uuid.uuid4())
    run = _BenchmarkRun(run_id, config)
    with _RUNS_LOCK:
        _RUNS[run_id] = run
    t = threading.Thread(target=_run_benchmark, args=(run,), daemon=True)
    run._thread = t
    t.start()
    return run_id


def get_run(run_id: str) -> _BenchmarkRun | None:
    with _RUNS_LOCK:
        return _RUNS.get(run_id)


def cancel_run(run_id: str) -> bool:
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
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
        "results": run.results,
        "errors": run.errors,
    }


def stream_events(run_id: str, timeout: float = 60.0) -> list[dict[str, Any]]:
    """Drain up to 50 pending events. Used for polling (non-SSE mode)."""
    run = get_run(run_id)
    if not run:
        return []
    events = []
    deadline = time.time() + timeout
    while time.time() < deadline and len(events) < 50:
        try:
            evt = run.events.get(timeout=0.1)
            events.append(evt)
            if evt.get("type") in ("run_done", "run_error"):
                break
        except queue.Empty:
            if run.status in ("done", "cancelled", "error"):
                break
    return events
