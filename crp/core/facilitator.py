# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Facilitator — LLM-in-the-Loop cognitive engine (§22).

╔═══════════════════════════════════════════════════════════════════╗
║               PARADIGM INVERSION                                  ║
║                                                                   ║
║   Traditional:   User → LLM → Text                               ║
║   RAG:           User → Context + LLM → Text                     ║
║   Agentic:       LLM (controller) → Tools → LLM → Output         ║
║                                                                   ║
║   CRP §22:       CRP (orchestrator) → LLM (cognitive engine)     ║
║                  → CRP (acts on reasoning) → LLM (generates)     ║
║                  → CRP (evaluates via LLM) → CRP (curates)       ║
║                                                                   ║
║   The LLM is INSIDE CRP.  CRP is the system.                     ║
║   The LLM provides reasoning.  CRP provides structure.           ║
╚═══════════════════════════════════════════════════════════════════╝

The CRPFacilitator uses the LLM for six cognitive functions:

  §22.1  TASK ANALYSIS — Parse task complexity, domain, knowledge needs
  §22.2  STRATEGY ROUTING — Choose optimal dispatch strategy
  §22.3  FACT SYNTHESIS — Merge/compress/derive new knowledge from facts
  §22.4  OUTPUT EVALUATION — Assess output quality against task intent
  §22.5  MEMORY CURATION — Decide what knowledge to keep/merge/discard
  §22.6  EXECUTION PLANNING — Decompose complex tasks into sub-tasks

The facilitator wraps each cognitive call in a structured prompt
with constrained JSON output.  CRP interprets the JSON and acts
on it — the LLM never touches CRP's internal state directly.

Inspired by:
  - Xi et al., "The Rise and Potential of LLM-Based Agents" (2023):
    Agent = Brain(LLM) + Perception + Action
  - Park et al., "Generative Agents" (2023):
    Observation → Planning → Reflection cognitive loop
  - Packer et al., "MemGPT" (2023):
    LLM manages its own memory via structured interrupts

CRP differs from all three: the LLM is NOT the controller.
CRP IS the controller.  The LLM is the reasoning module.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from crp.extraction.types import Fact
    from crp.providers.base import LLMProvider
    from crp.state.warm_store import WarmStateStore

logger = logging.getLogger("crp.facilitator")


# ═══════════════════════════════════════════════════════════════════════
# Cognitive output data structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TaskAnalysis:
    """LLM's analysis of a task — §22.1."""
    complexity: str = "medium"          # "simple", "medium", "complex", "multi_part"
    domain: str = "general"             # Detected domain/topic
    knowledge_needs: list[str] = field(default_factory=list)  # What knowledge the task requires
    expected_output_length: str = "medium"  # "short", "medium", "long", "variable"
    requires_factual_grounding: bool = True
    requires_creativity: bool = False
    requires_reasoning: bool = False
    subtasks: list[str] = field(default_factory=list)  # If multi_part
    confidence: float = 0.8


@dataclass
class StrategyDecision:
    """LLM's routing decision — §22.2."""
    strategy: str = "push"              # "push", "pull", "reflexive", "progressive", "stream_augmented", "agentic"
    reasoning: str = ""                 # Why this strategy was chosen
    envelope_priority: str = "balanced" # "minimal", "balanced", "maximal"
    continuation_likelihood: str = "low"  # "none", "low", "medium", "high"
    confidence: float = 0.7


@dataclass
class SynthesizedKnowledge:
    """LLM-synthesized knowledge from existing facts — §22.3."""
    summary: str = ""                   # Coherent synthesis of input facts
    key_insights: list[str] = field(default_factory=list)  # Distilled insights
    contradictions: list[str] = field(default_factory=list)  # Detected contradictions
    knowledge_gaps: list[str] = field(default_factory=list)  # Gaps identified
    redundant_fact_ids: list[str] = field(default_factory=list)  # Facts that are redundant
    merged_facts: list[dict[str, str]] = field(default_factory=list)  # New merged facts


