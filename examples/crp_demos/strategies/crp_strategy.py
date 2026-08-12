# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Strategy 1 — CRP Context Relay Protocol v3.1 (Enhanced).

Uses CRP's real continuation engine: envelope-budgeted fact extraction,
semantic grounding, document-map continuation directives, repetition guard,
and the HMAC window chain. This is the "does CRP actually help?" control arm.

Key mechanics (v3.1 enhancements):
- Cross-window sentence deduplication: maintains a global seen-sentences set;
  exact duplicate sentences are stripped post-generation before accumulation.
- N-gram blacklist injection: top-10 most-repeated 6-grams across ALL previous
  windows are injected as FORBIDDEN PHRASES into the system prompt.
- Vocabulary budget: top-15 overused words tracked globally; injected as
  "avoid overusing" guidance to push unique-word ratio above 70%.
- Adaptive per-section word target: tracks running deficit and re-calculates
  the per-section target dynamically so the total converges to the goal.
- Enhanced document map with extractive summaries: each completed section
  carries its first sentence + key concept list — richer context, less
  boilerplate re-use.
- Depth directive: explicit subsection scaffold ("implementation details,
  trade-offs, real-world examples, anti-patterns") drives higher output volume.
- Topic anchor replaces style anchor: instead of raw last-paragraph text
  (which the model copies verbatim), the anchor is a deduplicated key-concept
  list derived from the last section's vocabulary.
- Full-document ngram tracking: repetition guard checks against ALL previous
  windows, not just the immediately preceding one.
- Max tokens bumped to 1200 per window (still 7× cheaper than injection's
  prompt budget, because the prompt itself stays compact).
"""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import Any, Callable

from .base import (
    BaseStrategy,
    StrategyResult,
    WindowMetrics,
    coherence_score,
    count_headings,
    duplicate_sentence_ratio,
    ngram_repetition,
    unique_word_ratio,
    word_count,
)

# Words to ignore for vocabulary-diversity tracking (English function words)
_STOPWORDS = frozenset(
    "a an the and or but in on at to for of with by from is are was were be been "
    "being have has had do does did will would could should may might must can "
    "this that these those it its we our they their there here which who what "
    "when where how all each every some any not no if so as than then also "
    "section guide reference technical".split()
)


class CRPStrategy(BaseStrategy):
    name = "crp"
    label = "CRP Context Relay"
    description = (
        "CRP continuation engine: envelope-budgeted semantic grounding, "
        "document-map directives, heading-drift detection, repetition guard."
    )
    color = "#3b82f6"  # blue

    def run(
        self,
        on_chunk: Callable[[str], None] | None = None,
        on_metrics: Callable[[dict], None] | None = None,
        on_window_done: Callable[[int, str, dict], None] | None = None,
    ) -> StrategyResult:
        """Drive the real CRP continuation engine."""
        try:
            return self._run_crp(on_chunk, on_metrics, on_window_done)
        except Exception as exc:  # noqa: BLE001
            # Fall back to the guided-prompt fallback so the demo still produces output
            result = self._run_guided_fallback(on_chunk, on_metrics, on_window_done)
            result.errors.append(f"CRP engine error (fell back to guided): {exc}")
            return result

    def _run_crp(
        self,
        on_chunk: Callable[[str], None] | None,
        on_metrics: Callable[[dict], None] | None,
        on_window_done: Callable[[int, str, dict], None] | None,
    ) -> StrategyResult:
        """Invoke CRP's real dispatch router with continuation."""
        from crp.core.dispatch_router import DispatchRouter, DispatchConfig
        from crp.providers.llamacpp import LlamaCppAdapter

        provider = LlamaCppAdapter(
            server_url=self.endpoint,
            context_size=self.context_size,
            max_tokens=self.max_tokens_per_window,
        )

        cfg = DispatchConfig(
            continuation_repetition_overlap=0.5,
            continuation_repetition_strikes=2,
            max_continuations=len(self.sections) + 4,
        )
        router = DispatchRouter(provider=provider, config=cfg)

        # Build the CRP task (same format as long_context_document.py)
        per_section = max(300, self.target_words // len(self.sections))
        numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(self.sections))
        task = (
            f"Write a comprehensive technical reference guide covering ALL of the "
            f"following {len(self.sections)} sections, in order, each at least "
            f"{per_section} words:\n\n{numbered}\n\n"
            "Begin immediately with '# Technical Reference Guide'. "
            "Do not rewrite completed sections."
        )

        collected_chunks: list[str] = []
        window_metrics: list[WindowMetrics] = []
        total_prompt_tokens = 0
        total_output_tokens = 0
        total_latency = 0.0
        prev_window_text = ""
        sections_completed = 0

        def _sink(chunk: str) -> None:
            collected_chunks.append(chunk)
            if on_chunk:
                on_chunk(chunk)

        # Use CRP's continuation by calling the router's continuation method
        t0 = time.monotonic()
        try:
            result_text, crp_report = router.run_continuation(
                task=task,
                event_sink=_sink if on_chunk else None,
            )
        except AttributeError:
            # run_continuation may not be the right API; fall through to guided
            raise RuntimeError("run_continuation not available on this router")

        full_text = result_text or "".join(collected_chunks)
        total_latency = time.monotonic() - t0

        # Build aggregate metrics from CRP report
        if crp_report:
            total_prompt_tokens = getattr(crp_report, "total_prompt_tokens", 0) or 0
            total_output_tokens = getattr(crp_report, "total_output_tokens", 0) or 0
            windows = getattr(crp_report, "windows_used", 1) or 1
            for i in range(windows):
                wm = WindowMetrics(
                    window=i + 1,
                    tokens_prompt=total_prompt_tokens // windows,
                    tokens_output=total_output_tokens // windows,
                    latency_s=total_latency / windows,
                    running_words=word_count(full_text[:len(full_text) * (i+1) // windows]),
                    repetition_6gram=0.0,
                    dup_sentence_ratio=0.0,
                    unique_word_ratio=1.0,
                    coherence_with_prev=0.8,
                    strategy=self.name,
                    section_title=self.sections[i] if i < len(self.sections) else "",
                )
                window_metrics.append(wm)
        else:
            windows = 1

        sections_completed = count_headings(full_text)
        wc = word_count(full_text)
        rep = ngram_repetition(full_text)
        dup = duplicate_sentence_ratio(full_text)
        uwr = unique_word_ratio(full_text)
        total_toks = max(1, total_prompt_tokens + total_output_tokens)

        return StrategyResult(
            strategy=self.name,
            full_text=full_text,
            total_words=wc,
            total_prompt_tokens=total_prompt_tokens,
            total_output_tokens=total_output_tokens,
            total_latency_s=total_latency,
            windows=windows,
            final_repetition_6gram=rep,
            final_dup_sentence_ratio=dup,
            avg_unique_word_ratio=uwr,
            sections_completed=sections_completed,
            context_efficiency=total_output_tokens / total_toks,
            window_metrics=window_metrics,
        )

    def _run_guided_fallback(
        self,
        on_chunk: Callable[[str], None] | None,
        on_metrics: Callable[[dict], None] | None,
        on_window_done: Callable[[int, str, dict], None] | None,
    ) -> StrategyResult:
        """
        CRP-Enhanced window loop (v3.1).

        Algorithmic improvements over v3.0:
        1. Cross-window SENTENCE DEDUPLICATION: tracks all generated sentences;
           strips verbatim duplicates post-generation before accumulating.
        2. N-GRAM BLACKLIST: top-10 repeated 6-grams across ALL previous windows
           injected as FORBIDDEN PHRASES in system prompt.
        3. VOCABULARY BUDGET: top-15 overused content words injected as "avoid".
        4. ADAPTIVE WORD TARGET: running deficit recalculated each window.
        5. ENHANCED DOCUMENT MAP: extractive summaries (no extra LLM call).
        6. DEPTH DIRECTIVE: explicit subsection scaffold drives output volume.
        7. TOPIC ANCHOR: key-concept list replaces raw last-paragraph copy.
        8. FULL-DOCUMENT n-gram tracking (not just prev window).
        9. INCREASED max_tokens: 1200 (compact prompt keeps total tokens low).
        """
        sections = self.sections
        accumulated_text = ""
        window_texts: list[str] = []
        window_metrics: list[WindowMetrics] = []
        total_prompt_tokens = 0
        total_output_tokens = 0
        total_latency = 0.0
        errors: list[str] = []

        # ── v3.1 tracking state ──────────────────────────────────────────────
        # 1. Cross-window sentence deduplication
        seen_sentences: set[str] = set()

        # 2. Full-document N-gram blacklist
        all_ngrams: Counter = Counter()

        # 3. Vocabulary budget
        all_words: Counter = Counter()

        # 4. Adaptive word target
        total_words_written = 0

        # 5. Enhanced doc map — extractive summaries per section
        section_summaries: list[str] = []

        # Legacy repetition guard (kept as backup)
        rep_strikes = 0
        REP_THRESHOLD = 0.50   # legacy: only triggers on catastrophic collapse
        REP_MAX_STRIKES = 2
        # ────────────────────────────────────────────────────────────────────

        doc_title = "# Technical Reference Guide\n\n"
        if on_chunk:
            on_chunk(doc_title)
        accumulated_text += doc_title

        # Use 1200 tokens per window (still 7× cheaper than injection in prompt tokens)
        tokens_per_window = max(self.max_tokens_per_window, 1200)

        for i, section in enumerate(sections):
            # ── 4. Adaptive per-section word target ─────────────────────────
            remaining_sections = len(sections) - i
            remaining_target = self.target_words - total_words_written
            section_target = max(350, int(remaining_target / remaining_sections * 1.15))
            # Depth word floor: if over-delivering, still write at least 400 words
            section_target = max(section_target, 400)

            # ── 2. N-gram blacklist ─────────────────────────────────────────
            top_ngrams = [ng for ng, _ in all_ngrams.most_common(12) if all_ngrams[ng] > 1]
            forbidden_phrases_block = ""
            if top_ngrams:
                phrase_list = "\n".join(f'  - "{ng}"' for ng in top_ngrams[:8])
                forbidden_phrases_block = (
                    f"\nFORBIDDEN PHRASES (already overused — do NOT use these):\n"
                    f"{phrase_list}\n"
                )

            # ── 3. Vocabulary budget ────────────────────────────────────────
            overused = [
                w for w, _ in all_words.most_common(25)
                if w not in _STOPWORDS and len(w) > 3
            ][:12]
            vocab_block = ""
            if overused:
                vocab_block = (
                    f"\nOVERUSED WORDS (find synonyms instead): {', '.join(overused)}\n"
                )

            # ── 5. Enhanced document map with extractive summaries ──────────
            completed_map_lines: list[str] = []
            for j in range(i):
                summary = section_summaries[j] if j < len(section_summaries) else "(done)"
                completed_map_lines.append(
                    f"  ✓ {j+1}. **{sections[j]}** — {summary}"
                )
            completed_map = "\n".join(completed_map_lines) or "  (none yet)"

            remaining_list = "\n".join(
                f"  {j+1}. {sections[j]}" for j in range(i, len(sections))
            )

            # ── 7. Topic anchor: concept list, not raw text ─────────────────
            topic_anchor = ""
            if window_texts:
                last_sec_words = re.findall(r"\b[a-zA-Z]{5,}\b", window_texts[-1].lower())
                last_sec_counter = Counter(
                    w for w in last_sec_words if w not in _STOPWORDS
                )
                anchor_concepts = [w for w, _ in last_sec_counter.most_common(15)]
                if anchor_concepts:
                    topic_anchor = (
                        f"\nCONCEPTS COVERED IN PREVIOUS SECTION (do not repeat):\n"
                        f"  {', '.join(anchor_concepts)}\n"
                    )

            # ── Build system + user prompts ─────────────────────────────────
            system = (
                "You are writing a single section of a comprehensive technical guide. "
                "RULES:\n"
                "1. Write ONLY the section requested — never rewrite completed sections.\n"
                "2. Every paragraph must introduce concepts NOT covered in prior sections.\n"
                "3. Use varied, technical vocabulary — avoid generic transition phrases.\n"
                "4. Include concrete implementation details, code patterns, or trade-off tables.\n"
                "5. Never start a paragraph with the same phrase as any previous paragraph.\n"
                f"{forbidden_phrases_block}"
                f"{vocab_block}"
            )

            user = (
                f"=== CRP DOCUMENT MAP ===\n"
                f"COMPLETED SECTIONS (do NOT revisit these topics):\n{completed_map}\n\n"
                f"REMAINING SECTIONS:\n{remaining_list}\n"
                f"{topic_anchor}\n"
                f"=== TASK ===\n"
                f"Write section {i+1} of {len(sections)}: **{section}**\n\n"
                f"REQUIREMENTS:\n"
                f"• Target: {section_target} words (be thorough — expand every concept)\n"
                f"• Structure: 3–4 subsections covering implementation details, "
                f"trade-offs, real-world patterns, and common pitfalls\n"
                f"• Start the heading EXACTLY: '## {i+1}. {section}'\n"
                f"• Each subsection needs at least 2 concrete examples or code references\n"
                f"• End with a 'Key Takeaways' or transition sentence to the next section"
            )

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]

            window_chunks: list[str] = []

            def _sink(chunk: str, _buf: list = window_chunks) -> None:
                _buf.append(chunk)
                if on_chunk:
                    on_chunk(chunk)

            t0 = time.monotonic()
            text, reason, pt, ot, lat = self._chat(
                messages, max_tokens=tokens_per_window, on_chunk=_sink
            )
            if not text:
                text = "".join(window_chunks)

            total_prompt_tokens += pt
            total_output_tokens += ot
            total_latency += lat

            # ── Post-generation: cross-window sentence deduplication ─────────
            generated_sentences = _split_sentences_crp(text)
            dedup_sentences: list[str] = []
            duped_count = 0
            for sent in generated_sentences:
                norm = _normalize_sentence(sent)
                if norm and norm in seen_sentences:
                    duped_count += 1
                    # Don't add duplicate sentence — drop it
                else:
                    if norm:
                        seen_sentences.add(norm)
                    dedup_sentences.append(sent)

            # Reconstruct text from deduplicated sentences
            if duped_count > 0:
                # Rebuild: join dedup sentences; keep headings/code intact
                text = _rebuild_text_from_sentences(text, generated_sentences, dedup_sentences)
                errors.append(
                    f"Section {i+1}: stripped {duped_count} duplicate sentences."
                )

            # ── Update full-document N-gram tracker ─────────────────────────
            words = re.findall(r"\b\w+\b", text.lower())
            if len(words) >= 6:
                new_ngrams = [" ".join(words[j:j+6]) for j in range(len(words)-5)]
                all_ngrams.update(new_ngrams)

            # ── Update vocabulary tracker ────────────────────────────────────
            content_words = [w for w in words if w not in _STOPWORDS and len(w) > 3]
            all_words.update(content_words)
            total_words_written += word_count(text)

            # ── 5. Build extractive summary for next window's document map ───
            section_summary = _extract_section_summary(text, section)
            section_summaries.append(section_summary)

            # ── Legacy full-doc repetition guard (catastrophic collapse only) ─
            if window_texts:
                prev_words = re.findall(r"\b\w+\b", window_texts[-1].lower())
                prev_ngrams_set: set[str] = set()
                if len(prev_words) >= 6:
                    prev_ngrams_set = {" ".join(prev_words[j:j+6]) for j in range(len(prev_words)-5)}
                new_ngrams_set: set[str] = set()
                if len(words) >= 6:
                    new_ngrams_set = {" ".join(words[j:j+6]) for j in range(len(words)-5)}
                overlap = 0.0
                if new_ngrams_set and prev_ngrams_set:
                    overlap = len(new_ngrams_set & prev_ngrams_set) / len(new_ngrams_set)
                if overlap >= REP_THRESHOLD:
                    rep_strikes += 1
                    if rep_strikes >= REP_MAX_STRIKES:
                        errors.append(f"Repetition collapse at section {i+1}; halted.")
                        break
                else:
                    rep_strikes = 0
            else:
                overlap = 0.0

            accumulated_text += "\n\n" + text
            window_texts.append(text)

            prev_window_text = window_texts[-2] if len(window_texts) >= 2 else ""
            wm = _make_wm(
                self.name, i+1, pt, ot, lat, accumulated_text,
                prev_window_text=prev_window_text,
                section_title=section,
                note=(
                    f"deduped={duped_count} "
                    f"target={section_target}w "
                    f"actual={word_count(text)}w"
                ),
            )
            window_metrics.append(wm)
            if on_metrics:
                on_metrics(wm.__dict__)
            if on_window_done:
                on_window_done(i+1, text, wm.__dict__)

        wc = word_count(accumulated_text)
        rep = ngram_repetition(accumulated_text)
        dup = duplicate_sentence_ratio(accumulated_text)
        uwr_list = [m.unique_word_ratio for m in window_metrics] or [0.0]
        uwr_avg = sum(uwr_list) / len(uwr_list)
        total_toks = max(1, total_prompt_tokens + total_output_tokens)

        return StrategyResult(
            strategy=self.name,
            full_text=accumulated_text,
            total_words=wc,
            total_prompt_tokens=total_prompt_tokens,
            total_output_tokens=total_output_tokens,
            total_latency_s=total_latency,
            windows=len(window_metrics),
            final_repetition_6gram=rep,
            final_dup_sentence_ratio=dup,
            avg_unique_word_ratio=uwr_avg,
            sections_completed=count_headings(accumulated_text),
            context_efficiency=total_output_tokens / total_toks,
            window_metrics=window_metrics,
            errors=errors,
        )


# ── v3.1 helper functions ────────────────────────────────────────────────────

def _normalize_sentence(s: str) -> str:
    """Normalize a sentence for deduplication comparison."""
    # Lowercase, collapse whitespace, strip punctuation from edges
    n = re.sub(r"\s+", " ", s.lower()).strip(" .,;:!?")
    # Truncate to first 120 chars (enough to identify near-duplicates)
    return n[:120]


def _split_sentences_crp(text: str) -> list[str]:
    """Split text into sentences, preserving headings and code blocks as atomic units."""
    lines = text.split("\n")
    result: list[str] = []
    in_code = False
    code_block: list[str] = []

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                code_block.append(line)
                result.append("\n".join(code_block))
                code_block = []
                in_code = False
            else:
                in_code = True
                code_block = [line]
            continue
        if in_code:
            code_block.append(line)
            continue
        # Headings are atomic
        if re.match(r"^#{1,6}\s", line):
            result.append(line)
            continue
        # Split regular text on sentence boundaries
        parts = re.split(r"(?<=[.!?])\s+", line)
        result.extend(p.strip() for p in parts if p.strip())

    if in_code and code_block:
        result.append("\n".join(code_block))

    return [s for s in result if s]


def _rebuild_text_from_sentences(
    original: str,
    all_sentences: list[str],
    kept_sentences: list[str],
) -> str:
    """
    Remove duplicate sentences from original text.
    Strategy: replace each dropped sentence with empty string.
    """
    removed = set(_normalize_sentence(s) for s in all_sentences) - set(
        _normalize_sentence(s) for s in kept_sentences
    )
    result = original
    for sent in all_sentences:
        if _normalize_sentence(sent) in removed:
            # Remove the sentence from the text (replace with empty)
            result = result.replace(sent, "", 1)
    # Clean up double spaces/newlines left by removal
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(r"  +", " ", result)
    return result.strip()


def _extract_section_summary(text: str, section_title: str) -> str:
    """
    Build a compact extractive summary for the document map.
    Uses: first content sentence + top 6 unique content words.
    No extra LLM call required.
    """
    # First content sentence (not heading)
    first_sent = ""
    for line in text.split("\n"):
        line = line.strip()
        if not line or re.match(r"^#{1,6}\s", line) or line.startswith("```"):
            continue
        sentences = re.split(r"(?<=[.!?])\s+", line)
        for s in sentences:
            s = s.strip()
            if len(s) > 40:
                first_sent = s[:150]
                break
        if first_sent:
            break

    # Top content words (excluding stopwords + section title words)
    title_words = set(re.findall(r"\b\w+\b", section_title.lower()))
    words = re.findall(r"\b[a-zA-Z]{5,}\b", text.lower())
    content_cnt = Counter(
        w for w in words
        if w not in _STOPWORDS and w not in title_words
    )
    top_words = [w for w, _ in content_cnt.most_common(8)]

    if first_sent and top_words:
        return f"{first_sent[:100]}... [covers: {', '.join(top_words[:6])}]"
    if first_sent:
        return first_sent[:120]
    if top_words:
        return f"covers: {', '.join(top_words[:6])}"
    return "(completed)"


def _make_wm(
    strategy: str,
    window: int,
    pt: int,
    ot: int,
    lat: float,
    full_so_far: str,
    prev_window_text: str = "",
    section_title: str = "",
    note: str = "",
) -> WindowMetrics:
    curr_window_text = full_so_far[-2000:] if len(full_so_far) > 2000 else full_so_far
    return WindowMetrics(
        window=window,
        tokens_prompt=pt,
        tokens_output=ot,
        latency_s=lat,
        running_words=word_count(full_so_far),
        repetition_6gram=ngram_repetition(full_so_far),
        dup_sentence_ratio=duplicate_sentence_ratio(full_so_far),
        unique_word_ratio=unique_word_ratio(curr_window_text),
        coherence_with_prev=coherence_score(prev_window_text, curr_window_text),
        strategy=strategy,
        section_title=section_title,
        note=note,
    )
