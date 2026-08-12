# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Batch dispatch and ingest operations (§6.6).

dispatch_batch: Fan-out multiple intents in parallel.
ingest_batch: Batch ingestion with boundary reconciliation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class BatchResult:
    """Result for one item in a batch operation."""

    index: int = 0
    output: str = ""
    success: bool = True
    error: str | None = None
    facts_extracted: int = 0


def dispatch_batch(
    intents: list[dict[str, str]],
    dispatch_fn: Callable[[str, str], tuple[str, Any]] | None = None,
) -> list[BatchResult]:
    """Batch dispatch with sequential execution (parallel fan-out ready).

    Each intent should have keys: "system_prompt", "task_input".
    """
    results: list[BatchResult] = []
    for i, intent in enumerate(intents):
        sys_prompt = intent.get("system_prompt", "")
        task_input = intent.get("task_input", "")
        if dispatch_fn:
            try:
                output, report = dispatch_fn(sys_prompt, task_input)
                results.append(BatchResult(index=i, output=output))
            except Exception as exc:
                results.append(BatchResult(
                    index=i, success=False, error=str(exc),
                ))
        else:
            results.append(BatchResult(
                index=i, output="[no dispatch_fn]",
            ))
    return results


def ingest_batch(
    texts: list[str],
    extract_fn: Callable[[str, str], list[Any]] | None = None,
    task_intent: str = "",
) -> list[BatchResult]:
    """Batch ingestion with per-item extraction.

    Returns extraction results per text item.
    """
    results: list[BatchResult] = []
    for i, text in enumerate(texts):
        if extract_fn:
            try:
                facts = extract_fn(text, task_intent)
                results.append(BatchResult(
                    index=i, facts_extracted=len(facts),
                ))
            except Exception as exc:
                results.append(BatchResult(
                    index=i, success=False, error=str(exc),
                ))
        else:
            results.append(BatchResult(index=i, facts_extracted=0))
    return results
