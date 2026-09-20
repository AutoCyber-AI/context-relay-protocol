# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Visual-output regression tests for the CRP transparency layer (SPEC-056).

These tests prove that CRP can render its hash chain, processing mechanism,
thinking process, and run narrative without requiring a live LLM.  They use
synthetic AG-UI + CRP governance events so CI stays deterministic.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from crp.cognition import CognitivePreset, PresetCompiler
from crp.cognition.loader import resolve_preset_id
from crp.frontend import agent_console_html
from crp.tel import events as ev
from crp.tel.narrative import NarrativeBuilder


@pytest.fixture
def synthetic_run() -> list[ev.Event]:
    """A realistic, deterministic agent run event stream."""
    return [
        ev.run_started(goal="What is the weather in Sydney?"),
        ev.custom("crp.intent", {
            "detail": "weather question",
            "plan": ["RETRIEVE", "GENERATE"],
            "confidence": 0.94,
        }),
        ev.step_started(step="RETRIEVE"),
        ev.reasoning_start(),
        ev.reasoning_delta(delta="The user wants a weather report. "),
        ev.reasoning_delta(delta="I should look up the current conditions."),
        ev.reasoning_end(),
        ev.tool_start(call_id="tc1", name="get_weather", reason="RETRIEVE"),
        ev.tool_args(call_id="tc1", delta='{"city": "Sydney"}'),
        ev.tool_end(call_id="tc1"),
        ev.tool_result(call_id="tc1", content={"city": "Sydney", "temp": 22, "unit": "C"}),
        ev.step_finished(step="RETRIEVE"),
        ev.custom("crp.safety_scan", {
            "stage": "output",
            "risk": "LOW",
            "verdict": "safe",
        }),
        ev.custom("crp.quality", {"tier": "A", "confidence": 0.91, "semantic_entropy": 0.04}),
        ev.custom("crp.provenance", {
            "op": "RETRIEVE",
            "prev": "genesis",
            "hash": "a1b2c3d4e5f6",
        }),
        ev.step_started(step="GENERATE"),
        ev.text_start(messageId="m1"),
        ev.text_delta(messageId="m1", delta="Sydney is "),
        ev.text_delta(messageId="m1", delta="22 °C and sunny."),
        ev.text_end(messageId="m1"),
        ev.step_finished(step="GENERATE"),
        ev.custom("crp.provenance", {
            "op": "GENERATE",
            "prev": "a1b2c3d4e5f6",
            "hash": "f6e5d4c3b2a1",
        }),
        ev.custom("crp.verification", {"invalid": 0, "repairs": 0}),
        ev.run_finished(),
    ]


class TestNarrativeBuilder:
    def test_narrative_has_reasoning_steps(self, synthetic_run: list[ev.Event]) -> None:
        builder = NarrativeBuilder()
        builder.ingest_many(synthetic_run)
        kinds = [s.kind for s in builder.steps]
        assert "reasoning" in kinds
        reasoning = next(s for s in builder.steps if s.kind == "reasoning")
        assert "weather" in reasoning.detail.lower()
        assert "look up" in reasoning.detail.lower()

    def test_narrative_has_tool_call_chain(self, synthetic_run: list[ev.Event]) -> None:
        builder = NarrativeBuilder()
        builder.ingest_many(synthetic_run)
        titles = [s.title for s in builder.steps]
        assert any("get_weather" in t for t in titles)
        assert any("Tool result received" in t for t in titles)

    def test_narrative_has_provenance_links(self, synthetic_run: list[ev.Event]) -> None:
        builder = NarrativeBuilder()
        builder.ingest_many(synthetic_run)
        assert len(builder.provenance_chain) == 2
        assert builder.provenance_chain[0].this_hash == "a1b2c3d4e5f6"
        assert builder.provenance_chain[1].prev_hash == "a1b2c3d4e5f6"
        assert builder.governance["chain_valid"] is True

    def test_narrative_markdown_contains_governance(self, synthetic_run: list[ev.Event]) -> None:
        builder = NarrativeBuilder()
        builder.ingest_many(synthetic_run)
        md = builder.to_markdown()
        assert "# CRP Run Narrative" in md
        assert "Sydney is 22 °C" in md
        assert "Quality tier" in md
        assert "Provenance Chain" in md
        assert "genesis" in md or "a1b2c3d4e5f6" in md

    def test_narrative_html_is_safe(self, synthetic_run: list[ev.Event]) -> None:
        builder = NarrativeBuilder()
        builder.ingest_many(synthetic_run)
        html = builder.to_html()
        assert html.startswith('<div class="crp-narrative">')
        assert "</div>" in html
        # No raw script injection from the tool result.
        assert "<script>" not in html

    def test_narrative_json_round_trip(self, synthetic_run: list[ev.Event]) -> None:
        builder = NarrativeBuilder()
        builder.ingest_many(synthetic_run)
        data = builder.to_dict()
        text = json.dumps(data)
        back = json.loads(text)
        assert len(back["steps"]) == len(builder.steps)
        assert back["governance"]["tier"] == "A"
        assert back["governance"]["chain_valid"] is True

    def test_narrative_shows_safety_and_quality(self, synthetic_run: list[ev.Event]) -> None:
        builder = NarrativeBuilder()
        builder.ingest_many(synthetic_run)
        kinds = [s.kind for s in builder.steps]
        assert "safety" in kinds
        assert "quality" in kinds
        assert builder.governance["risk"] == "LOW"


