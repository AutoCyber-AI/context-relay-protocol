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


_WORD_RE = re.compile(r"\b\w+\b")


def _window_6grams(text: str) -> set[str]:
    """Word 6-gram set of a window output — the near-duplicate guard's unit."""
    words = _WORD_RE.findall(text.lower())
    if len(words) < 6:
        return set()
    return {" ".join(words[i: i + 6]) for i in range(len(words) - 5)}


# Duplicate-block collapse: when a model starts looping mid-window it often
# rewrites a whole section block a second time inside the SAME window. The
# cross-window near-duplicate guard cannot see that (it compares completed
# windows), so the redundant block would enter the document verbatim. Blocks
# are dropped on EITHER signal: (a) their normalized heading re-announces an
# already-written heading (catches heavily-reworded rewrites that share few
# 6-grams — measured as low as 0.37 overlap on real data), or (b) their
# 6-gram overlap with already-written content is very high.
_BLOCK_DUP_THRESHOLD = 0.50
_BLOCK_MIN_WORDS = 40
# Paragraph-level recycling inside a KEPT block: a window may close its real
# content, then append paragraphs that recycle earlier sections with no
# markdown heading of their own — the block-level ratio misses those because
# the genuine text dilutes it. Only near-verbatim recycling (>= 0.50) drops.
_PARA_MIN_WORDS = 40
_PARA_DUP_THRESHOLD = 0.50

# Subsection titles that legitimately recur under every section of a guide.
# A block under one of these needs the high _BLOCK_DUP_THRESHOLD overlap to be
# dropped; distinctive section titles get the lower heading-match bar below.
_BOILERPLATE_HEADINGS = {
    "key concepts",
    "trade offs",
    "real world patterns",
    "implementation details",
    "introduction",
    "overview",
    "conclusion",
    "summary",
    "examples",
    "example",
    "best practices",
    "design principles",
    "challenges",
    "key takeaways",
    "further reading",
    "references",
}


def _normalize_heading(text: str) -> str:
    """Normalize a heading for equality comparison: '## Section 3: Data
    Modeling and Storage' and '### 3. Data Modeling and Storage' must match."""
    h = re.sub(r"^#{1,6}\s*", "", text.strip().lower())
    h = re.sub(r"^section\s+\d{1,3}\s*[:.)-]?\s*", "", h)
    # Strip STACKED list prefixes: real artifacts include '3. 2. Language...'
    # (a re-announced section re-numbered by the model) and '5.4. ...' (an
    # outline depth that leaked into a heading). Loop until no leading
    # numeric token remains so both collapse to the bare title.
    while True:
        stripped = re.sub(r"^\d{1,3}\s*[.)]\s*", "", h)
        if stripped == h:
            break
        h = stripped
    return re.sub(r"[^a-z0-9 ]", "", h).strip()


def _block_headings(text: str) -> set[str]:
    """Normalized headings declared in a text."""
    return {
        _normalize_heading(m.group(1))
        for m in re.finditer(r"^#{1,6}\s+(.+)$", text, re.MULTILINE)
    }


