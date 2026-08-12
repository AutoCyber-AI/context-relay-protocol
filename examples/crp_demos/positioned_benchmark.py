# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v5 Positioned-Loop Benchmark — local SLM vs. Kimi (frontier).

Unlike the legacy SQB (a *naive* long-form continuation harness), this benchmark
exercises the real CRP v5 positioned-tool-loop (`run_positioned`, SPEC-049/050):
the model is positioned on one operation at a time with only the 1–3 tools that
operation needs, each tool result becomes a typed CSO observation, and the working
window stays bounded regardless of catalogue size or session length.

It runs the *same* agentic tasks on:
  • a local SLM via LM Studio (default meta-llama-3.1-8b-instruct), and
  • Kimi (Moonshot, kimi-k2.6) — a frontier model,

and reports, per model, the operation plan, the tools the protocol selected, the
bounded frame-token count, observation count, completion, and whether the final
answer is correct (the demo tools are deterministic, so correctness is checkable).

The point it proves: **identical governance + bounded-window contract on a 1-laptop
SLM and a frontier model** — positioning, not injection.

Usage:
    python examples/crp_demos/positioned_benchmark.py                 # local + kimi
    python examples/crp_demos/positioned_benchmark.py --only local
    python examples/crp_demos/positioned_benchmark.py --only kimi

Kimi key: MOONSHOT_API_KEY env var or kimi_moonshot_api_key.txt (never printed).
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
from crp.tools import CapabilityExecutor, CapabilityProfile, ToolCapabilityFabric

LOCAL_BASE = os.environ.get("CRP_LLM_BASE", "http://192.168.0.6:1234/v1")
LOCAL_MODEL = os.environ.get("CRP_LLM_MODEL", "meta-llama-3.1-8b-instruct")
KIMI_BASE = "https://api.moonshot.ai/v1"
KIMI_MODEL = "kimi-k2.6"


# ── deterministic demo tools (same fabric the demo server uses) ─────────────
_PORTS = {"22": "SSH", "80": "HTTP", "443": "HTTPS", "3306": "MySQL", "5432": "PostgreSQL"}
_CVES = {
    "CVE-2021-44228": {"name": "Log4Shell", "severity": "CRITICAL", "cvss": 10.0},
    "CVE-2014-0160": {"name": "Heartbleed", "severity": "HIGH", "cvss": 7.5},
}
_REGS = {
    "encryption": "ISO 27001 A.10 / GDPR Art. 32",
    "logging": "EU AI Act Art. 12",
    "oversight": "EU AI Act Art. 14",
}


def _port(args: dict[str, Any]) -> dict[str, Any]:
    p = str(args.get("port", "")).strip()
    return {"port": p, "service": _PORTS.get(p, "unknown")}


def _cve(args: dict[str, Any]) -> dict[str, Any]:
    c = str(args.get("cve_id", "")).strip().upper()
    return {"cve_id": c, **(_CVES.get(c) or {"severity": "unknown", "cvss": 0.0})}


def _reg(args: dict[str, Any]) -> dict[str, Any]:
    t = str(args.get("topic", "")).strip().lower()
    return {"topic": t, "reference": _REGS.get(t, "no mapped control")}


def build_fabric() -> tuple[ToolCapabilityFabric, CapabilityExecutor]:
    tcf = ToolCapabilityFabric()
    ex = CapabilityExecutor()
    specs = [
        ("lookup_port_service", _port, ["RETRIEVE"], ["port_lookup"], {"port": {"type": "string"}}, ["port"]),
        ("lookup_cve_severity", _cve, ["RETRIEVE", "ANALYSE"], ["cve_lookup"], {"cve_id": {"type": "string"}}, ["cve_id"]),
        ("lookup_regulation", _reg, ["RETRIEVE", "COMPARE"], ["regulation_lookup"], {"topic": {"type": "string"}}, ["topic"]),
    ]
    for cid, impl, ops, intents, props, req in specs:
        tcf.register_dict({
            "capability_id": cid, "kind": "tool", "version": "1.0.0",
            "operation_types": ops, "serves_intents": intents,
            "input_schema": {"type": "object", "properties": props, "required": req},
            "output_schema": {"type": "object"}, "produces_facts": True,
            "cost_profile": {"tokens": 30, "latency_ms": 5, "safety_class": "read-only"},
            "metadata": {"description": cid},
        })
        ex.register_impl(cid, impl)
    return tcf, ex