class TestEmbeddedConsole:
    def test_console_html_includes_narrative_panel(self) -> None:
        html = agent_console_html()
        assert 'id="narrative"' in html or "narrative" in html.lower()
        assert "What CRP is doing" in html

    def test_console_html_includes_provenance_panel(self) -> None:
        html = agent_console_html()
        assert 'id="provenance"' in html or "provenance" in html.lower()
        assert "HMAC" in html or "hash" in html.lower()

    def test_console_html_includes_governance_cards(self) -> None:
        html = agent_console_html()
        assert "risk" in html.lower()
        assert "grounded" in html.lower()
        assert "chain" in html.lower()

    def test_built_static_bundle_is_present(self) -> None:
        root = Path(__file__).parent.parent
        dist = root / "frontend" / "agent-console" / "dist"
        static = root / "crp" / "frontend" / "static"
        index = (dist / "index.html").exists() or (static / "index.html").exists()
        if not index:
            pytest.skip(
                "console bundle not built; run `npm run build` in "
                "frontend/agent-console/ (not built in CI)"
            )
        assets = dist / "assets" if dist.exists() else static / "assets"
        assert assets.exists()
        js = list(assets.glob("index-*.js"))
        css = list(assets.glob("index-*.css"))
        assert js and css, "Built console bundle missing JS/CSS assets"


class TestCognitivePresetRendering:
    def test_security_preset_compiles_to_system_prompt(self) -> None:
        preset = resolve_preset_id("security_analyst")
        compiled = PresetCompiler(preset).compile()
        assert "disciplined security analyst" in compiled.system.lower()
        assert "RETRIEVE" in compiled.operations
        assert "VERIFY" in compiled.operations
        assert compiled.output_hints.get("format") == "markdown"

    def test_companion_preset_has_emotion_and_safeguards(self) -> None:
        preset = resolve_preset_id("compassionate_companion")
        compiled = PresetCompiler(preset).compile()
        assert compiled.emotion_detector is not None
        assert compiled.safeguard_engine is not None
        assert any("self-harm" in s.name.lower() for s in preset.safeguards)

    def test_custom_robot_preset_renders_short_compassionate_output(self) -> None:
        data = {
            "id": "robot",
            "name": "Robot",
            "persona": " household robot",
            "reasoning": {
                "phases": [
                    {"name": "Understand", "operations": ["ANALYSE"], "depth": "quick"},
                    {"name": "Check safeguards", "operations": ["VERIFY"], "depth": "standard"},
                    {"name": "Act", "operations": ["GENERATE"], "depth": "standard"},
                ],
            },
            "safeguards": [
                {"name": "Do not harm humans", "scope": "global", "condition": "harm", "action": "halt"},
            ],
            "emotions": {"enabled": True, "default_affect": "compassion", "recognizer": "rule"},
            "output": {"length": "short", "format": "paragraph", "tone": "compassionate"},
        }
        preset = CognitivePreset.from_dict(data)
        compiled = PresetCompiler(preset).compile()
        assert "do not harm humans" in compiled.system.lower()
        assert compiled.output_hints["length"] == "short"
        assert compiled.output_hints["tone"] == "compassionate"


class TestRawVsCrpVisualArtifact:
    """Produce a deterministic side-by-side artifact for video/marketing use."""

    def test_raw_llm_vs_crp_visual(self, tmp_path: Path) -> None:
        builder = NarrativeBuilder()
        builder.ingest_many([
            ev.run_started(goal="Is port 443 safe for login pages?"),
            ev.custom("crp.intent", {"detail": "security question", "plan": ["RETRIEVE", "VERIFY", "GENERATE"]}),
            ev.step_started(step="RETRIEVE"),
            ev.tool_start(call_id="t1", name="lookup_port_service", reason="RETRIEVE"),
            ev.tool_args(call_id="t1", delta='{"port": 443}'),
            ev.tool_end(call_id="t1"),
            ev.tool_result(call_id="t1", content={"port": 443, "service": "HTTPS", "secure": True}),
            ev.step_finished(step="RETRIEVE"),
            ev.custom("crp.safety_scan", {"stage": "output", "risk": "LOW", "verdict": "safe"}),
            ev.custom("crp.quality", {"tier": "A", "confidence": 0.92}),
            ev.custom("crp.provenance", {"op": "RETRIEVE", "prev": "genesis", "hash": "abc123"}),
            ev.step_started(step="VERIFY"),
            ev.custom("crp.verification", {"invalid": 0, "repairs": 0}),
            ev.step_finished(step="VERIFY"),
            ev.step_started(step="GENERATE"),
            ev.text_start(messageId="m1"),
            ev.text_delta(messageId="m1", delta="Port 443 is HTTPS. It is the standard port for encrypted login pages."),
            ev.text_end(messageId="m1"),
            ev.step_finished(step="GENERATE"),
            ev.custom("crp.provenance", {"op": "GENERATE", "prev": "abc123", "hash": "def456"}),
            ev.run_finished(),
        ])

        artifact = {
            "scenario": "Port 443 login-page safety",
            "raw_llm": {
                "mode": "RAW LLM",
                "response": "Port 443 is generally used for HTTPS.",
                "governance": None,
                "sources": [],
                "chain": None,
            },
            "crp_agent": {
                "mode": "CRPv6 AGENT",
                "narrative_md": builder.to_markdown(),
                "governance": builder.governance,
                "provenance_chain": [p.to_dict() for p in builder.provenance_chain],
                "operations": builder.operations,
            },
        }
        out = tmp_path / "raw_vs_crp.json"
        out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        assert out.exists()
        assert "Port 443 is HTTPS" in out.read_text()
        assert any(link["this_hash"] == "abc123" for link in artifact["crp_agent"]["provenance_chain"])
