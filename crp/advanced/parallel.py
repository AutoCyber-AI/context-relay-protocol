# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Parallel fan-out — N independent windows dispatched concurrently (§4.4)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FanOutTask:
    """One independent task for parallel dispatch."""

    task_id: str = ""
    system_prompt: str = ""
    task_input: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FanOutResult:
    """Result of one parallel dispatch."""

    task_id: str = ""
    output: str = ""
    facts_extracted: int = 0
    success: bool = True
    error: str | None = None


class ParallelFanOut:
    """Dispatch N independent windows and merge results.

    Algorithm (§4.4):
      1. Identify N independent tasks
      2. Construct independent envelopes from warm_state
      3. Dispatch all N windows (sequential fallback if no async)
      4. Collect all N outputs
      5. Extract facts from all N outputs
      6. Merge facts into warm_state
      7. Update DAG with fan-out edges
      8. Continue with next dependent task
    """

    def __init__(
        self,
        dispatch_fn: Callable[[str, str], tuple[str, Any]] | None = None,
        extract_fn: Callable[[str], list[dict[str, Any]]] | None = None,
        max_concurrent: int = 4,
    ) -> None:
        self._dispatch_fn = dispatch_fn
        self._extract_fn = extract_fn
        self._max_concurrent = max_concurrent

    def fan_out(self, tasks: list[FanOutTask]) -> list[FanOutResult]:
        """Dispatch tasks (sequentially — async version would override).

        Returns results in same order as tasks.
        """
        results: list[FanOutResult] = []
        for task in tasks:
            if self._dispatch_fn:
                try:
                    output, _ = self._dispatch_fn(task.system_prompt, task.task_input)
                    facts_count = 0
                    if self._extract_fn:
                        facts = self._extract_fn(output)
                        facts_count = len(facts)
                    results.append(FanOutResult(
                        task_id=task.task_id,
                        output=output,
                        facts_extracted=facts_count,
                        success=True,
                    ))
                except Exception as exc:
                    results.append(FanOutResult(
                        task_id=task.task_id,
                        success=False,
                        error=str(exc),
                    ))
            else:
                results.append(FanOutResult(
                    task_id=task.task_id,
                    output=f"[no dispatch_fn] task={task.task_id}",
                ))
        return results

    def merge_results(
        self,
        results: list[FanOutResult],
        existing_facts: list[Any] | None = None,
    ) -> list[FanOutResult]:
        """Merge fan-out results. Successful results first, failures last."""
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        return successes + failures
