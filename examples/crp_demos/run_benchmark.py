"""Benchmark runner — tests all 4 context management strategies against a
local LLM and produces a comparison report.

Run:
    python examples/crp_demos/run_benchmark.py
    python examples/crp_demos/run_benchmark.py --sections 3 --words 1500

Results saved to: examples/crp_demos/_benchmark_results/
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
os.chdir(Path(__file__).parent.parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def detect_context(endpoint: str, model: str) -> int:
    import urllib.request, json as _json
    root = endpoint.rstrip("/v1").rstrip("/")
    try:
        with urllib.request.urlopen(f"{root}/api/v0/models", timeout=5) as r:
            d = _json.loads(r.read())
        for m in d.get("data", []):
            if m.get("id") == model and m.get("loaded_context_length"):
                return int(m["loaded_context_length"])
    except Exception:
        pass
    return 4096


def main() -> None:
    parser = argparse.ArgumentParser(description="CRP benchmark runner")
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234")
    parser.add_argument("--model", default="meta-llama-3.1-8b-instruct")
    parser.add_argument("--sections", type=int, default=5,
                        help="Number of sections (1-10, default 5)")
    parser.add_argument("--words", type=int, default=2500)
    parser.add_argument("--tokens-per-window", type=int, default=700)
    parser.add_argument("--strategies", default="crp,rag,injection,hierarchical")
    args = parser.parse_args()

    context_size = detect_context(args.endpoint, args.model)
    print(f"\n{'='*60}")
    print(f"  CRP Context Management Benchmark")
    print(f"{'='*60}")
    print(f"  endpoint   : {args.endpoint}")
    print(f"  model      : {args.model}")
    print(f"  context    : {context_size} tokens (loaded)")
    print(f"  sections   : {args.sections}")
    print(f"  target     : {args.words} words total")
    print(f"  strategies : {args.strategies}")
    print(f"{'='*60}\n")

    from examples.crp_demos.strategies.base import BENCHMARK_SECTIONS
    sections = BENCHMARK_SECTIONS[:args.sections]
    strategy_names = [s.strip() for s in args.strategies.split(",")]

    from examples.crp_demos.strategies.crp_strategy import CRPStrategy
    from examples.crp_demos.strategies.rag_strategy import RAGStrategy
    from examples.crp_demos.strategies.injection_strategy import InjectionStrategy
    from examples.crp_demos.strategies.hierarchical_strategy import HierarchicalSummarizationStrategy

    strategy_map = {
        "crp":          CRPStrategy,
        "rag":          RAGStrategy,
        "injection":    InjectionStrategy,
        "hierarchical": HierarchicalSummarizationStrategy,
    }

    kwargs = dict(
        endpoint=args.endpoint,
        model=args.model,
        context_size=context_size,
        max_tokens_per_window=args.tokens_per_window,
        target_words=args.words,
        sections=sections,
    )

    all_results = {}
    output_dir = Path("examples/crp_demos/_benchmark_results")
    output_dir.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    for sname in strategy_names:
        if sname not in strategy_map:
            print(f"[skip] unknown strategy: {sname}")
            continue

        print(f"\n{'\u2500'*60}")
        print(f"  STRATEGY: {sname.upper()}")
        print(f"{'\u2500'*60}")

        strategy = strategy_map[sname](**kwargs)

        def on_chunk(c: str) -> None:
            sys.stdout.write(c)
            sys.stdout.flush()

        def on_window_done(window: int, text: str, metrics: dict) -> None:
            print(f"\n\n  [window {window} done | {metrics.get('running_words',0):,} words | "
                  f"rep={metrics.get('repetition_6gram',0)*100:.2f}% | "
                  f"unique={metrics.get('unique_word_ratio',0)*100:.1f}%]")

        t0 = time.monotonic()
        result = strategy.run(on_chunk=on_chunk, on_window_done=on_window_done)
        elapsed = time.monotonic() - t0

        all_results[sname] = result.to_dict()

        # Save individual strategy output
        doc_path = output_dir / f"{ts}_{sname}_document.md"
        doc_path.write_text(result.full_text, encoding="utf-8")
        print(f"\n\n  \u2713 {sname} complete in {elapsed:.1f}s | "
              f"{result.total_words:,} words | "
              f"rep={result.final_repetition_6gram*100:.2f}% | "
              f"eff={result.context_efficiency*100:.1f}%")
        if result.errors:
            for e in result.errors:
                print(f"  \u26a0 {e}")

    # Save full comparison JSON
    report_path = output_dir / f"{ts}_comparison.json"
    report_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\n\n{'='*60}")
    print(f"  BENCHMARK COMPLETE")
    print(f"{'='*60}")
    print_comparison_table(all_results)
    print(f"\n  Results saved to: {output_dir}")
    print(f"  Full report: {report_path.name}")


def print_comparison_table(results: dict) -> None:
    if not results:
        return

    metrics = [
        ("total_words",              "Total Words",           True,  lambda v: f"{v:,}"),
        ("context_efficiency",       "Context Efficiency",    True,  lambda v: f"{v*100:.1f}%"),
        ("final_repetition_6gram",   "6-gram Repetition",     False, lambda v: f"{v*100:.3f}%"),
        ("final_dup_sentence_ratio", "Dup Sentence Ratio",    False, lambda v: f"{v*100:.2f}%"),
        ("avg_unique_word_ratio",    "Unique Word Ratio",     True,  lambda v: f"{v*100:.1f}%"),
        ("total_prompt_tokens",      "Prompt Tokens",         False, lambda v: f"{v:,}"),
        ("total_output_tokens",      "Output Tokens",         True,  lambda v: f"{v:,}"),
        ("sections_completed",       "Sections Completed",    True,  lambda v: str(v)),
        ("total_latency_s",          "Latency (s)",           False, lambda v: f"{v:.1f}"),
    ]

    strategies = list(results.keys())
    col_w = max(26, max(len(s) for s in strategies) + 2)

    # Header
    header = f"  {'Metric':<30}"
    for s in strategies:
        header += f"  {s:>{col_w}}"
    print(header)
    print("  " + "\u2500" * (30 + len(strategies) * (col_w + 2)))

    for key, label, higher_better, fmt in metrics:
        row = f"  {label:<30}"
        vals = {s: results[s].get(key, 0) for s in strategies}
        best = (max if higher_better else min)(vals.values())
        for s in strategies:
            v = vals[s]
            display = fmt(v)
            marker = " \u2605" if v == best else "  "
            row += f"  {(display+marker):>{col_w}}"
        print(row)

    print()
    print("  \u2605 = best in category")


if __name__ == "__main__":
    main()
