#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Unified live video demo — raw LLM vs CRPv6 agent.

This is ONE script that produces ONE side-by-side artifact you can show in a
video, a pitch, or a console. It uses a REAL loaded model in LM Studio and
REAL tool calls so the outputs are not hardcoded.

Run:
    python examples/crp_demos/unified_video_demo.py "What is the weather in Sydney and what is 12 times 7?"

Environment:
    CRP_LMSTUDIO_URL=http://localhost:1234/v1
    CRP_LMSTUDIO_MODEL=meta-llama-3.1-8b-instruct

Output:
    examples/crp_demos/_unified_demo.json   — structured proof artifact
    examples/crp_demos/_unified_demo.md    — human-readable side-by-side
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Make repo imports work when running from examples/crp_demos
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
# Make the shared _shared module from examples/templates available.
sys.path.insert(0, str(Path(__file__).parent.parent / "templates"))

import requests
from _shared import resolve_provider

import crp
from crp.cognition.loader import resolve_preset_id
from crp.tel import Event
from crp.tel import events as tel_events
from crp.tel.adapter import map_agent_event
from crp.tel.narrative import NarrativeBuilder

_UA = "Mozilla/5.0 (compatible; CRP-video-demo/1.0; +https://crprotocol.io)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Real tools the CRP agent can call ────────────────────────────────────────


def get_current_time(location: str = "UTC") -> dict:
    """Return the current UTC time."""
    now = datetime.now(timezone.utc)
    return {
        "location": location,
        "utc_time": now.isoformat(),
        "hour": now.hour,
        "minute": now.minute,
    }


def get_weather(city: str) -> dict:
    """Fetch live weather for a city from Open-Meteo (free, no API key)."""
    try:
        # 1. Geocode the city name.
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": "1"},
            timeout=10,
        )
        geo.raise_for_status()
        results = geo.json().get("results") or []
        if not results:
            return {"city": city, "error": "city not found"}
        lat = results[0]["latitude"]
        lon = results[0]["longitude"]

        # 2. Fetch current weather.
        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": str(lat),
                "longitude": str(lon),
                "current_weather": "true",
            },
            timeout=10,
        )
        weather.raise_for_status()
        current = weather.json().get("current_weather", {})
        return {
            "city": city,
            "temperature_c": current.get("temperature"),
            "windspeed_kmh": current.get("windspeed"),
            "weather_code": current.get("weathercode"),
        }
    except requests.RequestException as exc:
        return {"city": city, "error": str(exc)}


def calculate(a: float, b: float, operation: str = "add") -> dict:
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


# ── Raw LLM arm ────────────────────────────────────────────────────────────


def run_raw_llm(question: str, base_url: str, model: str) -> dict[str, object]:
    """Call the same model directly, with no tools and no CRP governance."""
    started = time.time()
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Answer concisely."},
            {"role": "user", "content": question},
        ],
        "temperature": 0.2,
        "max_tokens": 512,
    }
    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        finish_reason = data["choices"][0].get("finish_reason", "unknown")
    except Exception as exc:  # noqa: BLE001
        text = f"[RAW LLM ERROR: {exc}]"
        finish_reason = "error"
    return {
        "mode": "RAW LLM",
        "model": model,
        "endpoint": base_url,
        "question": question,
        "response": text,
        "finish_reason": finish_reason,
        "elapsed_s": round(time.time() - started, 2),
    }


# ── CRP agent arm ──────────────────────────────────────────────────────────


def _provider_base_url(provider: object) -> str:
    """Extract the base URL from a CRP provider for the raw-LLM arm."""
    client = getattr(provider, "_client", None)
    if client is None:
        return ""
    return str(getattr(client, "base_url", ""))


