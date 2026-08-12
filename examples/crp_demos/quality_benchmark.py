# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v5 — Quality benchmark (LLM-as-judge) for the positioned loop.

The e2e tests measure *correctness* (right answer) and *bounded windows*. This
benchmark measures *response quality*: it runs the real positioned loop on a set of
tasks (single-op, multi-op, multi-turn, and long continuation) on the local SLM and
Kimi, then scores each assembled output with a frontier judge (Kimi) on a rubric
(usefulness, coherence, completeness, grounding) 1–10.

This is the SQB Gate-5 (usefulness) dimension applied to the v5 positioned loop.

Run:
    python examples/crp_demos/quality_benchmark.py                 # local + kimi
    python examples/crp_demos/quality_benchmark.py --only local

Kimi key: MOONSHOT_API_KEY env or kimi_moonshot_api_key.txt (never printed).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from crp.stl import run_positioned
from crp.tools import CapabilityExecutor, CapabilityProfile, ToolCapabilityFabric

LOCAL_BASE = os.environ.get("CRP_LLM_BASE", "http://192.168.0.6:1234/v1")
LOCAL_MODEL = os.environ.get("CRP_LLM_MODEL", "meta-llama-3.1-8b-instruct")
KIMI_BASE = "https://api.moonshot.ai/v1"
KIMI_MODEL = "kimi-k2.6"

_PORTS = {"22": "SSH", "80": "HTTP", "443": "HTTPS", "3306": "MySQL"}


def _port(args: dict[str, Any]) -> dict[str, Any]:
    return {"port": str(args.get("port", "")), "service": _PORTS.get(str(args.get("port", "")), "unknown")}


def build_fabric() -> tuple[ToolCapabilityFabric, CapabilityExecutor]:
    tcf = ToolCapabilityFabric()
    ex = CapabilityExecutor()
    tcf.register_dict({
        "capability_id": "lookup_port_service", "kind": "tool", "version": "1.0.0",
        "operation_types": ["RETRIEVE"], "serves_intents": ["port_lookup"],
        "input_schema": {"type": "object", "properties": {"port": {"type": "string"}}, "required": ["port"]},
        "output_schema": {"type": "object"}, "produces_facts": True,
        "cost_profile": {"tokens": 30, "latency_ms": 5, "safety_class": "read-only"},
        "metadata": {"description": "Map a TCP port to its service name."},
    })
    ex.register_impl("lookup_port_service", _port)
    return tcf, ex


