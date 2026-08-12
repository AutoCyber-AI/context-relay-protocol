#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent Template — Local SLM Agent.

Shows how to run a fully local agent with Ollama. The CRP execution profile
keeps context per call so a small model can complete multi-step tasks without
hitting its context limit.

Prerequisites:
  pip install crprotocol
  ollama pull llama3.1       # or any local model you have running
  ollama serve                 # default http://localhost:11434
"""

from __future__ import annotations

import os

from crp.providers.ollama_provider import OllamaProvider

import crp


def get_local_time(timezone: str) -> str:
    """Return the current time in a timezone (mock for the template)."""
    return f"12:00 PM {timezone}"


def list_files(directory: str) -> list[str]:
    """List files in a directory."""
    try:
        return os.listdir(directory)[:10]
    except Exception as exc:
        return [f"Error: {exc}"]


# Use the local Ollama provider. If Ollama is not running, this will fail with
# a clear connection error — no cloud API key is required.
provider = OllamaProvider(
    model=os.environ.get("CRP_LOCAL_MODEL", "llama3.1"),
    base_url=os.environ.get("CRP_LOCAL_BASE_URL", "http://localhost:11434"),
)

agent = crp.Agent(
    provider=provider,
    tools=[get_local_time, list_files],
    system=(
        "You are a privacy-first assistant running entirely on the user's "
        "machine. Answer questions using only local tools."
    ),
    profile="efficient-local",
)

if __name__ == "__main__":
    result = agent.run("What time is it in UTC and list my current directory")
    print(result.answer)
    print("Operations:", result.how_it_was_built)
    print("Windows used:", result.continuation_windows + 1)
