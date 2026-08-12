# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for No-Code Governance Translator (SPEC-048 Part A)."""

from __future__ import annotations

import pytest

from crp.comply.no_code import (
    NoCodeTranslatorError,
    express_requirement,
    generate_config,
    generate_code_change,
    refuse_to_fabricate,
)


class TestExpressRequirement:
    def test_valid_intent_returns_capabilities(self) -> None:
        result = express_requirement({
            "prevent_hallucinations": True,
            "require_grounding": 0.85,
            "halt_on_critical": True,
        })
        assert result["valid"] is True
        assert "hallucination_risk_scoring" in result["capabilities"]
        assert "grounding_verification" in result["capabilities"]
        assert result["settings"]["grounding_verification"] == 0.85

    def test_unknown_intent_returns_refusal(self) -> None:
        result = express_requirement({"time_travel_detection": True})
        assert result["valid"] is False
        assert any("time_travel_detection" in r for r in result["refusals"])

    def test_grounding_threshold_out_of_range(self) -> None:
        result = express_requirement({"grounding_threshold": 1.5})
        assert result["valid"] is False
        assert any("grounding_threshold" in r for r in result["refusals"])

    def test_profile_validation(self) -> None:
        result = express_requirement({"profile": "strict"})
        assert result["valid"] is True
        assert result["settings"]["profile"] == "strict"

    def test_invalid_profile(self) -> None:
        result = express_requirement({"profile": "lax"})
        assert result["valid"] is False


class TestGenerateConfig:
    def test_generates_yaml(self) -> None:
        yaml = generate_config({
            "prevent_hallucinations": True,
            "require_grounding": 0.85,
            "profile": "strict",
        })
        assert "safety:" in yaml
        assert "grounding_verification: 0.85" in yaml
        assert "strict" in yaml

    def test_raises_on_unsupported(self) -> None:
        with pytest.raises(NoCodeTranslatorError) as exc:
            generate_config({"time_travel_detection": True})
        assert "unsupported asks" in str(exc.value)


class TestGenerateCodeChange:
    def test_returns_diff(self) -> None:
        change = generate_code_change({
            "prevent_hallucinations": True,
            "halt_on_critical": True,
        })
        assert change["file"] == "crp.config.yaml"
        assert "--- a/crp.config.yaml" in change["diff"]
        assert "hallucination_risk_scoring" in change["explanation"]


class TestRefuseToFabricate:
    def test_refusal_message(self) -> None:
        msg = refuse_to_fabricate("time_travel_detection")
        assert "does not have a capability" in msg
        assert "SPEC-033" in msg
