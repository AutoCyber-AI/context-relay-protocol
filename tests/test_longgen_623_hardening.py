# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for 6.2.3 long-gen hardening: stacked heading prefixes, paragraph-
level recycling inside kept blocks, and numbered-line section-title parsing.

Artifacts calibrated on a real user run (2026-10-16, qwen2.5-7b-instruct,
custom 'Philosophy & Cognitive Science' topic): a re-announced section
survived as '3. 2. Language, Perception...', and the conclusion window
appended recycled fragments with no markdown headings of their own.
"""

from __future__ import annotations

from crp.continuation.manager import (
    _normalize_heading,
    collapse_duplicate_blocks,
)
from examples.crp_demos.longgen_backend import parse_section_titles


class TestStackedHeadingPrefixes:
    def test_double_numbered_prefix_collapses(self) -> None:
        a = _normalize_heading("## 2. Language, Perception, and the Construction of Objective Reality")
        b = _normalize_heading("### 3. 2. Language, Perception, and the Construction of Objective Reality")
        assert a == b == "language perception and the construction of objective reality"

    def test_outline_depth_prefix_collapses(self) -> None:
        a = _normalize_heading("## 5. Technological Rationalism and the Alienation of Modern Society")
        b = _normalize_heading("##### 5.4. Technological Rationalism and the Alienation of Modern Society")
        assert a == b

    def test_single_prefix_still_works(self) -> None:
        assert _normalize_heading("## Section 3: Data Modeling") == "data modeling"

    def test_renumbered_section_rewrite_is_dropped(self) -> None:
        """The 2026-10-16 artifact: window 3 re-announced section 2 as
        '3. 2. ...', rewording the intro but continuing the exact sentence
        the previous window was cut off mid-way ('...but a construct based').
        Heading match must fire after prefix normalization."""
        prior = (
            "## 1. Foundational Epistemology and the Nature of Human Consciousness\n"
            "Epistemology is the branch of philosophy that examines the "
            "nature, origin, and limits of knowledge. It explores different "
            "types of knowledge: propositional knowledge about facts, "
            "practical knowledge in the form of skills, and knowledge by "
            "acquaintance as a familiarity through experience.\n"
        )
        window = (
            "## 2. Language, Perception, and the Construction of Objective Reality\n"
            "The Social Construction of Reality, as proposed by Peter L. "
            "Berger and Thomas Luckmann (1966), suggests that social groups "
            "create concepts through interaction, which become habitualized "
            "behaviors and institutionalized roles within society over time.\n"
            "Objective reality is not an inherent property of the external "
            "world but a construct based\n"
            "### 3. 2. Language, Perception, and the Construction of Objective Reality\n"
            "Language, perception, and the construction of objective reality "
            "are fundamental aspects in understanding how humans interact "
            "with their environment and form knowledge about the world.\n"
            "Objective reality is not an inherent property of the external "
            "world but a construct based on collective agreement and shared "
            "understandings, built through language over long time periods.\n"
        )
        cleaned, dropped = collapse_duplicate_blocks(window, prior)
        assert dropped >= 1
        assert "fundamental aspects in understanding how humans interact" not in cleaned


class TestParagraphRecyclingInsideKeptBlock:
    _PRIOR = (
        "## 4. Determinism, Free Will, and the Boundaries of Moral Responsibility\n"
        "Determinism asserts that every event is necessitated by antecedent "
        "events and conditions together with the laws of nature. In the "
        "context of human behavior, this means that all actions are "
        "ultimately caused by preceding physical or psychological states.\n"
    )

    def test_recycled_fragment_after_conclusion_is_dropped(self) -> None:
        """The 2026-10-16 artifact: the conclusion block ended with
        paragraphs recycling earlier sections as plain text (no headings)."""
        window = (
            "## Conclusion\n"
            "This guide covered epistemology, language, determinism, and "
            "technological rationalism, showing how each shapes modern "
            "understanding of cognition and society for engineers today.\n"
            "\n"
            "Determinism posits that every event is necessitated by "
            "antecedent events and conditions together with the laws of "
            "nature. In the context of human behavior, this means that all "
            "actions are ultimately caused by preceding physical or "
            "psychological states, rendering free will an illusion.\n"
        )
        cleaned, dropped = collapse_duplicate_blocks(window, self._PRIOR)
        assert dropped >= 1
        assert "rendering free will an illusion" not in cleaned
        assert "This guide covered epistemology" in cleaned

    def test_genuine_conclusion_paragraphs_survive(self) -> None:
        window = (
            "## Conclusion\n"
            "This guide covered epistemology, language, determinism, and "
            "technological rationalism, showing how each shapes modern "
            "understanding of cognition and society for engineers today.\n"
        )
        cleaned, dropped = collapse_duplicate_blocks(window, self._PRIOR)
        assert dropped == 0
        assert cleaned == window


class TestParseSectionTitles:
    _USER_PASTE = [
        "Conduct a comprehensive and cohesive informative text that covers "
        "the following sections about the topic 'Philosophy & Cognitive Science'",
        "",
        "1. Foundational Epistemology and the Nature of Human Consciousness",
        "2. Language, Perception, and the Construction of Objective Reality",
        "3. Determinism, Free Will, and the Boundaries of Moral Responsibility",
        "4. Technological Rationalism and the Alienation of Modern Society",
        "5. Future Philosophical Horizons in the Age of Synthetic Cognition",
    ]

    def test_numbered_paste_ignores_preamble(self) -> None:
        titles = parse_section_titles(self._USER_PASTE, 5)
        assert titles == [
            "Foundational Epistemology and the Nature of Human Consciousness",
            "Language, Perception, and the Construction of Objective Reality",
            "Determinism, Free Will, and the Boundaries of Moral Responsibility",
            "Technological Rationalism and the Alienation of Modern Society",
            "Future Philosophical Horizons in the Age of Synthetic Cognition",
        ]

    def test_limit_caps_numbered_titles(self) -> None:
        titles = parse_section_titles(self._USER_PASTE, 3)
        assert len(titles) == 3
        assert "Determinism" in titles[2]

    def test_unnumbered_lines_keep_verbatim_behaviour(self) -> None:
        titles = parse_section_titles(
            ["The economics of renewable energy", "Grid storage technologies"],
            5,
        )
        assert titles == [
            "The economics of renewable energy",
            "Grid storage technologies",
        ]

    def test_mixed_paste_without_any_numbers_is_verbatim(self) -> None:
        titles = parse_section_titles(
            ["An unnumbered preamble line", "A plain section title"], 5,
        )
        assert titles == ["An unnumbered preamble line", "A plain section title"]

    def test_empty_input(self) -> None:
        assert parse_section_titles([], 5) == []
        assert parse_section_titles(["", "  "], 5) == []


class TestSmallReannouncedBlocks:
    """The 6.2.3 live run's tail: 27- and 37-word re-announced blocks
    (0.29/0.76 overlap) sat under _BLOCK_MIN_WORDS and bypassed every dup
    check. Heading re-announcement must be checked at ANY size."""

    _PRIOR_DOC = (
        "## 5. Future Philosophical Horizons in the Age of Synthetic Cognition\n"
        "### Determinism vs. Free Will in Synthetic Cognition\n"
        "The debates surrounding determinism and free will have profound "
        "implications for moral responsibility in an age of synthetic "
        "cognition, where autonomous systems make decisions that affect "
        "human lives and societies in ways we are only beginning to grasp.\n"
    )

    def test_small_reannounced_block_with_overlap_is_dropped(self) -> None:
        window = (
            "## Conclusion\n"
            "This guide covered the foundations and future horizons of "
            "philosophy in the age of synthetic cognition for engineers.\n"
            "#### Determinism vs. Free Will in Synthetic Cognition\n"
            "The debates surrounding determinism and free will have profound "
            "implications for moral responsibility in an age of synthetic "
            "cognition, where autonomous systems make decisions.\n"
        )
        cleaned, dropped = collapse_duplicate_blocks(window, self._PRIOR_DOC)
        assert dropped >= 1
        assert "Determinism vs. Free Will" not in cleaned

    def test_small_fresh_block_survives(self) -> None:
        window = (
            "## Conclusion\n"
            "This guide covered the foundations and future horizons.\n"
            "#### A Glossary of Terms\n"
            "Compatibilism holds that free will and determinism can coexist.\n"
        )
        cleaned, dropped = collapse_duplicate_blocks(window, self._PRIOR_DOC)
        assert dropped == 0
        assert "A Glossary of Terms" in cleaned


class TestPostConclusionPruning:
    """After a '## Conclusion' block, a re-announced heading or >= 0.35
    overlap block is epilogue recycling (6.2.3 live run: 0.29/0.42/0.76
    overlap fragments after the conclusion). New epilogue content is kept."""

    _PRIOR_DOC = (
        "## 2. Language, Perception, and the Construction of Objective Reality\n"
        "Perceptions construct objective reality through collective "
        "agreement. Language shapes what we perceive and how we categorize "
        "the world around us in everyday social interaction.\n"
    )

    def test_reannounced_epilogue_block_dropped(self) -> None:
        window = (
            "## Conclusion\n"
            "This guide covered language, perception, and reality at length "
            "for a technical audience of senior engineers and researchers.\n"
            "#### Perceptions Construct Objective Reality\n"
            "Perceptions construct objective reality through collective "
            "agreement. Language shapes what we perceive and how we "
            "categorize the world around us.\n"
        )
        cleaned, dropped = collapse_duplicate_blocks(window, self._PRIOR_DOC)
        assert dropped >= 1
        assert cleaned.count("Perceptions Construct Objective Reality") == 0

    def test_new_epilogue_content_kept(self) -> None:
        window = (
            "## Conclusion\n"
            "This guide covered language, perception, and reality at length "
            "for a technical audience of senior engineers and researchers.\n"
            "#### Further Reading\n"
            "Berger and Luckmann's later essays expand on the construction "
            "of reality with case studies from science and technology that "
            "reward a careful reading.\n"
        )
        cleaned, dropped = collapse_duplicate_blocks(window, self._PRIOR_DOC)
        assert dropped == 0
        assert "Further Reading" in cleaned