@dataclass
class OutputEvaluation:
    """LLM's evaluation of CRP's output — §22.4."""
    task_completion: float = 0.0        # 0-1: how well the output addresses the task
    factual_accuracy: float = 0.0       # 0-1: estimated accuracy
    coherence: float = 0.0             # 0-1: logical flow and structure
    missing_elements: list[str] = field(default_factory=list)  # What's missing
    revision_needed: bool = False
    revision_focus: str = ""            # What to focus on in revision
    overall_grade: str = "B"            # S/A/B/C/D


@dataclass
class CurationDecision:
    """LLM's memory curation recommendations — §22.5."""
    promote_ids: list[str] = field(default_factory=list)     # Fact IDs to boost confidence
    demote_ids: list[str] = field(default_factory=list)      # Fact IDs to reduce confidence
    merge_groups: list[list[str]] = field(default_factory=list)  # Groups of IDs to merge
    discard_ids: list[str] = field(default_factory=list)     # Fact IDs to remove
    reasoning: str = ""


@dataclass
class ExecutionPlan:
    """LLM's execution plan for complex tasks — §22.6."""
    steps: list[PlanStep] = field(default_factory=list)
    estimated_windows: int = 1
    parallel_possible: bool = False


@dataclass
class PlanStep:
    """One step in an execution plan."""
    description: str = ""
    strategy: str = "push"              # Which dispatch strategy
    context_needs: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)  # Step indices this depends on
    priority: int = 1                   # 1=highest


@dataclass
class FacilitatorMetrics:
    """Telemetry for facilitator cognitive calls."""
    task_analysis_ms: float = 0.0
    strategy_routing_ms: float = 0.0
    fact_synthesis_ms: float = 0.0
    output_evaluation_ms: float = 0.0
    memory_curation_ms: float = 0.0
    execution_planning_ms: float = 0.0
    total_cognitive_tokens: int = 0
    cognitive_calls: int = 0

    @property
    def total_cognitive_ms(self) -> float:
        """Return the total cognitive ms."""
        return (self.task_analysis_ms + self.strategy_routing_ms +
                self.fact_synthesis_ms + self.output_evaluation_ms +
                self.memory_curation_ms + self.execution_planning_ms)


# ═══════════════════════════════════════════════════════════════════════
# Core Facilitator Engine
# ═══════════════════════════════════════════════════════════════════════