def _split_markdown_blocks(text: str) -> list[str]:
    """Split markdown into heading-delimited blocks (heading kept with body)."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.split("\n"):
        if line.startswith("#") and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(b) for b in blocks if "\n".join(b).strip()]


def _dedup_block_paragraphs(
    block: str, prior_grams: set[str], kept_grams: set[str],
) -> tuple[str, int]:
    """Drop near-verbatim recycled paragraphs inside a KEPT block.

    Real qwen2.5-7b artifact (6.2.2 era): a window wrote '## Conclusion',
    then appended paragraphs recycling earlier sections with no markdown
    heading of their own ('Introduction' as plain text, a re-stated
    determinism paragraph). The block-level overlap misses these because the
    genuine conclusion text dilutes the ratio. Paragraphs >= 40 words whose
    6-gram overlap with all prior/kept content reaches 0.50 are near-verbatim
    recycling and are dropped. If every paragraph would drop, the block is
    returned unchanged — never leave an empty block.
    """
    paragraphs = re.split(r"\n\s*\n", block)
    if len(paragraphs) < 2:
        return block, 0
    seen = prior_grams | kept_grams
    if not seen:
        return block, 0
    kept_paras: list[str] = []
    dropped = 0
    for para in paragraphs:
        if len(_WORD_RE.findall(para)) >= _PARA_MIN_WORDS:
            grams = _window_6grams(para)
            if grams and len(grams & seen) / len(grams) >= _PARA_DUP_THRESHOLD:
                dropped += 1
                continue
        kept_paras.append(para)
    if dropped and kept_paras:
        return "\n\n".join(kept_paras), dropped
    return block, 0


def collapse_duplicate_blocks(output: str, prior_text: str) -> tuple[str, int]:
    """Drop blocks that rewrite content already written (prior windows or
    earlier blocks of this same window).

    Returns (cleaned_text, blocks_dropped). If every block duplicates, the
    original is returned unchanged so the cross-window near-duplicate guard
    remains the terminating authority — never leave an empty document.
    """
    blocks = _split_markdown_blocks(output)
    # NOTE: no early return for single-block output. A window can carry all
    # of its recycling INSIDE one block (e.g. '## Conclusion' followed by
    # recycled fragments with no headings of their own) — the paragraph pass
    # below is the only line of defence there. The 'dropped and kept' guard
    # at the end still prevents an empty result.

    prior_grams = _window_6grams(prior_text) if prior_text else set()
    prior_headings = _block_headings(prior_text) if prior_text else set()
    kept: list[str] = []
    kept_grams: set[str] = set()
    kept_headings: set[str] = set()
    dropped = 0
    conclusion_seen = False
    for block in blocks:
        heading_line = next(
            (ln for ln in block.split("\n") if ln.startswith("#")), "",
        )
        norm_h = _normalize_heading(heading_line) if heading_line else ""
        word_n = len(_WORD_RE.findall(block))
        # Orphan heading: a heading line with no body of its own (observed
        # live: a window closed its section, then re-announced two earlier
        # section headings as the token budget cut it off mid-retry). It
        # carries no content, so the _BLOCK_MIN_WORDS exemption must not
        # protect it — but only when it RE-announces: a first announcement is
        # kept so a following window can still write content under it.
        body_words = word_n - len(_WORD_RE.findall(heading_line))
        if (
            norm_h
            and body_words == 0
            and (norm_h in kept_headings or norm_h in prior_headings)
        ):
            dropped += 1
            continue
        # A block that RE-ANNOUNCES an earlier heading is checked regardless
        # of size: the 40-word floor exists to protect small blocks from weak
        # overlap signals, but a re-announced heading with real overlap is a
        # rewrite at any length (observed live: 27- and 37-word blocks at
        # 0.29/0.76 overlap bypassed every check because they sat under the
        # floor, and the pure-overlap path is unreachable for them). The
        # same applies to HEADED blocks once a conclusion exists — the
        # post-conclusion pruning below needs their overlap measured.
        reannounced = bool(norm_h) and (
            norm_h in kept_headings or norm_h in prior_headings
        )
        check_overlap = (
            word_n >= _BLOCK_MIN_WORDS
            or reannounced
            or (conclusion_seen and bool(norm_h))
        )
        if check_overlap:
            grams = _window_6grams(block)
            max_overlap = 0.0
            if grams:
                against_prior = (
                    len(grams & prior_grams) / len(grams) if prior_grams else 0.0
                )
                against_kept = (
                    len(grams & kept_grams) / len(grams) if kept_grams else 0.0
                )
                max_overlap = max(against_prior, against_kept)
            # Heading re-announcement alone is NOT enough: recurring
            # subsection titles like "Key Concepts" / "Trade-offs" appear in
            # every section of a guide. A block is dropped on a heading match
            # only when its wording also overlaps the earlier content —
            # distinctive titles get a low bar (a summarized rewrite of a
            # whole section measured 0.19 on real data and must be dropped),
            # while boilerplate subheads keep the high overlap-only path so a
            # fresh "Key Concepts" block under a repeated heading (~0.05)
            # survives.
            heading_dup = reannounced and (
                (norm_h not in _BOILERPLATE_HEADINGS and max_overlap >= 0.10)
                or max_overlap >= _BLOCK_DUP_THRESHOLD
            )
            # Post-conclusion pruning: once a '## Conclusion' block is kept,
            # later blocks can only be epilogue. A re-announced heading or
            # >= 0.35 overlap there is the model re-treading earlier sections
            # (observed live: re-announced subsections at 0.29/0.42/0.76
            # after the conclusion). Genuinely new epilogue content has new
            # headings and low overlap, so it is unaffected.
            post_conclusion_dup = (
                conclusion_seen
                and (reannounced or max_overlap >= 0.35)
            )
            if (
                heading_dup
                or post_conclusion_dup
                or (word_n >= _BLOCK_MIN_WORDS
                    and max_overlap >= _BLOCK_DUP_THRESHOLD)
            ):
                # Salvage path: if dropping this block would leave nothing
                # kept, try paragraph-level removal first — the block may
                # MIX genuine content with recycled fragments (observed live:
                # a '## Conclusion' block whose recycled tail pushed the
                # whole block to 0.51 overlap; dropping it outright would
                # have discarded a real conclusion).
                _salvaged, _sdropped = _dedup_block_paragraphs(
                    block, prior_grams, kept_grams,
                )
                if _sdropped and _salvaged.strip() and not kept:
                    block = _salvaged
                    dropped += _sdropped
                    grams = _window_6grams(block)
                    kept_grams |= grams
                else:
                    dropped += 1
                    continue
            if word_n >= _BLOCK_MIN_WORDS:
                block, _pdropped = _dedup_block_paragraphs(
                    block, prior_grams, kept_grams,
                )
                if _pdropped:
                    dropped += _pdropped
                    grams = _window_6grams(block)
            kept_grams |= grams
        if norm_h == "conclusion":
            conclusion_seen = True
        if norm_h:
            kept_headings.add(norm_h)
        kept.append(block)

    if dropped and kept:
        return "\n".join(kept), dropped
    return output, 0


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
    # A-PR-7 decider guard: when the model stops naturally (finish=stop) but
    # the gap scorer keeps insisting on continuation, terminate after this
    # many consecutive stop-continuations whose novel-6-gram fraction is
    # below ``stop_novelty_threshold`` — regardless of the gap score.  The
    # pre-6.2.2 decider could stall for the full 50-window budget on
    # low-novelty stop output (WASA live evidence: 22-window stall at
    # finish=stop, gap_score ~0.94).  Set max_low_novelty_stops=0 to disable.
    stop_novelty_threshold: float = 0.2
    max_low_novelty_stops: int = 3


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
        section_rewrites: Headings that re-announced an already-completed
            section across all windows so far (anti-rewrite guard signal).
        blocks_collapsed: Whole blocks (sections/paragraph groups) removed
            from window outputs because they rewrote earlier content —
            within-window duplication the cross-window near-duplicate guard
            cannot see.
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
    section_rewrites: int = 0
    blocks_collapsed: int = 0


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
        # A-PR-7: consecutive stop-continuations with sub-threshold novel
        # content (see process_window).
        self._stop_novelty_streak = 0

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
            titles = self._get_expected_section_titles(task_intent)
            # Name each missing section by TITLE, not just number. The compact
            # task reference in continuation windows drops the original
            # numbered list, so a bare "section 3" leaves the model to guess
            # the topic — and it guesses wrong (observed live: window tasked
            # with "3. API Design and Versioning" wrote "Data Modeling and
            # Storage" instead).
            missing_named = ", ".join(
                f"{n}. {titles[n]}" if n in titles else str(n)
                for n in missing[:10]
            )
            next_n = missing[0]
            next_title = titles.get(next_n)
            heading_instr = (
                f"Begin your output with the heading '## {next_n}. {next_title}' "
                if next_title
                else f"Begin your output with the heading '## {next_n}.' "
            )
            sections.append(
                "[CONTINUATION DIRECTIVE]\n"
                f"You have completed sections up to {last_completed}. "
                f"The following sections are MISSING and MUST be written next, "
                f"in this order: {missing_named}.\n"
                f"Write ONLY section {next_n}"
                + (f" ({next_title})" if next_title else "")
                + " now. " + heading_instr +
                "Do NOT repeat any previously written sections. "
                "Do NOT restart from Section 1. "
                "Do NOT write any section other than the one named above."
            )
        elif completed_sections:
            last_completed = max(completed_sections)
            # All numbered sections are done. If the document has no
            # conclusion yet, aim the remaining window(s) at it — otherwise
            # the vague "continue where you left off" invites a rewrite of
            # the last section (observed live: full rewrites of Section 1
            # once sections ran out).
            has_conclusion = any(
                "conclusion" in h.text.lower()
                for h in self._document_map.headings
            )
            if not has_conclusion:
                sections.append(
                    "[CONTINUATION DIRECTIVE]\n"
                    f"All {len(all_expected) if all_expected else last_completed} "
                    "planned sections are complete. "
                    "Write ONLY a short '## Conclusion' section now, "
                    "summarising the guide in a few sentences. "
                    "Begin your output with the heading '## Conclusion'. "
                    "Do NOT rewrite any completed section."
                )
            else:
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

        # ── 2b. Explicit anti-rewrite guard ──
        # The TOC shows completion, but small models routinely re-open a
        # completed section anyway. Name the completed sections verbatim and
        # state the consequence, and surface any rewrites observed so far.
        completed_titles: list[str] = []
        seen_titles: set[str] = set()
        for h in self._document_map.headings:
            title = re.sub(r"^\d{1,3}\.\s*", "", h.text).strip()
            if title and title.lower() not in seen_titles:
                seen_titles.add(title.lower())
                completed_titles.append(title)
        if completed_titles:
            guard_lines = "\n".join(f"- {t}" for t in completed_titles[:12])
            warn = ""
            if self._state.section_rewrites:
                warn = (
                    f" WARNING: previous windows rewrote {self._state.section_rewrites} "
                    "already-completed section heading(s). That content already exists "
                    "in the document - repeating it counts as failure."
                )
            sections.append(
                "[COMPLETED - DO NOT REWRITE]\n"
                "These sections are already fully written. Do NOT write any of them "
                "again. Continue only with sections that are not in this list.\n"
                f"{guard_lines}{warn}"
            )

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

        # ── 5b. Truncation point: quote the exact dangling tail ──
        # Wall-hit windows can end mid-sentence. "Continue from exactly where
        # you left off" is not enough for a small model — it guesses, and
        # often guesses "start the next section" (observed live: a window
        # ended "...exercise control over their actions in a way that is
        # necessary" and the next window abandoned the sentence). Quoting the
        # verbatim tail makes the resume point unambiguous.
        _prev_out = (
            self._state.window_outputs[-1]["output"]
            if self._state.window_outputs else ""
        )
        _tail = _prev_out.rstrip()
        if _tail and _tail[-1] not in ".!?\"')\"]":
            _tail_words = _tail.split()
            if _tail_words:
                _frag = " ".join(_tail_words[-12:])
                sections.append(
                    "[TRUNCATION POINT]\n"
                    "The previous window was cut off mid-sentence. Its exact "
                    "final words were:\n"
                    f"'...{_frag}'\n"
                    "Begin your output by completing that exact sentence "
                    "first, then continue with the task."
                )

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

    def _get_expected_section_titles(self, task_intent: str) -> dict[int, str]:
        """Map section number -> title from a numbered list in the task text.

        Matches lines like "3. API Design and Versioning" so continuation
        directives can name the exact topic each missing section must cover.
        """
        titles: dict[int, str] = {}
        for m in re.finditer(
            r"^\s*(\d{1,3})[.)]\s+(.+?)\s*$", task_intent, re.MULTILINE,
        ):
            titles[int(m.group(1))] = m.group(2).strip()
        return titles

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
        # Within-window duplicate collapse: drop section blocks that rewrite
        # content already in the document (including earlier blocks of THIS
        # window) before anything ingests the output. The cross-window
        # near-duplicate guard fires only after the fact; this keeps the
        # recycled material out of the document and the document map.
        prior_text = self._outputs[-1] if self._outputs else ""
        output, _collapsed = collapse_duplicate_blocks(output, prior_text)
        if _collapsed:
            self._state.blocks_collapsed += _collapsed

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

        # Section-rewrite detection: headings that re-announce a section the
        # document map already holds. Each rewrite burns a generation window
        # on content that already exists and inflates repetition metrics.
        # The pre-update snapshot is compared against this window's raw
        # headings so a section is never counted against itself.
        raw_headings = [
            m.group(2).strip()
            for m in re.finditer(r"^(#{1,6})\s+(.+)$", output, re.MULTILINE)
        ]
        pre_nums: set[int] = set()
        pre_texts: set[str] = set()
        for h in self._document_map.headings:
            m = re.match(r"(\d{1,3})\.", h.text)
            if m:
                pre_nums.add(int(m.group(1)))
            pre_texts.add(re.sub(r"^\d{1,3}\.\s*", "", h.text).strip().lower())
        for ht in raw_headings:
            m = re.match(r"(\d{1,3})\.", ht)
            norm = re.sub(r"^\d{1,3}\.\s*", "", ht).strip().lower()
            if (m and int(m.group(1)) in pre_nums) or (norm and norm in pre_texts):
                self._state.section_rewrites += 1

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

        # Repetition guard: if this window reproduced the immediately preceding
        # window's raw output near-verbatim, the model has nothing more to
        # add — continuing would just keep regenerating the same text and
        # burn the continuation budget. Compared against
        # ``window_outputs`` (per-window raw records), not ``self._outputs``
        # (which gets progressively stitched/combined), so the comparison is
        # always "this window vs. the immediately preceding one," not
        # "this window vs. an ever-growing combined blob."
        _is_repeat = (
            len(self._state.window_outputs) > 1
            and bool(output.strip())
            and self._state.window_outputs[-1]["output"].strip()
            == self._state.window_outputs[-2]["output"].strip()
        )

        # Near-duplicate guard (paraphrase class): small models that run out
        # of instructed content do not copy the previous window verbatim —
        # they rephrase an EARLIER window (section rewrites with altered
        # wording). 6-gram overlap with any single prior window above the
        # threshold means the model is recycling material, not adding new
        # material, so the loop stops instead of accumulating repetition
        # window over window.
        # Threshold 0.50 (raised from 0.30 in 6.2.4): a CONCLUSION window
        # legitimately restates earlier sections and routinely overlaps a
        # prior window 0.3-0.45 — the old bar terminated the loop mid-run
        # exactly when the document was about to finish (observed live:
        # "repetition_detected" after the conclusion window, 1,657 words,
        # gate word-count fail). Measured anchors: real whole-window
        # rewrites sit at 0.66-0.82; legitimate new-content windows are
        # <= 0.45. The duplicate-block collapse remains the primary
        # recycling defence; the A-PR-7 low-novelty stop guard (3 strikes)
        # backstops runaway windows within the bounded budget.
        _is_near_duplicate = False
        if output.strip() and len(self._state.window_outputs) > 1:
            _cur_grams = _window_6grams(output)
            if _cur_grams:
                for _prev in self._state.window_outputs[:-1]:
                    _prev_grams = _window_6grams(_prev["output"])
                    if not _prev_grams:
                        continue
                    _overlap = len(_cur_grams & _prev_grams) / len(_cur_grams)
                    if _overlap >= 0.50:
                        _is_near_duplicate = True
                        break

        # A-PR-7: measure this window's novelty (novel-6-gram fraction vs all
        # prior windows) and maintain the low-novelty stop streak.  Only
        # windows where the trigger wants to continue on a natural stop
        # (gap_override) count — wall-hit (finish=length) continuations are
        # genuine truncation recovery, and a trigger-level stop ends the loop
        # on its own.
        if (
            self._config.max_low_novelty_stops > 0
            and self._state.trigger_result.should_continue
            and finish_reason is not None
            and finish_reason.lower() not in ("length", "max_tokens")
        ):
            _novelty = 1.0
            if output.strip() and len(self._state.window_outputs) > 1:
                _cur_grams = _window_6grams(output)
                if _cur_grams:
                    _seen_grams: set = set()
                    for _prev in self._state.window_outputs[:-1]:
                        _seen_grams |= _window_6grams(_prev["output"])
                    if _seen_grams:
                        _novelty = len(_cur_grams - _seen_grams) / len(_cur_grams)
            if _novelty < self._config.stop_novelty_threshold:
                self._stop_novelty_streak += 1
            else:
                self._stop_novelty_streak = 0

        # 3-way termination check
        # A-PR-7 decider guard: terminate when finish=stop continuations keep
        # firing on sub-threshold-novelty output regardless of the gap score
        # (gap_override would otherwise loop until the raw window cap).
        _force_low_novelty_stop = (
            self._config.max_low_novelty_stops > 0
            and self._stop_novelty_streak >= self._config.max_low_novelty_stops
        )
        if _is_repeat or _is_near_duplicate:
            self._state.finished = True
            self._state.termination_reason = "repetition_detected"
        elif _force_low_novelty_stop:
            self._state.finished = True
            self._state.termination_reason = "low_novelty_stop"
        elif self._state.gap_result.is_complete:
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
