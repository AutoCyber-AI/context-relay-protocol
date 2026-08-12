#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Streaming — receive tokens as they arrive.

dispatch_stream() yields StreamEvent objects with real-time tokens,
extraction progress, and continuation notifications.
"""

import crp

client = crp.Client()

print("Streaming output:\n")
for event in client.dispatch_stream(
    system_prompt="You are a helpful assistant.",
    task_input="Write a haiku about distributed systems.",
):
    if event.event_type == "token":
        print(event.data, end="", flush=True)
    elif event.event_type == "extraction":
        pass  # Extraction happened in background
    elif event.event_type == "continuation":
        print(f"\n[continuation {event.data.continuation_index}]")
    elif event.event_type == "done":
        report = event.data
        print(f"\n\nQuality: {report.quality_tier} | "
              f"Facts: {report.facts_extracted}")

client.close()