def run_crp_agent(
    question: str,
    model: str,
    preset: dict | None = None,
) -> dict[str, object]:
    """Run the question through a governed CRP agent and capture everything."""
    started = time.time()

    # Use the same provider auto-detection as the CRP templates.
    provider = resolve_provider(default_model=model)

    system = (
        "You have access to a calculator, current time, and weather tools. "
        "Use them when needed and answer concisely."
    )
    if preset is not None:
        # Let the preset drive the reasoning; still mention tools are available.
        system = (
            "You have access to a calculator, current time, and weather tools. "
            "Use them when needed and answer concisely."
        )

    kwargs: dict = {
        "provider": provider,
        "tools": [get_current_time, get_weather, calculate],
        "system": system,
        "profile": "capable-local",
        "depth": "standard",
    }
    if preset is not None:
        kwargs["preset"] = preset

    agent = crp.Agent(**kwargs)

    # Run synchronously while capturing every internal event for the narrative.
    events: list[Event] = []

    def _capture(event: object) -> None:
        from crp.agent_sdk.events import AgentEvent
        if isinstance(event, AgentEvent):
            for tel_event in map_agent_event(event):
                events.append(tel_event)

    result = agent.run(question, event_callback=_capture)

    # Add the final answer as a synthetic text event because the internal
    # stream does not currently emit the final answer text as TEXT_MESSAGE_CONTENT.
    if result.answer:
        events.append(tel_events.text_start(messageId="final"))
        events.append(tel_events.text_delta(messageId="final", delta=result.answer))
        events.append(tel_events.text_end(messageId="final"))

    # Build narrative from captured events.
    builder = NarrativeBuilder()
    for ev_obj in events:
        builder.ingest(ev_obj)

    preset_id = None
    if isinstance(preset, dict):
        preset_id = preset.get("id")
    elif preset is not None:
        preset_id = getattr(preset, "id", None)

    return {
        "mode": "CRPv6 AGENT",
        "model": model,
        "endpoint": _provider_base_url(provider),
        "question": question,
        "response": result.answer,
        "operations": result.how_it_was_built,
        "preset": preset_id,
        "governance": {
            "risk": result.crp.risk,
            "grounded": result.crp.grounded,
            "chain_valid": result.crp.chain_valid,
            "tier": getattr(result.crp, "tier", ""),
            "sources": len(result.sources),
        },
        "elapsed_s": round(time.time() - started, 2),
        "narrative_md": builder.to_markdown(),
        "provenance_chain": [p.to_dict() for p in builder.provenance_chain],
        "events": [e.to_dict() for e in events],
    }


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> int:
    question = " ".join(sys.argv[1:]) or "What is the weather in Sydney?"
    model = os.environ.get("CRP_LMSTUDIO_MODEL", "meta-llama-3.1-8b-instruct")

    out_dir = Path(__file__).parent
    json_path = out_dir / "_unified_demo.json"
    md_path = out_dir / "_unified_demo.md"

    # Discover the provider once; use the same endpoint for both arms.
    provider = resolve_provider(default_model=model)
    base_url = _provider_base_url(provider)

    print("=" * 70)
    print("UNIFIED VIDEO DEMO — Raw LLM vs CRPv6 Agent")
    print(f"Model: {model}")
    print(f"Endpoint: {base_url or '(provider default)'}")
    print(f"Question: {question!r}")
    print("=" * 70)

    print("\n[1/3] Running RAW LLM...")
    raw = run_raw_llm(question, base_url, model)
    print(f"      -> {raw['response'][:120]}{'...' if len(raw['response']) > 120 else ''}")

    print("\n[2/3] Running CRP AGENT (no preset)...")
    crp_no_preset = run_crp_agent(question, model)
    print(f"      -> {crp_no_preset['response'][:120]}{'...' if len(crp_no_preset['response']) > 120 else ''}")
    print(f"      -> ops: {crp_no_preset['operations']} | risk: {crp_no_preset['governance']['risk']}")

    print("\n[3/3] Running CRP AGENT with research_assistant preset...")
    preset = resolve_preset_id("research_assistant").to_dict()
    crp_with_preset = run_crp_agent(question, model, preset=preset)
    print(f"      -> {crp_with_preset['response'][:120]}{'...' if len(crp_with_preset['response']) > 120 else ''}")
    print(f"      -> ops: {crp_with_preset['operations']} | risk: {crp_with_preset['governance']['risk']}")

    artifact = {
        "generated_at": _now(),
        "question": question,
        "model": model,
        "endpoint": base_url,
        "raw_llm": raw,
        "crp_agent_no_preset": crp_no_preset,
        "crp_agent_with_preset": crp_with_preset,
    }

    json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote JSON artifact: {json_path}")

    # Build a readable markdown side-by-side.
    md = [
        f"# CRPv6 Live Demo — {question}\n",
        f"**Model:** `{model}`  ",
        f"**Endpoint:** `{base_url}`  ",
        f"**Generated:** {_now()}\n",
        "## Raw LLM (no CRP)\n",
        f"**Response:** {raw['response']}\n",
        f"**Finish reason:** `{raw['finish_reason']}`  ",
        f"**Elapsed:** {raw['elapsed_s']}s  ",
        "**Governance:** none  ",
        "**Sources:** none\n",
        "## CRPv6 Agent (no preset)\n",
        f"**Response:** {crp_no_preset['response']}\n",
        f"**Operations:** `{crp_no_preset['operations']}`  ",
        f"**Risk:** `{crp_no_preset['governance']['risk']}`  ",
        f"**Grounded:** `{crp_no_preset['governance']['grounded']}`  ",
        f"**Chain valid:** `{crp_no_preset['governance']['chain_valid']}`  ",
        f"**Sources:** {crp_no_preset['governance']['sources']}  ",
        f"**Elapsed:** {crp_no_preset['elapsed_s']}s\n",
        "### Narrative\n",
        crp_no_preset["narrative_md"],
        "\n## CRPv6 Agent (research_assistant preset)\n",
        f"**Response:** {crp_with_preset['response']}\n",
        f"**Operations:** `{crp_with_preset['operations']}`  ",
        f"**Risk:** `{crp_with_preset['governance']['risk']}`  ",
        f"**Grounded:** `{crp_with_preset['governance']['grounded']}`  ",
        f"**Chain valid:** `{crp_with_preset['governance']['chain_valid']}`  ",
        f"**Sources:** {crp_with_preset['governance']['sources']}  ",
        f"**Elapsed:** {crp_with_preset['elapsed_s']}s\n",
        "### Narrative\n",
        crp_with_preset["narrative_md"],
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote Markdown report: {md_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