class CRPFacilitator:
    """LLM-in-the-Loop cognitive engine for CRP.

    The facilitator uses the LLM for CRP's internal reasoning:
    - Task analysis (what kind of task is this?)
    - Strategy routing (which dispatch method?)
    - Fact synthesis (merge/compress knowledge)
    - Output evaluation (did we actually help?)
    - Memory curation (what to keep/discard?)
    - Execution planning (how to handle complex tasks?)

    The LLM never touches CRP state directly.  It returns structured
    JSON that CRP interprets and acts upon.  This maintains CRP's
    sovereignty over its own subsystems while leveraging the LLM's
    reasoning capability at every decision point.
    """

    # Maximum tokens budget for each cognitive call
    MAX_ANALYSIS_TOKENS = 500
    MAX_ROUTING_TOKENS = 300
    MAX_SYNTHESIS_TOKENS = 800
    MAX_EVALUATION_TOKENS = 500
    MAX_CURATION_TOKENS = 500
    MAX_PLANNING_TOKENS = 600

    def __init__(
        self,
        provider: LLMProvider,
        count_tokens: Callable[[str], int],
    ):
        self._provider = provider
        self._count_tokens = count_tokens
        self._metrics = FacilitatorMetrics()

    @property
    def metrics(self) -> FacilitatorMetrics:
        """Return the metrics."""
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset all facilitator timing and token counters to zero."""
        self._metrics = FacilitatorMetrics()

    # ───────────────────────────────────────────────────────────────
    # §22.1  TASK ANALYSIS
    # ───────────────────────────────────────────────────────────────

    def analyze_task(
        self,
        task_input: str,
        system_prompt: str,
        fact_count: int = 0,
    ) -> TaskAnalysis:
        """Use the LLM to analyze what kind of task this is.

        Instead of CRP guessing task complexity via regex, the LLM
        actually *understands* the task semantically.  This feeds
        into every downstream decision: strategy routing, envelope
        budget, continuation thresholds, extraction depth.
        """
        prompt = _TASK_ANALYSIS_PROMPT.format(
            system_prompt=system_prompt[:300],
            task_input=task_input[:500],
            fact_count=fact_count,
        )

        start = time.monotonic_ns()
        raw = self._cognitive_call(prompt, self.MAX_ANALYSIS_TOKENS)
        self._metrics.task_analysis_ms = (time.monotonic_ns() - start) / 1_000_000

        return _parse_task_analysis(raw)

    # ───────────────────────────────────────────────────────────────
    # §22.2  STRATEGY ROUTING
    # ───────────────────────────────────────────────────────────────

    def route_strategy(
        self,
        analysis: TaskAnalysis,
        fact_count: int,
        available_strategies: list[str] | None = None,
    ) -> StrategyDecision:
        """Use the LLM to choose the optimal dispatch strategy.

        Given the task analysis and CRP's current state (fact count,
        available strategies), the LLM reasons about which approach
        will produce the best output.

        This replaces the hardcoded "always use push" default.
        """
        strategies = available_strategies or [
            "push", "pull", "reflexive", "progressive", "stream_augmented",
        ]

        prompt = _STRATEGY_ROUTING_PROMPT.format(
            complexity=analysis.complexity,
            domain=analysis.domain,
            knowledge_needs=", ".join(analysis.knowledge_needs[:5]),
            output_length=analysis.expected_output_length,
            requires_grounding=analysis.requires_factual_grounding,
            requires_creativity=analysis.requires_creativity,
            fact_count=fact_count,
            available_strategies=", ".join(strategies),
        )

        start = time.monotonic_ns()
        raw = self._cognitive_call(prompt, self.MAX_ROUTING_TOKENS)
        self._metrics.strategy_routing_ms = (time.monotonic_ns() - start) / 1_000_000

        return _parse_strategy_decision(raw, strategies)

    # ───────────────────────────────────────────────────────────────
    # §22.3  FACT SYNTHESIS
    # ───────────────────────────────────────────────────────────────

    def synthesize_facts(
        self,
        facts: list[tuple[str, str, float]],  # [(id, text, confidence), ...]
        task_context: str = "",
    ) -> SynthesizedKnowledge:
        """Use the LLM to synthesize coherent knowledge from raw facts.

        Instead of CRP dumping raw facts into an envelope, the LLM:
        - Merges overlapping facts into coherent statements
        - Identifies contradictions
        - Spots knowledge gaps
        - Ranks by actual relevance to the task

        This produces BETTER context than raw fact packing.
        """
        if not facts:
            return SynthesizedKnowledge()

        facts_block = "\n".join(
            f"[{fid}] (conf={conf:.0%}) {text}"
            for fid, text, conf in facts[:30]  # Cap at 30 for token budget
        )

        prompt = _FACT_SYNTHESIS_PROMPT.format(
            task_context=task_context[:200],
            facts_block=facts_block,
            fact_count=len(facts),
        )

        start = time.monotonic_ns()
        raw = self._cognitive_call(prompt, self.MAX_SYNTHESIS_TOKENS)
        self._metrics.fact_synthesis_ms = (time.monotonic_ns() - start) / 1_000_000

        return _parse_synthesis(raw)

    # ───────────────────────────────────────────────────────────────
    # §22.4  OUTPUT EVALUATION
    # ───────────────────────────────────────────────────────────────

    def evaluate_output(
        self,
        task_input: str,
        output: str,
        facts_used: int = 0,
    ) -> OutputEvaluation:
        """Use the LLM to evaluate CRP's own output.

        After generation, the LLM assesses whether the output
        actually addresses the task.  This replaces the heuristic
        quality scoring (fact count × saturation × token count).

        The evaluation feeds back into:
        - Whether to trigger continuation
        - Whether to try a different strategy
        - Quality tier classification
        - Memory curation decisions
        """
        prompt = _OUTPUT_EVALUATION_PROMPT.format(
            task_input=task_input[:300],
            output=output[:1500],
            facts_used=facts_used,
        )

        start = time.monotonic_ns()
        raw = self._cognitive_call(prompt, self.MAX_EVALUATION_TOKENS)
        self._metrics.output_evaluation_ms = (time.monotonic_ns() - start) / 1_000_000

        return _parse_evaluation(raw)

    # ───────────────────────────────────────────────────────────────
    # §22.5  MEMORY CURATION
    # ───────────────────────────────────────────────────────────────

    def curate_memory(
        self,
        facts: list[tuple[str, str, float, int]],  # [(id, text, confidence, age), ...]
        recent_task: str = "",
    ) -> CurationDecision:
        """Use the LLM to curate CRP's knowledge base.

        Instead of fixed-interval curation with hardcoded rules,
        the LLM reviews the knowledge base and makes intelligent
        decisions about what to keep, merge, or discard.

        This is the LLM managing CRP's own memory — the deepest
        integration of LLM-as-cognitive-engine.
        """
        if not facts:
            return CurationDecision()

        facts_block = "\n".join(
            f"[{fid}] age={age}w conf={conf:.0%} | {text}"
            for fid, text, conf, age in facts[:25]
        )

        prompt = _MEMORY_CURATION_PROMPT.format(
            facts_block=facts_block,
            fact_count=len(facts),
            recent_task=recent_task[:200],
        )

        start = time.monotonic_ns()
        raw = self._cognitive_call(prompt, self.MAX_CURATION_TOKENS)
        self._metrics.memory_curation_ms = (time.monotonic_ns() - start) / 1_000_000

        return _parse_curation(raw)

    # ───────────────────────────────────────────────────────────────
    # §22.6  EXECUTION PLANNING
    # ───────────────────────────────────────────────────────────────

    def plan_execution(
        self,
        analysis: TaskAnalysis,
        fact_count: int = 0,
    ) -> ExecutionPlan:
        """Use the LLM to create an execution plan for complex tasks.

        For multi-part or complex tasks, the LLM decomposes the task
        into steps, each with its own dispatch strategy and context
        needs.  CRP then orchestrates the plan, running each step
        with the optimal configuration.

        This replaces the flat "one dispatch" approach with intelligent
        multi-step orchestration.
        """
        if analysis.complexity in ("simple", "medium"):
            # Simple tasks don't need planning
            return ExecutionPlan(
                steps=[PlanStep(
                    description="Direct dispatch",
                    strategy="push",
                    priority=1,
                )],
                estimated_windows=1,
            )

        subtasks_text = "\n".join(
            f"- {st}" for st in analysis.subtasks
        ) if analysis.subtasks else "None identified yet"

        prompt = _EXECUTION_PLANNING_PROMPT.format(
            complexity=analysis.complexity,
            domain=analysis.domain,
            knowledge_needs=", ".join(analysis.knowledge_needs[:5]),
            subtasks=subtasks_text,
            fact_count=fact_count,
        )

        start = time.monotonic_ns()
        raw = self._cognitive_call(prompt, self.MAX_PLANNING_TOKENS)
        self._metrics.execution_planning_ms = (time.monotonic_ns() - start) / 1_000_000

        return _parse_execution_plan(raw)

    # ───────────────────────────────────────────────────────────────
    # Internal: structured LLM call
    # ───────────────────────────────────────────────────────────────

    def _cognitive_call(self, prompt: str, max_tokens: int) -> str:
        """Execute a single cognitive LLM call.

        All cognitive calls go through this bottleneck so we can:
        - Track token usage
        - Enforce budget limits
        - Log cognitive reasoning
        - Handle failures gracefully
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the cognitive engine of CRP (Context Relay Protocol). "
                    "You make internal reasoning decisions for the system. "
                    "ALWAYS respond with valid JSON matching the requested schema. "
                    "Be concise and precise."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response, _ = self._provider.generate_chat(
                messages, max_tokens=max_tokens,
            )
            self._metrics.cognitive_calls += 1
            self._metrics.total_cognitive_tokens += self._count_tokens(response)
            return response
        except Exception as exc:
            logger.warning("Facilitator cognitive call failed: %s", exc)
            return "{}"  # Return empty JSON — parsers handle gracefully


