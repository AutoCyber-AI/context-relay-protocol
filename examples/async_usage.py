#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Async — use with FastAPI, asyncio, or any async framework.

CRP provides async_ variants of all core operations:
  await client.async_dispatch(...)
  await client.async_ingest(...)
  async for event in client.async_dispatch_stream(...)
  await client.async_close()
"""

import asyncio
import crp


async def main():
    client = crp.Client()

    # Async dispatch
    output, report = await client.async_dispatch(
        system_prompt="You are a helpful assistant.",
        task_input="Explain the actor model in concurrent programming.",
    )
    print(f"Quality: {report.quality_tier}")
    print(output[:200] + "...")

    # Async ingest
    facts = await client.async_ingest(
        "The actor model was introduced by Carl Hewitt in 1973. "
        "Each actor has a mailbox and processes messages sequentially.",
        label="actor-model",
    )
    print(f"\nIngested {facts} facts")

    # Async streaming
    print("\nStreaming:")
    async for event in client.async_dispatch_stream(
        system_prompt="You are a helpful assistant.",
        task_input="How does Erlang implement the actor model?",
    ):
        if event.event_type == "token":
            print(event.data, end="", flush=True)
        elif event.event_type == "done":
            print(f"\n\nTier: {event.data.quality_tier}")

    await client.async_close()


if __name__ == "__main__":
    asyncio.run(main())
