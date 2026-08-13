#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRPv6 Agent SDK — real-world research agent using free public APIs.

This agent answers multi-fact questions by calling live public endpoints:

- Open-Meteo (weather)   — https://open-meteo.com/  (no API key)
- Nominatim (geocoding)  — https://nominatim.org/   (no API key)
- CoinGecko (crypto)     — https://www.coingecko.com/ (no API key)
- Wikipedia (summary)    — https://en.wikipedia.org/api/rest_v1/ (no API key)

Run against LM Studio by setting the environment variables below, or run
against the mock provider by leaving them unset.

Example questions:
    "What is the weather in Tokyo and what is the Bitcoin price in USD?"
    "Give me the current Bitcoin price and a one-paragraph Wikipedia summary of machine learning."
    "Summarise the Wikipedia article on Artificial intelligence."
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import crp
from crp.providers.custom import CustomProvider
from crp.providers.openai import OpenAIAdapter

# ── HTTP helper (zero external dependencies) ─────────────────────────────────

_USER_AGENT = "CRPv6-demo-agent/1.0 (github.com/AutoCyber-AI/context-relay-protocol)"


def _http_get_json(url: str, timeout: int = 15) -> dict[str, Any]:
    """Fetch JSON from a public API, returning an error dict on failure."""
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
    """Convert a city name to latitude, longitude, and display name using Nominatim."""
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
    return {"city": city, "error": "location not found", "raw": data}


def get_weather(city: str) -> dict[str, Any]:
    """Return current weather for a city using Open-Meteo (no API key)."""
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
        "data_source": "open-meteo.com",
    }


def get_crypto_price(crypto_id: str, currency: str = "usd") -> dict[str, Any]:
    """Return the current price of a cryptocurrency using CoinGecko (no API key)."""
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
        "data_source": "api.coingecko.com",
    }


def wikipedia_summary(title: str) -> dict[str, Any]:
    """Return a Wikipedia summary for a page title (no API key)."""
    encoded = urllib.parse.quote(title.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    data = _http_get_json(url)
    if "error" in data:
        return {"title": title, "error": data["error"], "raw": data}
    return {
        "title": data.get("title", title),
        "extract": data.get("extract", ""),
        "description": data.get("description", ""),
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        "data_source": "en.wikipedia.org",
    }


# ── Provider selection: live LM Studio or deterministic mock ────────────────


def _make_provider() -> Any:
    url = os.environ.get("CRP_LMSTUDIO_URL")
    model = os.environ.get("CRP_LMSTUDIO_MODEL", "meta-llama-3.1-8b-instruct")
    if url:
        return OpenAIAdapter(model=model, base_url=url, api_key="lm-studio")

    # Offline mock: emits JSON tool calls for tool frames and natural prose for synthesis.
    def _mock_generate(messages: list[dict[str, str]]) -> tuple[str, str]:
        prompt = messages[-1]["content"].lower()
        objective_match = __import__("re").search(r"objective:\s*(.+)", prompt)
        objective = objective_match.group(1).strip() if objective_match else prompt

        # Synthesis/direct-answer prompts do not contain the tool catalogue.
        if "available tools" not in prompt:
            if "weather" in prompt:
                return ("The current weather in Tokyo is mild, around 24.6°C with a light breeze.", "stop")
            if "bitcoin" in prompt or "crypto" in prompt:
                return ("The current price of Bitcoin in USD is approximately $63,500.", "stop")
            if "machine learning" in prompt or "wikipedia" in prompt:
                return (
                    "Machine learning is a field of artificial intelligence where systems learn from data "
                    "without being explicitly programmed.",
                    "stop",
                )
            return ("I can check the weather, Bitcoin price, or Wikipedia summaries.", "stop")

        if "weather" in objective or "temperature" in objective:
            city = "Tokyo"
            for c in ["tokyo", "paris", "london", "sydney", "new york", "athens"]:
                if c in objective:
                    city = c.title()
                    break
            return (
                json.dumps({"capability_id": "get_weather", "arguments": {"city": city}}),
                "stop",
            )

        if "bitcoin" in objective or "crypto" in objective or "price" in objective:
            crypto = "bitcoin"
            for c in ["bitcoin", "ethereum", "solana", "cardano"]:
                if c in objective:
                    crypto = c
                    break
            return (
                json.dumps({"capability_id": "get_crypto_price", "arguments": {"crypto_id": crypto, "currency": "usd"}}),
                "stop",
            )

        if "wikipedia" in objective or "article" in objective or "machine learning" in objective or "artificial intelligence" in objective:
            title = "Artificial intelligence"
            if "machine learning" in objective:
                title = "Machine learning"
            return (
                json.dumps({"capability_id": "wikipedia_summary", "arguments": {"title": title}}),
                "stop",
            )

        return (
            json.dumps({"capability_id": None, "answer": "I can check the weather, Bitcoin price, or Wikipedia summaries."}),
            "stop",
        )

    return CustomProvider(
        generate_fn=_mock_generate,
        count_tokens_fn=lambda text: max(1, len(text.split())),
        context_size=8192,
        name="mock-slm",
    )


# ── Agent declaration ───────────────────────────────────────────────────────


def main() -> None:
    provider = _make_provider()
    agent = crp.Agent(
        provider=provider,
        tools=[get_weather, get_crypto_price, wikipedia_summary, geocode_city],
        system=(
            "You are a precise research assistant. Use the available tools to answer "
            "questions. Always cite the data source in your final answer."
        ),
        profile="capable-local",
        max_operations=8,
    )

    questions = [
        "What is the current weather in Tokyo?",
        "What is the current Bitcoin price in USD?",
        "What does the Wikipedia article on Machine learning say?",
    ]

    for question in questions:
        print("\n" + "=" * 70)
        print(f"Q: {question}")
        result = agent.run(question, prior_cso=None)
        print(f"A: {result.answer}")
        print(f"Operations: {result.how_it_was_built}")
        print(f"Risk: {result.crp.risk} | Grounded: {result.crp.grounded} | Chain valid: {result.crp.chain_valid}")
        print(f"Sources: {len(result.sources)}")


if __name__ == "__main__":
    main()
