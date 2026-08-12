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
    assert "Operations & Governance" in html


def test_console_custom_title() -> None:
    html = agent_console_html(title="My Agent")
    assert "<title>My Agent</title>" in html