# ── model_call factories ────────────────────────────────────────────────────
def make_model_call(base: str, model: str, api_key: str | None, extra: dict | None = None,
                    temperature: float = 0.2) -> Any:
    client = httpx.Client(timeout=300.0)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def model_call(prompt: str, schema: dict[str, Any] | None) -> str:
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 512,
        }
        if extra:
            body.update(extra)
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "tool_call", "schema": schema, "strict": False},
            }
        try:
            r = client.post(f"{base}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
        except httpx.HTTPStatusError:
            body.pop("response_format", None)
            r = client.post(f"{base}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""

    return model_call


# ── tasks: (request, profile, substrings the final answer must contain) ─────
TASKS = [
    ("Look up the service running on port 443, then summarise what it is used for.",
     CapabilityProfile.CAPABLE_LOCAL, ["HTTPS"]),
    ("Look up the severity of CVE-2021-44228, then state how urgently it must be triaged.",
     CapabilityProfile.CAPABLE_LOCAL, ["CRITICAL"]),
    ("Find the service on port 3306 and the regulation governing logging, then write a one-line audit note.",
     CapabilityProfile.CAPABLE_LOCAL, ["MySQL"]),
]


def _tools_used(events: list[dict]) -> list[str]:
    out: list[str] = []
    for e in events:
        if e.get("state") == "TOOL_SELECTED":
            d = str(e.get("detail", ""))
            cap = d.split("capability=")[-1].strip() if "capability=" in d else ""
            if cap and cap not in out:
                out.append(cap)
    return out


def run_backend(name: str, model_call: Any) -> dict[str, Any]:
    print(f"\n=== {name} ===")
    rows = []
    for i, (request, profile, must) in enumerate(TASKS, 1):
        tcf, ex = build_fabric()
        result = run_positioned(request, model_call, fabric=tcf, executor=ex, profile=profile)
        text = (result.text or "").upper()
        correct = all(m.upper() in text for m in must)
        used = _tools_used(list(result.event_stream))
        row = {
            "task": i,
            "operations": list(result.operations),
            "tools_used": used,
            "frame_tokens": result.frame_tokens_total,
            "observations": result.observation_count,
            "completion": round(result.cso.goal_state.completion, 2),
            "halted": result.halted,
            "correct": correct,
        }
        rows.append(row)
        print(f"  task {i}: ops={'/'.join(result.operations)} | tools={used} | "
              f"frame={result.frame_tokens_total} tok | obs={result.observation_count} | "
              f"complete={row['completion']:.0%} | correct={'YES' if correct else 'no'}")
    n_correct = sum(1 for r in rows if r["correct"])
    max_frame = max((r["frame_tokens"] for r in rows), default=0)
    print(f"  → {n_correct}/{len(rows)} correct | max frame {max_frame} tokens (bounded)")
    return {"backend": name, "model": None, "rows": rows, "correct": n_correct, "max_frame": max_frame}


def _load_kimi_key() -> str:
    key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if key:
        return key
    f = Path(__file__).resolve().parents[2] / "kimi_moonshot_api_key.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def main() -> int:
    ap = argparse.ArgumentParser(description="CRP v5 positioned-loop benchmark (local vs Kimi)")
    ap.add_argument("--only", choices=["local", "kimi"], default=None)
    ap.add_argument("--save", default="sqb_results/positioned_benchmark.json")
    args = ap.parse_args()

    results = []
    if args.only in (None, "local"):
        try:
            httpx.Client(timeout=8.0).get(f"{LOCAL_BASE}/models").raise_for_status()
            mc = make_model_call(LOCAL_BASE, LOCAL_MODEL, None)
            r = run_backend(f"LOCAL · {LOCAL_MODEL}", mc)
            r["model"] = LOCAL_MODEL
            results.append(r)
        except Exception as exc:  # noqa: BLE001
            print(f"  local backend skipped: {exc}")

    if args.only in (None, "kimi"):
        key = _load_kimi_key()
        if not key:
            print("  kimi backend skipped: no MOONSHOT_API_KEY / kimi_moonshot_api_key.txt")
        else:
            mc = make_model_call(KIMI_BASE, KIMI_MODEL, key, extra={"thinking": {"type": "disabled"}}, temperature=0.6)
            r = run_backend(f"KIMI · {KIMI_MODEL}", mc)
            r["model"] = KIMI_MODEL
            results.append(r)

    if results:
        out = Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"backends": results}, indent=2), encoding="utf-8")
        print(f"\n  Saved → {out}")
        print("\n  SUMMARY (positioning is model-agnostic; window stays bounded):")
        for r in results:
            print(f"    {r['backend']}: {r['correct']}/{len(r['rows'])} correct · "
                  f"max frame {r['max_frame']} tok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
