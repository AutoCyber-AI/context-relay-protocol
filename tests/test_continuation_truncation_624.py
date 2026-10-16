# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for 6.2.4 continuation fixes: the [TRUNCATION POINT] envelope
section, the raised near-duplicate guard bar, and dangling-sentence trimming
in the demo strategy's document assembly.

Artifacts calibrated on the user's 2026-10-16 run: a window ended
"...exercise control over their actions in a way that is necessary" and the
next window abandoned the sentence; the run then stopped at 1,657 words when
the 0.30 near-duplicate guard fired on the conclusion window (which
legitimately restates earlier sections at 0.3-0.45 overlap).
"""

from __future__ import annotations

from crp.continuation.manager import ContinuationManager
from examples.crp_demos.strategies.crp_strategy import _trim_dangling_sentence


class TestTrimDanglingSentence:
    def test_mid_sentence_cut_back_to_last_period(self) -> None:
        text = (
            "Free will is the capacity to choose. It implies control "
            "over actions in a way that is necessary"
        )
        trimmed, cut = _trim_dangling_sentence(text)
        assert cut is True
        assert trimmed.endswith("choose.\n")
        assert "necessary" not in trimmed

    def test_complete_segment_untouched(self) -> None:
        text = "Free will is the capacity to choose. It implies control.\n"
        trimmed, cut = _trim_dangling_sentence(text)
        assert cut is False
        assert trimmed == text

    def test_question_and_exclamation_endings(self) -> None:
        for punct in ("?", "!"):
            text = f"Does free will exist{punct}"
            trimmed, cut = _trim_dangling_sentence(text)
            assert cut is False
            assert trimmed == text

    def test_quote_after_period_is_complete(self) -> None:
        text = 'He wrote "control is necessary."\n'
        _, cut = _trim_dangling_sentence(text)
        assert cut is False

    def test_single_unterminated_sentence_kept(self) -> None:
        text = "a fragment with no sentence end at all"
        trimmed, cut = _trim_dangling_sentence(text)
        assert cut is False
        assert trimmed == text


class TestTruncationPointEnvelope:
    def _process_mid_sentence_window(self, mgr: ContinuationManager) -> None:
        mgr.process_window(
            task_intent="write a technical reference guide",
            output=(
                "## 3. Determinism and Moral Responsibility\n"
                "Free will is generally understood as the capacity of people "
                "to choose between courses of action, exercising control in "
                "a way that is necessary"
            ),
            finish_reason="length",
            output_tokens=300,
            facts=[],
            window_id="w1",
        )

    def test_envelope_quotes_dangling_tail(self) -> None:
        mgr = ContinuationManager()
        self._process_mid_sentence_window(mgr)
        envelope = mgr.build_continuation_envelope("write a technical reference guide")
        assert "[TRUNCATION POINT]" in envelope
        assert "a way that is necessary" in envelope
        assert "completing that exact sentence" in envelope

    def test_envelope_omitted_when_window_ended_cleanly(self) -> None:
        mgr = ContinuationManager()
        mgr.process_window(
            task_intent="write a technical reference guide",
            output=(
                "## 3. Determinism and Moral Responsibility\n"
                "Free will is understood as the capacity of people to choose "
                "between courses of action, exercising control responsibly."
            ),
            finish_reason="length",
            output_tokens=300,
            facts=[],
            window_id="w1",
        )
        envelope = mgr.build_continuation_envelope("write a technical reference guide")
        assert "[TRUNCATION POINT]" not in envelope


class TestNearDuplicateGuardBar:
    def _window(self, mgr: ContinuationManager, output: str, wid: str) -> None:
        mgr.process_window(
            task_intent="write a technical reference guide",
            output=output,
            finish_reason="length",
            output_tokens=300,
            facts=[],
            window_id=wid,
        )

    def test_conclusion_level_overlap_does_not_terminate(self) -> None:
        """A conclusion restating earlier sections overlaps ~0.3-0.45 with
        a prior window — under the 0.50 bar it must NOT stop the loop
        (6.2.3 fired 'repetition_detected' here and stranded 1,657 words)."""
        mgr = ContinuationManager()
        self._window(
            mgr,
            "## 4. Caching Strategies\n"
            "Caching stores frequently accessed data for fast retrieval. "
            "In-memory caches like Redis minimize disk operations while "
            "invalidation policies keep distributed copies consistent over "
            "time across every node in the cluster.\n",
            "w1",
        )
        self._window(
            mgr,
            "## Conclusion\n"
            "This guide covered caching strategies, in-memory caches like "
            "Redis, and invalidation policies that keep distributed copies "
            "consistent across every node in the cluster over time.\n",
            "w2",
        )
        # NOTE: the loop may still finish here via an independent signal
        # (zero facts -> info_flow_dead in this minimal harness) — what
        # matters is that the near-duplicate guard itself did not fire.
        # The 3-way check evaluates _is_near_duplicate FIRST, so a
        # "repetition_detected" reason proves the guard fired.
        assert mgr._state.termination_reason != "repetition_detected"

    def test_whole_window_rewrite_still_terminates(self) -> None:
        """Real rewrites measure 0.66-0.82 and must still stop the loop."""
        section = (
            "## 3. Data Modeling and Storage\n"
            "Data modeling defines the structure of information systems. "
            "Relational models use tables with primary and foreign keys, "
            "while sharding partitions data across nodes for scalability.\n"
        )
        mgr = ContinuationManager()
        self._window(mgr, section, "w1")
        self._window(
            mgr,
            "## Section 3: Data Modeling and Storage\n"
            "Data modeling defines the structure of information systems. "
            "Relational models use tables with primary and foreign keys, "
            "while sharding partitions data across nodes for scalability.\n",
            "w2",
        )
        assert mgr._state.finished
        assert mgr._state.termination_reason == "repetition_detected"