# ═══════════════════════════════════════════════════════════════════════
# Structured prompts for cognitive calls
# ═══════════════════════════════════════════════════════════════════════

_TASK_ANALYSIS_PROMPT = """\
Analyze this task for CRP's internal routing.  You are NOT generating the response — \
you are analyzing what KIND of task this is so CRP can configure itself optimally.

SYSTEM PROMPT (context): {system_prompt}
TASK INPUT: {task_input}
AVAILABLE FACTS: {fact_count} facts in knowledge base

Respond with JSON:
{{
  "complexity": "simple|medium|complex|multi_part",
  "domain": "<detected domain, e.g. 'software engineering', 'history', 'data analysis'>",
  "knowledge_needs": ["<what knowledge this task requires>", ...],
  "expected_output_length": "short|medium|long|variable",
  "requires_factual_grounding": true/false,
  "requires_creativity": true/false,
  "requires_reasoning": true/false,
  "subtasks": ["<if multi_part, list the sub-tasks>"],
  "confidence": 0.0-1.0
}}"""

_STRATEGY_ROUTING_PROMPT = """\
Choose the optimal CRP dispatch strategy.  You are CRP's routing brain.

TASK PROFILE:
  Complexity: {complexity}
  Domain: {domain}
  Knowledge needs: {knowledge_needs}
  Expected output: {output_length}
  Needs grounding: {requires_grounding}
  Needs creativity: {requires_creativity}
  Facts available: {fact_count}

AVAILABLE STRATEGIES: {available_strategies}
  - push: Pre-load ALL relevant context (envelope). Best for fact-heavy tasks with enough KB coverage.
  - pull: LLM requests context via tools. Best when LLM knows what it needs.
  - reflexive: Generate blind, then fact-check & refine. Best for accuracy-critical tasks.
  - progressive: Send compact index, expand on demand. Best for broad tasks with many available facts.
  - stream_augmented: Inject context mid-generation. Best for long-form coherent output.

Respond with JSON:
{{
  "strategy": "<chosen strategy>",
  "reasoning": "<1-2 sentences explaining why>",
  "envelope_priority": "minimal|balanced|maximal",
  "continuation_likelihood": "none|low|medium|high",
  "confidence": 0.0-1.0
}}"""

