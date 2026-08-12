#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Quick Start — 10 lines to unbounded context.

Prerequisites:
  pip install crprotocol
  export OPENAI_API_KEY=sk-...    # or ANTHROPIC_API_KEY, or run Ollama locally
"""

import crp

# Zero-config: auto-detects your LLM from environment variables—
# checks OPENAI_API_KEY, ANTHROPIC_API_KEY, then local Ollama.
client = crp.Client()

# dispatch() replaces your raw llm.generate() call.
# CRP handles: envelope packing, extraction, continuation, security.
output, report = client.dispatch(
    system_prompt="You are a helpful assistant.",
    task_input="Explain how attention mechanisms work in transformer models.",
)

print(output)
print(f"\nQuality: {report.quality_tier}")
print(f"Facts extracted: {report.facts_extracted}")
print(f"Windows used: {report.continuation_windows + 1}")

# Always close when done — persists session state.
client.close()
