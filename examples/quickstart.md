<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# Quick Start Guide

Get CRP running in under 5 minutes.

## Prerequisites

- Python 3.10+ (or TypeScript/Rust when SDKs are available)
- An LLM accessible via API or running locally

## Install

```bash
pip install crprotocol
```

## Minimal Example

```python
import crp

# Zero-config: auto-detects your LLM from environment
# (OPENAI_API_KEY, ANTHROPIC_API_KEY, or local Ollama)
client = crp.Client()

# Replace llm.generate() with client.dispatch()
output, report = client.dispatch(
    system_prompt="You are a helpful assistant.",
    task_input="Explain how transformers handle attention in 3 paragraphs."
)

print(output)               # Raw LLM output, unmodified
print(report.quality_tier)  # "S" | "A" | "B" | "C" | "D"
```

### Explicit Provider

```python
from crp import Client
from crp.providers import OpenAIAdapter

client = Client(provider=OpenAIAdapter(model="gpt-4o"))
output, report = client.dispatch(
    system_prompt="You are a helpful assistant.",
    task_input="Explain how transformers handle attention in 3 paragraphs."
)
```

### Model Name Shortcut

```python
import crp

client = crp.Client(model="gpt-4o")           # → OpenAIAdapter
client = crp.Client(model="claude-sonnet-4-20250514")  # → AnthropicAdapter
client = crp.Client(model="llama3.1")          # → OllamaAdapter
```

That's it. CRP is now:
- Building context envelopes for each window
- Extracting facts from output (read-only)
- Carrying knowledge forward to future windows
- Reporting quality tier with every dispatch

## What Changed?

| Before | After |
|--------|-------|
| `openai.Client().chat.completions.create(messages=...)` | `crp.dispatch(system_prompt=..., task_input=...)` |
| Context degrades with each call | Each window gets peak context quality |
| Output truncated at model limit | Automatic continuation for unlimited output |
| No knowledge persistence | Facts persist across sessions |

## Next Steps

- [Local Model Setup](local-model.md) — Zero-config with Ollama or llama.cpp
- [Multi-Provider Fallback](multi-provider.md) — Automatic failover between LLM providers
- [Extraction Pipeline](extraction-pipeline.md) — Customize extraction stages
- [Session Resumption](session-resumption.md) — Cross-session knowledge persistence

## Verify It's Working

```python
# After a few dispatches, check session status
status = client.session_status()
print(f"Windows: {status.windows_completed}")
print(f"Facts: {status.facts_in_warm_state}")
print(f"Saturation: {status.overhead_ratio:.1%}")
```
