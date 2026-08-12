#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Multi-Turn — knowledge accumulates across dispatches.

Each dispatch() enriches the context for the next one. CRP handles
fact extraction, ranking, and envelope packing automatically.
"""

import crp

client = crp.Client()

# Turn 1: establish context
output1, r1 = client.dispatch(
    system_prompt="You are a Python expert.",
    task_input="Explain Python's GIL and its impact on concurrency.",
)
print(f"[Turn 1] {r1.quality_tier} — {r1.facts_extracted} facts extracted")

# Turn 2: CRP automatically includes relevant facts from Turn 1
output2, r2 = client.dispatch(
    system_prompt="You are a Python expert.",
    task_input="Now explain asyncio and how it works around the GIL limitation.",
)
print(f"[Turn 2] {r2.quality_tier} — {r2.facts_extracted} facts extracted")
print(f"  Envelope saturation: {r2.envelope_saturation:.0%}")

# Turn 3: deep dive with accumulated knowledge from turns 1+2
output3, r3 = client.dispatch(
    system_prompt="You are a Python expert.",
    task_input="Compare threading, multiprocessing, and asyncio. "
               "Which should I use for CPU-bound vs IO-bound tasks?",
)
print(f"[Turn 3] {r3.quality_tier} — {r3.facts_extracted} facts extracted")
print(f"\n--- Final answer (with 3 turns of context) ---\n")
print(output3)

# Session status shows total usage
status = client.session_status()
print(f"\nSession: {status.total_windows} windows, "
      f"{status.total_input_tokens} input tokens, "
      f"{status.total_output_tokens} output tokens")

client.close()
