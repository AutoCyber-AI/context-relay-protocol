# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Scratch Buffer — ephemeral tool context (SPEC-029)."""

from __future__ import annotations

import time

from crp.state.scratch_buffer import ScratchBuffer, ScratchEntry, ScratchPersistence


class TestScratchBuffer:
    def test_store_and_retrieve(self) -> None:
        buf = ScratchBuffer(session_id="s1")
        ptr = buf.store("raw output", "scratch_001", tool_name="query")
        assert ptr == "scratch_001"
        entry = buf.entries["scratch_001"]
        assert entry.tool_name == "query"
        assert entry.provenance_hash

    def test_fresh_ttl(self) -> None:
        buf = ScratchBuffer(session_id="s1")
        buf.store("data", "scratch_002", freshness_ttl=300)
        fresh = buf.get_fresh("scratch_002")
        assert fresh is not None
        assert fresh.is_fresh is True

    def test_expired_not_fresh(self) -> None:
        buf = ScratchBuffer(session_id="s1")
        buf.store("data", "scratch_003", freshness_ttl=0)
        time.sleep(0.05)
        expired = buf.get_fresh("scratch_003")
        assert expired is None

    def test_pinned_not_expired(self) -> None:
        buf = ScratchBuffer(session_id="s1")
        buf.store("data", "scratch_004", freshness_ttl=0)
        buf.pin("scratch_004")
        time.sleep(0.05)
        pinned = buf.get_fresh("scratch_004")
        assert pinned is not None
        assert pinned.persistence == ScratchPersistence.PINNED

    def test_json_structure_detection(self) -> None:
        buf = ScratchBuffer(session_id="s1")
        buf.store('{"key": "value"}', "scratch_005", structure="auto")
        entry = buf.entries["scratch_005"]
        assert entry.structured == {"key": "value"}
        assert "JSON object" in entry.summary

    def test_tabular_summary(self) -> None:
        buf = ScratchBuffer(session_id="s1")
        buf.store("id\tname\n1\tAlice\n2\tBob", "scratch_006", structure="tabular")
        summary = buf.summarise("scratch_006")
        assert "2 rows" in summary or "rows" in summary

    def test_provenance(self) -> None:
        buf = ScratchBuffer(session_id="s1")
        buf.store("data", "scratch_007", tool_name="sql")
        prov = buf.get_provenance("scratch_007")
        assert prov["type"] == "TOOL_GROUNDED"
        assert prov["tool"] == "sql"
        assert "hash" in prov

    def test_purge_expired(self) -> None:
        buf = ScratchBuffer(session_id="s1")
        buf.store("old", "scratch_008", freshness_ttl=0)
        time.sleep(0.05)
        removed = buf.purge_expired()
        assert removed == 1
        assert "scratch_008" not in buf.entries
