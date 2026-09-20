#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Live proof that CRP makes small local models useful.

Tests three small/capable local models against the same simple tool task.
Without CRP the model would emit JSON tool-call syntax and do nothing.
With CRP the tool actually executes and returns a real observation.

Environment:
    CRP_LMSTUDIO_URL=http://localhost:1234/v1
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "templates"))

from _shared import resolve_provider

import crp


def get_current_time(location: str = "UTC") -> dict[str, Any]:
    """Return the current UTC time."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return {"location": location, "utc_time": now.isoformat()}


def calculate(a: float, b: float, operation: str = "add") -> dict[str, Any]:
    """Perform a basic calculation. Use add/subtract/multiply/divide or + - * /."""
    op = operation.lower().strip()
    if op in ("add", "+"):
        return {"result": a + b}
    if op in ("subtract", "-"):
        return {"result": a - b}
    if op in ("multiply", "*", "x"):
        return {"result": a * b}
    if op in ("divide", "/"):
        return {"result": a / b if b != 0 else "undefined"}
    return {"result": "unknown operation"}


MODELS = [
    ("meta-llama-3.1-8b-instruct", "capable-local"),
    ("qwen2.5-7b-instruct", "capable-local"),
    ("qwen3-4b", "small-local"),
    ("gemma-3-270m-it-qat", "small-local"),
]

QUESTIONS = [
    "What is the current UTC time?",
    "What is 7 times 8?",
    "What time is it in UTC and what is 10 plus 5?",
]


def run_model(model: str, profile: str, question: str) -> dict[str, Any]:
    """Run a single question through CRP with the given model."""
    from crp.providers.openai import OpenAIAdapter

    provider = OpenAIAdapter(
        model=model,
        base_url=os.environ.get("CRP_LMSTUDIO_URL", "http://localhost:1234/v1"),
        api_key="lm-studio",
    )
    agent = crp.Agent(
        provider=provider,
        tools=[get_current_time, calculate],
        system="You have a clock and a calculator. Use them when needed. Answer concisely.",
        profile=profile,
        max_tokens=256,
    )
    started = time.time()
    try:
        result = agent.run(question)
        elapsed = time.time() - started
        return {
            "model": model,
            "profile": profile,
            "question": question,
            "success": not result.halted and result.observation_count > 0,
            "halted": result.halted,
            "answer": result.answer,
            "operations": result.how_it_was_built,
            "observation_count": result.observation_count,
            "risk": result.crp.risk,
            "elapsed_seconds": round(elapsed, 2),
        }
    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - started
        return {
            "model": model,
            "profile": profile,
            "question": question,
            "success": False,
            "error": str(exc),
            "elapsed_seconds": round(elapsed, 2),
        }


def main() -> int:
    results: list[dict[str, Any]] = []
    print("=" * 70)
    print("SMALL MODEL LIVE PROOF — CRP makes local SLMs useful")
    print("=" * 70)
    for model, profile in MODELS:
        print(f"\nModel: {model} (profile={profile})")
        for question in QUESTIONS:
            record = run_model(model, profile, question)
            results.append(record)
            status = "PASS" if record.get("success") else "FAIL"
            print(f"  [{status}] {question[:50]!r}...")
            print(f"        -> {record.get('answer', record.get('error', ''))[:120]}...")

    out_path = Path(__file__).parent / "_small_model_live_results.json"
    out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
