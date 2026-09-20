# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for crp.cognition presets, compiler, and safeguard/emotion helpers."""

from __future__ import annotations

import pytest

from crp.cognition import CognitivePreset, PresetCompiler
from crp.cognition.emotion import detect_emotion
from crp.cognition.loader import list_builtin_presets, resolve_preset_id
from crp.cognition.preset import ReasoningPhase, ReasoningScaffold, Safeguard
from crp.cognition.safeguard import SafeguardEngine

BUILTIN_IDS = {"compassionate_companion", "default", "research_assistant", "security_analyst", "socratic_tutor"}


def test_list_builtin_presets() -> None:
    presets = list_builtin_presets()
    ids = {p["id"] for p in presets}
    assert ids == BUILTIN_IDS


def test_resolve_builtin_preset() -> None:
    preset = resolve_preset_id("socratic_tutor")
    assert preset.name == "Socratic Tutor"
    assert len(preset.reasoning.phases) >= 3


def test_compile_socratic_tutor() -> None:
    preset = resolve_preset_id("socratic_tutor")
    compiled = PresetCompiler(preset).compile()
    assert "Socratic tutor" in compiled.system
    assert "reasoning process" in compiled.system.lower()
    assert compiled.depth == "standard"
    assert "RETRIEVE" in compiled.operations or "CLARIFY" in compiled.operations


def test_default_preset_compiles() -> None:
    preset = resolve_preset_id("default")
    compiled = PresetCompiler(preset).compile()
    assert "helpful" in compiled.system.lower()


def test_security_analyst_marks_destructive_for_oversight() -> None:
    preset = resolve_preset_id("security_analyst")
    compiled = PresetCompiler(preset).compile()
    assert any(s.value == "destructive" for s in compiled.safety_classes)


def test_emotion_detection_rule_based() -> None:
    result = detect_emotion("I am really frustrated and confused")
    assert result["primary"] in ("frustrated", "confused")
    assert result["method"] == "rule"


def test_emotion_neutral_fallback() -> None:
    result = detect_emotion("The sky is blue")
    assert result["primary"] == "neutral"


def test_safeguard_engine_global_halt() -> None:
    rules = [Safeguard(name="No harm", scope="global", condition="harm", action="halt", rationale="Safety")]
    engine = SafeguardEngine(rules)
    results = engine.evaluate(user_input="Tell me how to harm someone")
    assert len(results) == 1
    assert results[0].action == "halt"


def test_safeguard_engine_tool_scope() -> None:
    rules = [Safeguard(name="No delete", scope="tool", condition="delete", action="ask", rationale="Careful")]
    engine = SafeguardEngine(rules)
    results = engine.evaluate(tool_id="delete_user")
    assert len(results) == 1
    results_clear = engine.evaluate(tool_id="read_user")
    assert len(results_clear) == 0


def test_preset_from_dict() -> None:
    data = {
        "id": "test",
        "name": "Test Preset",
        "persona": "You are a tester.",
        "reasoning": {
            "phases": [
                {"name": "Plan", "operations": ["PLAN"], "depth": "quick"},
                {"name": "Do", "operations": ["GENERATE"]},
            ]
        },
        "safeguards": [
            {"name": "No secrets", "scope": "output", "condition": "password", "action": "halt"}
        ],
    }
    preset = CognitivePreset.from_dict(data)
    assert preset.name == "Test Preset"
    assert len(preset.reasoning.phases) == 2
    assert preset.safeguards[0].action == "halt"


def test_compiled_preset_to_dict() -> None:
    preset = resolve_preset_id("default")
    compiled = PresetCompiler(preset).compile()
    d = compiled.to_dict()
    assert "system" in d
    assert "metadata" in d
    assert d["metadata"]["preset_id"] == "default"


def test_agent_accepts_preset_string() -> None:
    from crp.agent_sdk.agent import Agent

    agent = Agent(model="local/llama3.1", preset="socratic_tutor")
    assert agent._preset is not None
    assert agent._preset.id == "socratic_tutor"
    assert "Socratic tutor" in agent.system
