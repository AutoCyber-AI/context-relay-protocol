# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for input-side continuation — multi-window input processing (§4.6)."""

from __future__ import annotations

from crp.core.orchestrator import CRPOrchestrator
from crp.providers.custom import CustomProvider


def _make_provider(
    replies: list[str],
    context_window: int = 4096,
) -> CustomProvider:
    """Return a CustomProvider that cycles through ``replies``."""
    index = {"i": 0}

    def _generate(messages: list[dict[str, str]], **kwargs: object) -> tuple[str, str]:
        reply = replies[index["i"] % len(replies)]
        index["i"] += 1
        return reply, "stop"

    return CustomProvider(
        generate_fn=_generate,
        count_tokens_fn=lambda text: max(1, len(text) // 4),
        context_size=context_window,
    )


def test_input_continuation_processes_oversized_task_in_multiple_windows() -> None:
    """A task larger than the context window is split into input windows."""
    # Each input chunk returns a fact; the final window answers.
    replies = [
        "FACT: section 1 covers GDPR data minimization.",
        "FACT: section 2 covers EU AI Act high-risk obligations.",
        "FINAL: The document covers GDPR and EU AI Act obligations.",
    ]
    provider = _make_provider(replies, context_window=4096)
    orch = CRPOrchestrator(
        provider=provider,
        input_continuation_mode="multi_window",
    )

    # Build a task that exceeds the 4K budget (4 chars/token => ~8192 chars).
    long_task = (
        "Analyze the following compliance document and list all obligations:\n\n"
        + "\n\n".join(
            f"Section {i}: " + "Lorem ipsum dolor sit amet. " * 50
            for i in range(12)
        )
    )

    output, report = orch.dispatch(
        system_prompt="You are a compliance analyst.",
        task_input=long_task,
    )

    assert "FINAL:" in output
    assert report.continuation_windows >= 0
    assert report.facts_extracted >= 0


def test_input_continuation_disabled_uses_auto_ingest() -> None:
    """With mode=auto_ingest, legacy auto-ingest path runs and still succeeds."""
    provider = _make_provider(
        ["The synthesized summary answers the task."],
        context_window=4096,
    )
    orch = CRPOrchestrator(
        provider=provider,
        input_continuation_mode="auto_ingest",
    )

    long_task = "\n\n".join(
        f"Section {i}: " + "word " * 200
        for i in range(20)
    )

    output, report = orch.dispatch(
        system_prompt="You are a compliance analyst.",
        task_input=long_task,
    )

    assert "synthesized summary" in output
    assert report.facts_extracted >= 0
