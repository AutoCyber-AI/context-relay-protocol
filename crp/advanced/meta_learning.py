# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Meta-learning — ORC, ICML, Reasoning Template Library (§19; CRP-SPEC-019).

Three mechanisms:
  1. Orchestrated Reasoning Chains (ORC): decompose complex reasoning into micro-steps
  2. In-Context Meta-Learning (ICML): reasoning scaffolds + few-shot examples
  3. Reasoning Template Library (RTL): store/retrieve successful reasoning traces

Relevant specifications:
  - CRP-SPEC-019: Cognitive Quality Recognition (CQR)
  - CRP specification §19: Meta-learning / amplified reasoning
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ReasoningStep:
    """Single step in a reasoning chain.

    Attributes:
        step_description: Human-readable description of what this step does.
        system_prompt_template: Prompt template used to execute the step.
        expected_output_format: Description of the output shape expected from
            the step.
        scaffold_level: Amount of scaffolding to apply (0–3).
    """

    step_description: str = ""
    system_prompt_template: str = ""
    expected_output_format: str = ""
    scaffold_level: int = 0  # 0-3


@dataclass
class ReasoningTrace:
    """Complete reasoning trace for RTL storage.

    Attributes:
        trace_id: Unique identifier for the trace.
        task_type: Category of task this trace addresses.
        task_summary: Short summary of the original task.
        steps: Ordered reasoning steps that produced the result.
        model_class: Model capability class (e.g., "0.5B-1B", "2B-7B", "7B+").
        quality_score: Quality score assigned to the trace.
        created_at: Unix timestamp when the trace was created.
        usage_count: Number of times the trace has been retrieved.
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = ""
    task_summary: str = ""
    steps: list[ReasoningStep] = field(default_factory=list)
    model_class: str = ""  # "0.5B-1B" | "2B-7B" | "7B+"
    quality_score: float = 0.0
    created_at: float = field(default_factory=time.time)
    usage_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the trace to a JSON-friendly dictionary.

        Returns:
            Dictionary representation of the trace, including nested steps.
        """
        return {
            "trace_id": self.trace_id,
            "task_type": self.task_type,
            "task_summary": self.task_summary,
            "steps": [
                {
                    "step_description": s.step_description,
                    "system_prompt_template": s.system_prompt_template,
                    "expected_output_format": s.expected_output_format,
                    "scaffold_level": s.scaffold_level,
                }
                for s in self.steps
            ],
            "model_class": self.model_class,
            "quality_score": self.quality_score,
            "created_at": self.created_at,
            "usage_count": self.usage_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasoningTrace:
        """Restore a ``ReasoningTrace`` from a dictionary.

        Args:
            data: Serialized trace data produced by :meth:`to_dict`.

        Returns:
            Reconstructed ``ReasoningTrace`` instance.
        """
        steps = [
            ReasoningStep(
                step_description=s.get("step_description", ""),
                system_prompt_template=s.get("system_prompt_template", ""),
                expected_output_format=s.get("expected_output_format", ""),
                scaffold_level=s.get("scaffold_level", 0),
            )
            for s in data.get("steps", [])
        ]
        return cls(
            trace_id=data.get("trace_id", str(uuid.uuid4())),
            task_type=data.get("task_type", ""),
            task_summary=data.get("task_summary", ""),
            steps=steps,
            model_class=data.get("model_class", ""),
            quality_score=data.get("quality_score", 0.0),
            created_at=data.get("created_at", 0.0),
            usage_count=data.get("usage_count", 0),
        )


@dataclass
class ORCResult:
    """Result of orchestrated reasoning chain.

    Attributes:
        steps_completed: Number of steps that produced output.
        steps_total: Total number of steps in the chain.
        final_output: Synthesised final response.
        step_outputs: Raw output from each executed step.
        quality_score: Estimated quality score for the chain.
        trace: Optional ``ReasoningTrace`` captured for the RTL.
    """

    steps_completed: int = 0
    steps_total: int = 0
    final_output: str = ""
    step_outputs: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    trace: ReasoningTrace | None = None


@dataclass
class MetaLearningConfig:
    """Configuration for meta-learning features.

    Attributes:
        enabled: Master switch for meta-learning.
        orc_enabled: Enable Orchestrated Reasoning Chains.
        orc_max_steps: Maximum number of reasoning steps allowed in ORC.
        orc_min_model_capability: Minimum model capability required for ORC.
        icml_enabled: Enable In-Context Meta-Learning.
        icml_max_examples: Maximum few-shot examples to inject.
        rtl_enabled: Enable Reasoning Template Library storage/retrieval.
        rtl_min_quality_for_storage: Minimum quality score for storing a trace.
        scaffold_level: Default scaffolding level ("auto", "none", "light", "heavy").
        curation_interval: Number of windows between RTL curation passes.
    """

    enabled: bool = True
    orc_enabled: bool = True
    orc_max_steps: int = 10
    orc_min_model_capability: int = 1
    icml_enabled: bool = True
    icml_max_examples: int = 3
    rtl_enabled: bool = True
    rtl_min_quality_for_storage: float = 0.7
    scaffold_level: str = "auto"  # "auto" | "none" | "light" | "heavy"
    curation_interval: int = 5


# ---------------------------------------------------------------------------
# MetaLearningEngine
# ---------------------------------------------------------------------------


class MetaLearningEngine:
    """ORC + ICML + RTL meta-learning capabilities.

    Args:
        dispatch_fn: Callable accepting ``(prompt, context)`` and returning
            ``(output, metadata)``.  Used to execute reasoning steps and probe
            the model.  May be None for offline planning.
        model_capability: Integer capability level of the active model.
        config: ``MetaLearningConfig`` overrides; defaults are used if None.
    """

    def __init__(
        self,
        dispatch_fn: Callable[[str, str], tuple[str, Any]] | None = None,
        model_capability: int = 1,
        config: MetaLearningConfig | None = None,
    ) -> None:
        self._dispatch_fn = dispatch_fn
        self._model_capability = model_capability
        self.config = config or MetaLearningConfig()
        self._trace_library: list[ReasoningTrace] = []

    # ------------------------------------------------------------------
    # Mechanism 1: Orchestrated Reasoning Chains (ORC)
    # ------------------------------------------------------------------

    def should_use_orc(
        self,
        task_complexity: int = 3,
        resource_pressure: str = "NONE",
        probe_quality: float = 0.0,
    ) -> bool:
        """Gate check for ORC activation.

        Gate 1: resource_pressure >= HIGH → False
        Gate 2: model_capability >= task_complexity → False
        Gate 3: probe_quality >= 0.7 → False (ORC unnecessary)

        Args:
            task_complexity: Estimated complexity of the task on a 1–5 scale.
            resource_pressure: Resource pressure label ("NONE", "LOW",
                "MODERATE", "HIGH", "CRITICAL").
            probe_quality: Quality score from a zero-shot probe; high values
                indicate ORC is unnecessary.

        Returns:
            True when ORC should be used to break the task into steps.
        """
        if not self.config.orc_enabled:
            return False
        if resource_pressure in ("HIGH", "CRITICAL"):
            return False
        if self._model_capability >= task_complexity:
            return False
        return probe_quality < 0.7

    def orchestrated_reasoning(
        self,
        task_intent: str,
        task_complexity: int = 3,
        resource_pressure: str = "NONE",
    ) -> ORCResult:
        """Decompose and execute an orchestrated reasoning chain.

        Args:
            task_intent: Natural-language description of the task to solve.
            task_complexity: Estimated complexity of the task.
            resource_pressure: Resource pressure label; reduces the number of
                allowed steps under higher pressure.

        Returns:
            An ``ORCResult`` containing step outputs and the synthesised final
            answer.
        """
        # Determine max steps based on resource pressure
        max_steps = self.config.orc_max_steps
        if resource_pressure == "MODERATE":
            max_steps = min(max_steps, 5)
        elif resource_pressure in ("HIGH", "CRITICAL"):
            max_steps = min(max_steps, 3)

        steps = self._decompose_reasoning(task_intent, max_steps)
        step_outputs: list[str] = []

        for step in steps:
            if not self._dispatch_fn:
                step_outputs.append(f"[no dispatch] {step.step_description}")
                continue

            try:
                prompt = step.system_prompt_template or step.step_description
                output, _ = self._dispatch_fn(prompt, "")
                step_outputs.append(output)
            except Exception:
                # Retry with more scaffolding
                scaffolded_prompt = (
                    f"Step-by-step, {step.step_description}\n"
                    f"Expected format: {step.expected_output_format}"
                )
                try:
                    output, _ = self._dispatch_fn(scaffolded_prompt, "")
                    step_outputs.append(output)
                except Exception:
                    step_outputs.append(f"[failed] {step.step_description}")

        # Synthesize
        final = self._synthesize_chain(step_outputs, task_intent)

        trace = ReasoningTrace(
            task_type="orc",
            task_summary=task_intent[:200],
            steps=steps,
            model_class=self._model_class_str(),
        )

        return ORCResult(
            steps_completed=len(step_outputs),
            steps_total=len(steps),
            final_output=final,
            step_outputs=step_outputs,
            trace=trace,
        )

    def _decompose_reasoning(
        self, task_intent: str, max_steps: int,
    ) -> list[ReasoningStep]:
        """Decompose a task into reasoning steps.

        Attempts to ask the model for a numbered list of steps; falls back to
        a default two-step decomposition when the model is unavailable.

        Args:
            task_intent: Task description.
            max_steps: Upper bound on the number of steps returned.

        Returns:
            Ordered list of ``ReasoningStep`` objects.
        """
        if self._dispatch_fn:
            try:
                prompt = (
                    f"Decompose this task into {max_steps} or fewer reasoning steps. "
                    f"For each step, give a one-line description.\n\n"
                    f"Task: {task_intent}"
                )
                output, _ = self._dispatch_fn(prompt, "")
                steps: list[ReasoningStep] = []
                for line in output.split("\n"):
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith("-")):
                        desc = line.lstrip("0123456789.-) ").strip()
                        if desc:
                            steps.append(ReasoningStep(step_description=desc))
                if steps:
                    return steps[:max_steps]
            except Exception:
                pass

        return self._default_decomposition(task_intent, max_steps)

    def _default_decomposition(
        self, task_intent: str, max_steps: int,
    ) -> list[ReasoningStep]:
        """Default decomposition when an LLM is unavailable.

        Args:
            task_intent: Task description.
            max_steps: Maximum number of steps to return.

        Returns:
            A short, generic list of reasoning steps capped to ``max_steps``.
        """
        return [
            ReasoningStep(
                step_description=f"Analyze: {task_intent}",
                expected_output_format="structured analysis",
                scaffold_level=2,
            ),
            ReasoningStep(
                step_description="Synthesize findings into coherent response",
                expected_output_format="summary",
                scaffold_level=1,
            ),
        ][:max_steps]

    def _synthesize_chain(
        self, step_outputs: list[str], task_intent: str,
    ) -> str:
        """Synthesise step outputs into a final response.

        Args:
            step_outputs: Outputs produced by each reasoning step.
            task_intent: Original task description.

        Returns:
            Synthesised final answer.  Falls back to joining step outputs if
            synthesis is unavailable or has only one step.
        """
        if self._dispatch_fn and len(step_outputs) > 1:
            joined = "\n\n---\n\n".join(step_outputs)
            try:
                output, _ = self._dispatch_fn(
                    f"Synthesize these reasoning steps into a final answer for: {task_intent}",
                    joined[:5000],
                )
                return output
            except Exception:
                pass
        return "\n\n".join(step_outputs)

    # ------------------------------------------------------------------
    # Mechanism 2: In-Context Meta-Learning (ICML)
    # ------------------------------------------------------------------

    def build_reasoning_scaffold(
        self,
        task_intent: str,
    ) -> str:
        """Build a reasoning scaffold adapted to model capability.

        Capability ≤ 1 (0.5B-1B): Full step-by-step template
        Capability ≤ 2 (2B-7B): Light approach
        Capability > 2: No scaffolding

        Args:
            task_intent: Task description to scaffold.

        Returns:
            Scaffold string to prepend to the prompt, or an empty string when
            scaffolding is disabled.
        """
        level = self.config.scaffold_level
        if level == "auto":
            if self._model_capability <= 1:
                level = "heavy"
            elif self._model_capability <= 2:
                level = "light"
            else:
                level = "none"

        if level == "none":
            return ""
        if level == "light":
            return (
                f"[APPROACH]\n"
                f"Consider: key factors, potential issues, evidence available.\n"
                f"Task: {task_intent}\n"
            )
        # Heavy scaffolding
        return (
            f"[REASONING APPROACH]\n"
            f"Step 1: Identify the key elements of: {task_intent}\n"
            f"Step 2: Analyze relationships between elements\n"
            f"Step 3: Consider potential issues or gaps\n"
            f"Step 4: Synthesize findings\n"
            f"Step 5: Verify conclusions against evidence\n"
        )

    def build_metacognitive_envelope(
        self,
        task_intent: str,
        base_envelope: str = "",
        few_shot_traces: list[ReasoningTrace] | None = None,
    ) -> str:
        """Build an envelope with reasoning scaffold + few-shot examples.

        Args:
            task_intent: Task description.
            base_envelope: Existing envelope text to preserve, if any.
            few_shot_traces: Optional explicit traces to include as examples.
                When omitted, the RTL is queried for matching traces.

        Returns:
            Combined envelope string containing the base envelope, scaffold,
            and any few-shot examples.
        """
        parts: list[str] = []

        if base_envelope:
            parts.append(base_envelope)

        scaffold = self.build_reasoning_scaffold(task_intent)
        if scaffold:
            parts.append(scaffold)

        # Few-shot examples from trace library
        traces = few_shot_traces or self._retrieve_traces(task_intent)
        if traces and self.config.icml_enabled:
            examples = "\n".join(
                f"Example {i+1}: {t.task_summary[:100]} → {t.steps[0].step_description if t.steps else 'N/A'}"
                for i, t in enumerate(traces[:self.config.icml_max_examples])
            )
            parts.append(f"[EXAMPLES]\n{examples}")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Mechanism 3: Reasoning Template Library (RTL)
    # ------------------------------------------------------------------

    def store_trace(self, trace: ReasoningTrace) -> bool:
        """Store a reasoning trace if quality meets the configured threshold.

        Args:
            trace: ``ReasoningTrace`` to store.

        Returns:
            True when the trace was stored, False when RTL is disabled or the
            trace quality is too low.
        """
        if not self.config.rtl_enabled:
            return False
        if trace.quality_score < self.config.rtl_min_quality_for_storage:
            return False
        self._trace_library.append(trace)
        return True

    def _retrieve_traces(
        self,
        task_intent: str,
        top_k: int = 3,
    ) -> list[ReasoningTrace]:
        """Retrieve matching traces from the library (simplified text match).

        Scores traces by word-overlap with ``task_intent`` and increments the
        usage count of returned traces.

        Args:
            task_intent: Query used to rank traces.
            top_k: Maximum number of traces to return.

        Returns:
            Up to ``top_k`` traces whose overlap exceeds the 0.2 threshold.
        """
        if not self._trace_library:
            return []
        task_words = set(task_intent.lower().split())
        scored: list[tuple[float, ReasoningTrace]] = []
        for trace in self._trace_library:
            trace_words = set(trace.task_summary.lower().split())
            if not task_words:
                continue
            overlap = len(task_words & trace_words) / len(task_words)
            scored.append((overlap, trace))

        scored.sort(key=lambda x: -x[0])
        results = [t for _, t in scored[:top_k] if _ > 0.2]
        for t in results:
            t.usage_count += 1
        return results

    @property
    def trace_count(self) -> int:
        """Return the number of traces currently stored in the RTL."""
        return len(self._trace_library)

    def _model_class_str(self) -> str:
        """Map the model capability level to a human-readable model class."""
        if self._model_capability <= 1:
            return "0.5B-1B"
        if self._model_capability <= 2:
            return "2B-7B"
        return "7B+"

    def to_dict(self) -> dict[str, Any]:
        """Serialize the engine and its trace library.

        Returns:
            Dictionary with the trace library and active configuration.
        """
        return {
            "traces": [t.to_dict() for t in self._trace_library],
            "config": {
                "enabled": self.config.enabled,
                "orc_enabled": self.config.orc_enabled,
                "orc_max_steps": self.config.orc_max_steps,
                "icml_enabled": self.config.icml_enabled,
                "rtl_enabled": self.config.rtl_enabled,
            },
        }
