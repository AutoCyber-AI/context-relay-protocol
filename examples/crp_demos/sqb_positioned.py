# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""SQB on the CRP v5 positioned loop (SPEC-026 metrics on the real agentic path).

The legacy SQB harness (``sqb_benchmark.py --mode full``) drives a *naive* continuation
loop. This benchmark runs the SQB test cases through the **real positioned loop**
(``run_positioned`` with output continuation) and computes the SQB metrics — factual
recall / F1, 4-gram repetition, and required-topic coverage — on the assembled output.

It closes two gaps:
  1. "Have we run SQB on the positioned loop?" — yes, here.
  2. "Does the continuation anti-repetition fix work?" — measured by ``repetition_rate``.

Runs on the local SLM and Kimi. Kimi judges usefulness (Gate 5) too.

Run:
    python examples/crp_demos/sqb_positioned.py                 # local + kimi
    python examples/crp_demos/sqb_positioned.py --only local

Kimi key: MOONSHOT_API_KEY env or kimi_moonshot_api_key.txt (never printed).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from crp.stl import run_positioned
from crp.tools import CapabilityProfile

from examples.crp_demos.sqb_benchmark import (  # noqa: E402
    factual_f1,
    factual_precision,
    factual_recall,
    get_all_test_cases,
    llm_judge,
    repetition_rate,
    required_topic_coverage,
)

LOCAL_BASE = os.environ.get("CRP_LLM_BASE", "http://192.168.0.6:1234/v1")
LOCAL_MODEL = os.environ.get("CRP_LLM_MODEL", "meta-llama-3.1-8b-instruct")
KIMI_BASE = "https://api.moonshot.ai/v1"
KIMI_MODEL = "kimi-k2.6"


def make_model_call(base: str, model: str, api_key: str | None, temperature: float, extra: dict | None = None) -> Any:
    client = httpx.Client(timeout=300.0)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def model_call(prompt: str, schema: dict[str, Any] | None) -> str:
        body: dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": prompt}],
                                "temperature": temperature, "max_tokens": 600}
        if extra:
            body.update(extra)
        try:
            r = client.post(f"{base}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
        except httpx.HTTPStatusError:
            r = client.post(f"{base}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""

    return model_call


def run_backend(name: str, mc: Any, judge_key: str | None, judge_fields: dict | None,
                max_windows: int = 10) -> dict[str, Any]:
    print(f"\n=== {name} (max_continuation_windows={max_windows}) ===")
    rows = []
    for tc in get_all_test_cases():
        # Ground the loop with the case corpus so factual metrics are meaningful.
        r = run_positioned(tc.task, mc, profile=CapabilityProfile.CAPABLE_LOCAL,
                           context_facts=tc.source_corpus, max_continuation_windows=max_windows)
        out = r.text or ""
        recall = factual_recall(out, tc.reference_facts)
        prec = factual_precision(out, tc.source_corpus)
        f1 = factual_f1(recall, prec)
        rep = repetition_rate(out)
        cov = required_topic_coverage(out, tc.required_topics)
        judge = 0.0
        if judge_key:
            j = llm_judge(tc, out, api_url=KIMI_BASE, api_key=judge_key, model=KIMI_MODEL,
                          temperature=0.6, extra_request_fields=judge_fields)
            judge = j.get("mean_score", 0.0)
        rows.append({"case": tc.case_id, "domain": tc.domain, "words": len(out.split()),
                     "windows": r.continuation_windows, "recall": round(recall, 3),
                     "f1": round(f1, 3), "repetition": round(rep, 4), "coverage": round(cov, 3),
                     "judge": judge})
        print(f"  {tc.case_id} ({tc.domain}): words={len(out.split())} win={r.continuation_windows} "
              f"recall={recall:.2f} F1={f1:.3f} rep={rep:.2%} cov={cov:.2f} judge={judge}/10")
    mean_f1 = round(sum(x["f1"] for x in rows) / len(rows), 3)
    mean_rep = round(sum(x["repetition"] for x in rows) / len(rows), 4)
    mean_judge = round(sum(x["judge"] for x in rows) / max(1, sum(1 for x in rows if x["judge"])), 2) \
        if any(x["judge"] for x in rows) else 0.0
    print(f"  → mean F1 {mean_f1} | mean repetition {mean_rep:.2%} | mean judge {mean_judge}/10")
    return {"backend": name, "mean_f1": mean_f1, "mean_repetition": mean_rep,
            "mean_judge": mean_judge, "rows": rows}


def _load_kimi_key() -> str:
    key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if key:
        return key
    f = Path(__file__).resolve().parents[2] / "kimi_moonshot_api_key.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["local", "kimi"], default=None)
    ap.add_argument("--save", default="sqb_results/sqb_positioned.json")
    ap.add_argument("--windows", type=int, default=10,
                    help="max_continuation_windows per case (default 10; use 6 for a shorter run)")
    args = ap.parse_args()

    key = _load_kimi_key()
    results = []
    if args.only in (None, "local"):
        try:
            httpx.Client(timeout=8.0).get(f"{LOCAL_BASE}/models").raise_for_status()
            results.append(run_backend(f"LOCAL·{LOCAL_MODEL}",
                           make_model_call(LOCAL_BASE, LOCAL_MODEL, None, 0.3),
                           key or None, None, max_windows=args.windows))
        except Exception as exc:  # noqa: BLE001
            print(f"  local skipped: {exc}")
    if args.only in (None, "kimi"):
        if key:
            results.append(run_backend(f"KIMI·{KIMI_MODEL}",
                           make_model_call(KIMI_BASE, KIMI_MODEL, key, 0.6, {"thinking": {"type": "disabled"}}),
                           key, {"thinking": {"type": "disabled"}}, max_windows=args.windows))
        else:
            print("  kimi skipped: no key")

    if results:
        out = Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"backends": results}, indent=2), encoding="utf-8")
        print("\n=== SQB-ON-POSITIONED SUMMARY ===")
        for r in results:
            print(f"  {r['backend']}: F1 {r['mean_f1']} | repetition {r['mean_repetition']:.2%} | judge {r['mean_judge']}/10")
        print(f"  saved → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
