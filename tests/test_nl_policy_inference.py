# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for natural-language safety policy inference (crp.policy.nl_infer)."""

from __future__ import annotations

from crp.policy.nl_infer import (
    infer_from_text,
    infer_from_text_with_llm,
    looks_like_natural_language,
)


class TestLooksLikeNaturalLanguage:
    def test_known_profile_names_are_not_natural_language(self) -> None:
        for name in ("strict", "balanced", "permissive", "research", "STRICT"):
            assert not looks_like_natural_language(name)

    def test_csp_directive_string_is_not_natural_language(self) -> None:
        assert not looks_like_natural_language(
            "default-src context; halt-on CRITICAL; require-grounding 0.70"
        )

    def test_plain_english_sentence_is_natural_language(self) -> None:
        assert looks_like_natural_language("never let it delete files without asking me")
        assert looks_like_natural_language("please be strict about privacy")

    def test_empty_string_is_not_natural_language(self) -> None:
        assert not looks_like_natural_language("")


class TestInferFromText:
    def test_destructive_action_requires_oversight(self) -> None:
        result = infer_from_text("never let it delete files without asking me first")
        assert result.settings.get("human_oversight") == "automatic"
        assert "destructive" in result.oversight_required
        assert result.matched_rules
        assert result.source == "keyword"

    def test_pii_block_instruction(self) -> None:
        result = infer_from_text("never leak personal information")
        assert result.settings.get("pii_detection") == "block"

    def test_pii_generic_mention_flags_only(self) -> None:
        result = infer_from_text("be aware of PII in the responses")
        assert result.settings.get("pii_detection") == "flag"

    def test_strict_tone_raises_grounding_bar(self) -> None:
        result = infer_from_text("be very strict and careful with facts")
        assert result.settings.get("grounding_verification") == 0.85

    def test_permissive_tone_lowers_grounding_bar(self) -> None:
        result = infer_from_text("keep it relaxed and permissive")
        assert result.settings.get("grounding_verification") == 0.5

    def test_unrecognised_text_returns_empty(self) -> None:
        result = infer_from_text("purple elephants dance quietly")
        assert result.settings == {}
        assert result.oversight_required == set()
        assert result.matched_rules == []

    def test_to_dict_is_json_safe(self) -> None:
        result = infer_from_text("never let it delete files without asking me")
        d = result.to_dict()
        assert isinstance(d["oversight_required"], list)
        assert d["source"] == "keyword"


class TestInferFromTextWithLLM:
    def test_llm_enrichment_merges_with_keyword_layer(self) -> None:
        def fake_model_call(prompt: str) -> str:
            return '{"grounding_verification": 0.95, "pii_detection": "block"}'

        result = infer_from_text_with_llm(
            "never let it delete files without asking me", fake_model_call,
        )
        # keyword layer still contributes oversight
        assert "destructive" in result.oversight_required
        # LLM layer contributes/overrides grounding + pii
        assert result.settings["grounding_verification"] == 0.95
        assert result.settings["pii_detection"] == "block"
        assert result.source == "keyword+llm"

    def test_llm_failure_falls_back_to_keyword_only(self) -> None:
        def failing_model_call(prompt: str) -> str:
            raise RuntimeError("provider unreachable")

        result = infer_from_text_with_llm(
            "never let it delete files without asking me", failing_model_call,
        )
        assert result.source == "keyword"
        assert "destructive" in result.oversight_required

    def test_llm_malformed_json_falls_back_to_keyword_only(self) -> None:
        def bad_model_call(prompt: str) -> str:
            return "not json at all"

        result = infer_from_text_with_llm("be strict", bad_model_call)
        assert result.source == "keyword"
        assert result.settings.get("grounding_verification") == 0.85

    def test_llm_unknown_keys_are_ignored(self) -> None:
        def fake_model_call(prompt: str) -> str:
            return '{"grounding_verification": 0.9, "delete_everything": true}'

        result = infer_from_text_with_llm("be careful", fake_model_call)
        assert "delete_everything" not in result.settings
        assert result.settings["grounding_verification"] == 0.9

    def test_llm_unknown_oversight_class_ignored(self) -> None:
        def fake_model_call(prompt: str) -> str:
            return '{"oversight_required": ["not-a-real-class", "destructive"]}'

        result = infer_from_text_with_llm("do something", fake_model_call)
        assert result.oversight_required == {"destructive"}
