#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Live CRPv6 proof against a local SLM using real public APIs.

This script runs the same small local model on the same real-world question twice:

1. RAW LLM — tools are described in the system prompt; the model must decide what to do.
2. CRPv6 Agent — tools are declared; CRP positions the task, executes the loop, and
   emits governance metadata.

The APIs used are free, public, and require no API key:
- Open-Meteo (weather)        https://open-meteo.com/
- Nominatim (geocoding)       https://nominatim.org/
- CoinGecko (crypto prices)   https://www.coingecko.com/
- Wikipedia REST (summary)    https://en.wikipedia.org/api/rest_v1/

Set CRP_LMSTUDIO_URL and CRP_LMSTUDIO_MODEL, or rely on the defaults below.
"""

from __future__ import annotations

import json
import os
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import crp
from crp.providers.openai import OpenAIAdapter

# ── HTTP helper (stdlib only) ──────────────────────────────────────────────

_USER_AGENT = "CRPv6-demo-agent/1.0 (github.com/AutoCyber-AI/context-relay-protocol)"


def _http_get_json(url: str, timeout: int = 15) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}", "url": url}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "url": url}


# ── Real-world tools ────────────────────────────────────────────────────────


def geocode_city(city: str) -> dict[str, Any]:
    """Convert a city name to lat/lon/display name via Nominatim."""
    query = urllib.parse.quote(city)
    url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
    data = _http_get_json(url)
    if isinstance(data, list) and data:
        return {
            "city": city,
            "latitude": float(data[0]["lat"]),
            "longitude": float(data[0]["lon"]),
            "display_name": data[0]["display_name"],
        }
    return {"city": city, "error": "location not found"}


def get_weather(city: str) -> dict[str, Any]:
    """Return current weather for a city using Open-Meteo."""
    geo = geocode_city(city)
    if "error" in geo:
        return {"city": city, "error": geo["error"]}
    lat, lon = geo["latitude"], geo["longitude"]
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&current=temperature_2m,weather_code,wind_speed_10m"
    )
    data = _http_get_json(url)
    current = data.get("current", {})
    return {
        "city": city,
        "display_name": geo["display_name"],
        "temperature_c": current.get("temperature_2m"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "weather_code": current.get("weather_code"),
    }


def get_crypto_price(crypto_id: str, currency: str = "usd") -> dict[str, Any]:
    """Return the current price of a cryptocurrency using CoinGecko."""
    ids = urllib.parse.quote(crypto_id.lower().replace(" ", ","))
    vs = urllib.parse.quote(currency.lower())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies={vs}"
    data = _http_get_json(url)
    if "error" in data:
        return {"crypto_id": crypto_id, "currency": currency, "error": data["error"]}
    coin = data.get(crypto_id.lower(), {})
    price = coin.get(currency.lower())
    if price is None:
        return {"crypto_id": crypto_id, "currency": currency, "error": "price not found"}
    return {
        "crypto_id": crypto_id,
        "currency": currency.upper(),
        "price": price,
    }


def wikipedia_summary(title: str) -> dict[str, Any]:
    """Return a Wikipedia summary for a page title."""
    encoded = urllib.parse.quote(title.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    data = _http_get_json(url)
    if "error" in data:
        return {"title": title, "error": data["error"]}
    return {
        "title": data.get("title", title),
        "extract": data.get("extract", ""),
        "description": data.get("description", ""),
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
    }


# ── LM Studio connection ────────────────────────────────────────────────────


lmstudio_url = os.environ.get("CRP_LMSTUDIO_URL", "http://localhost:1234/v1")
model = os.environ.get("CRP_LMSTUDIO_MODEL", "meta-llama-3.1-8b-instruct")

print(f"Endpoint: {lmstudio_url}")
print(f"Model:    {model}\n")


def make_provider() -> OpenAIAdapter:
    return OpenAIAdapter(model=model, base_url=lmstudio_url, api_key="lm-studio")


# ── Shared tool catalogue description for the raw LLM arm ─────────────────────


TOOLS_BLURB = textwrap.dedent("""\
    get_weather(city: str) -> live weather from Open-Meteo.
    get_crypto_price(crypto_id: str, currency: str) -> live crypto price from CoinGecko.
    wikipedia_summary(title: str) -> Wikipedia article summary.
""")


# ── Arm 1: raw LLM ─────────────────────────────────────────────────────────


def ask_raw(question: str) -> str:
    provider = make_provider()
    system = (
        "You are a helpful assistant. You have these tools:\n\n"
        f"{TOOLS_BLURB}\n\n"
        "If you need a tool, output JSON like: "
        '{"tool": "get_weather", "arguments": {"city": "Tokyo"}}. '
        "Then stop. The user will give you the result. Answer the question."
    )
    output, _ = provider.generate_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ])
    return output


# ── Arm 2: CRPv6 Agent SDK ──────────────────────────────────────────────────


def ask_crp(question: str) -> crp.AgentResponse:
    provider = make_provider()
    agent = crp.Agent(
        provider=provider,
        tools=[get_weather, get_crypto_price, wikipedia_summary, geocode_city],
        system="Answer precisely using the available tools. Cite your data sources.",
        profile="capable-local",
        max_operations=8,
    )
    return agent.run(question)


def print_crp_result(name: str, result: crp.AgentResponse) -> None:
    print(f"\n🟩 CRPv6 — {name}")
    print("-" * 70)
    print(result.answer)
    print("-" * 70)
    governance = {
        "risk": result.crp.risk,
        "grounded": result.crp.grounded,
        "chain_valid": result.crp.chain_valid,
        "operations": result.operations,
        "sources": [
            {
                "capability_id": s.get("capability_id") if isinstance(s, dict) else getattr(s, "capability_id", None),
                "operation_type": s.get("operation_type") if isinstance(s, dict) else getattr(s, "operation_type", None),
                "payload": str(s.get("payload", "") if isinstance(s, dict) else getattr(s, "payload", ""))[:120],
            }
            for s in result.sources
        ],
    }
    print(json.dumps(governance, indent=2, default=str))


# ── Run the proof ────────────────────────────────────────────────────────────


def main() -> None:
    # Case 1: live weather
    q1 = "What is the current weather in Tokyo?"
    print("🟦 RAW LLM — live weather")
    print(ask_raw(q1))
    print_crp_result("live weather", ask_crp(q1))

    # Case 2: live crypto price
    q2 = "What is the current Bitcoin price in USD?"
    print("\n🟦 RAW LLM — live crypto price")
    print(ask_raw(q2))
    print_crp_result("live crypto price", ask_crp(q2))

    # Case 3: RAG-like retrieval from Wikipedia
    q3 = "What does the Wikipedia article on Machine learning say?"
    print("\n🟦 RAW LLM — live Wikipedia retrieval")
    print(ask_raw(q3))
    print_crp_result("live Wikipedia retrieval", ask_crp(q3))

    print("\n" + "=" * 70)
    print("All CRP results above use live public APIs and runtime governance.")
    print("No API keys required. No governance values are hardcoded.")
    print("=" * 70)


if __name__ == "__main__":
    main()
