#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP with explicit provider — choose your LLM backend.

Shows how to use OpenAI, Anthropic, Ollama, or a custom callable.
"""

import crp
from crp.providers import OpenAIAdapter, OllamaAdapter, CustomProvider

# --- Option 1: OpenAI ---
# provider = OpenAIAdapter(model="gpt-4o")

# --- Option 2: Anthropic ---
# from crp.providers import AnthropicAdapter
# provider = AnthropicAdapter(model="claude-sonnet-4-20250514")

# --- Option 3: Ollama (local, free) ---
# provider = OllamaAdapter(model="llama3.1")

# --- Option 4: Any OpenAI-compatible API (vLLM, LM Studio, etc.) ---
# provider = OpenAIAdapter(
#     model="my-model",
#     base_url="http://localhost:8000/v1",
#     api_key="not-needed",
# )

# --- Option 5: Custom callable ---
# provider = CustomProvider(
#     fn=lambda messages, **kw: ("Hello from my model!", "stop"),
#     context_window=8192,
#     token_counter=lambda text: len(text) // 4,
# )

# For this example, use auto-detect:
client = crp.Client()

output, report = client.dispatch(
    system_prompt="You are a security analyst.",
    task_input="List the OWASP Top 10 2025 vulnerabilities and their mitigations.",
)

print(output)
print(f"\nTier: {report.quality_tier} | Facts: {report.facts_extracted}")
client.close()
