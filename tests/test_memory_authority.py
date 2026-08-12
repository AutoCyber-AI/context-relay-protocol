# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for memory write-authority lattice (SPEC-045)."""

from __future__ import annotations

import pytest

from crp.state.memory_authority import (
    Authority,
    MemoryAuditEvent,
    MemoryAuthorityLattice,
    MemoryEntry,
    MemoryOperation,
    MemoryTier,
)


class TestMemoryAuthorityLattice:
    def test_user_can_write_persistent(self) -> None:
        mem = MemoryAuthorityLattice()
        entry = mem.remember("goal", "deploy", Authority.USER, MemoryTier.PERSISTENT)
        assert entry is not None
        assert entry.key == "goal"
        assert entry.authority == Authority.USER

    def test_agent_cannot_write_persistent(self) -> None:
        mem = MemoryAuthorityLattice()
        entry = mem.remember("goal", "deploy", Authority.AGENT, MemoryTier.PERSISTENT)
        assert entry is None

    def test_tool_can_write_ephemeral(self) -> None:
        mem = MemoryAuthorityLattice()
        entry = mem.remember("temp", "42", Authority.TOOL, MemoryTier.EPHEMERAL)
        assert entry is not None
        assert entry.tier == MemoryTier.EPHEMERAL

    def test_agent_can_overwrite_agent(self) -> None:
        mem = MemoryAuthorityLattice()
        mem.remember("state", "A", Authority.AGENT, MemoryTier.CONVERSATIONAL)
        entry = mem.remember("state", "B", Authority.AGENT, MemoryTier.CONVERSATIONAL)
        assert entry is not None
        assert entry.value == "B"

    def test_agent_cannot_overwrite_user(self) -> None:
        mem = MemoryAuthorityLattice()
        mem.remember("goal", "deploy", Authority.USER, MemoryTier.PERSISTENT)
        entry = mem.remember("goal", "delete", Authority.AGENT, MemoryTier.PERSISTENT)
        assert entry is None
        recalled = mem.recall("goal")
        assert recalled is not None
        assert recalled.value == "deploy"

    def test_system_can_overwrite_user(self) -> None:
        mem = MemoryAuthorityLattice()
        mem.remember("goal", "deploy", Authority.USER, MemoryTier.PERSISTENT)
        entry = mem.remember("goal", "updated", Authority.SYSTEM, MemoryTier.PERSISTENT)
        assert entry is not None
        assert entry.value == "updated"

    def test_recall_returns_entry_and_audits(self) -> None:
        mem = MemoryAuthorityLattice()
        mem.remember("goal", "deploy", Authority.USER, MemoryTier.PERSISTENT)
        entry = mem.recall("goal")
        assert entry is not None
        recall_events = [e for e in mem.audit_log if e.operation == MemoryOperation.RECALL]
        assert len(recall_events) == 1

    def test_erase_requires_sufficient_authority(self) -> None:
        mem = MemoryAuthorityLattice()
        mem.remember("goal", "deploy", Authority.USER, MemoryTier.PERSISTENT)
        assert not mem.erase("goal", Authority.AGENT)
        assert mem.erase("goal", Authority.USER)
        assert mem.recall("goal") is None

    def test_erase_unauthorized_is_audited(self) -> None:
        mem = MemoryAuthorityLattice()
        mem.remember("goal", "deploy", Authority.USER, MemoryTier.PERSISTENT)
        mem.erase("goal", Authority.AGENT)
        events = [e for e in mem.audit_log if e.operation == MemoryOperation.ERASE]
        assert any(not e.allowed for e in events)

    def test_to_dict_serializes(self) -> None:
        mem = MemoryAuthorityLattice()
        mem.remember("goal", "deploy", Authority.USER, MemoryTier.PERSISTENT)
        d = mem.to_dict()
        assert "goal" in d["entries"]
        assert len(d["audit_log"]) >= 1

    def test_memory_entry_to_dict(self) -> None:
        entry = MemoryEntry(key="k", value="v", tier=MemoryTier.EPHEMERAL, authority=Authority.TOOL)
        d = entry.to_dict()
        assert d["key"] == "k"
        assert d["value"] == "v"
        assert d["tier"] == "ephemeral"

    def test_audit_event_to_dict(self) -> None:
        event = MemoryAuditEvent(
            event_id="e1",
            operation=MemoryOperation.WRITE,
            key="k",
            actor=Authority.USER,
            tier=MemoryTier.PERSISTENT,
            allowed=True,
            reason="ok",
            timestamp=1.0,
        )
        d = event.to_dict()
        assert d["operation"] == "write"
        assert d["allowed"] is True

    def test_tool_cannot_overwrite_user_even_in_ephemeral(self) -> None:
        mem = MemoryAuthorityLattice()
        mem.remember("goal", "deploy", Authority.USER, MemoryTier.EPHEMERAL)
        entry = mem.remember("goal", "delete", Authority.TOOL, MemoryTier.EPHEMERAL)
        assert entry is None

    def test_list_entries_and_keys(self) -> None:
        mem = MemoryAuthorityLattice()
        mem.remember("a", "1", Authority.USER, MemoryTier.PERSISTENT)
        mem.remember("b", "2", Authority.AGENT, MemoryTier.CONVERSATIONAL)
        assert sorted(mem.list_keys()) == ["a", "b"]
        assert len(mem.list_entries()) == 2
