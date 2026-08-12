# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Continuation manager — envelope builder, master loop, 3-way termination (§4.7).

Implements the continuation loop that decides when to keep generating,
what context to carry forward, and when to stop. Combines gap analysis,
completion detection, information-flow monitoring, and chain degradation
tracking into a single per-window step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from crp.continuation.completion import CompletionDetector, CompletionResult
from crp.continuation.degradation import ChainDegradation
from crp.continuation.document_map import DocumentMap
from crp.continuation.flow import InformationFlowMonitor
from crp.continuation.gap import GapResult, extract_task_requirements, gap_analysis
from crp.continuation.quality_monitor import GenerationQualityMonitor
from crp.continuation.stitch import stitch_outputs
from crp.continuation.trigger import TriggerConfig, TriggerResult, evaluate_continuation
from crp.continuation.voice import VoiceProfile, extract_voice_profile

if TYPE_CHECKING:
    from crp.extraction.types import Fact


class LLMDispatcher(Protocol):
    """Protocol for an LLM dispatch callback used by the continuation loop."""

    def dispatch(self, prompt: str, **kwargs: Any) -> DispatchResult:
        """Send a prompt to the LLM and return the dispatch result."""
        ...


@dataclass
class DispatchResult:
    """Result from a single LLM dispatch.

    Attributes:
        output: Generated text.
        finish_reason: Provider finish reason (e.g. "stop", "length").
        output_tokens: Number of tokens generated.
        facts: Facts extracted from the output.
        window_id: Identifier for the generated window.
    """

    output: str
    finish_reason: str | None
    output_tokens: int
    facts: list[Fact] = field(default_factory=list)
    window_id: str = ""


@dataclass
class ContinuationConfig:
    """Configuration for the continuation manager.

    Attributes:
        max_continuations: Safety bound on continuation windows.
        max_output_tokens: Provider output limit.
        reground_interval: Windows between regrounding checks.
        content_type: Content type hint for completion detection.
        style_anchor_sentences: Sentences to extract as style anchor.
        l3_extractor: LLM-assisted requirement extractor callback (§5B.1).
        embedding_fn: Text→embedding function for semantic gap analysis (§5B.3).
        max_accumulated_facts: Cap on accumulated facts to bound memory (§audit H7).
    """

    max_continuations: int = 50
    max_output_tokens: int | None = None
    reground_interval: int = 5
    content_type: str = ""
    style_anchor_sentences: int = 3  # sentences for style anchor
    l3_extractor: Any = None  # LLM-assisted requirement extractor callback (§5B.1)
    embedding_fn: Any = None  # text→embedding function for semantic gap analysis (§5B.3)
    max_accumulated_facts: int = 5000  # cap fact history to bound memory (§audit H7)


@dataclass
class ContinuationState:
    """Current state of the continuation loop.

    Attributes:
        window_count: Number of continuation windows processed.
        total_tokens: Cumulative generated tokens.
        total_facts: Cumulative extracted facts.
        gap_result: Latest gap analysis result.
        completion_result: Latest completion-detection result.
        trigger_result: Latest continuation-trigger result.
        voice_profile: Extracted voice profile from the first window.
        chain_degradation: Current chain degradation score.
        stitched_output: Accumulated stitched output.
        finished: True when the loop terminates.
        termination_reason: Why the loop terminated.
        quality_anomaly: True if a quality anomaly was detected.
        regrounded: True if regrounding occurred this window.
        window_outputs: Per-window raw outputs with metadata.
    """

    window_count: int = 0
    total_tokens: int = 0
    total_facts: int = 0
    gap_result: GapResult | None = None
    completion_result: CompletionResult | None = None
    trigger_result: TriggerResult | None = None
    voice_profile: VoiceProfile | None = None
    chain_degradation: float = 0.0
    stitched_output: str = ""
    finished: bool = False
    termination_reason: str = ""
    quality_anomaly: bool = False
    regrounded: bool = False
    window_outputs: list[dict[str, Any]] = field(default_factory=list)