_FACT_SYNTHESIS_PROMPT = """\
Synthesize these CRP knowledge base facts into coherent knowledge.  \
You are CRP's knowledge engine — merge, deduplicate, and organize.

TASK CONTEXT: {task_context}
FACTS ({fact_count} total):
{facts_block}

Respond with JSON:
{{
  "summary": "<coherent 2-3 sentence synthesis of the key knowledge>",
  "key_insights": ["<distilled insight 1>", "<insight 2>", ...],
  "contradictions": ["<any contradicting facts>"],
  "knowledge_gaps": ["<what important knowledge is missing>"],
  "redundant_fact_ids": ["<IDs of facts that are duplicates or subsumed>"],
  "merged_facts": [{{"original_ids": ["id1", "id2"], "merged_text": "<new merged fact>"}}]
}}"""

_OUTPUT_EVALUATION_PROMPT = """\
Evaluate this CRP output.  You are CRP's quality brain — assess whether the output \
actually addresses the task.  This is NOT about style — it's about substance.

ORIGINAL TASK: {task_input}
CRP OUTPUT (may be truncated): {output}
FACTS USED: {facts_used}

Respond with JSON:
{{
  "task_completion": 0.0-1.0,
  "factual_accuracy": 0.0-1.0,
  "coherence": 0.0-1.0,
  "missing_elements": ["<what's missing>"],
  "revision_needed": true/false,
  "revision_focus": "<what to focus on if revision needed>",
  "overall_grade": "S|A|B|C|D"
}}"""

_MEMORY_CURATION_PROMPT = """\
Review CRP's knowledge base and make curation decisions.  You are CRP's memory manager — \
decide what to keep, merge, or discard.

RECENT TASK CONTEXT: {recent_task}
KNOWLEDGE BASE ({fact_count} facts):
{facts_block}

Respond with JSON:
{{
  "promote_ids": ["<fact IDs to boost — high value, should rank higher>"],
  "demote_ids": ["<fact IDs to reduce — low value or stale>"],
  "merge_groups": [["<id1>", "<id2>"], ...],
  "discard_ids": ["<fact IDs that are useless or harmful>"],
  "reasoning": "<brief explanation of curation logic>"
}}"""

