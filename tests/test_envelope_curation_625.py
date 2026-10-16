# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for 6.2.5 envelope root-cause fixes: KEY FINDINGS curation, style
anchor fragment skipping, and completed-section requirement filtering.

Root cause (measured live, 2026-10-16): every continuation envelope carried
274-349 words of uncurated "findings" (headings, fragments, verbatim
sentences) — larger than the window's own ~500-word output budget — and a
style anchor that ended mid-sentence in all 7 windows. The model mirrored
the recap-shaped envelope: summary drift + verbatim phrase recycling.
"""

from __future__ import annotations

from types import SimpleNamespace

from crp.continuation.manager import ContinuationManager


def _fact(text: str, confidence: float = 0.9) -> SimpleNamespace:
    return SimpleNamespace(text=text, confidence=confidence)


class TestKeyFindingsCuration:
    def _envelope_with_facts(self, facts: list[SimpleNamespace]) -> str:
        mgr = ContinuationManager()
        mgr.process_window(
            task_intent="write a guide",
            output=(
                "## 1. Epistemology\n"
                "Epistemology is the branch of philosophy that examines the "
                "nature, origin, and limits of human knowledge and belief.\n"
            ),
            finish_reason="length",
            output_tokens=300,
            facts=[],
            window_id="w1",
        )
        mgr._accumulated_facts.extend(facts)
        return mgr.build_continuation_envelope("write a guide")

    def test_headings_and_fragments_excluded(self) -> None:
        env = self._envelope_with_facts([
            _fact("Epistemology", 0.99),                      # heading text
            _fact("The Nature of Knowledge", 0.98),           # heading text
            _fact("Short.", 0.97),                            # too short
            _fact("A fragment with no ending punctuat", 0.96),  # no terminator
            _fact(                                             # multi-line
                "First line\n## 1. Epistemology", 0.95),
            _fact(  # full sentence, should survive
                "Epistemology is the branch of philosophy that examines "
                "the nature and origin of human knowledge and belief "
                "formation in detail.", 0.7),
        ])
        assert "[KEY FINDINGS" in env
        findings = env.split("[KEY FINDINGS FROM PRIOR SECTIONS]\n")[1]
        findings = findings.split("\n\n[")[0]
        assert "The Nature of Knowledge" not in findings
        assert "Short." not in findings
        assert "no ending punctuat" not in findings
        assert "First line" not in findings
        assert "branch of philosophy that examines" in findings

    def test_cap_eight_and_dedupe(self) -> None:
        facts = [
            _fact(
                f"This is a distinct full sentence about topic number {i} "
                "written with enough words to pass the length filter here.",
                0.5 + i * 0.01,
            )
            for i in range(12)
        ]
        facts.append(_fact(facts[0].text, 0.99))  # duplicate
        env = self._envelope_with_facts(facts)
        section = env.split("[KEY FINDINGS FROM PRIOR SECTIONS]\n")[1]
        section = section.split("\n\n[")[0]
        lines = [ln for ln in section.split("\n") if ln.startswith("- ")]
        assert len(lines) == 8
        assert len({ln for ln in lines}) == 8


class TestStyleAnchorSkipsFragments:
    def test_mid_sentence_tail_uses_last_complete_paragraph(self) -> None:
        mgr = ContinuationManager()
        out = (
            "## 1. Epistemology\n"
            "Knowledge is structured belief. Justification comes from many "
            "sources including perception and memory of past events.\n"
            "\n"
            "However, the deeper problem is that justification can fail "
            "when perception is"
        )
        anchor = mgr._extract_style_anchor(out)
        assert anchor
        assert anchor.rstrip()[-1] in ".!?"
        assert "when perception is" not in anchor

    def test_all_fragments_returns_empty(self) -> None:
        mgr = ContinuationManager()
        assert mgr._extract_style_anchor("a dangling fragment with no end") == ""

    def test_clean_output_uses_last_paragraph(self) -> None:
        mgr = ContinuationManager()
        out = (
            "## 1. Epistemology\n"
            "First paragraph ends here.\n"
            "\n"
            "Second paragraph is complete and ends cleanly."
        )
        anchor = mgr._extract_style_anchor(out)
        assert "ends cleanly." in anchor


class TestCompletedRequirementFiltering:
    def test_completed_section_word_requirements_dropped(self) -> None:
        mgr = ContinuationManager()
        mgr.process_window(
            task_intent="write a guide",
            output=(
                "## 1. Epistemology\n"
                "Knowledge is structured belief with justification from "
                "perception, memory, reason, and testimony of other people.\n"
            ),
            finish_reason="length",
            output_tokens=300,
            facts=[],
            window_id="w1",
        )
        gap = SimpleNamespace(unfulfilled=[
            SimpleNamespace(
                text="## Section 1: Epistemology - Minimum 400 words.",
            ),
            SimpleNamespace(
                text="## Section 2: Consciousness - Minimum 400 words.",
            ),
            SimpleNamespace(
                text="After the final numbered section, add a short "
                     "'## Conclusion' summarising the guide",
            ),
        ])
        env = mgr.build_continuation_envelope("write a guide", gap_result=gap)
        assert "Section 1: Epistemology - Minimum" not in env
        assert "Section 2: Consciousness - Minimum" in env
        assert "## Conclusion" in env
