# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Self-hosted CRP Agent Console launcher (SPEC-032 §4).

Run this file to start a local FastAPI server that serves the CRP Agent
Console and exposes an OpenAI-compatible chat endpoint backed by ``crp.Agent``.

    python examples/self_hosted_console.py

Then open http://127.0.0.1:8000/crp/console in a browser.

The console shows:
  * Chat with the agent
  * Narrative of what CRP is doing (intent → operations → tool calls → safety)
  * Governance cards (risk, grounded, chain, quality, confidence, sources)
  * Provenance chain (HMAC links)
  * Raw AG-UI + CRP events

Environment variables:
  CRP_MODEL          model identifier, default "local/llama3.1"
  CRP_LM_STUDIO_URL  override the local base URL, e.g. "http://192.168.0.6:1234/v1"
  CRP_CONSOLE_PORT   default 8000
"""

from __future__ import annotations

import argparse
import json
import os
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

import crp
from crp.frontend.console import mount_fastapi
from crp.providers.openai import OpenAIAdapter


def _default_model() -> str:
    return os.environ.get("CRP_MODEL", "local/meta-llama-3.1-8b-instruct")


def _make_agent(model: str | None = None, depth: str = "standard") -> crp.Agent:
    """Build an agent with a small set of demonstration tools."""
    model = model or _default_model()

    def get_weather(city: str) -> dict[str, Any]:
        """Fetch current weather for a city from Open-Meteo."""
        import urllib.parse
        import urllib.request

        # Demo uses Sydney coordinates; a production app would geocode first.
        url = (
            "https://api.open-meteo.com/v1/forecast?"
            + urllib.parse.urlencode(
                {
                    "latitude": -33.8688,
                    "longitude": 151.2093,
                    "current": "temperature_2m,weather_code,windspeed_10m",
                }
            )
        )
        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310
            data = json.load(resp)
        current = data.get("current", {})
        return {
            "city": city,
            "temperature_c": current.get("temperature_2m"),
            "weather_code": current.get("weather_code"),
            "windspeed_kmh": current.get("windspeed_10m"),
        }

    def get_time(timezone: str = "UTC") -> dict[str, Any]:
        """Return the current time in a given timezone."""
        from datetime import datetime

        try:
            import zoneinfo  # type: ignore[import]

            tz = zoneinfo.ZoneInfo(timezone)
        except Exception:
            tz = None
        now = datetime.now(tz)
        return {
            "timezone": timezone,
            "iso": now.isoformat(),
            "time": now.strftime("%H:%M:%S"),
        }

    def calculate(expression: str) -> dict[str, Any]:
        """Safely evaluate a simple arithmetic expression."""
        allowed = {"__builtins__": {}}
        # Replace common symbols so small models do not need to emit python operators.
        expr = (
            expression.replace("x", "*")
            .replace("X", "*")
            .replace("÷", "/")
            .replace("times", "*")
            .replace("divided by", "/")
        )
        try:
            value = eval(expr, allowed, {"__builtins__": {}})  # noqa: S307
        except Exception as exc:
            return {"error": f"Could not evaluate {expression!r}: {exc}"}
        return {"expression": expression, "result": value}

    # If a local/LM-Studio style identifier is requested, build a provider manually
    # so we can point at the user's local server without requiring global env vars.
    provider: crp.providers.LLMProvider | None = None
    if model.startswith("local/") or model.startswith("lm-studio/"):
        base_url = os.environ.get("CRP_LM_STUDIO_URL", "http://127.0.0.1:1234/v1")
        model_name = model.split("/", 1)[1] if "/" in model else model
        provider = OpenAIAdapter(
            model=model_name,
            base_url=base_url,
            api_key="not-needed",
        )
        model = None  # tell crp.Agent to use provider instead

    return crp.Agent(
        model=model,
        provider=provider,
        tools=[get_weather, get_time, calculate],
        system="You are a helpful, governed agent. Be concise.",
        profile="capable-local",
        depth=depth,
        max_operations=8,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Self-hosted CRP Agent Console")
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("CRP_CONSOLE_PORT", "8000"))
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--model", default=None, help="Model identifier (default: local/llama3.1)")
    args = parser.parse_args()

    app = FastAPI(title="CRP Self-Hosted Agent Console")

    # Mount the console at /crp/console and the TEL stream at /v1/tel/stream.
    mount_fastapi(app, path="/crp/console", stream_path="/v1/tel/stream")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": crp.__version__}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> StreamingResponse:
        body = await request.json()
        messages = body.get("messages", [])
        if not messages:
            return JSONResponse({"error": "messages required"}, status_code=400)
        user_request = "\n".join(
            m.get("content", "") for m in messages if m.get("role") == "user"
        )
        session_id = body.get("session_id") or f"console-{os.urandom(4).hex()}"
        depth = body.get("depth", "standard")

        agent = _make_agent(args.model, depth=depth)

        async def stream_events():
            try:
                for event in agent.run_tel(user_request, session_id=session_id):
                    # Emit AG-UI events as SSE frames.
                    data = json.dumps(
                        event.to_dict() if hasattr(event, "to_dict") else event.__dict__
                    )
                    yield f"data: {data}\n\n".encode()
            except Exception as exc:  # noqa: BLE001
                err = {
                    "type": "RUN_ERROR",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
                yield f"data: {json.dumps(err)}\n\n".encode()

        return StreamingResponse(stream_events(), media_type="text/event-stream")

    import uvicorn

    print(f"CRP self-hosted console starting at http://{args.host}:{args.port}/crp/console")
    print(f"Stream endpoint: http://{args.host}:{args.port}/v1/tel/stream")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
