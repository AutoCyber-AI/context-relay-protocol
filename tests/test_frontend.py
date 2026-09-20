# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
"""Tests for frontend components."""

from __future__ import annotations

from crp.frontend import agent_console_html


def test_console_includes_depth_selector() -> None:
    html = agent_console_html()
    assert '<select id="depth"' in html
    assert 'value="thorough"' in html
    assert 'value="exhaustive"' in html
    assert "Deep Research" in html


def test_console_includes_event_panel() -> None:
    html = agent_console_html()
    assert 'id="events"' in html
    assert "What CRP is doing" in html
    assert "Governance" in html
    assert "Provenance" in html
    assert "Narrative" in html


def test_console_custom_title() -> None:
    html = agent_console_html(title="My Agent")
    assert "<title>My Agent</title>" in html


def test_built_static_bundle_exists() -> None:
    from pathlib import Path

    root = Path(__file__).parent.parent
    static_dir = root / "crp" / "frontend" / "static"
    dist_dir = root / "frontend" / "agent-console" / "dist"
    assert (static_dir / "index.html").exists() or (dist_dir / "index.html").exists(), (
        "Built console bundle not found; run `npm run build` in frontend/agent-console/"
    )
    assert (static_dir / "assets").exists() or (dist_dir / "assets").exists()


def test_narrative_builder_from_tel_events() -> None:
    from crp.tel import events as ev
    from crp.tel.narrative import NarrativeBuilder

    builder = NarrativeBuilder()
    builder.ingest_many([
        ev.run_started(goal="test"),
        ev.custom("crp.quality", {"tier": "A", "confidence": 0.95}),
        ev.run_finished(),
    ])
    story = builder.to_dict()
    assert story["governance"]["tier"] == "A"
    assert any(s.kind == "run" for s in builder.steps)
    assert any(s.kind == "quality" for s in builder.steps)