def make_model_call(base: str, model: str, api_key: str | None, temperature: float, extra: dict | None = None) -> Any:
    client = httpx.Client(timeout=300.0)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def model_call(prompt: str, schema: dict[str, Any] | None) -> str:
        body: dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": prompt}],
                                "temperature": temperature, "max_tokens": 512}
        if extra:
            body.update(extra)
        if schema is not None:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "tool_call", "schema": schema, "strict": False}}
        try:
            r = client.post(f"{base}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
        except httpx.HTTPStatusError:
            body.pop("response_format", None)
            r = client.post(f"{base}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""

    return model_call


_JUDGE_RUBRIC = [
    "Usefulness: does it actually answer the request?",
    "Coherence: is it well-structured and readable?",
    "Completeness: does it cover the requested scope?",
    "Grounding: are claims consistent with the tool facts / not fabricated?",
]


def kimi_judge(task: str, output: str, api_key: str) -> dict[str, Any]:
    crit = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(_JUDGE_RUBRIC))
    prompt = (
        f"You are a precise evaluator. Rate the RESPONSE to the TASK on each criterion "
        f"1 (poor) to 10 (excellent).\n\nTASK:\n{task}\n\nCRITERIA:\n{crit}\n\n"
        f"RESPONSE (first 3500 chars):\n{output[:3500]}\n\n"
        f'Reply ONLY JSON: {{"scores":[{{"criterion":"...","score":8}}],"notes":"..."}}'
    )
    for attempt in range(4):
        try:
            r = httpx.post(f"{KIMI_BASE}/chat/completions",
                           headers={"Authorization": f"Bearer {api_key}"},
                           json={"model": KIMI_MODEL, "messages": [{"role": "user", "content": prompt}],
                                 "temperature": 0.6, "max_tokens": 500,
                                 "response_format": {"type": "json_object"},
                                 "thinking": {"type": "disabled"}}, timeout=90)
            r.raise_for_status()
            parsed = json.loads(r.json()["choices"][0]["message"]["content"])
            scores = [float(s["score"]) for s in parsed.get("scores", []) if isinstance(s.get("score"), (int, float))]
            mean = round(sum(scores) / len(scores), 2) if scores else 0.0
            return {"mean": mean, "notes": str(parsed.get("notes", ""))[:120]}
        except Exception:
            time.sleep(20 if attempt else 3)
    return {"mean": 0.0, "notes": "judge failed"}


# task builders: (label, callable(mc) -> (task_text, output_text))
def task_single(mc: Any) -> tuple[str, str]:
    t = "Look up the service running on port 443, then summarise what it is used for."
    tcf, ex = build_fabric()
    return t, run_positioned(t, mc, fabric=tcf, executor=ex, profile=CapabilityProfile.CAPABLE_LOCAL).text


def task_multitool(mc: Any) -> tuple[str, str]:
    t = ("Look up the service on port 3306, then analyse the security posture of exposing "
         "it to the internet and give two mitigations.")
    tcf, ex = build_fabric()
    return t, run_positioned(t, mc, fabric=tcf, executor=ex, profile=CapabilityProfile.CAPABLE_LOCAL).text


def task_multiturn(mc: Any) -> tuple[str, str]:
    tcf, ex = build_fabric()
    r1 = run_positioned("Look up the service on port 443.", mc, fabric=tcf, executor=ex,
                        profile=CapabilityProfile.CAPABLE_LOCAL)
    t2 = "Based on what we found, write a short paragraph advising whether it is safe for login pages."
    tcf2, ex2 = build_fabric()
    out = run_positioned(t2, mc, fabric=tcf2, executor=ex2, profile=CapabilityProfile.CAPABLE_LOCAL,
                         prior_cso=r1.cso).text
    return f"(turn 1: port 443 lookup)\n{t2}", out


def task_long(mc: Any) -> tuple[str, str]:
    t = ("Write a comprehensive multi-section guide to Kubernetes networking: flat model, "
         "kube-proxy, Services, Network Policies, CNI, DNS, Ingress, service mesh, troubleshooting. "
         "Finish with a conclusion.")
    r = run_positioned(t, mc, profile=CapabilityProfile.CAPABLE_LOCAL, max_continuation_windows=10)
    return t, r.text


TASKS = [("single-op", task_single), ("multi-op", task_multitool),
         ("multi-turn", task_multiturn), ("long-continuation", task_long)]


def run_backend(name: str, mc: Any, judge_key: str) -> dict[str, Any]:
    print(f"\n=== {name} ===")
    rows = []
    for label, fn in TASKS:
        t0 = time.time()
        task, output = fn(mc)
        j = kimi_judge(task, output, judge_key)
        rows.append({"task": label, "quality": j["mean"], "words": len(output.split()), "notes": j["notes"]})
        print(f"  {label:<18} quality={j['mean']}/10  words={len(output.split())}  ({time.time()-t0:.0f}s)  {j['notes']}")
    scores = [r["quality"] for r in rows if r["quality"] > 0]
    mean = round(sum(scores) / len(scores), 2) if scores else 0.0
    print(f"  → mean quality {mean}/10")
    return {"backend": name, "mean_quality": mean, "rows": rows}


def _load_kimi_key() -> str:
    key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if key:
        return key
    f = Path(__file__).resolve().parents[2] / "kimi_moonshot_api_key.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["local", "kimi"], default=None)
    ap.add_argument("--save", default="sqb_results/quality_benchmark.json")
    args = ap.parse_args()

    key = _load_kimi_key()
    if not key:
        print("Kimi judge key required (MOONSHOT_API_KEY or kimi_moonshot_api_key.txt)")
        return 1

    results = []
    if args.only in (None, "local"):
        try:
            httpx.Client(timeout=8.0).get(f"{LOCAL_BASE}/models").raise_for_status()
            results.append(run_backend(f"LOCAL·{LOCAL_MODEL}", make_model_call(LOCAL_BASE, LOCAL_MODEL, None, 0.2), key))
        except Exception as exc:  # noqa: BLE001
            print(f"  local skipped: {exc}")
    if args.only in (None, "kimi"):
        results.append(run_backend(f"KIMI·{KIMI_MODEL}",
                       make_model_call(KIMI_BASE, KIMI_MODEL, key, 0.6, {"thinking": {"type": "disabled"}}), key))

    if results:
        out = Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"backends": results}, indent=2), encoding="utf-8")
        print("\n=== QUALITY SUMMARY (Kimi-judged, 1–10) ===")
        for r in results:
            print(f"  {r['backend']}: mean {r['mean_quality']}/10")
        print(f"  saved → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
