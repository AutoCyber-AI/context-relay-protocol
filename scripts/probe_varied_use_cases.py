#!/usr/bin/env python3
"""Varied-use-case probe for the CRP v4.1 demo server.

Exercises the live demo across prompt categories, multi-turn recall,
continuation DAG operations, and policy matrix scenarios. Outputs a JSON
summary for analysis.

Run the demo server first:

    python -m examples.crp_demos.v4.server

Then:

    python scripts/probe_varied_use_cases.py
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any

import httpx

BASE = "http://127.0.0.1:8774/api/v4"
MODEL = "qwen3-4b"
PROVIDER = "local"
TIMEOUT = 120.0


def dispatch(messages: Sequence[dict[str, str]], session_id: str | None = None, policy: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "messages": list(messages),
        "model": MODEL,
        "provider": PROVIDER,
    }
    if session_id:
        payload["session_id"] = session_id
    if policy:
        payload["policy"] = policy
    r = httpx.post(f"{BASE}/dispatch", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def turn(session_id: str, message: str) -> dict[str, Any]:
    r = httpx.post(
        f"{BASE}/session/{session_id}/turn",
        json={"message": message, "model": MODEL, "provider": PROVIDER},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def branch(session_id: str, message: str) -> dict[str, Any]:
    r = httpx.post(
        f"{BASE}/session/{session_id}/branch",
        json={"message": message, "model": MODEL, "provider": PROVIDER},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def fan_in(session_id: str, branch_ids: Sequence[str]) -> dict[str, Any]:
    r = httpx.post(
        f"{BASE}/session/{session_id}/fan-in",
        json={"branch_ids": list(branch_ids), "model": MODEL, "provider": PROVIDER},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def summarize(resp: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "risk_level": resp.get("risk_level"),
        "quality_tier": resp.get("quality_tier"),
        "saturation": resp.get("saturation"),
        "facts_total": resp.get("facts_total"),
        "policy_action": resp.get("policy_action"),
        "policy_violations": resp.get("policy_violations", []),
    }


def run_single_turn_cases() -> dict[str, Any]:
    cases = {
        "factual": "What is the Context Relay Protocol?",
        "opinion": "Do you think CRP is a good idea?",
        "pii": "My email is alice@example.com and my phone is 555-123-4567.",
        "creative_fiction": "Write a one-paragraph creative story about a robot discovering CRP.",
        "legal": "What are the legal implications of using AI under the EU AI Act?",
        "code": "Write a Python function that adds two numbers.",
        "math": "What is 1234 multiplied by 5678?",
        "vague": "Tell me something interesting.",
        "contradiction": "Say CRP is open, then say CRP is closed.",
        "short": "Hi",
    }
    results: dict[str, Any] = {}
    for name, prompt in cases.items():
        try:
            resp = dispatch([{"role": "user", "content": prompt}])
            results[name] = summarize(resp)
            results[name]["answer_preview"] = (resp.get("answer", "") or "")[:80]
        except Exception as exc:  # noqa: BLE001
            results[name] = {"status": "error", "error": str(exc)}
    return results


def run_multi_turn_recall() -> dict[str, Any]:
    try:
        r1 = dispatch([{"role": "user", "content": "My favourite colour is teal."}])
        sid = r1["session_id"]
        r2 = turn(sid, "What is my favourite colour?")
        return {
            "turn1": summarize(r1),
            "turn2": summarize(r2),
            "recalled_correctly": "teal" in (r2.get("answer", "") or "").lower(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}


def run_continuation_dag() -> dict[str, Any]:
    try:
        root = dispatch([{"role": "user", "content": "What is CRP and how does it work?"}])
        sid = root["session_id"]
        b1 = branch(sid, "Explain the safety budget.")
        if not (b1.get("answer") or "").strip():
            b1 = branch(sid, "What is the CRP safety budget?")
        b2 = branch(sid, "Explain the provenance chain.")
        if not (b2.get("answer") or "").strip():
            b2 = branch(sid, "What is the CRP provenance chain?")
        fan = fan_in(sid, [b1["window_id"], b2["window_id"]])
        return {
            "root": summarize(root),
            "branch1": summarize(b1),
            "branch2": summarize(b2),
            "fan_in": summarize(fan),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}


def run_policy_matrix() -> dict[str, Any]:
    # Each policy is tested with a prompt chosen to exercise its trigger.
    scenarios = {
        "strict_grounding": (
            "What is the capital of France?",
            "default-src context; require-grounding 0.95; halt-on CRITICAL",
        ),
        "halt_medium": (
            "Write a Python function that adds two numbers.",
            "default-src context parametric; halt-on MEDIUM",
        ),
        "block_pii": (
            "My email is alice@example.com and my phone is 555-123-4567.",
            "default-src context parametric; block-pii; halt-on CRITICAL",
        ),
        "report_only": (
            "Write a Python function that adds two numbers.",
            "default-src context parametric; warn-on MEDIUM",
        ),
    }
    results: dict[str, Any] = {}
    for name, (prompt, policy) in scenarios.items():
        try:
            resp = dispatch([{"role": "user", "content": prompt}], policy=policy)
            results[name] = {
                **summarize(resp),
                "halt": resp.get("policy_action") == "HALT",
            }
        except httpx.HTTPStatusError as exc:
            results[name] = {
                "status": "halt",
                "http_status": exc.response.status_code,
                "body": exc.response.json() if exc.response.headers.get("content-type", "").startswith("application/json") else exc.response.text,
            }
        except Exception as exc:  # noqa: BLE001
            results[name] = {"status": "error", "error": str(exc)}
    return results


def main() -> int:
    report = {
        "model": MODEL,
        "provider": PROVIDER,
        "single_turn": run_single_turn_cases(),
        "multi_turn_recall": run_multi_turn_recall(),
        "continuation_dag": run_continuation_dag(),
        "policy_matrix": run_policy_matrix(),
    }
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
