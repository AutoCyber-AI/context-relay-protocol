# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for crp.tel.narrative — event-stream to chain-of-thought narrative."""

from __future__ import annotations

from crp.tel import events as ev
from crp.tel.narrative import NarrativeBuilder


def _events_for_simple_run() -> list[ev.Event]:
    return [
        ev.run_started(goal="What is 12 * 7?"),
        ev.custom("crp.intent", {"detail": "math question", "plan": ["RETRIEVE", "GENERATE"]}),
        ev.step_started(step="calculate"),
        ev.reasoning_delta(messageId="r1", delta="The user wants a multiplication result."),
        ev.tool_start(call_id="c1", name="calculator", reason="calculate"),
        ev.tool_args(call_id="c1", delta='{"a":12,"b":7}'),
        ev.tool_end(call_id="c1"),
        ev.tool_result(call_id="c1", content={"result": 84}),
        ev.custom("crp.safety_scan", {"stage": "output", "risk": "LOW", "verdict": "PASS", "ms": 12}),
        ev.custom("crp.quality", {"tier": "S", "confidence": 0.97}),
        ev.custom("crp.provenance", {"op": "agent_run", "prev": "genesis", "hash": "abcd1234"}),
        ev.text_delta(messageId="a1", delta="12 times 7 is 84."),
        ev.run_finished(),
    ]


def test_narrative_builds_steps() -> None:
    builder = NarrativeBuilder()
    builder.ingest_many(_events_for_simple_run())
    story = builder.to_dict()
    kinds = {s["kind"] for s in story["steps"]}
    assert "run" in kinds
    assert "intent" in kinds
    assert "operation" in kinds
    assert "reasoning" in kinds
    assert "tool-select" in kinds
    assert "tool-call" in kinds
    assert "tool-result" in kinds
    assert "safety" in kinds
    assert "quality" in kinds
    assert "provenance" in kinds
    assert "answer" in kinds


def test_governance_summary_extracted() -> None:
    builder = NarrativeBuilder()
    builder.ingest_many(_events_for_simple_run())
    gov = builder.governance
    assert gov["tier"] == "S"
    assert gov["confidence"] == 0.97
    assert gov["chain_valid"] is True
    assert len(gov["safety_scans"]) == 1


def test_provenance_chain_rendered() -> None:
    builder = NarrativeBuilder()
    builder.ingest_many(_events_for_simple_run())
    assert len(builder.provenance_chain) == 1
    assert builder.provenance_chain[0].short_this() == "abcd1234"


def test_markdown_output() -> None:
    builder = NarrativeBuilder()
    builder.ingest_many(_events_for_simple_run())
    md = builder.to_markdown()
    assert "# CRP Run Narrative" in md
    assert "Intent classified" in md
    assert "Provenance Chain" in md


def test_html_output_escaped() -> None:
    builder = NarrativeBuilder()
    builder.ingest_many(_events_for_simple_run())
    html = builder.to_html()
    assert "crp-narrative" in html
    assert "<script>" not in html


def test_interrupt_becomes_narrative_step() -> None:
    builder = NarrativeBuilder()
    builder.ingest(ev.interrupt(reason="approval needed", action={"tool": "delete"}))
    assert any(s.kind == "interrupt" for s in builder.steps)