_EXECUTION_PLANNING_PROMPT = """\
Create an execution plan for this complex task.  You are CRP's planner — \
decompose the task and assign strategies.

TASK PROFILE:
  Complexity: {complexity}
  Domain: {domain}
  Knowledge needs: {knowledge_needs}
  Identified subtasks: {subtasks}
  Facts available: {fact_count}

Respond with JSON:
{{
  "steps": [
    {{
      "description": "<what this step does>",
      "strategy": "push|pull|reflexive|progressive|stream_augmented",
      "context_needs": ["<what knowledge this step needs>"],
      "depends_on": [<step indices this depends on, 0-indexed>],
      "priority": 1-3
    }}
  ],
  "estimated_windows": <total generation windows expected>,
  "parallel_possible": true/false
}}"""


# ═══════════════════════════════════════════════════════════════════════
# JSON parsers — extract structured data from LLM output
# ═══════════════════════════════════════════════════════════════════════

def _extract_json(raw: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences etc."""
    # Try direct parse first
    text = raw.strip()
    if text.startswith("```"):
        # Strip markdown code fence
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}


def _parse_task_analysis(raw: str) -> TaskAnalysis:
    d = _extract_json(raw)
    return TaskAnalysis(
        complexity=d.get("complexity", "medium"),
        domain=d.get("domain", "general"),
        knowledge_needs=d.get("knowledge_needs", []),
        expected_output_length=d.get("expected_output_length", "medium"),
        requires_factual_grounding=d.get("requires_factual_grounding", True),
        requires_creativity=d.get("requires_creativity", False),
        requires_reasoning=d.get("requires_reasoning", False),
        subtasks=d.get("subtasks", []),
        confidence=float(d.get("confidence", 0.5)),
    )


def _parse_strategy_decision(raw: str, valid_strategies: list[str]) -> StrategyDecision:
    d = _extract_json(raw)
    strategy = d.get("strategy", "push")
    if strategy not in valid_strategies:
        strategy = "push"  # Safe fallback
    return StrategyDecision(
        strategy=strategy,
        reasoning=d.get("reasoning", ""),
        envelope_priority=d.get("envelope_priority", "balanced"),
        continuation_likelihood=d.get("continuation_likelihood", "low"),
        confidence=float(d.get("confidence", 0.5)),
    )


def _parse_synthesis(raw: str) -> SynthesizedKnowledge:
    d = _extract_json(raw)
    return SynthesizedKnowledge(
        summary=d.get("summary", ""),
        key_insights=d.get("key_insights", []),
        contradictions=d.get("contradictions", []),
        knowledge_gaps=d.get("knowledge_gaps", []),
        redundant_fact_ids=d.get("redundant_fact_ids", []),
        merged_facts=d.get("merged_facts", []),
    )


def _parse_evaluation(raw: str) -> OutputEvaluation:
    d = _extract_json(raw)
    return OutputEvaluation(
        task_completion=float(d.get("task_completion", 0.5)),
        factual_accuracy=float(d.get("factual_accuracy", 0.5)),
        coherence=float(d.get("coherence", 0.5)),
        missing_elements=d.get("missing_elements", []),
        revision_needed=d.get("revision_needed", False),
        revision_focus=d.get("revision_focus", ""),
        overall_grade=d.get("overall_grade", "B"),
    )


def _parse_curation(raw: str) -> CurationDecision:
    d = _extract_json(raw)
    return CurationDecision(
        promote_ids=d.get("promote_ids", []),
        demote_ids=d.get("demote_ids", []),
        merge_groups=d.get("merge_groups", []),
        discard_ids=d.get("discard_ids", []),
        reasoning=d.get("reasoning", ""),
    )


def _parse_execution_plan(raw: str) -> ExecutionPlan:
    d = _extract_json(raw)
    steps = []
    for s in d.get("steps", []):
        steps.append(PlanStep(
            description=s.get("description", ""),
            strategy=s.get("strategy", "push"),
            context_needs=s.get("context_needs", []),
            depends_on=s.get("depends_on", []),
            priority=int(s.get("priority", 1)),
        ))
    if not steps:
        steps = [PlanStep(description="Direct dispatch", strategy="push", priority=1)]
    return ExecutionPlan(
        steps=steps,
        estimated_windows=int(d.get("estimated_windows", 1)),
        parallel_possible=d.get("parallel_possible", False),
    )