class ContinuationManager:
    """Master continuation loop with 3-way termination (§4.7).

    Orchestrates: trigger → gap analysis → envelope → dispatch → extract →
    stitch → completion check → repeat or terminate.

    Termination conditions (ANY triggers stop):
    1. gap_is_zero: all task requirements fulfilled
    2. all_signals_dead: no completion signal is alive
    3. count >= max: safety bound on continuation count
    """

    def __init__(self, config: ContinuationConfig | None = None) -> None:
        self._config = config or ContinuationConfig()
        self._flow = InformationFlowMonitor()
        self._quality = GenerationQualityMonitor()
        self._completion = CompletionDetector(content_type=self._config.content_type)
        self._degradation = ChainDegradation(reground_interval=self._config.reground_interval)
        self._document_map = DocumentMap()
        self._voice: VoiceProfile | None = None
        self._state = ContinuationState()
        self._outputs: list[str] = []
        self._accumulated_facts: list[Fact] = []  # all facts across windows (§5G.2)

    @property
    def state(self) -> ContinuationState:
        """Current continuation loop state."""
        return self._state

    @property
    def voice_profile(self) -> VoiceProfile | None:
        """Extracted voice profile from the first window."""
        return self._voice

    @property
    def document_map(self) -> DocumentMap:
        """Document map showing completed vs remaining sections."""
        return self._document_map

    @property
    def flow_monitor(self) -> InformationFlowMonitor:
        """Information-flow monitor."""
        return self._flow

    @property
    def quality_monitor(self) -> GenerationQualityMonitor:
        """Generation quality monitor."""
        return self._quality

    @property
    def degradation(self) -> ChainDegradation:
        """Chain degradation tracker."""
        return self._degradation

    def build_continuation_envelope(
        self,
        task_intent: str,
        gap_result: GapResult | None = None,
        structural_state: dict[str, object] | None = None,
        last_output: str = "",
    ) -> str:
        """Build a continuation envelope: directive + map + gap + style anchor (§04 §3.2).

        The continuation prompt includes:
        1. Explicit continuation directive (FIRST — dominant signal)
        2. Document map showing completed vs remaining sections
        3. Unfulfilled requirements with specific section numbers
        4. Style anchor from last output
        5. Key findings summary

        Args:
            task_intent: Original task description.
            gap_result: Latest gap analysis result.
            structural_state: Structural position (section, list position, etc.).
            last_output: Last generated output for style anchoring.

        Returns:
            Continuation envelope text.
        """
        sections: list[str] = []

        # ── 1. Continuation directive (FIRST — must be the dominant signal) ──
        # Build explicit "where to continue" from document map
        completed_sections = self._get_completed_section_numbers()
        all_expected = self._get_expected_section_numbers(task_intent)
        missing = sorted(set(all_expected) - set(completed_sections))

        if missing and completed_sections:
            last_completed = max(completed_sections)
            next_sections = ", ".join(str(n) for n in missing[:10])
            sections.append(
                "[CONTINUATION DIRECTIVE]\n"
                f"You have completed sections up to {last_completed}. "
                f"The following sections are MISSING and MUST be written next: {next_sections}.\n"
                "Do NOT repeat any previously written sections. "
                "Start writing from the next missing section immediately. "
                "Do NOT restart from Section 1."
            )
        elif completed_sections:
            last_completed = max(completed_sections)
            sections.append(
                "[CONTINUATION DIRECTIVE]\n"
                f"You have completed sections up to {last_completed}. "
                "Continue from exactly where you left off. "
                "Do NOT repeat any previously written sections. "
                "Do NOT restart from the beginning."
            )
        else:
            sections.append(
                "[CONTINUATION]\n"
                "Continue generating from exactly where you left off. "
                "Do not repeat content already produced. "
                "Maintain the same voice, style, and structure."
            )

        # ── 2. Document map (shows what's done and what's not) ──
        toc = self._document_map.get_toc()
        if toc:
            sections.append(f"[DOCUMENT PROGRESS]\nSections already written:\n{toc}")

        # ── 3. Unfulfilled requirements ──
        if gap_result and gap_result.unfulfilled:
            items = [f"- {r.text}" for r in gap_result.unfulfilled[:10]]
            sections.append("[REMAINING REQUIREMENTS]\n" + "\n".join(items))

        # ── 4. Style anchor: last natural paragraph ──
        if last_output:
            anchor = self._extract_style_anchor(last_output)
            if anchor:
                sections.append(f"[STYLE ANCHOR — last paragraph written]\n{anchor}")

        # ── 5. Key findings summary: top facts from all windows so far ──
        if self._accumulated_facts:
            sorted_facts = sorted(
                self._accumulated_facts,
                key=lambda f: getattr(f, "confidence", 0.5),
                reverse=True,
            )
            top_facts = sorted_facts[:15]
            if top_facts:
                items = [f"- {f.text}" for f in top_facts if hasattr(f, "text")]
                if items:
                    sections.append("[KEY FINDINGS FROM PRIOR SECTIONS]\n" + "\n".join(items))

        # ── 6. Structural state ──
        if structural_state:
            lines: list[str] = []
            if structural_state.get("current_section"):
                lines.append(f"Current section: {structural_state['current_section']}")
            if structural_state.get("list_position"):
                lines.append(f"List position: {structural_state['list_position']}")
            if structural_state.get("open_blocks"):
                lines.append(f"Open blocks: {structural_state['open_blocks']}")
            if structural_state.get("code_block_open"):
                lines.append(f"Code block: {structural_state.get('code_language', 'unknown')}")
            if lines:
                sections.append("[STRUCTURAL POSITION]\n" + "\n".join(lines))

        return "\n\n".join(sections)

    def _get_completed_section_numbers(self) -> list[int]:
        """Extract section numbers (e.g. "1.") from document map headings."""
        numbers: set[int] = set()
        for h in self._document_map.headings:
            m = re.match(r"(\d{1,3})\.", h.text)
            if m:
                numbers.add(int(m.group(1)))
        return sorted(numbers)

    def _get_expected_section_numbers(self, task_intent: str) -> list[int]:
        """Parse expected section count from task intent text."""
        m = re.search(r"\b(\d+)\s*(?:sections?|parts?|items?|steps?)\b", task_intent, re.IGNORECASE)
        if m:
            count = int(m.group(1))
            return list(range(1, count + 1))
        return []

    def process_window(
        self,
        task_intent: str,
        output: str,
        finish_reason: str | None,
        output_tokens: int,
        facts: list[Fact],
        window_id: str = "",
    ) -> ContinuationState:
        """Process a completed window and determine next action.

        This is the per-window step of the master loop. Call repeatedly
        until ``state.finished`` is True.

        Incremental extraction: processes only this window's output
        (O(N) not O(N²)).

        Args:
            task_intent: Original task description.
            output: Generated text from this window.
            finish_reason: Provider finish reason.
            output_tokens: Number of tokens generated.
            facts: Facts extracted from this window's output.
            window_id: Identifier for this window.

        Returns:
            Updated ``ContinuationState``.
        """
        self._outputs.append(output)
        self._state.window_count += 1
        self._state.total_tokens += output_tokens
        self._state.total_facts += len(facts)
        self._accumulated_facts.extend(facts)  # track all facts (§5G.2)

        # Expose per-window raw output with metadata
        self._state.window_outputs.append({
            "window": self._state.window_count,
            "window_id": window_id,
            "output": output,
            "output_tokens": output_tokens,
            "finish_reason": finish_reason,
            "facts_extracted": len(facts),
        })

        # Cap accumulated facts to bound memory (§audit H7)
        cap = self._config.max_accumulated_facts
        if len(self._accumulated_facts) > cap:
            # Keep the highest-confidence facts
            self._accumulated_facts.sort(
                key=lambda f: getattr(f, "confidence", 0.5), reverse=True,
            )
            self._accumulated_facts = self._accumulated_facts[:cap]

        # Voice profile: extract from first window only
        if self._voice is None and output:
            self._voice = extract_voice_profile(output)
            self._state.voice_profile = self._voice

        # Document map update
        self._document_map.update(output, window_id)

        # Flow monitoring
        self._flow.record(window_id, len(facts), output_tokens)

        # Quality monitoring
        q_score = self._quality.score(output, len(facts), window_id)

        # Quality anomaly detection (§5C.1c)
        self._state.quality_anomaly = self._quality.detect_anomaly()

        # Degradation tracking
        expected_facts = max(1, int(self._flow.rolling_average() * output_tokens / 1000.0))
        self._degradation.record(
            window_id=window_id,
            facts_expected=expected_facts,
            facts_produced=len(facts),
            quality_score=q_score.overall,
        )
        self._state.chain_degradation = self._degradation.chain_degradation

        # Regrounding check (§5F.5): every N windows, reconcile facts
        self._state.regrounded = False
        if self._degradation.should_reground() and self._accumulated_facts:
            self._degradation.reground(self._accumulated_facts, facts)
            self._state.regrounded = True

        # Gap analysis (incremental: use accumulated facts from all windows)
        requirements = extract_task_requirements(
            task_intent, l3_extractor=self._config.l3_extractor,
        )
        # Pass document headings so section-level requirements can be matched
        # against actual headings produced across all windows
        doc_headings = [h.text for h in self._document_map.headings]
        self._state.gap_result = gap_analysis(
            task_intent, self._accumulated_facts, requirements,
            embedding_fn=self._config.embedding_fn,
            document_headings=doc_headings,
        )

        # Completion assessment
        self._state.completion_result = self._completion.evaluate(
            text=output,
            facts_produced=len(facts),
            tokens_consumed=output_tokens,
        )

        # Trigger evaluation
        gap_score = self._state.gap_result.gap_score
        info_flow = self._flow.current_rate()

        self._state.trigger_result = evaluate_continuation(
            finish_reason=finish_reason,
            output_tokens=output_tokens,
            max_output_tokens=self._config.max_output_tokens,
            gap_score=gap_score,
            info_flow=info_flow,
            continuation_count=self._state.window_count,
            config=TriggerConfig(max_continuations=self._config.max_continuations),
        )

        # 3-way termination check
        if self._state.gap_result.is_complete:
            self._state.finished = True
            self._state.termination_reason = "gap_fulfilled"
        elif self._state.completion_result.is_complete:
            self._state.finished = True
            self._state.termination_reason = "all_signals_dead"
        elif not self._state.trigger_result.should_continue:
            self._state.finished = True
            self._state.termination_reason = self._state.trigger_result.reason
        else:
            self._state.finished = False
            self._state.termination_reason = ""

        # Stitch accumulated output
        if len(self._outputs) > 1:
            result = stitch_outputs(
                self._outputs[-2],
                self._outputs[-1],
            )
            # Update the last two entries with stitched result
            self._outputs[-2:] = [result.text]
        self._state.stitched_output = self._outputs[0] if self._outputs else ""

        return self._state

    def run(
        self,
        task_intent: str,
        dispatcher: LLMDispatcher,
        initial_output: str = "",
        initial_finish_reason: str | None = None,
        initial_output_tokens: int = 0,
        initial_facts: list[Fact] | None = None,
    ) -> ContinuationState:
        """Full autonomous continuation loop with 3-way termination (§5G.1).

        Orchestrates: trigger → gap analysis → envelope → dispatch → extract →
        stitch → completion check → repeat or terminate.

        Args:
            task_intent: Original task description.
            dispatcher: Callable that dispatches a prompt and returns a result.
            initial_output: Output from the initial window.
            initial_finish_reason: Finish reason from the initial window.
            initial_output_tokens: Token count from the initial window.
            initial_facts: Facts extracted from the initial window.

        Returns:
            Final ``ContinuationState`` after termination.
        """
        # Process initial window
        self.process_window(
            task_intent=task_intent,
            output=initial_output,
            finish_reason=initial_finish_reason,
            output_tokens=initial_output_tokens,
            facts=initial_facts or [],
            window_id=f"w-{self._state.window_count}",
        )

        while not self._state.finished:
            # Build continuation envelope
            structural_state: dict[str, object] = {}
            envelope = self.build_continuation_envelope(
                task_intent=task_intent,
                gap_result=self._state.gap_result,
                structural_state=structural_state,
                last_output=self._outputs[-1] if self._outputs else "",
            )

            # Dispatch via LLM
            result = dispatcher.dispatch(envelope)

            # Process the new window
            self.process_window(
                task_intent=task_intent,
                output=result.output,
                finish_reason=result.finish_reason,
                output_tokens=result.output_tokens,
                facts=result.facts,
                window_id=result.window_id or f"w-{self._state.window_count}",
            )

        return self._state

    def reset(self) -> None:
        """Reset all continuation state for a new task."""
        self._flow.reset()
        self._quality.reset()
        self._completion.reset()
        self._degradation.reset()
        self._document_map = DocumentMap()
        self._voice = None
        self._state = ContinuationState()
        self._outputs.clear()
        self._accumulated_facts.clear()

    def get_context_summary(self) -> str:
        """Return a structured summary of continuation progress.

        Includes window count, key findings, gap status, and document
        progress. Can be injected into external prompts that need
        awareness of in-progress continuation state.

        Returns:
            Multi-line summary string.
        """
        parts: list[str] = []

        parts.append(f"Windows completed: {self._state.window_count}")
        parts.append(f"Facts accumulated: {self._state.total_facts}")

        if self._accumulated_facts:
            sorted_facts = sorted(
                self._accumulated_facts,
                key=lambda f: getattr(f, "confidence", 0.5),
                reverse=True,
            )
            items = [f.text for f in sorted_facts[:10] if hasattr(f, "text")]
            if items:
                parts.append("Key findings:")
                parts.extend(f"  - {item}" for item in items)

        if self._state.gap_result:
            gap = self._state.gap_result
            parts.append(f"Gap score: {gap.gap_score:.2f}")
            if gap.unfulfilled:
                parts.append("Remaining requirements:")
                parts.extend(f"  - {r.text}" for r in gap.unfulfilled[:5])

        toc = self._document_map.get_toc()
        if toc:
            parts.append(f"Document progress:\n{toc}")

        return "\n".join(parts)

    # ── Internal ──────────────────────────────────────────────

    def _extract_style_anchor(self, text: str) -> str:
        """Extract the last natural paragraph as style anchor.

        Args:
            text: Window output text.

        Returns:
            Last few sentences of the last paragraph.
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return text[-200:] if len(text) > 200 else text

        # Take last N sentences from last paragraph
        last = paragraphs[-1]
        import re
        sentences = re.split(r"(?<=[.!?])\s+", last)
        n = self._config.style_anchor_sentences
        anchor = " ".join(sentences[-n:]) if len(sentences) >= n else last

        return anchor
