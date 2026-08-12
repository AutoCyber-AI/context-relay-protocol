# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Live validation of the CRP v5 positioned-tool-loop on a local SLM (LM Studio).

Demonstrates the depth of the protocol on a real <15B model:
  - the request is decomposed into operations (STL),
  - the model is positioned on ONE operation at a time with only the 1-3 tools the
    TCF selected (never the full catalogue),
  - the tool runs, its result becomes a typed CSO observation (not raw prompt text),
  - the next operation is positioned with the CSO state carried forward,
  - the Operation State Machine emits a live event stream ("not a blind machine"),
  - the final response is assembled coherently.

Run:
    .venv\\Scripts\\python.exe examples/crp_demos/positioned_8b_validation.py

Requires an OpenAI-compatible endpoint (LM Studio) with a chat model loaded.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx

from crp.stl import run_positioned
from crp.tools import CapabilityExecutor, CapabilityProfile, ToolCapabilityFabric

BASE_URL = os.environ.get("CRP_LLM_BASE", "http://192.168.0.6:1234/v1")
MODEL = os.environ.get("CRP_LLM_MODEL", "meta-llama-3.1-8b-instruct")


# ── model_call: the only LLM dependency of the positioned loop ──────────────


def make_model_call() -> Any:
    client = httpx.Client(timeout=240.0)

    def model_call(prompt: str, schema: dict[str, Any] | None) -> str:
        body: dict[str, Any] = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 512,
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "tool_call", "schema": schema, "strict": False},
            }
        try:
            r = client.post(f"{BASE_URL}/chat/completions", json=body)
            r.raise_for_status()
        except httpx.HTTPStatusError:
            # Endpoint rejected the structured-output request — retry plain.
            body.pop("response_format", None)
            r = client.post(f"{BASE_URL}/chat/completions", json=body)
            r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""

    return model_call


# ── a deterministic local tool (no real network) ────────────────────────────

_PORT_SERVICES = {"22": "SSH", "80": "HTTP", "443": "HTTPS", "3306": "MySQL", "5432": "PostgreSQL"}


def _lookup_port_service(args: dict[str, Any]) -> dict[str, Any]:
    port = str(args.get("port", "")).strip()
    return {"port": port, "service": _PORT_SERVICES.get(port, "unknown")}


def build_fabric() -> tuple[ToolCapabilityFabric, CapabilityExecutor]:
    tcf = ToolCapabilityFabric()
    tcf.register_dict({
        "capability_id": "lookup_port_service",
        "kind": "tool",
        "version": "1.0.0",
        "operation_types": ["RETRIEVE"],
        "serves_intents": ["port_lookup", "service_identification"],
        "input_schema": {
            "type": "object",
            "properties": {"port": {"type": "string"}},
            "required": ["port"],
        },
        "output_schema": {"type": "object"},
        "produces_facts": True,
        "cost_profile": {"tokens": 30, "latency_ms": 5, "safety_class": "read-only"},
        "metadata": {"description": "Map a TCP port number to its well-known service name."},
    })
    ex = CapabilityExecutor()
    ex.register_impl("lookup_port_service", _lookup_port_service)
    return tcf, ex


def main() -> int:
    print(f"→ LLM endpoint: {BASE_URL}  model: {MODEL}\n")
    try:
        httpx.Client(timeout=10.0).get(f"{BASE_URL}/models").raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"!! Cannot reach {BASE_URL}: {exc}")
        return 2

    tcf, ex = build_fabric()
    request = "Look up the service running on port 443, then summarise what it is used for."

    print(f"Request: {request}\n")
    result = run_positioned(
        request,
        make_model_call(),
        fabric=tcf,
        executor=ex,
        profile=CapabilityProfile.CAPABLE_LOCAL,
    )

    print("── Operations (positioned, one at a time) ──")
    print("  " + " → ".join(result.operations))
    print("\n── Operation State Machine event stream ──")
    for e in result.event_stream:
        op = e["operation"] or "-"
        print(f"  [{e['state']:<20}] op={op:<11} {e['detail']}")
    print("\n── CSO tool observations (typed, decoupled from the window) ──")
    for obs in result.cso.tool_observations:
        print(f"  • {obs['capability_id']}: {json.dumps(obs['payload'], default=str)}")
    print("\n── Bounded-window metrics ──")
    print(f"  frame tokens total : {result.frame_tokens_total}")
    print(f"  observations stored: {result.observation_count}")
    print(f"  completion         : {result.cso.goal_state.completion:.0%}")
    print(f"  halted             : {result.halted}")
    print("\n── Final assembled response ──")
    print(result.text)
    print("\n── Headers (visibility) ──")
    for k, v in result.headers.items():
        print(f"  {k}: {v}")

    ok = result.observation_count >= 1 and not result.halted and bool(result.text)
    print("\n" + ("✅ POSITIONED LOOP VALIDATED ON LOCAL SLM" if ok else "⚠️ check output above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
